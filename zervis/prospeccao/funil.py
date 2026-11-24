"""O funil da prospecção (ADR 0127): achar, qualificar, aprovar e enviar, poucas por dia.

Ligada na página Prospecção, a cada poucos minutos o Zé:

1. **qualifica** as empresas novas: o CNPJ, o sócio que decide e os telefones (`dono`); depois o
   modelo dá a nota (dor, encaixe, momento, alcance e prova, de 0 a 5, com os pesos do
   first-customer-finder, MIT; ver THIRD_PARTY.md) e escreve a primeira mensagem ao dono, pelo
   nome. Abaixo de `MINIMO`, sem telefone ou já nas conversas de quem usa: descartada, com o
   motivo;
2. **busca mais** no Google Maps (`apify`) quando faltam empresas prontas, um ramo por vez;
3. **envia** pelo WhatsApp conectado, nos dias úteis, das 9h às 17h, no máximo `por_dia` por dia
   e com `ESPACO_S` entre uma e outra: o número de quem usa não pode parecer disparo em massa.
   Sem "Enviar sozinho", cada mensagem espera a aprovação na página.

Ninguém recebe duas vezes: a empresa (o id do Google, o CNPJ) e o telefone ficam guardados para
sempre. Toda mensagem termina com a saída ("é só me avisar que não mando mais nada"), e a
resposta de quem não quer vira "Sem interesse". A resposta de qualquer um vira aviso de lead.

O que vem das fontes é dado, nunca ordem: vai ao modelo entre <<< e >>>, com a regra de ignorar
instruções. Estado em `<dados>/prospeccao.db`; a configuração, em `<config>/prospeccao.json`.
"""

import json
import logging
import random
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from zervis import atividade, fuso, lugares
from zervis.dados.lista import Lista
from zervis.pesquisa import cnpj as cnpj_mod
from zervis.prospeccao import apify, dono, mensagem

log = logging.getLogger(__name__)

ARQUIVO = lugares.DADOS / "prospeccao.json"  # o banco é o prospeccao.db, ao lado
CONFIG = lugares.CONFIG / "prospeccao.json"
PESOS = {"dor": 25, "encaixe": 25, "momento": 20, "alcance": 15, "prova": 15}
MINIMO = 50  # abaixo disto, a empresa não tem sinal que justifique a mensagem
POR_DIA, POR_DIA_MAXIMO = 2, 5  # o número é o de quem usa: nada de volume
INICIO, FIM = 9, 17  # o horário de envio, em dias úteis, no fuso de quem usa
ESPACO_S = 2 * 3600  # entre uma mensagem e outra, no mínimo
VARIACAO_S = 90 * 60  # somada ao espaço, sorteada a cada envio: sem ritmo de robô
COMECO_S = 2 * 3600  # o primeiro envio do dia sai num minuto sorteado entre 9h e 11h
FREIO_RECUSAS = 2  # tantas pessoas pedindo para não receber em FREIO_S: a prospecção pausa
FREIO_S = 7 * 86400
INTERVALO_S = 300  # o ciclo
DESCOBRIR_S = 6 * 3600  # entre uma busca no Maps e outra
RESERVA = 4  # empresas prontas (ou por qualificar) abaixo das quais o Zé busca mais
POR_BUSCA = 10  # empresas por busca no Maps: cada uma custa na Apify
QUALIFICAR_POR_CICLO = 3
TENTATIVAS = 3  # o modelo falhou tantas vezes: descartada
LIMITE_EDITADA = 900
NA_TELA = 80
SEM_INTERESSE = re.compile(
    r"\b(n[aã]o|sem)\s+(tenho\s+|temos\s+|h[aá]\s+)?interesse|\bn[aã]o\s+quero|\bpar[ae]\s+de\b"
    r"|\bn[aã]o\s+(me\s+)?(mande|envie|chame|mandem|liguem?)|\bremov|\bdescadastr|\bbloque",
    re.IGNORECASE,
)
ROTULOS = {
    "nova": "Qualificando",
    "aprovar": "Aguardando aprovação",
    "fila": "Na fila de envio",
    "enviando": "Envio não confirmado",
    "enviada": "Enviada",
    "respondeu": "Respondeu",
    "reuniao": "Reunião marcada",
    "sem_interesse": "Sem interesse",
    "descartada": "Descartada",
}
DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
ESPERANDO = ("nova", "aprovar", "fila")  # contam na reserva
# "enviando" fica marcado antes do envio: se o Zé cair no meio, a empresa não recebe de novo.
CONTATADAS = ("enviando", "enviada", "respondeu", "reuniao", "sem_interesse")
MARCAVEIS = ("reuniao", "sem_interesse", "respondeu")


