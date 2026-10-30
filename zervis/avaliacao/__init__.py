"""A bateria de avaliação do cérebro: o julgamento do Zé medido, não suposto (20/10/2026).

Cada cenário (`cenarios/*.toml`) é um pedido de quem usa, o que as ferramentas respondem e o que
se espera do Zé: que ferramentas ele usa ou não usa, o que vai nos argumentos e o que a resposta
diz. O cérebro é o de verdade (a mesma persona, o mesmo modelo e as descrições reais das
ferramentas, que é por onde ele decide); só a execução das ferramentas é simulada: nada é
criado, enviado nem apagado. Roda sob demanda (`zervis avaliar`), porque gasta a conta de quem
usa; o `make check` testa o motor com um cérebro falso.

O modelo varia de uma vez para outra: `repetir` dá a taxa de acerto de cada cenário.
"""

import dataclasses
import json
import re
import time
import tomllib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol

from claude_agent_sdk import SdkMcpTool

from zervis.cerebro.base import Aprovar, EventoCerebro, Fim, Resposta, Texto

PASTA = Path(__file__).with_name("cenarios")
PADRAO = '{"ok": true}'
MAX_PALAVRAS = 80  # a persona pede até cinquenta; o teto deixa folga para listar nomes
MARKDOWN = re.compile(r"\*\*|^#|^\s*[-*] |`", re.MULTILINE)


class AvaliacaoErro(ValueError):
    pass


@dataclass(frozen=True)
class Cenario:
    nome: str
    arquivo: str
    pedido: str
    ferramentas: dict[str, str]  # nome curto -> o que ela responde
    espera: dict[str, Any]
    aprovar: bool = True  # a resposta falada a um pedido de aprovação


@dataclass
class Chamada:
    ferramenta: str  # nome curto, sem `mcp__jarvis__`
    entrada: dict[str, Any]


@dataclass
class Rodada:
    resposta: str = ""
    chamadas: list[Chamada] = field(default_factory=list)
    aprovacoes: list[str] = field(default_factory=list)
    erro: str = ""
    segundos: float = 0.0
    # O que a resposta gastou, por parte (a via rápida, o cérebro), como na Conversa.
    gastos: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return sum(
            g["entrada"] + g["cache_lido"] + g["cache_criado"] + g["saida"] for g in self.gastos
        )

    @property
    def via(self) -> str:
        return "+".join(g["rotulo"] for g in self.gastos)


@dataclass(frozen=True)
class Conferencia:
    regra: str
    ok: bool
    detalhe: str = ""


def _texto(valor: Any) -> str:
    return valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)


def carregar(pasta: Path = PASTA) -> list[Cenario]:
    cenarios = []
    for arquivo in sorted(pasta.glob("*.toml")):
        try:
            dados = tomllib.loads(arquivo.read_text())
        except tomllib.TOMLDecodeError as erro:
            raise AvaliacaoErro(f"{arquivo.name}: {erro}") from None
        if not str(dados.get("pedido", "")).strip():
            raise AvaliacaoErro(f"{arquivo.name}: falta o pedido")
        cenarios.append(
            Cenario(
                nome=str(dados.get("nome") or arquivo.stem),
                arquivo=arquivo.stem,
                pedido=str(dados["pedido"]),
                ferramentas={k: _texto(v) for k, v in (dados.get("ferramentas") or {}).items()},
                espera=dict(dados.get("espera") or {}),
                aprovar=bool(dados.get("aprovar", True)),
            )
        )
    return cenarios


# --- as ferramentas do Zé, com a execução simulada --------------------------------------------


def definicoes() -> list[SdkMcpTool[Any]]:
    """As ferramentas do servidor `jarvis` com os nomes, descrições e esquemas de verdade. Os
    serviços são vazios: as fábricas só montam as definições, e os handlers são trocados."""
    from zervis.cerebro.ferramentas import (
        aprendizado,
        atualizacoes,
        automacoes,
        conectores,
        manutencao,
        modelos,
        navegador,
        pesquisa,
        sessoes,
        sistema,
        sobre,
        tela,
    )
    from zervis.sistema import catalogo

    vazio: Any = SimpleNamespace()
    maquina: Any = SimpleNamespace(acoes=catalogo.carregar())  # o resumo entra na descrição
    return [
        *sessoes.ferramentas(vazio),
        *tela.ferramentas(vazio),
        *sistema.ferramentas(maquina),
        *automacoes.ferramentas(vazio),
        *aprendizado.ferramentas(vazio, vazio, vazio, vazio),
        *manutencao.ferramentas(vazio),
        *navegador.ferramentas(),
        *conectores.ferramentas(),
        *atualizacoes.ferramentas(),
        *sobre.ferramentas(lambda: ""),
        *pesquisa.ferramentas(_sem_pesquisa),
        *modelos.ferramentas(Path("/nao-existe"), vazio),
    ]


async def _sem_pesquisa(_pedido: str) -> str:
    return ""  # só a definição; quem responde é o cenário


def simuladas(cenario: Cenario, rodada: Rodada) -> list[SdkMcpTool[Any]]:
    """As ferramentas que respondem o que o cenário diz e anotam cada chamada."""
    base = definicoes()
    nomes = {f.name for f in base}
    if desconhecidas := sorted(set(cenario.ferramentas) - nomes):
        raise AvaliacaoErro(f"{cenario.arquivo}: ferramenta desconhecida: {desconhecidas[0]}")

    def simular(nome: str) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
        async def handler(entrada: dict[str, Any]) -> dict[str, Any]:
            rodada.chamadas.append(Chamada(nome, dict(entrada)))
            texto = cenario.ferramentas.get(nome, PADRAO)
            return {"content": [{"type": "text", "text": texto}]}

        return handler

    return [dataclasses.replace(f, handler=simular(f.name)) for f in base]


