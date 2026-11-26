"""Ações da página inicio."""

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from zervis import atividade, usuario, visuais
from zervis.avisos import lidos, mensagens
from zervis.cerebro import rapido
from zervis.memoria import anexos
from zervis.nucleo import precisa as lista_precisa
from zervis.portal.acoes.apoio import _latencia_de_hoje, linhas_do_registro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

NO_FIO = 200  # o fio de hoje que o chat relê; o resto vem rolando para cima
POR_PAGINA = 80  # o que o chat busca de uma vez, rolando para cima (ADR 0139)
AVISOS_DIAS = 7  # os avisos do Zé no sino: uma semana
AVISOS_MAXIMO = 60
TIPOS_AVISO = {"aviso", "lembrete", "manutencao"}

log = logging.getLogger(__name__)


def _item(atual: dict[str, str], tipo: str) -> dict[str, Any]:
    if tipo == "voce":
        return _pedido(atual["quando"], atual["pessoa"])
    return {"quando": atual["quando"], "tipo": tipo, "texto": atual["ze"]}


def _pedido(quando: str, pessoa: str) -> dict[str, Any]:
    """O que a pessoa escreveu e, se anexou, cada anexo com o nome e a miniatura (ADR 0137)."""
    texto, nomes = anexos.separar(pessoa)
    pedido: dict[str, Any] = {"quando": quando, "tipo": "voce", "texto": texto}
    if nomes:
        pedido["anexos"] = [anexos.PADRAO.info(n) for n in nomes]
    return pedido


