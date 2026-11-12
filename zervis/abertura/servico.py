"""O lado do Zé na abertura (ADR 0078), pelo mesmo contrato de arquivos da Imersão (ADR 0045):

- `abertura.json`: o Zé grava o panorama do dia uma vez por minuto (a Imersão o serve em
  `GET /abertura`). O clima e as notícias vêm de um cache renovado em segundo plano; até a
  primeira busca terminar, o panorama sai com `completo: false`;
- `abertura-falar.json`: a página grava `{montado, passo, ts}` (POST /abertura/falar) quando um
  painel aparece, e o Zé fala a fala daquele bloco. A página só escolhe o passo: o texto é
  sempre o do panorama que o próprio Zé montou. O passo -1 diz que a abertura começou e o -2,
  que foi pulada.

Enquanto a abertura roda (`rodando`), os avisos esperam na fila e nada é oferecido: eles saem
depois do fechamento ("Esse é o seu dia"), sem atropelar a entrada.
"""

import contextlib
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from zervis import fuso, usuario
from zervis.abertura import ajustes, clima, noticias, panorama
from zervis.automacoes import calendario
from zervis.redes import analise
from zervis.redes.instagram import _epoch as instagram_epoch

log = logging.getLogger(__name__)
RETRATO_S = 60.0
EXTERNAS_S = 20 * 60.0  # o clima e as manchetes mudam devagar
FALA_VALE_S = 15.0  # pedido de fala mais velho que isso (Zé parado, reinício) não vale
CONVERSA_RECENTE_S = 24 * 3600.0
GUARDADOS = 4  # panoramas lembrados: a página pode ter carregado o anterior
INICIO_S = 60.0  # a abertura começou: a vinheta e a primeira fala cabem nisso
SUBINDO_S = 25.0  # o Zé acabou de subir (o programa abriu): a página da abertura está vindo
PASSO_S = 45.0  # um passo pedido: a fala dele e o pedido do próximo cabem nisso


class FontesDoDia(Protocol):
    """O que a coleta lê do núcleo (o `Nucleo` serve; os testes passam um falso)."""

    sessoes: Any
    jobs: Any
    calendario: Any
    caixa: Any
    prioridade: Any
    foco: Any
    pendencias: Any  # as sugestões de memória esperando decisão
    versoes: Any

    def historico(self, dias: int = 7) -> Any:
        """O que o Zé fez nos últimos dias (a Atividade): a contagem por tipo e por dia."""
        ...


def _sessoes(fontes: FontesDoDia) -> list[panorama.SessaoParada]:
    ativas = set(fontes.sessoes.trabalhando())
    lista = []
    for s in fontes.sessoes.listar():
        if s.origem == "manutencao":
            continue
        if s.id in ativas:
            situacao = "trabalhando"
        elif s.interrompida:
            situacao = "interrompida"
        elif s.limite:
            situacao = "limite"
        elif s.estado == "erro":
            situacao = "erro"
        else:
            continue
        lista.append(panorama.SessaoParada(s.nome, situacao))
    ordem = list(panorama.SITUACOES)
    return sorted(lista, key=lambda s: ordem.index(s.situacao))


def _hoje(fontes: FontesDoDia, agora: datetime) -> list[panorama.Item]:
    itens = []
    cache = getattr(fontes.calendario, "cache", calendario.CACHE)
    for evento in calendario.eventos(cache, agora.timestamp()):
        quando = datetime.fromtimestamp(float(evento["inicio"]), agora.tzinfo)  # type: ignore[arg-type]
        if quando.date() == agora.date() and quando >= agora - timedelta(minutes=10):
            itens.append(panorama.Item(quando, str(evento["titulo"]), "compromisso"))
    for job in fontes.jobs.listar():
        if not (job.ativo and job.proxima):
            continue
        quando = datetime.fromisoformat(job.proxima).astimezone(agora.tzinfo)
        if quando.date() == agora.date() and quando >= agora:
            itens.append(panorama.Item(quando, job.nome, "automacao"))
    return itens