class ProspeccaoErro(ValueError):
    """Mensagem curta, pronta para a tela."""


@dataclass
class Config:
    ligada: bool = False  # o Zé busca, qualifica e envia
    sozinho: bool = False  # envia sem esperar a aprovação de cada mensagem
    cidade: str = ""  # "Caruaru, PE"
    ramos: list[str] = field(default_factory=list)  # "clínica odontológica", "imobiliária"
    oferta: str = ""  # o que quem usa oferece, em poucas linhas
    por_dia: int = POR_DIA
    # A mensagem (ADR 0129): o convite que ela faz, o link de agendamento e, se for verdade, o
    # limite que dá urgência ("5 diagnósticos por mês"). O Zé não inventa prazo nem vaga.
    convite: str = ""  # "um diagnóstico gratuito de 20 minutos"
    link: str = ""  # a agenda de horários (https)
    link_na_mensagem: bool = False  # o link já na primeira mensagem
    vagas: str = ""


def _limpo(texto: Any, limite: int) -> str:
    return " ".join(str(texto or "").split())[:limite]


def ler_config(arquivo: Path = CONFIG) -> Config:
    try:
        bruto = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return Config()
    if not isinstance(bruto, dict):
        return Config()
    lista = bruto.get("ramos")
    ramos: list[Any] = lista if isinstance(lista, list) else []
    try:
        por_dia = int(bruto.get("por_dia", POR_DIA))
    except (TypeError, ValueError):
        por_dia = POR_DIA
    return Config(
        ligada=bruto.get("ligada") is True,
        sozinho=bruto.get("sozinho") is True,
        cidade=_limpo(bruto.get("cidade"), 80),
        ramos=[r for r in (_limpo(x, 60) for x in ramos[:20]) if r],
        oferta=str(bruto.get("oferta") or "")[:1500].strip(),
        por_dia=max(1, min(por_dia, POR_DIA_MAXIMO)),
        convite=_limpo(bruto.get("convite"), 120),
        link=_limpo(bruto.get("link"), 300),
        link_na_mensagem=bruto.get("link_na_mensagem") is True,
        vagas=_limpo(bruto.get("vagas"), 120),
    )


# Os campos que mudam a mensagem: mudou um deles, as que esperam são escritas de novo.
CAMPOS_DA_MENSAGEM = ("oferta", "convite", "link", "link_na_mensagem", "vagas")


def salvar_config(cfg: Config, arquivo: Path = CONFIG) -> None:
    if cfg.ligada and not cfg.cidade:
        raise ProspeccaoErro("Informe a cidade.")
    if not 1 <= cfg.por_dia <= POR_DIA_MAXIMO:
        raise ProspeccaoErro(f"Envios por dia: de 1 a {POR_DIA_MAXIMO}.")
    if cfg.link and not re.fullmatch(r"https://[^\s<>\"']{4,290}", cfg.link):
        raise ProspeccaoErro("Link de agendamento inválido: use o endereço completo, com https.")
    if cfg.link_na_mensagem and not cfg.link:
        raise ProspeccaoErro("Informe o link de agendamento.")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2))
    temporario.replace(arquivo)


def nota(notas: dict[str, int]) -> int:
    return round(sum(notas.get(k, 0) / 5 * peso for k, peso in PESOS.items()))


