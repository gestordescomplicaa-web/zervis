"""As ferramentas do cérebro sob demanda (17/11/2026): as mais usadas sempre à mão, o resto pela
busca do Claude Code.

Toda chamada ao modelo levava a descrição das ~100 ferramentas do Zé: uns 42 mil tokens, antes
de qualquer conversa (eram ~6 mil em outubro), e um pedido com ferramentas faz de 5 a 12
chamadas. O Claude Code tem a busca de ferramentas (`ToolSearch`): as que não estão à mão ficam
de fora do contexto e o modelo as acha quando precisa. Ela não ligava no Zé porque a lista de
ferramentas embutidas (`tools`) não trazia o `ToolSearch`.

Medido em 17/11/2026, com 100 ferramentas do tamanho das do Zé e uma pergunta que pede uma
delas: todas carregadas, 78,7 mil tokens e 3,8 a 6,0 s; todas sob demanda, 10,3 mil e ~5,1 s (a
busca é uma ida e volta a mais); as mais usadas sempre à mão e o resto sob demanda, 7,6 mil e
3,8 a 4,1 s. Por isso as mais usadas ficam marcadas com `anthropic/alwaysLoad` (o Claude Code as
põe sempre no contexto), escolhidas pelo uso real (`UsoDeFerramentas`).

Com as ferramentas e a persona reais (as 57 da avaliação, Sonnet): uma conversa simples foi de
33,7 mil para 23,5 mil tokens; um pedido com uma ferramenta (duas chamadas), de 67,4 mil para
47,1 mil; o tempo ficou igual. O que sobra é a persona (~7,7 mil), as essenciais (~6,3 mil, a
`tela_explicar` sozinha tem 3,2 mil) e a base do Claude Code.

Fora da Anthropic (OmniRoute, outro provedor), o Claude Code desliga a busca e carrega todas,
como antes.
"""

import dataclasses
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any

log = logging.getLogger(__name__)
BUSCA = "ToolSearch"  # a ferramenta embutida do Claude Code que acha as outras
SEMPRE = "anthropic/alwaysLoad"  # no `_meta` da ferramenta: fica sempre no contexto
MAXIMO = 16  # as sempre à mão: o resto (~85) sai do contexto
RECENTE_S = 30 * 24 * 3600  # o uso que conta para escolher
# Sem uso registrado ainda (uma instalação nova): as que todo dia pedem.
PADRAO = (
    "mcp__jarvis__tela_explicar",
    "mcp__jarvis__tela_agir",
    "mcp__jarvis__internet_pesquisar",
    "mcp__jarvis__sessoes_listar",
    "mcp__jarvis__sessao_ler",
    "mcp__jarvis__sessao_enviar",
    "mcp__jarvis__ze_sobre",
    "mcp__jarvis__automacao_lembrete",
    "mcp__jarvis__historico_buscar",
    "mcp__jarvis__memoria",
    "mcp__tempo__conversa_do_dia",
    "mcp__foco__foco_ver",
)
_marcados: dict[int, set[str]] = {}  # id(servidor) -> as sempre à mão (lido a cada listagem)


def essenciais(
    uso: dict[str, dict[str, int]],
    agora: float | None = None,
    maximo: int = MAXIMO,
    padrao: Iterable[str] = PADRAO,
) -> set[str]:
    """As mais usadas nos últimos 30 dias (só as de servidores MCP) e, até completar, as do
    padrão."""
    agora = time.time() if agora is None else agora
    recentes = sorted(
        (
            (int(r.get("usos", 0)), nome)
            for nome, r in uso.items()
            if nome.startswith("mcp__") and agora - int(r.get("ultimo", 0)) <= RECENTE_S
        ),
        reverse=True,
    )
    escolhidas = [nome for _, nome in recentes[:maximo]]
    for nome in padrao:
        if len(escolhidas) >= maximo:
            break
        if nome not in escolhidas:
            escolhidas.append(nome)
    return set(escolhidas)


def do_uso_registrado() -> set[str]:
    """As essenciais pelo uso que o núcleo registra (`nucleo/laco.py`, `uso_ferramentas`)."""
    from zervis import lugares
    from zervis.cerebro.consumo import UsoDeFerramentas

    try:
        uso = UsoDeFerramentas(lugares.ESTADO / "uso-ferramentas.json").ler()
    except Exception as erro:  # sem o registro, o padrão serve
        log.warning("uso das ferramentas ilegível (%s): fico com as do padrão", erro)
        uso = {}
    return essenciais(uso)


def marcar(mcp: dict[str, Any], nomes: set[str]) -> int:
    """Marca como sempre à mão, nos servidores do próprio processo (`type: sdk`), as ferramentas
    em `nomes` (`mcp__<servidor>__<ferramenta>`). Devolve quantos servidores foram marcados.

    O SDK em Python não leva o `alwaysLoad` por ferramenta (só o `maxResultSizeChars`): a
    listagem do servidor é embrulhada para acrescentar o `_meta`. Se a forma interna do servidor
    mudar, nada quebra: as ferramentas só ficam todas sob demanda (o teste avisa)."""
    marcados = 0
    for chave, config in mcp.items():
        if not isinstance(config, dict) or config.get("type") != "sdk":
            continue
        servidor = config.get("instance")
        prefixo = f"mcp__{config.get('name', chave)}__"
        meus = {n.removeprefix(prefixo) for n in nomes if n.startswith(prefixo)}
        if _embrulhar(servidor, meus):
            marcados += 1
    return marcados


def _embrulhar(servidor: Any, nomes: set[str]) -> bool:
    tratadores = getattr(servidor, "_request_handlers", None)
    if not isinstance(tratadores, dict):
        log.warning("servidor MCP sem a listagem esperada: as ferramentas ficam sob demanda")
        return False
    entrada = tratadores.get("tools/list")
    if entrada is None or not hasattr(entrada, "handler"):
        log.warning("servidor MCP sem a listagem esperada: as ferramentas ficam sob demanda")
        return False
    if id(servidor) in _marcados:  # já embrulhado: só troca a escolha
        _marcados[id(servidor)] = nomes
        return True
    _marcados[id(servidor)] = nomes
    original: Callable[..., Any] = entrada.handler

    async def listar(contexto: Any, parametros: Any) -> Any:
        resultado = await original(contexto, parametros)
        sempre = _marcados.get(id(servidor), set())
        for ferramenta in getattr(resultado, "tools", []):
            meta = dict(ferramenta.meta or {})
            if ferramenta.name in sempre:
                meta[SEMPRE] = True
            else:
                meta.pop(SEMPRE, None)
            ferramenta.meta = meta or None
        return resultado

    tratadores["tools/list"] = dataclasses.replace(entrada, handler=listar)
    return True