def _conversas(fontes: FontesDoDia, agora: float) -> list[panorama.Conversa]:
    return [
        panorama.Conversa(c.nome, c.quando)
        for c in fontes.caixa.conversas(grupos=False)
        if c.sem_resposta
        and agora - c.quando < CONVERSA_RECENTE_S
        and not fontes.prioridade.calado(c.chat, c.telefone)
    ]


def _foco(fontes: FontesDoDia, agora: datetime) -> panorama.Foco | None:
    foco = getattr(fontes, "foco", None)
    if foco is None:
        return None
    atual = foco.atual()
    semana = (agora - timedelta(days=7)).isoformat()
    return panorama.Foco(
        atual.titulo if atual else "",
        atual.proximo_passo if atual else "",
        len(foco.com_estado("ativa")),
        len(foco.com_estado("bloqueada")),
        len(foco.com_estado("pausada")),
        sum(1 for f in foco.com_estado("concluida") if (f.concluida_em or "") >= semana),
    )


def _atividade(fontes: FontesDoDia, agora: datetime) -> panorama.Atividade | None:
    """A Atividade dos últimos dias e as automações que rodaram hoje."""
    historico = getattr(fontes, "historico", None)
    if historico is None:
        return None
    h = historico(panorama.Atividade._field_defaults["dias"])
    hoje = agora.date().isoformat()
    rodaram = sum(1 for j in fontes.jobs.listar() if str(getattr(j, "ultima", ""))[:10] == hoje)
    return panorama.Atividade(
        int(h.contagem.get("pedido", 0)),
        int(h.contagem.get("execucao", 0)),
        int(h.contagem.get("falha", 0)),
        [(d.dia, d.registros, d.falhas) for d in h.por_dia],
        rodaram,
        h.dias,
    )


def _pedem(fontes: FontesDoDia, melhorias: int) -> list[panorama.Pendencia]:
    """O que espera quem usa fora das sessões (essas, o panorama tira de `sessoes`)."""

    def contar(fazer: Callable[[], Any], padrao: Any) -> Any:
        try:
            return fazer()
        except Exception:
            log.debug("abertura: uma pendência não foi lida", exc_info=True)
            return padrao

    com_erro = contar(
        lambda: [
            j.nome
            for j in fontes.jobs.listar()
            if j.ativo and getattr(j, "ultimo_status", "") == "erro"
        ],
        [],
    )
    sugestoes = contar(lambda: len(fontes.pendencias.listar()), 0)
    atualizacao = contar(lambda: bool(fontes.versoes.foto().get("disponivel")), False)
    return panorama.pendencias((), com_erro, melhorias, sugestoes, atualizacao)


def coletar(fontes: FontesDoDia, agora: datetime, melhorias: int = 0) -> dict[str, Any]:
    """As partes do Zé; cada uma que falhar fica vazia (a abertura nunca cai por uma delas)."""

    def tentar(fazer: Callable[[], list[Any]]) -> list[Any]:
        try:
            return fazer()
        except Exception:
            log.debug("abertura: uma parte do dia falhou", exc_info=True)
            return []

    return {
        "hoje": tentar(lambda: _hoje(fontes, agora)),
        "sessoes": tentar(lambda: _sessoes(fontes)),
        "conversas": tentar(lambda: _conversas(fontes, agora.timestamp())),
        "foco": (tentar(lambda: [_foco(fontes, agora)]) or [None])[0],
        "atividade": (tentar(lambda: [_atividade(fontes, agora)]) or [None])[0],
        "pedem": tentar(lambda: _pedem(fontes, melhorias)),
    }


def ler_instagram(leitor: Any) -> panorama.Instagram | None:
    """O perfil e as publicações mais novas pela conta conectada (zervis/redes/instagram.py);
    None sem conta. Falha de rede ou de token sobe: quem chama fica com o último que leu."""
    if leitor is None or not leitor.conectado:
        return None
    perfil = leitor.perfil()
    publicacoes = [
        panorama.Publicacao(
            instagram_epoch(p.get("timestamp")),
            analise.valor(p, "views"),
            " ".join(str(p.get("caption") or "").split()),
        )
        for p in leitor.recentes(panorama.NO_GRAFICO)
    ]
    return panorama.Instagram(
        str(perfil.get("username", "")), int(perfil.get("followers_count", 0) or 0), publicacoes
    )