def _ultimos(itens: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Os `n` últimos, sem separar o pedido da resposta (os dois têm a mesma hora): o chat busca
    o que veio antes pela hora do primeiro, e um par cortado ao meio sumiria."""
    corte = max(0, len(itens) - n)
    while 0 < corte < len(itens) and itens[corte]["quando"] == itens[corte - 1]["quando"]:
        corte -= 1
    return itens[corte:]


class AcoesInicio(Pagina):
    dependencias = (
        "_aplicar_depois",
        "_fonte",
        "atualizacao",
        "aprovacoes_pendentes",
        "autoconhecimento",
        "central",
        "cerebro",
        "cfg",
        "chamado",
        "consumo",
        "conversa_em_andamento",
        "conversas",
        "decidir_aprovacao",
        "dispensar_lead",
        "escrever",
        "espera",
        "foco",
        "jobs",
        "leads",
        "linha",
        "manutencao",
        "maquina",
        "mensagens",
        "modo_escuta",
        "modo_fala",
        "pendencias",
        "provedor",
        "sessoes",
        "tem_janela",
        "ultimo_na_tela",
        "ver_sessao",
        "versoes",
    )

    def estado(self) -> dict[str, Any]:
        from zervis.memoria.linha import agora

        via = self.painel._via()
        cerebro = self.n.cerebro
        return {
            "ze": self.n.maquina.estado.value,
            "cerebro": {"provedor": self.n.provedor, "modelo": getattr(cerebro, "modelo", "")},
            "via_rapida": {
                "ativa": isinstance(cerebro, rapido.Roteado),
                "motor": via["motor"],
                "modelo": via["modelo"],
            },
            "consumo": self.n.consumo.resumo_falado(),
            "latencia": _latencia_de_hoje(self.painel.pasta_latencias, agora().date().isoformat()),
            "foco": self.n.foco.onde_estava(),
            "tela_ts": self.painel._tela_ts(),
            "modo_fala": self.n.modo_fala,
            "escuta": {"modo": self.n.modo_escuta, "janela": self.n.tem_janela},
            "chamado": self.n.chamado,
            "espera": self.n.espera,
            "whatsapp": {
                "ligado": self.n.mensagens.ativo,
                "disponivel": mensagens.disponivel() or self.n.central.whatsapp_ativo,
            },
            "voz_remota": {"conectada": self.n._fonte is not None},
            "manutencao": {
                "ligada": self.n.manutencao.ligado,
                "aguardando": self.n._aplicar_depois is not None,
            },
            "atualizacao": self.n.atualizacao.foto(),
            "versao": self.n.versoes.foto(),  # a bolinha de "tem atualização" no menu
            "tela": self.n.ultimo_na_tela,  # [quando, texto]: o painel mostra no Silencioso
            "inicio": os.getpid(),  # muda a cada reinício: o painel recarrega sozinho
        }

    def _do_dia(self, dia: date, antes: datetime | None = None) -> list[dict[str, Any]]:
        """O fio de um dia: o que a pessoa disse ou escreveu, as respostas, os avisos e os visuais;
        com `antes`, só o que veio antes desse momento."""
        from zervis.memoria.linha import agora

        agora_ = agora()
        cedo = (lambda m: m < antes) if antes is not None else (lambda m: True)
        itens: list[dict[str, Any]] = []
        for t in self.n.conversas.do_dia(dia):
            if not cedo(t.em):
                continue
            quando = t.em.isoformat(timespec="seconds")
            pedido = _pedido(quando, t.pessoa)
            if origem := getattr(t, "origem", ""):
                pedido["origem"] = origem  # "whatsapp": a Conversa marca (ADR 0104)
            itens.append(pedido)
            if t.ze:
                resposta: dict[str, Any] = {"quando": quando, "tipo": "ze", "texto": t.ze}
                if gasto := getattr(t, "gasto", None):
                    resposta["gasto"] = gasto
                itens.append(resposta)
        inicio = datetime(dia.year, dia.month, dia.day, tzinfo=agora_.tzinfo)
        fim = min(inicio + timedelta(days=1), agora_ + timedelta(seconds=1))
        for ev in self.n.linha.entre(inicio, fim, TIPOS_AVISO):
            # Um lembrete é gravado ao ser criado, com a hora em que vai tocar.
            momento = max(ev.quando, ev.registrado)
            if momento <= agora_ and cedo(momento):
                itens.append(
                    {
                        "quando": momento.isoformat(timespec="seconds"),
                        "tipo": "aviso",
                        "texto": ev.texto,
                    }
                )
        for v in visuais.PADRAO.do_dia(dia):  # o que o Zé montou (ADR 0138)
            if cedo(v.criado):
                quando = v.criado.isoformat(timespec="seconds")
                itens.append({"quando": quando, "tipo": "visual", "visual": v.para_tela()})
        itens.sort(key=lambda i: i["quando"])  # estável: o pedido antes da resposta
        return itens

    def conversa(self) -> dict[str, Any]:
        """O fio de hoje com o Zé; o dos dias anteriores vem pela `conversa_anteriores`."""
        from zervis.memoria.linha import agora

        hoje = agora()
        itens = self._do_dia(hoje.date())
        andamento = getattr(self.n, "conversa_em_andamento", None)
        if andamento is not None and (atual := andamento()) is not None:
            # A troca em curso ainda não está no histórico: vai no fim, marcada, com o que o Zé
            # já respondeu até aqui.
            itens.append({**_item(atual, "voce"), "pendente": "1"})
            if atual["ze"]:
                itens.append({**_item(atual, "ze"), "pendente": "1"})
        fila = getattr(self.n, "fila", None)
        esperando = [a.titulo or a.texto for a in fila.validos()] if fila is not None else []
        pendentes = getattr(self.n, "aprovacoes_pendentes", None)  # sem a Central nos testes
        return {
            "dia": hoje.date().isoformat(),  # o "Hoje" do chat é o dia do Zé, não o do aparelho
            "itens": _ultimos(itens, NO_FIO),
            "esperando": esperando,
            "consumo": self._consumo_de_hoje(),
            "aprovacoes": pendentes() if pendentes is not None else [],
        }

    def conversa_anteriores(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O que veio antes de `antes` (o chat rolando para cima, ADR 0139): uma página, dia a dia,
        sem separar um pedido da resposta. `mais` diz se ainda há o que buscar."""
        from zervis.memoria.linha import agora

        try:
            antes = datetime.fromisoformat(str(dados.get("antes", "")))
        except ValueError:
            raise PedidoInvalido("Data inválida.") from None
        if antes.tzinfo is None:
            antes = antes.replace(tzinfo=agora().tzinfo)
        dias = [d for d in self.n.conversas.dias() if d <= antes.date()]
        itens: list[dict[str, Any]] = []
        while dias and len(itens) < POR_PAGINA:
            itens = self._do_dia(dias.pop(), antes) + itens
        pagina = _ultimos(itens, POR_PAGINA)
        return {"itens": pagina, "mais": bool(dias) or len(pagina) < len(itens)}

    def _consumo_de_hoje(self) -> dict[str, Any]:
        """O dia inteiro: as mensagens, o que saiu sem modelo e o que o Zé gastou sozinho, em
        segundo plano (avisos, notas, revisões e automações)."""
        from zervis.cerebro.consumo import CAMPOS, FUNDO

        consumo = getattr(self.n, "consumo", None)
        if consumo is None:
            return {}
        hoje = consumo.hoje
        origens = hoje.get("origens") or {}
        fundo = {nome: sum(int(origens.get(o, {}).get(nome, 0)) for o in FUNDO) for nome in CAMPOS}
        return {
            "locais": int(hoje.get("locais", 0)),
            "fundo": fundo,
            "fundo_vezes": sum(int(origens.get(o, {}).get("respostas", 0)) for o in FUNDO),
        }

    def escrever(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Um pedido escrito no painel: o mesmo caminho da fala; com anexos, os nomes guardados."""
        texto, nomes = str(dados.get("texto", "")), dados.get("anexos")
        if not nomes:
            return {"aviso": self.n.escrever(texto)}
        if not isinstance(nomes, list) or len(nomes) > anexos.MAX_POR_PEDIDO:
            raise PedidoInvalido(f"No máximo {anexos.MAX_POR_PEDIDO} anexos por mensagem.")
        return {"aviso": self.n.escrever(texto, [str(n) for n in nomes])}

    def anexar_conversa(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        """Um anexo do chat (ADR 0137): guarda e volta o nome que vai no pedido."""
        try:
            return {"anexo": anexos.PADRAO.guardar(consulta.get("nome", ""), corpo)}
        except anexos.AnexoErro as erro:
            raise PedidoInvalido(str(erro)) from None

    def decidir_aprovacao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Aprovar ou negar uma ação pedida pelo WhatsApp (ADR 0104): só aqui, com login."""
        ident = str(dados.get("id", ""))[:32]
        return {"aviso": self.n.decidir_aprovacao(ident, dados.get("aprovar") is True)}

    def atividade(self) -> dict[str, Any]:
        """O que o Zé fez e onde tropeçou (ADR 0025), do mais recente ao mais antigo."""
        return {"itens": atividade.PADRAO.listar(300), "resumo": atividade.PADRAO.resumo()}

    def autoconhecimento(self) -> dict[str, Any]:
        """O Zé por ele mesmo, em dados (ADR 0045): as apresentações da Imersão saem daqui."""
        return dict(self.n.autoconhecimento())

    def registro_tecnico(self, dados: dict[str, Any]) -> dict[str, Any]:
        """As últimas linhas do registro do serviço, sem segredos; `nivel`: erros, avisos, tudo.
        O nível sai do texto da linha: o journal guarda tudo o que o Zé escreve num nível só."""
        marcas = {
            "erros": ("ERROR", "CRITICAL", "Traceback"),
            "avisos": ("WARNING", "ERROR", "CRITICAL", "Traceback"),
        }
        linhas = linhas_do_registro()
        if linhas is None:
            return {"linhas": [], "aviso": "Registro do sistema indisponível."}
        if filtro := marcas.get(str(dados.get("nivel", ""))):
            linhas = [x for x in linhas if any(m in x for m in filtro)]
        return {"linhas": linhas[-400:]}

    def painel_vendo(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O painel está com esta sessão aberta e à vista: o Zé não fala o que ela já mostra."""
        self.n.ver_sessao(str(dados.get("sessao", ""))[:40])
        return {}

    def _tela_ts(self) -> float:
        """Quando o Zé mandou algo para o modo imersivo pela última vez (o painel abre a aba)."""
        try:
            pasta: Path = self.n.cfg.caminho("barehands", "pasta_estado")
            return float((pasta / "tela-comando.json").stat().st_mtime)
        except (OSError, KeyError):
            return 0.0

    def inicio(self) -> dict[str, Any]:
        from zervis.abertura.panorama import saudacao
        from zervis.memoria.linha import agora

        hoje = self.n.consumo.retrato()
        lido = sum(int(hoje.get(k) or 0) for k in ("entrada", "cache_lido", "cache_criado"))
        totais = [
            g["total_ms"]
            for g in _latencia_de_hoje(self.painel.pasta_latencias, agora().date().isoformat())
            if g.get("origem") == "voz" and g.get("total_ms")
        ]
        trabalhando = set(self.n.sessoes.trabalhando())
        sessoes = self.n.sessoes.listar()
        proximas = sorted(
            (j for j in self.n.jobs.listar() if j.ativo and j.proxima), key=lambda j: j.proxima
        )[:3]
        atual = self.n.foco.atual()
        fontes = self._fontes()
        nome = usuario.ler().nome.split(" ")[0]
        return {
            "ze": self.n.maquina.estado.value,
            "saudacao": f"{saudacao(agora())}{f', {nome}' if nome else ''}.",
            "chamado": self.n.chamado,
            "precisa": [i.para_tela() for i in lista_precisa.montar(fontes)],
            "agora": lista_precisa.agora(fontes),
            "foco": {"titulo": atual.titulo, "passo": atual.proximo_passo} if atual else None,
            "sessoes": {
                "total": len(sessoes),
                "trabalhando": [s.nome for s in sessoes if s.id in trabalhando],
            },
            "proximas": [{"nome": j.nome, "quando": j.proxima} for j in proximas],
            "hoje": {
                "respostas": int(hoje.get("respostas") or 0) + int(hoje.get("locais") or 0),
                "tokens_mil": round(lido / 1000),
                "voz_s": round(min(totais) / 1000, 1) if totais else None,
            },
        }

    def _fontes(self) -> lista_precisa.Fontes:
        return lista_precisa.Fontes(
            self.n.leads, self.n.sessoes, self.n.jobs, self.n.manutencao, self.n.pendencias,
            self.n.versoes, getattr(self.n, "aprovacoes_pendentes", None),
        )  # fmt: skip

    def precisa(self) -> dict[str, Any]:
        """O sino do painel (ADR 0133): o que precisa de quem usa e os avisos do Zé da semana,
        cada um com a chave e se já foi visto (o número do sino) e lido (o ponto, ADR 0139)."""
        from zervis.memoria.linha import agora

        hoje = agora()
        inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        avisos, comecou = [], lidos.PADRAO.inicio()
        for ev in self.n.linha.entre(inicio - timedelta(days=AVISOS_DIAS - 1), hoje, TIPOS_AVISO):
            momento = max(ev.quando, ev.registrado)
            if momento <= hoje:
                quando = momento.isoformat(timespec="seconds")
                avisos.append(
                    {
                        "quando": quando,
                        "texto": ev.texto,
                        "chave": lidos.chave("aviso", quando, ev.texto),
                        "antigo": momento.timestamp() < comecou,
                    }
                )
        avisos.sort(key=lambda a: a["quando"], reverse=True)
        avisos = avisos[:AVISOS_MAXIMO]
        itens = []
        for i in lista_precisa.montar(self._fontes()):
            item = i.para_tela()
            item["chave"] = lista_precisa.chave(i)
            itens.append(item)
        marcas = lidos.PADRAO.estado(x["chave"] for x in [*itens, *avisos])
        for x in [*itens, *avisos]:
            feito = {"visto", "lido"} if x.pop("antigo", False) else marcas.get(x["chave"], set())
            x["novo"], x["lido"] = "visto" not in feito, "lido" in feito
        return {
            "itens": itens,
            "avisos": avisos,
            "novos": sum(x["novo"] for x in [*itens, *avisos]),
        }

    def marcar_avisos(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O sino abriu (`visto`) ou a pessoa clicou num item (`lido`), ou em "Marcar todas como
        lidas" (ADR 0139)."""
        chaves, como = dados.get("chaves"), str(dados.get("como", ""))
        if not isinstance(chaves, list) or len(chaves) > 500 or como not in ("visto", "lido"):
            raise PedidoInvalido("Pedido inválido.")
        lidos.PADRAO.marcar((str(c) for c in chaves), como)
        return {}

    def dispensar_aviso(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O botão Dispensar de um item do "Precisa de você" (ADR 0142). O lead do WhatsApp
        recebe o "já vi" (para de lembrar, também no celular); os outros saem da lista até
        mudar. A aprovação do WhatsApp não se dispensa: aprovar ou negar."""
        marca = str(dados.get("chave", ""))
        alvo = next(
            (i for i in lista_precisa.montar(self._fontes()) if lista_precisa.chave(i) == marca),
            None,
        )
        if alvo is not None:
            if alvo.aprovacao:
                raise PedidoInvalido("Aprove ou negue.")
            if alvo.id.startswith("lead:"):
                self.n.dispensar_lead(alvo.id.removeprefix("lead:"))
            lidos.PADRAO.marcar([marca], "dispensado")
        return self.precisa()

    def abrir_link(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Um link para fora, clicado no painel do PC, abre no navegador de quem usa (ADR 0142)."""
        from zervis.sistema import navegador_padrao

        try:
            return {"aberto": navegador_padrao.abrir(str(dados.get("url", "")))}
        except navegador_padrao.LinkErro as erro:
            raise PedidoInvalido(str(erro)) from None

    def automacoes(self) -> list[dict[str, Any]]:
        """Cada automação com a agenda dita como gente e o que dá para mudar nela (ADR 0141)."""
        from zervis.automacoes import parametros
        from zervis.video import roteiro

        duracoes = {"duracoes": sorted(roteiro.DURACOES)}
        return [
            {
                "id": j.id,
                "nome": j.nome,
                "tipo": j.tipo,
                "tipo_nome": parametros.NOMES.get(j.tipo, j.tipo),
                "agenda": j.agenda,
                "agenda_frase": parametros.frase(j.agenda),
                "quando": parametros.partes(j.agenda),
                "proxima": j.proxima,
                "ativo": j.ativo,
                "ultimo_status": j.ultimo_status,
                "parametros": parametros.ler(j.tipo, j.texto),
                **(duracoes if j.tipo == "video" else {}),
            }
            for j in self.n.jobs.listar()
        ]

    def foco(self) -> dict[str, Any]:
        return dict(self.n.foco.quadro())

    def acao_no_foco(self, dados: dict[str, Any]) -> dict[str, Any]:
        from zervis.foco.frentes import FocoErro

        foco, id_, acao = self.n.foco, str(dados.get("id", "")), str(dados.get("acao", ""))
        try:
            f = foco.por_id(id_)
            if acao == "passo":
                foco.passo_feito(f.id)
            elif acao == "concluir":
                foco.concluir(f.id)
            elif acao == "pausar":
                foco.atualizar(f.id, estado="pausada")
            elif acao == "focar":
                foco.focar(f.id)
            elif acao == "descartar":
                foco.atualizar(f.id, estado="descartada")
            elif acao == "passo_novo":
                foco.atualizar(f.id, proximo_passo=str(dados.get("texto", "")))
            else:
                raise PedidoInvalido("ação desconhecida")
        except FocoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.painel.foco()

    def ativar_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        from zervis.memoria.linha import agora

        id_ = str(dados.get("id", ""))
        if dados.get("ativo"):
            self.painel._chamar(lambda: self.n.jobs.retomar(id_, agora()))
        else:
            self.painel._chamar(lambda: self.n.jobs.pausar(id_))
        return self.painel.automacoes()

    def editar_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        """O nome, quando e os parâmetros do tipo (ADR 0141). Só muda o que veio."""
        from zervis.automacoes import parametros
        from zervis.memoria.linha import agora

        id_ = str(dados.get("id", ""))
        job = next((j for j in self.n.jobs.listar() if j.id == id_), None)
        if job is None:
            raise PedidoInvalido("Automação não encontrada.")
        quando, novos = dados.get("quando"), dados.get("parametros")
        try:
            agenda = parametros.montar_agenda(quando) if isinstance(quando, dict) else None
            texto = None
            if isinstance(novos, dict) and parametros.ler(job.tipo, job.texto):
                texto = parametros.montar(job.tipo, job.texto, novos)
        except parametros.ParametroErro as erro:
            raise PedidoInvalido(str(erro)) from None
        nome = dados.get("nome")
        feito = self.painel._chamar(
            lambda: self.n.jobs.editar(
                id_, agora(), nome=None if nome is None else str(nome), agenda=agenda, texto=texto
            )
        )
        atividade.PADRAO.registrar("execucao", f"Automação editada: {feito.nome}", origem="painel")
        return self.painel.automacoes()

    def remover_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self.painel._chamar(lambda: self.n.jobs.remover(str(dados.get("id", ""))))
        return self.painel.automacoes()
