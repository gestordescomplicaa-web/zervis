"""O que espera quem usa e o que o Zé está fazendo agora (ADR 0133): o "Precisa de você" e o
"O Zé agora" do Início, o sino do painel e a resposta do Zé a "o que precisa de mim?".

Cada fonte que falhar fica de fora: a lista nunca cai por uma delas. Os itens vão do mais grave
para o menos; no mesmo nível, o que espera há mais tempo primeiro. Nada aqui decide nada: cada
item leva à página que resolve (ou ao WhatsApp, para responder um lead); só as aprovações do
WhatsApp se resolvem ali mesmo, pelo pedido que a Conversa já usa.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple

log = logging.getLogger(__name__)

NIVEIS = ("critico", "alerta", "info")
RASCUNHO_VALE_S = 7 * 24 * 3600  # vídeo ou post para revisar sai da lista depois de uma semana
JUNTAR_A_PARTIR = 3  # tantas mensagens da prospecção para aprovar viram um item só
AGORA_MAXIMO = 6
FALADOS = 3

SITUACOES = {"interrompida": "Interrompida", "limite": "Limite da conta", "erro": "Parou com erro"}


class Fontes(NamedTuple):
    """As partes do Zé que a lista lê (o núcleo, ou os serviços declarados de uma página)."""

    leads: Any  # zervis/avisos/pendentes.py
    sessoes: Any
    jobs: Any
    manutencao: Any
    pendencias: Any  # as sugestões de memória esperando decisão
    versoes: Any
    aprovacoes: Callable[[], list[dict[str, Any]]] | None = None  # as do WhatsApp (ADR 0104)


class Item(NamedTuple):
    id: str
    secao: str  # a página do painel de onde vem (o ícone e o link)
    area: str
    titulo: str
    detalhe: str = ""
    quando: float = 0.0  # epoch, em segundos; 0 = sem hora
    nivel: str = "alerta"
    acao: str = "Abrir"
    link: str = ""  # para onde o botão leva; vazio = a página (`#secao`)
    aprovacao: str = ""  # uma aprovação do WhatsApp: aprovar ou negar ali mesmo

    def para_tela(self) -> dict[str, Any]:
        d = self._asdict()
        d["link"] = self.link or f"#{self.secao}"
        return d


def _epoch(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _curto(texto: str, limite: int = 90) -> str:
    limpo = " ".join(str(texto or "").split())
    return limpo if len(limpo) <= limite else limpo[: limite - 1].rsplit(" ", 1)[0] + "…"


def _leads(n: Fontes) -> list[Item]:
    itens = []
    for p in n.leads.abertas():
        citacao = f"“{_curto(p.texto)}”" if p.texto else "Esperando a sua resposta"
        link = f"https://wa.me/{p.telefone}" if p.telefone else "#atendimento"
        itens.append(
            Item(
                f"lead:{p.id}",
                "atendimento",
                "WhatsApp",
                f"Responder {p.nome}",
                citacao,
                p.chegou,
                "alerta",
                "Responder",
                link,
            )
        )
    return itens


def _aprovacoes(n: Fontes) -> list[Item]:
    pendentes = n.aprovacoes  # sem a Central nos testes
    return [
        Item(
            f"aprovacao:{a['id']}",
            "conversa",
            "WhatsApp",
            "Aprovação pendente",
            _curto(a["descricao"], 140),
            _epoch(a["quando"]),
            "alerta",
            "Aprovar",
            aprovacao=str(a["id"]),
        )
        for a in (pendentes() if pendentes is not None else [])
    ]


def _sessoes(n: Fontes) -> list[Item]:
    trabalhando = set(n.sessoes.trabalhando())
    itens = []
    for s in n.sessoes.listar():
        secao = "melhorias" if s.origem == "manutencao" else "sessoes"
        pedidos = n.sessoes.permissoes.pendentes(s.id)
        for p in pedidos:
            pergunta = p.get("tipo") == "pergunta"
            itens.append(
                Item(
                    f"permissao:{p['id']}",
                    secao,
                    "Sessões",
                    f"{'Responder' if pergunta else 'Aprovar'} na sessão {s.nome}",
                    _curto(p.get("frase", "")),
                    0.0,
                    "alerta",
                    "Abrir",
                )
            )
        if pedidos or s.id in trabalhando or s.origem == "manutencao":
            continue
        situacao = next(
            (k for k, vale in (("interrompida", s.interrompida), ("limite", s.limite),
                               ("erro", s.estado == "erro")) if vale),
            "",
        )  # fmt: skip
        if situacao:
            nivel = "critico" if situacao == "erro" else "alerta"
            itens.append(
                Item(
                    f"sessao:{s.id}",
                    secao,
                    "Sessões",
                    f"Sessão {s.nome}",
                    SITUACOES[situacao],
                    _epoch(s.atualizada),
                    nivel,
                    "Abrir",
                )
            )
    return itens


def _prospeccao(_: Fontes) -> list[Item]:
    from zervis.prospeccao import funil

    esperando = [p for p in funil.padrao().todas() if p.get("status") == "aprovar"]
    if len(esperando) >= JUNTAR_A_PARTIR:
        nomes = ", ".join(p["nome"] for p in esperando[:3])
        return [
            Item(
                "prospeccao",
                "prospeccao",
                "Prospecção",
                f"Aprovar {len(esperando)} mensagens",
                f"{nomes}…",
                min(float(p.get("atualizado", 0)) for p in esperando),
                "info",
                "Revisar",
            )
        ]
    return [
        Item(
            f"prospeccao:{p['id']}",
            "prospeccao",
            "Prospecção",
            f"Aprovar a mensagem para {p['nome']}",
            f"Nota {p.get('nota', 0)}",
            float(p.get("atualizado", 0)),
            "info",
            "Revisar",
        )
        for p in esperando
    ]


def _marketing(_: Fontes) -> list[Item]:
    from zervis import marketing_posts
    from zervis.video import videos

    agora, itens = time.time(), []
    for v in videos.PADRAO.listar():
        feito = v.feito_em or v.criado
        if v.estado == "rascunho" and agora - feito < RASCUNHO_VALE_S:
            tela = videos.PADRAO.para_tela(v)
            if tela.get("pronto"):
                itens.append(
                    Item(
                        f"video:{v.id}",
                        "marketing",
                        "Marketing",
                        "Revisar o vídeo",
                        _curto(v.titulo or v.tema),
                        feito,
                        "info",
                        "Assistir",
                    )
                )
    for p in marketing_posts.PADRAO.listar():
        if p.estado == "rascunho" and agora - p.criado < RASCUNHO_VALE_S:
            itens.append(
                Item(
                    f"post:{p.id}",
                    "marketing",
                    "Marketing",
                    "Revisar o post",
                    _curto(p.chamada or p.tema),
                    p.criado,
                    "info",
                    "Revisar",
                )
            )
    return itens


def _o_ze(n: Fontes) -> list[Item]:
    itens = [
        Item(
            f"automacao:{j.id}",
            "automacoes",
            "Automações",
            f"A automação {j.nome} falhou",
            "Confira e rode de novo",
            0.0,
            "critico",
            "Abrir",
        )
        for j in n.jobs.listar()
        if j.ativo and getattr(j, "ultimo_status", "") == "erro"
    ]
    m = n.manutencao.mudancas()
    if prontas := len(m.get("commits") or ()) or int(bool(m.get("arquivos"))):
        itens.append(
            Item(
                "melhorias",
                "melhorias",
                "Autodesenvolvimento",
                "Aprovar as melhorias",
                f"{prontas} {'mudança pronta' if prontas == 1 else 'mudanças prontas'}",
                0.0,
                "info",
                "Revisar",
            )
        )
    if sugestoes := len(n.pendencias.listar()):
        itens.append(
            Item(
                "sugestoes",
                "memoria",
                "Memória",
                "Decidir as sugestões de memória",
                f"{sugestoes} {'sugestão' if sugestoes == 1 else 'sugestões'}",
                0.0,
                "info",
            )
        )
    if n.versoes.foto().get("disponivel"):
        itens.append(
            Item(
                "atualizacao",
                "atualizacoes",
                "Atualizações",
                "Nova versão disponível",
                "",
                0.0,
                "info",
                "Ver",
            )
        )
    return itens


FONTES: tuple[Callable[[Fontes], list[Item]], ...] = (
    _aprovacoes,
    _leads,
    _sessoes,
    _prospeccao,
    _marketing,
    _o_ze,
)


def montar(n: Fontes) -> list[Item]:
    itens: list[Item] = []
    for fonte in FONTES:
        try:
            itens += fonte(n)
        except Exception:
            log.debug("precisa: %s não foi lida", fonte.__name__, exc_info=True)
    return sorted(itens, key=lambda i: (NIVEIS.index(i.nivel), i.quando or float("inf")))


def agora(n: Fontes) -> list[dict[str, Any]]:
    """O que o Zé está fazendo: as sessões trabalhando, o que o Marketing está criando, a próxima
    mensagem da prospecção e as próximas automações."""
    vivo: list[dict[str, Any]] = []

    def tentar(fazer: Callable[[], None]) -> None:
        try:
            fazer()
        except Exception:
            log.debug("agora: uma parte não foi lida", exc_info=True)

    def sessoes() -> None:
        ativas = set(n.sessoes.trabalhando())
        for s in n.sessoes.listar():
            if s.id in ativas:
                secao = "melhorias" if s.origem == "manutencao" else "sessoes"
                vivo.append(
                    {
                        "secao": secao,
                        "titulo": f"Sessão {s.nome}",
                        "detalhe": _curto(s.resumo) or "Trabalhando",
                        "vivo": True,
                    }
                )

    def marketing() -> None:
        from zervis import marketing_posts
        from zervis.video import videos

        for v in videos.PADRAO.listar():
            if v.estado in ("criando", "publicando"):
                fazendo = "Criando o vídeo" if v.estado == "criando" else "Publicando o vídeo"
                vivo.append(
                    {
                        "secao": "marketing",
                        "titulo": f"{fazendo}: {_curto(v.tema, 60)}",
                        "detalhe": v.etapa or "Na fila",
                        "vivo": True,
                    }
                )
        for p in marketing_posts.PADRAO.listar():
            if p.estado in ("criando", "publicando"):
                fazendo = "Criando o post" if p.estado == "criando" else "Publicando o post"
                vivo.append(
                    {
                        "secao": "marketing",
                        "titulo": f"{fazendo}: {_curto(p.tema, 60)}",
                        "detalhe": "",
                        "vivo": True,
                    }
                )

    def prospeccao() -> None:
        from zervis.prospeccao import funil

        t = funil.padrao().para_tela()
        if t["config"]["ligada"] and t["proximo"]:
            vivo.append(
                {
                    "secao": "prospeccao",
                    "titulo": "Próxima mensagem da prospecção",
                    "detalhe": f"{t['hoje']['enviadas']} de {t['hoje']['limite']} hoje",
                    "hora": t["proximo"],
                }
            )

    def automacoes() -> None:
        proximas = sorted(
            (j for j in n.jobs.listar() if j.ativo and j.proxima), key=lambda j: j.proxima
        )
        for j in proximas[:2]:
            vivo.append(
                {
                    "secao": "automacoes",
                    "titulo": j.nome,
                    "detalhe": "Automação",
                    "quando": j.proxima,
                }
            )

    for parte in (sessoes, marketing, prospeccao, automacoes):
        tentar(parte)
    return vivo[:AGORA_MAXIMO]


def texto(itens: list[Item]) -> str:
    """Para o retrato do Zé (`ze_sobre`): o que responder a "o que precisa de mim?"."""
    if not itens:
        return (
            "## O que espera o usuário agora\nNada: nenhuma aprovação, resposta ou sessão parada."
        )
    linhas = [
        f"## O que espera o usuário agora ({len(itens)}; fale os {FALADOS} primeiros, o mais "
        "grave primeiro, e diga que o resto está no Início do painel)"
    ]
    linhas += [
        f"- {i.titulo}{f' ({i.detalhe})' if i.detalhe else ''} · {i.area}" for i in itens[:12]
    ]
    return "\n".join(linhas)