# --- rodar --------------------------------------------------------------------------------------


class Cerebro(Protocol):
    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None: ...
    def ask(self, texto: str) -> AsyncIterator[EventoCerebro]: ...
    async def close(self) -> None: ...


CriarCerebro = Callable[[list[SdkMcpTool[Any]]], Cerebro]


async def rodar(cenario: Cenario, criar: CriarCerebro, persona: str) -> Rodada:
    """Um cérebro novo por rodada: nada de uma conversa vaza para a outra."""
    rodada = Rodada()

    async def aprovar(frase: str) -> Resposta:
        rodada.aprovacoes.append(frase)
        return Resposta(cenario.aprovar, "sim" if cenario.aprovar else "não")

    cerebro = criar(simuladas(cenario, rodada))
    inicio = time.monotonic()
    try:
        await cerebro.start(persona, aprovar)
        partes = []
        async for evento in cerebro.ask(cenario.pedido):
            if isinstance(evento, Texto):
                partes.append(evento.texto)
            elif isinstance(evento, Fim) and evento.erro:
                rodada.erro = evento.erro
        rodada.resposta = "".join(partes).strip()
        rodada.gastos = _gastos(cerebro)
    finally:
        await cerebro.close()
        rodada.segundos = time.monotonic() - inicio
    return rodada


def _gastos(cerebro: Cerebro) -> list[dict[str, Any]]:
    """As partes do gasto: a via rápida já as separa; o cérebro sozinho é uma parte só."""
    from zervis.cerebro.consumo import gasto

    if partes := list(getattr(cerebro, "gastos", None) or []):
        return partes
    modelo = str(getattr(cerebro, "modelo_usado", None) or getattr(cerebro, "modelo", "") or "")
    parte = gasto(getattr(cerebro, "uso", None), "completo", modelo)
    return [parte] if parte else []


# --- julgar -------------------------------------------------------------------------------------


def _lista(espera: dict[str, Any], chave: str) -> list[str]:
    valor = espera.get(chave, [])
    return [valor] if isinstance(valor, str) else [str(v) for v in valor]


def _entradas(rodada: Rodada, nome: str) -> list[str]:
    return [
        json.dumps(c.entrada, ensure_ascii=False).lower()
        for c in rodada.chamadas
        if c.ferramenta == nome
    ]


def julgar(cenario: Cenario, rodada: Rodada) -> list[Conferencia]:
    espera, usadas = cenario.espera, [c.ferramenta for c in rodada.chamadas]
    resposta = rodada.resposta
    regras = [Conferencia("respondeu", not rodada.erro and bool(resposta), rodada.erro)]
    for nome in _lista(espera, "usa"):
        regras.append(Conferencia(f"usa {nome}", nome in usadas, f"usou: {usadas or 'nada'}"))
    if alguma := _lista(espera, "usa_alguma"):
        ok = any(n in usadas for n in alguma)
        regras.append(Conferencia(f"usa uma de {alguma}", ok, f"usou: {usadas or 'nada'}"))
    for nome in _lista(espera, "nao_usa"):
        regras.append(Conferencia(f"não usa {nome}", nome not in usadas))
    for nome, trechos in (espera.get("entrada") or {}).items():
        entradas = _entradas(rodada, nome)
        for trecho in [trechos] if isinstance(trechos, str) else trechos:
            ok = any(str(trecho).lower() in e for e in entradas)
            regras.append(Conferencia(f"{nome} com {trecho!r}", ok, "; ".join(entradas)[:200]))
    for nome, trechos in (espera.get("entrada_alguma") or {}).items():
        entradas = _entradas(rodada, nome)
        lista = [trechos] if isinstance(trechos, str) else [str(t) for t in trechos]
        ok = any(t.lower() in e for t in lista for e in entradas)
        regras.append(Conferencia(f"{nome} com um de {lista}", ok, "; ".join(entradas)[:200]))
    if em_alguma := espera.get("entrada_em_alguma") or {}:
        ok = any(
            str(t).lower() in e
            for n, trechos in em_alguma.items()
            for t in ([trechos] if isinstance(trechos, str) else trechos)
            for e in _entradas(rodada, n)
        )
        regras.append(Conferencia(f"uma de {sorted(em_alguma)} com o alvo certo", ok))
    for padrao in _lista(espera, "resposta"):
        ok = re.search(padrao, resposta, re.IGNORECASE) is not None
        regras.append(Conferencia(f"resposta tem /{padrao}/", ok))
    if alguma := _lista(espera, "resposta_alguma"):
        ok = any(re.search(p, resposta, re.IGNORECASE) for p in alguma)
        regras.append(Conferencia(f"resposta tem uma de {alguma}", ok))
    for padrao in _lista(espera, "resposta_nao"):
        ok = re.search(padrao, resposta, re.IGNORECASE) is None
        regras.append(Conferencia(f"resposta não tem /{padrao}/", ok))
    if espera.get("pergunta"):
        regras.append(Conferencia("pergunta de volta", "?" in resposta))
    if espera.get("voz", True):
        palavras = len(resposta.split())
        regras.append(Conferencia("sem Markdown", MARKDOWN.search(resposta) is None))
        regras.append(
            Conferencia(f"até {MAX_PALAVRAS} palavras", palavras <= MAX_PALAVRAS, f"{palavras}")
        )
    return regras


def nota(regras: list[Conferencia]) -> bool:
    return all(r.ok for r in regras)