class Funil:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        config: Path = CONFIG,
        *,
        agora: Callable[[], float] = time.time,
        buscar_lugares: Callable[[str, str, int, str], list[apify.Lugar]] = apify.buscar,
        consultar_cnpj: Callable[[str], dict[str, Any]] = cnpj_mod.consultar,
        perguntar: Callable[[str, str], str] = mensagem.perguntar,
        identidade: Callable[[], tuple[str, str, str]] = mensagem.identidade,
        chave_apify: Callable[[], str] = apify.chave,
        sortear: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._empresas = Lista(arquivo, "empresas")
        self._meta = Lista(arquivo, "meta")
        self.config_arquivo = config
        self.agora = agora
        self.buscar_lugares = buscar_lugares
        self.consultar_cnpj = consultar_cnpj
        self.perguntar = perguntar
        self.identidade = identidade
        self.chave_apify = chave_apify
        self.sortear = sortear
        # Ligados pelo núcleo (as automações): sem eles, o funil não busca na web nem envia.
        self.buscar_web: Callable[[str], Iterable[Any]] | None = None
        self.enviar: Callable[[str, str, str], str] | None = None  # telefone, nome, texto
        self.avisar: Callable[[str], None] | None = None
        self.conhecido: Callable[[str], bool] = lambda _telefone: False
        self._trava = threading.Lock()
        self.em = 0.0  # o último ciclo

    # --- estado ---------------------------------------------------------------------------------

    def config(self) -> Config:
        return ler_config(self.config_arquivo)

    def todas(self) -> list[dict[str, Any]]:
        return self._empresas.ler()

    def _achar(self, ident: str) -> dict[str, Any] | None:
        return next((p for p in self.todas() if p.get("id") == ident), None)

    def achar(self, quem: str) -> dict[str, Any]:
        """A empresa pelo id ou pelo nome falado ("a Sorrir", "o Carlos"): no nome da empresa ou
        do dono. Nenhuma ou mais de uma: ProspeccaoErro, com os nomes para escolher."""
        quem = " ".join(str(quem or "").split())
        if not quem:
            raise ProspeccaoErro("Diga qual empresa.")
        if (exata := self._achar(quem)) is not None:
            return exata
        alvo = dono.sem_acento(quem)
        achadas = [
            p for p in self.todas()
            if alvo in dono.sem_acento(f"{p.get('nome', '')} {p.get('dono', '')}")
        ]  # fmt: skip
        if len(achadas) == 1:
            return achadas[0]
        if not achadas:
            raise ProspeccaoErro(f"Nenhuma empresa com {quem!r} na prospecção.")
        nomes = ", ".join(f"{p['nome']} (id {p['id']})" for p in achadas[:6])
        raise ProspeccaoErro(f"Mais de uma empresa com {quem!r}: {nomes}.")

    def _mudar(
        self, ident: str, campos: dict[str, Any], so_se: tuple[str, ...] = ()
    ) -> dict[str, Any] | None:
        """Muda uma empresa numa transação; com `so_se`, só se ela ainda estiver num desses
        estados (o ciclo trabalhou fora da transação e a pessoa pode ter mexido no meio)."""
        with self._empresas.transacao():
            itens = self._empresas.ler()
            p = next((x for x in itens if x.get("id") == ident), None)
            if p is None or (so_se and p.get("status") not in so_se):
                return None
            p.update(campos, atualizado=self.agora())
            self._empresas.gravar(itens)
            return p

    def _meta_ler(self) -> dict[str, Any]:
        return next((m for m in self._meta.ler() if m.get("id") == "meta"), {"id": "meta"})

    def _meta_gravar(self, **campos: Any) -> None:
        with self._meta.transacao():
            self._meta.gravar([{**self._meta_ler(), **campos}])

    def _avisar(self, texto: str) -> None:
        if self.avisar is not None:
            self.avisar(texto)

    def ocupado(self) -> bool:
        return self._trava.locked()

    # --- entrada --------------------------------------------------------------------------------

    def _repetida(self, itens: list[dict[str, Any]], lugar_id: str, cnpj: str, tel: str) -> bool:
        """A empresa (o lugar, o CNPJ) ou o telefone já apareceram, em qualquer estado."""
        chave = dono.chave_do_telefone(tel) if tel else ""
        for p in itens:
            lugar, cadastro = p.get("lugar") or {}, p.get("cadastro") or {}
            if lugar_id and lugar.get("id") == lugar_id:
                return True
            if cnpj and re.sub(r"[^0-9A-Z]", "", str(cadastro.get("cnpj", "")).upper()) == cnpj:
                return True
            # O do Google conta antes da qualificação, quando a lista de telefones ainda é vazia.
            numeros = [str(lugar.get("telefone", ""))] + [
                t["numero"] for t in p.get("telefones", [])
            ]
            if chave and chave in {dono.chave_do_telefone(n) for n in numeros if n}:
                return True
        return False

    def _nova(self, nome: str, origem: str, **campos: Any) -> dict[str, Any]:
        agora = self.agora()
        return {
            "id": uuid.uuid4().hex[:10], "nome": nome, "origem": origem, "status": "nova",
            "motivo": "", "lugar": {}, "cadastro": {}, "dono": "", "cargo": "", "telefones": [],
            "nota": 0, "notas": {}, "sinal": "", "mensagem": "", "tentativas": 0, "erro": "",
            "enviado": 0.0, "telefone_enviado": "", "resposta": "", "criado": agora,
            "atualizado": agora, **campos,
        }  # fmt: skip

    def adicionar_lugares(self, achados: Iterable[apify.Lugar]) -> int:
        """As empresas do Maps que ainda não vimos; devolve quantas entraram."""
        novas = 0
        with self._empresas.transacao():
            itens = self._empresas.ler()
            for x in achados:
                if self._repetida(itens, x.id, "", x.telefone):
                    continue
                itens.append(self._nova(x.nome, "maps", lugar=x.para_dados()))
                novas += 1
            self._empresas.gravar(itens)
        return novas

    def adicionar_cnpj(self, numero: str) -> dict[str, Any]:
        """Uma empresa pelo CNPJ, posta na página: entra para qualificar no próximo ciclo."""
        try:
            normal = cnpj_mod.normalizar(numero)
        except (cnpj_mod.CnpjErro, ValueError) as erro:
            raise ProspeccaoErro("CNPJ inválido.") from erro
        try:
            cadastro = self.consultar_cnpj(normal)
        except Exception as erro:
            raise ProspeccaoErro(str(erro).capitalize() or "CNPJ não encontrado.") from None
        with self._empresas.transacao():
            itens = self._empresas.ler()
            if self._repetida(itens, "", normal, ""):
                raise ProspeccaoErro("Empresa já está na lista.")
            nome = cadastro.get("nome_fantasia") or cadastro.get("razao_social") or normal
            p = self._nova(str(nome)[:120], "cnpj", cadastro=cadastro)
            itens.append(p)
            self._empresas.gravar(itens)
        atividade.PADRAO.registrar(
            "execucao", f"Prospecção: {p['nome']} adicionada", origem="painel"
        )
        return p

    # --- qualificar -----------------------------------------------------------------------------

    def _enriquecer(self, p: dict[str, Any], cfg: Config) -> dict[str, Any]:
        """O cadastro da Receita, quem decide e os telefones (rede: fora da transação)."""
        lugar = p.get("lugar") or {}
        cadastro = p.get("cadastro") or {}
        if not cadastro and self.buscar_web is not None and cfg.cidade:
            try:
                cadastro = (
                    dono.achar_cnpj(p["nome"], cfg.cidade, self.buscar_web, self.consultar_cnpj)
                    or {}
                )
            except Exception:  # a busca fora do ar não para o funil: segue sem o cadastro
                log.warning("prospecção: CNPJ não buscado", exc_info=True)
        nome, cargo = dono.decisor(cadastro) if cadastro else ("", "")
        return {
            "cadastro": cadastro,
            "dono": nome,
            "cargo": cargo,
            "telefones": dono.telefones(cadastro, str(lugar.get("telefone", ""))),
        }

    def _dados_ao_modelo(self, p: dict[str, Any]) -> str:
        lugar, cad = p.get("lugar") or {}, p.get("cadastro") or {}
        dados = {
            "nome": p["nome"],
            "ramo": lugar.get("categoria") or cad.get("atividade", ""),
            "bairro_e_cidade": lugar.get("endereco") or cad.get("endereco", ""),
            "nota_no_google": lugar.get("nota") or None,
            "avaliacoes_no_google": lugar.get("avaliacoes") or None,
            "piores_avaliacoes": lugar.get("reclamacoes") or [],
            "tem_site": bool(lugar.get("site")),
            "aberta_em": cad.get("abertura", ""),
            "porte": cad.get("porte", ""),
            "atividade_na_receita": cad.get("atividade", ""),
            "quem_decide": f"{p['dono']} ({p['cargo']})" if p.get("dono") else "desconhecido",
            "tem_celular": any(dono.celular(t["numero"]) for t in p.get("telefones", [])),
        }
        texto = json.dumps(
            {k: v for k, v in dados.items() if v not in ("", None, [])}, ensure_ascii=False
        )
        return texto.replace("<<<", " ").replace(">>>", " ")

    def link(self, cfg: Config) -> str:
        """O link de agendamento: o da Prospecção ou, sem ele, o do direct do Instagram."""
        if cfg.link:
            return cfg.link
        try:
            from zervis.redes import instagram_direct

            return str(instagram_direct.PADRAO.estado().get("link") or "")
        except Exception:
            return ""

    def reescrever(self) -> int:
        """A estratégia da mensagem mudou: as que esperam (aprovação ou fila) voltam a ser
        escritas no próximo ciclo, menos as que quem usa editou. Devolve quantas."""
        n = 0
        with self._empresas.transacao():
            itens = self._empresas.ler()
            for p in itens:
                if p.get("status") in ("aprovar", "fila") and not p.get("editada"):
                    p.update(status="nova", mensagem="", tentativas=0, atualizado=self.agora())
                    n += 1
            self._empresas.gravar(itens)
        return n

    def _avaliar(self, p: dict[str, Any], cfg: Config) -> dict[str, Any]:
        remetente, marca, sobre = self.identidade()
        link = self.link(cfg) if cfg.link_na_mensagem else ""
        pedido = mensagem.pedido(
            self._dados_ao_modelo(p), dono.primeiro_nome(p.get("dono", "")), remetente, marca,
            cfg.oferta or sobre, cfg.cidade, cfg.convite, cfg.vagas, link,
        )  # fmt: skip
        resposta = mensagem.json_do_modelo(self.perguntar(pedido, mensagem.SISTEMA))
        notas = {}
        for k in PESOS:
            try:
                notas[k] = max(0, min(5, int(resposta.get(k, 0))))
            except (TypeError, ValueError):
                notas[k] = 0
        if not p.get("dono"):
            notas["alcance"] = min(notas["alcance"], 2)  # sem o dono, a mensagem cai na recepção
        return {
            "notas": notas,
            "nota": nota(notas),
            "sinal": _limpo(resposta.get("sinal"), 240),
            "mensagem": mensagem.final(str(resposta.get("mensagem", "")), link),
        }

    def _qualificar(self, p: dict[str, Any], cfg: Config) -> str:
        """Devolve o estado em que a empresa ficou."""
        campos = self._enriquecer(p, cfg)
        p = {**p, **campos}
        telefones = [t for t in p["telefones"] if not self.conhecido(t["numero"])]
        if not p["telefones"]:
            return self._descartar(p["id"], "Sem telefone.", campos)
        if not telefones:
            return self._descartar(p["id"], "Já está nas suas conversas.", campos)
        situacao = str(p["cadastro"].get("situacao", "")).lower()
        if situacao and situacao != "ativa":
            return self._descartar(p["id"], "CNPJ não está ativo.", campos)
        try:
            avaliacao = self._avaliar(p, cfg)
        except Exception:
            log.warning("prospecção: qualificação falhou", exc_info=True)
            tentativas = int(p.get("tentativas", 0)) + 1
            if tentativas >= TENTATIVAS:
                return self._descartar(p["id"], "Não foi possível qualificar.", campos)
            self._mudar(p["id"], {**campos, "tentativas": tentativas}, so_se=("nova",))
            return "nova"
        if avaliacao["nota"] < MINIMO or not avaliacao["mensagem"]:
            return self._descartar(
                p["id"], f"Nota {avaliacao['nota']}: pouco sinal.", {**campos, **avaliacao}
            )
        status = "fila" if cfg.sozinho else "aprovar"
        self._mudar(p["id"], {**campos, **avaliacao, "status": status}, so_se=("nova",))
        return status

    def _descartar(self, ident: str, motivo: str, campos: dict[str, Any]) -> str:
        self._mudar(ident, {**campos, "status": "descartada", "motivo": motivo}, so_se=("nova",))
        return "descartada"

    def _qualificar_novas(self, cfg: Config) -> None:
        novas = [p for p in self.todas() if p.get("status") == "nova"][:QUALIFICAR_POR_CICLO]
        resultados = [self._qualificar(p, cfg) for p in novas]
        if (n := resultados.count("aprovar")) and not cfg.sozinho:
            plural = "empresa aguardando" if n == 1 else "empresas aguardando"
            self._avisar(f"Prospecção: {n} {plural} aprovação.")

    # --- buscar mais ----------------------------------------------------------------------------

    def _descobrir(self, cfg: Config, forcar: bool = False) -> int:
        chave = self.chave_apify()
        if not (chave and cfg.cidade and cfg.ramos):
            return 0
        meta = self._meta_ler()
        if not forcar:
            esperando = sum(1 for p in self.todas() if p.get("status") in ESPERANDO)
            if (
                esperando >= RESERVA
                or self.agora() - float(meta.get("descoberta", 0)) < DESCOBRIR_S
            ):
                return 0
        indice = int(meta.get("ramo", 0))
        ramo = cfg.ramos[indice % len(cfg.ramos)]
        self._meta_gravar(descoberta=self.agora(), ramo=indice + 1)
        try:
            achados = self.buscar_lugares(ramo, cfg.cidade, POR_BUSCA, chave)
        except apify.ApifyErro as erro:
            self._meta_gravar(erro=str(erro))
            self._avisar(f"Prospecção: {erro}")
            return 0
        novas = self.adicionar_lugares(achados)
        self._meta_gravar(erro="")
        atividade.PADRAO.registrar("execucao", f"Prospecção: {novas} empresa(s) novas ({ramo})")
        return novas

    def buscar_agora(self, esperar: bool = False) -> None:
        """O "Buscar empresas" da página: uma busca já, fora da reserva e do intervalo, e a
        qualificação do que veio. Numa thread: a Apify leva minutos e a página não espera."""
        cfg = self.config()
        if not self.chave_apify():
            raise ProspeccaoErro("Chave da Apify não configurada.")
        if not (cfg.cidade and cfg.ramos):
            raise ProspeccaoErro("Informe a cidade e os ramos.")
        if not self._trava.acquire(blocking=False):
            raise ProspeccaoErro("Busca em andamento.")

        def buscar() -> None:
            try:
                if self._descobrir(cfg, forcar=True):
                    self._qualificar_novas(cfg)
            except Exception:
                log.exception("prospecção: a busca falhou")
            finally:
                self._trava.release()

        linha = threading.Thread(target=buscar, name="prospeccao-busca", daemon=True)
        linha.start()
        if esperar:
            linha.join()

    # --- enviar ---------------------------------------------------------------------------------

    def _local(self, quando: float) -> datetime:
        return datetime.fromtimestamp(quando, fuso.local())

    def na_janela(self, quando: float) -> bool:
        momento = self._local(quando)
        return momento.weekday() < 5 and INICIO <= momento.hour < FIM

    def enviadas_hoje(self) -> list[dict[str, Any]]:
        hoje = self._local(self.agora()).date()
        return [
            p for p in self.todas()
            if p.get("enviado") and self._local(float(p["enviado"])).date() == hoje
        ]  # fmt: skip

    def proxima_janela(self, quando: float) -> float:
        """O primeiro momento, a partir de `quando`, dentro do horário de envio."""
        momento = self._local(quando)
        for _ in range(24 * 8):
            if self.na_janela(momento.timestamp()):
                return momento.timestamp()
            momento = momento.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return quando

    def _comeco_do_dia(self) -> float:
        """O primeiro envio de hoje: um minuto sorteado (uma vez por dia) a partir das 9h."""
        momento = self._local(self.agora())
        hoje = momento.date().isoformat()
        meta = self._meta_ler()
        if meta.get("dia") != hoje:
            atraso = self.sortear(0, COMECO_S)
            self._meta_gravar(dia=hoje, atraso=atraso)
        else:
            atraso = float(meta.get("atraso", 0))
        nove = momento.replace(hour=INICIO, minute=0, second=0, microsecond=0)
        return nove.timestamp() + atraso

    def proximo_envio(self, cfg: Config) -> float:
        """Quanto falta para a próxima mensagem poder sair (0: agora; -1: o limite de hoje
        chegou). O espaço desde a última é sorteado a cada envio; a janela fica de fora."""
        if len(self.enviadas_hoje()) >= cfg.por_dia:
            return -1.0
        ultima = max(self.todas(), key=lambda p: float(p.get("enviado") or 0), default=None)
        livre = 0.0
        if ultima is not None and ultima.get("enviado"):
            livre = float(ultima["enviado"]) + float(ultima.get("espera") or ESPACO_S)
        if not self.enviadas_hoje():
            livre = max(livre, self._comeco_do_dia())
        return max(0.0, livre - self.agora())

    def _freio(self, cfg: Config) -> bool:
        """Pessoas demais pedindo para não receber: a mensagem ou o público estão errados, e
        insistir faz o WhatsApp marcar o número. Pausa (desliga) e avisa."""
        # Depois de uma pausa, só contam as recusas novas: ligar de novo não pausa na hora.
        desde = max(self.agora() - FREIO_S, float(self._meta_ler().get("freio_em", 0)))
        recusas = sum(1 for p in self.todas() if float(p.get("recusou") or 0) > desde)
        if recusas < FREIO_RECUSAS:
            return False
        salvar_config(Config(**{**asdict(cfg), "ligada": False}), self.config_arquivo)
        motivo = f"Pausada: {recusas} pessoas pediram para não receber mensagens nesta semana."
        self._meta_gravar(erro=motivo, freio_em=self.agora())
        atividade.PADRAO.registrar("execucao", f"Prospecção {motivo.lower()}")
        self._avisar(f"Prospecção {motivo.lower()} Revise a mensagem e os ramos antes de ligar.")
        return True

    def _enviar_da_fila(self, cfg: Config) -> None:
        if self.enviar is None or not self.na_janela(self.agora()) or self.proximo_envio(cfg) != 0:
            return
        fila = sorted(
            (p for p in self.todas() if p.get("status") == "fila"),
            key=lambda p: (-int(p.get("nota", 0)), float(p.get("criado", 0))),
        )
        if not fila:
            return
        p = fila[0]
        nome = f"{p['dono']} ({p['nome']})" if p.get("dono") else p["nome"]
        for t in p.get("telefones", []):
            if self.conhecido(t["numero"]):
                continue  # virou conversa de quem usa depois da qualificação: não é prospecção
            # Gravado antes de enviar: se o Zé cair no meio, ela não volta para a fila.
            marcada = self._mudar(
                p["id"],
                {"status": "enviando", "enviado": self.agora(), "telefone_enviado": t["numero"],
                 "espera": ESPACO_S + self.sortear(0, VARIACAO_S)},
                so_se=("fila",),
            )  # fmt: skip
            if marcada is None:
                return  # descartada na página no meio
            try:
                self.enviar(t["numero"], nome, p["mensagem"])
            except RuntimeError as erro:
                volta = {"status": "fila", "enviado": 0.0, "telefone_enviado": "", "espera": 0}
                if "não está no WhatsApp" in str(erro):
                    self._mudar(p["id"], volta, so_se=("enviando",))
                    continue
                # Desconectado: tenta no próximo ciclo.
                self._mudar(p["id"], {**volta, "erro": str(erro)}, so_se=("enviando",))
                log.warning("prospecção: envio adiado: %s", erro)
                return
            self._mudar(p["id"], {"status": "enviada", "erro": ""}, so_se=("enviando",))
            self._avisar(f"Prospecção: mensagem enviada para {nome}.")
            return
        self._mudar(p["id"], {"status": "descartada", "motivo": "Sem WhatsApp."}, so_se=("fila",))

    # --- o ciclo --------------------------------------------------------------------------------

    def ciclo(self) -> None:
        """Uma rodada: qualifica, busca mais se faltar e envia uma, se for a hora."""
        if not self._trava.acquire(blocking=False):
            return
        try:
            self.em = self.agora()
            cfg = self.config()
            if not cfg.ligada or self._freio(cfg):
                return
            self._qualificar_novas(cfg)
            self._descobrir(cfg)
            self._enviar_da_fila(cfg)
        except Exception:  # um erro de uma empresa não para o funil das próximas rodadas
            log.exception("prospecção: o ciclo falhou")
        finally:
            self._trava.release()

    def _amanha(self) -> float:
        hoje = self._local(self.agora()).replace(hour=0, minute=0, second=0, microsecond=0)
        return (hoje + timedelta(days=1)).timestamp()

    def _quando_falado(self, quando: float) -> str:
        momento, hoje = self._local(quando), self._local(self.agora()).date()
        hora = momento.strftime("%H:%M")
        if momento.date() == hoje:
            return f"Hoje, {hora}"
        if momento.date() == hoje + timedelta(days=1):
            return f"Amanhã, {hora}"
        return f"{DIAS[momento.weekday()]}, {hora}"

    # --- a página -------------------------------------------------------------------------------

    def aprovar(self, ident: str, texto: str = "") -> dict[str, Any]:
        campos: dict[str, Any] = {"status": "fila"}
        if texto.strip():
            if len(texto) > LIMITE_EDITADA:
                raise ProspeccaoErro(f"Mensagem longa demais: até {LIMITE_EDITADA} caracteres.")
            campos["mensagem"] = texto.strip()
            campos["editada"] = True  # uma estratégia nova não reescreve o texto dela
        p = self._mudar(ident, campos, so_se=("aprovar",))
        if p is None:
            raise ProspeccaoErro("Empresa não está aguardando aprovação.")
        atividade.PADRAO.registrar("execucao", f"Prospecção: {p['nome']} aprovada", origem="painel")
        return p

    def descartar(self, ident: str) -> dict[str, Any]:
        p = self._mudar(
            ident, {"status": "descartada", "motivo": "Descartada por você."}, so_se=ESPERANDO
        )
        if p is None:
            raise ProspeccaoErro("Empresa não pode mais ser descartada.")
        return p

    def marcar(self, ident: str, status: str) -> dict[str, Any]:
        if status not in MARCAVEIS:
            raise ProspeccaoErro("Estado inválido.")
        campos: dict[str, Any] = {"status": status}
        if status == "sem_interesse":
            campos["recusou"] = self.agora()  # conta no freio
        p = self._mudar(ident, campos, so_se=CONTATADAS)
        if p is None:
            raise ProspeccaoErro("Só uma empresa já contatada muda assim.")
        atividade.PADRAO.registrar(
            "execucao", f"Prospecção: {p['nome']} · {ROTULOS[status]}", origem="painel"
        )
        return p

    def respondeu(self, telefone: str, texto: str) -> dict[str, Any] | None:
        """Uma mensagem chegou: era de uma empresa contatada? Marca a resposta e devolve ela."""
        chave = dono.chave_do_telefone(telefone)
        if len(chave) < 10:
            return None
        alvo = next(
            (p for p in self.todas() if p.get("status") in CONTATADAS
             and dono.chave_do_telefone(str(p.get("telefone_enviado", ""))) == chave),
            None,
        )  # fmt: skip
        if alvo is None:
            return None
        campos: dict[str, Any] = {"resposta": _limpo(texto, 300)}
        if alvo["status"] in ("enviando", "enviada"):
            campos["status"] = "respondeu"
        if SEM_INTERESSE.search(texto or "") and alvo["status"] != "reuniao":
            campos["status"] = "sem_interesse"
            campos["recusou"] = self.agora()  # conta no freio
        return self._mudar(alvo["id"], campos) or alvo

    def para_tela(self) -> dict[str, Any]:
        cfg = self.config()
        todas = sorted(self.todas(), key=lambda p: -float(p.get("atualizado", 0)))
        contagem = {s: 0 for s in ROTULOS}
        for p in todas:
            contagem[p.get("status", "nova")] = contagem.get(p.get("status", "nova"), 0) + 1

        def resumo(p: dict[str, Any]) -> dict[str, Any]:
            lugar = p.get("lugar") or {}
            return {
                "id": p["id"], "nome": p["nome"], "status": p["status"],
                "rotulo": ROTULOS.get(p["status"], p["status"]), "motivo": p.get("motivo", ""),
                "ramo": lugar.get("categoria") or p.get("cadastro", {}).get("atividade", ""),
                "dono": p.get("dono", ""), "cargo": p.get("cargo", ""),
                "telefones": p.get("telefones", []), "nota": p.get("nota", 0),
                "sinal": p.get("sinal", ""), "mensagem": p.get("mensagem", ""),
                "link": lugar.get("link", ""), "cnpj": p.get("cadastro", {}).get("cnpj", ""),
                "enviado": p.get("enviado", 0), "resposta": p.get("resposta", ""),
                "erro": p.get("erro", ""), "atualizado": p.get("atualizado", 0),
            }  # fmt: skip

        espera = self.proximo_envio(cfg)
        proximo = ""
        if cfg.ligada and contagem["fila"]:
            # Sem espera hoje (o limite do dia chegou): o começo do próximo dia útil.
            inicio = self.agora() + espera if espera >= 0 else self._amanha()
            proximo = self._quando_falado(self.proxima_janela(inicio))
        meta = self._meta_ler()
        return {
            "config": {**asdict(cfg), "link": self.link(cfg)},
            "apify": bool(self.chave_apify()),
            "obter_chave": apify.CONSOLE,
            "hoje": {"enviadas": len(self.enviadas_hoje()), "limite": cfg.por_dia},
            "proximo": proximo,
            "horario": f"Dias úteis, das {INICIO}h às {FIM}h",
            "contagem": contagem,
            "aguardando": [resumo(p) for p in todas if p["status"] == "aprovar"],
            "empresas": [resumo(p) for p in todas if p["status"] != "aprovar"][:NA_TELA],
            "erro": str(meta.get("erro", "")),
            "ocupado": self.ocupado(),
        }


_PADRAO: Funil | None = None


def padrao() -> Funil:
    """O funil do Zé, criado no primeiro uso (o banco não nasce só de importar o módulo)."""
    global _PADRAO
    if _PADRAO is None:
        _PADRAO = Funil()
    return _PADRAO