class Externas:
    """O clima, as manchetes, o Instagram e as melhorias prontas do autodesenvolvimento (lidas
    pelo git), buscados fora do laço do Zé e guardados por 20 minutos."""

    def __init__(
        self,
        localizar: Callable[[str], clima.Lugar | None] = clima.localizar,
        buscar_clima: Callable[[clima.Lugar], clima.Clima | None] = clima.buscar,
        buscar_noticias: Callable[[], list[noticias.Noticia]] = noticias.buscar,
        instagram: Callable[[], Any] | None = None,
        melhorias: Callable[[], int] | None = None,
    ) -> None:
        self._localizar, self._clima, self._noticias = localizar, buscar_clima, buscar_noticias
        self._leitor_instagram = instagram  # devolve o leitor do Zé (ou None)
        self._contar_melhorias = melhorias  # quantas o autodesenvolvimento tem para aprovar
        self.melhorias = 0
        self.clima: clima.Clima | None = None
        self.noticias: list[noticias.Noticia] = []
        self.instagram: panorama.Instagram | None = None
        self._lugares: dict[str, clima.Lugar | None] = {}
        self._cidade = ""
        self._buscado = float("-inf")
        self._buscando: threading.Thread | None = None
        self.versao = 0  # sobe a cada busca terminada: o panorama é regravado na hora

    def renovar(self, cidade: str, agora: float) -> None:
        mudou = cidade != self._cidade
        if self._buscando is not None and self._buscando.is_alive():
            return
        if not mudou and agora - self._buscado < EXTERNAS_S:
            return
        self._cidade, self._buscado = cidade, agora
        self._buscando = threading.Thread(
            target=self._buscar, args=(cidade,), name="abertura-externas", daemon=True
        )
        self._buscando.start()

    def _buscar(self, cidade: str) -> None:
        if cidade and cidade not in self._lugares:
            self._lugares[cidade] = self._localizar(cidade)
        lugar = self._lugares.get(cidade) if cidade else None
        self.clima = self._clima(lugar) if lugar is not None else None
        if novas := self._noticias():
            self.noticias = novas
        if self._leitor_instagram is not None:
            try:
                self.instagram = ler_instagram(self._leitor_instagram())
            except Exception as erro:  # sem rede, token vencido: fica o último lido
                log.info("abertura: o Instagram não foi lido (%s)", type(erro).__name__)
        if self._contar_melhorias is not None:
            try:
                self.melhorias = int(self._contar_melhorias())
            except Exception as erro:
                log.info("abertura: as melhorias não foram contadas (%s)", type(erro).__name__)
        self.versao += 1

    def esperar(self, prazo: float = 10.0) -> None:
        """Só para os testes e para a primeira abertura: a busca em andamento termina."""
        if self._buscando is not None:
            self._buscando.join(prazo)


class Abertura:
    def __init__(
        self,
        pasta: Path,
        fontes: FontesDoDia,
        externas: Externas | None = None,
        ler_ajustes: Callable[[], ajustes.Ajustes] = ajustes.ler,
    ) -> None:
        self.pasta = pasta
        self.fontes = fontes
        self.externas = externas or Externas()
        self.ler_ajustes = ler_ajustes
        self.retratado = float("-inf")
        self._versao = -1
        self.guardados: dict[str, list[str]] = {}  # montado -> as falas, na ordem dos blocos
        self._pedido = self.pasta / "abertura-falar.json"
        self._mtime = self._modificado()
        self._rodando_ate = 0.0  # epoch: até quando a abertura conta como em andamento
        self._faladas: set[str] = set()  # as falas que a página pediu (nunca viram aviso)
        with contextlib.suppress(Exception):
            if self.ler_ajustes().ligada:  # abrir o programa sobe o Zé e abre a abertura
                self._rodando_ate = time.time() + SUBINDO_S

    def cidade(self) -> str:
        return self.ler_ajustes().cidade or ajustes.cidade_do_fuso(str(fuso.local()))

    def montar(self, agora: datetime) -> dict[str, Any]:
        partes = coletar(self.fontes, agora, self.externas.melhorias)
        dia = panorama.montar(
            agora,
            usuario.ler().nome,
            self.externas.clima,
            partes["hoje"],
            partes["sessoes"],
            partes["conversas"],
            self.externas.noticias,
            self.externas.instagram,
            partes["foco"],
            partes["atividade"],
            partes["pedem"],
        )
        dia["ligada"] = self.ler_ajustes().ligada
        # Abrir o programa sobe o Zé: o primeiro panorama sai antes da primeira busca de fora
        # terminar. A página espera o completo para não abrir sem o clima, o Instagram e as
        # manchetes (visto em 11/11/2026: só três cards).
        dia["completo"] = self.externas.versao > 0
        dia["musica"] = ajustes.musica() is not None
        return dia

    def retratar(self, agora: float, ja: bool = False) -> None:
        """Uma vez por minuto (ou `ja`): o panorama para a Imersão. Falhar não derruba o laço."""
        self.externas.renovar(self.cidade(), agora)
        novas = self.externas.versao != self._versao
        if not (ja or novas) and agora - self.retratado < RETRATO_S:
            return
        self.retratado, self._versao = agora, self.externas.versao
        try:
            dia = self.montar(datetime.fromtimestamp(agora, fuso.local()))
        except Exception:
            log.warning("abertura: o panorama do dia falhou", exc_info=True)
            return
        self.guardados[dia["montado"]] = [str(b["fala"]) for b in dia["blocos"]]
        while len(self.guardados) > GUARDADOS:
            self.guardados.pop(next(iter(self.guardados)))
        with contextlib.suppress(OSError):
            arquivo = self.pasta / "abertura.json"
            temporario = arquivo.with_suffix(".next")
            temporario.write_text(json.dumps({**dia, "ts": agora}, ensure_ascii=False))
            temporario.replace(arquivo)

    def _modificado(self) -> float:
        try:
            return self._pedido.stat().st_mtime
        except OSError:
            return 0.0

    def e_fala(self, texto: str) -> bool:
        """`texto` é uma fala da abertura: pedida pela página, de um panorama guardado ou com o
        jeito de uma (as que ficaram na fila de avisos antes desta correção, 11/11/2026)."""
        if texto in self._faladas or any(texto in f for f in self.guardados.values()):
            return True
        return bool(panorama.JEITO_DE_FALA.match(texto))

    def rodando(self, agora: float | None = None) -> bool:
        """A abertura está na tela: os avisos esperam (nada de oferta no meio da entrada)."""
        return (time.time() if agora is None else agora) < self._rodando_ate

    def fala(self, agora: float | None = None) -> str | None:
        """A fala pedida pela página, uma vez só (barato: só lê se o arquivo mudou)."""
        if (mtime := self._modificado()) == self._mtime:
            return None
        self._mtime = mtime
        try:
            pedido = json.loads(self._pedido.read_text())
            agora = time.time() if agora is None else agora
            if agora - float(pedido["ts"]) > FALA_VALE_S:
                return None
            falas = self.guardados.get(str(pedido["montado"]))
            passo = int(pedido["passo"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if passo in (-1, -2):
            self._rodando_ate = agora + INICIO_S if passo == -1 else 0.0
            return None
        if falas is None or not 0 <= passo < len(falas):
            return None
        # o último passo é o fechamento: depois dele, os avisos voltam a sair
        self._rodando_ate = agora + PASSO_S if passo < len(falas) - 1 else 0.0
        if falas[passo]:
            self._faladas.add(falas[passo])
        return falas[passo] or None
