"""Os cérebros que o usuário escolhe por voz ou no Barehands (ADR 0010).

Claude usa o Agent SDK; Codex usa o app-server oficial; as rotas do OmniRoute usam o SDK
(ADR 0008). A escolha vale até a próxima troca, inclusive depois de reiniciar.
"""

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from jarvis.cerebro import contas, omniroute
from jarvis.cerebro.base import Brain
from jarvis.cerebro.claude import ClaudeBrain
from jarvis.cerebro.codex import CodexBrain
from jarvis.cerebro.eco import Eco
from jarvis.cerebro.reserva import ComReserva
from jarvis.config import Config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Opcao:
    id: str
    nome: str  # falado e mostrado no Barehands
    familia: str | None  # de qual bateria ele gasta (None: o OmniRoute decide)
    rota: str | None  # rota do OmniRoute; None = Claude pela assinatura


OPCOES = {
    "claude": Opcao("claude", "Claude", "claude", None),
    "codex": Opcao("codex", "Codex", "gpt", None),
    "gpt": Opcao("gpt", "GPT", "gpt", "cx/gpt-6-luna"),
    "gemini": Opcao("gemini", "Gemini", "gemini", "agy/gemini-3.1-pro-high"),
    "auto": Opcao("auto", "Automático", None, ""),  # rota da config (omniroute_rota)
}


class Indisponivel(RuntimeError):
    """O cérebro pedido não pode ser montado agora; a mensagem é falável."""


SEM_ESFORCO = {"high", "medium", "low", "xhigh", "max", "thinking"}


def rotulo(modelo: str) -> str:
    """Nome legível de um modelo: "cx/gpt-6-luna" -> "GPT-6 Luna", "claude-sonnet-5-5" ->
    "Sonnet 5.5", "agy/gemini-3.1-pro-high" -> "Gemini 3.1 Pro"."""
    partes = [
        p
        for p in modelo.rsplit("/", 1)[-1].split("-")
        if p and p not in SEM_ESFORCO and not (len(p) == 8 and p.isdigit())  # data da versão
    ]
    if partes[:1] == ["claude"]:
        partes = partes[1:]
    if partes[:1] == ["gpt"] and len(partes) > 1:
        partes = [f"GPT-{partes[1]}", *partes[2:]]
    palavras: list[str] = []
    for p in partes:
        if p.isdigit() and palavras and palavras[-1][-1:].isdigit():
            palavras[-1] += f".{p}"  # "5-5" vira "5.5"
        else:
            palavras.append(p if p[:1].isdigit() or p.startswith("GPT") else p.capitalize())
    return " ".join(palavras) or modelo


def inicial(cfg: Config) -> str:
    """O cérebro da config: `provedor = "omniroute"` é o automático."""
    return {"claude": "claude", "codex": "codex", "omniroute": "auto"}.get(
        cfg["cerebro"]["provedor"], "eco"
    )


@dataclass(frozen=True)
class Extras:
    """Ferramentas MCP do JARVIS, iguais em todo cérebro."""

    mcp: dict[str, Any] = field(default_factory=dict)
    livres: tuple[str, ...] = ()
    bloqueadas: tuple[str, ...] = ()  # ferramentas MCP que o cérebro nem vê (mcp.toml)
    foto: Callable[[], str] | None = None
    prechecar: Callable[[str, dict[str, Any]], str | None] | None = None
    mostrar: Callable[[str, dict[str, Any]], None] | None = None
    descrever_extra: Callable[[str, dict[str, Any]], str | None] | None = None
    autoaprovar: Callable[[str, dict[str, Any]], bool] | None = None
    frase_exata: Callable[[str, dict[str, Any]], str | None] | None = None
    depois: Callable[[str, Any], Any | None] | None = None


def criar(
    id_: str,
    cfg: Config,
    pasta: Path,
    extras: Extras | None = None,
    conta: contas.Conta | None = None,
) -> ClaudeBrain:
    c = cfg["cerebro"]
    opcao = OPCOES[id_]
    ferramentas = list(c["ferramentas"])
    x = extras or Extras()
    comum: dict[str, Any] = {
        "tempo_limite_s": c["tempo_limite_s"],
        "mcp": x.mcp,
        "livres": list(x.livres),
        "bloqueadas": list(x.bloqueadas),
        "foto": x.foto,
        "prechecar": x.prechecar,
        "mostrar": x.mostrar,
        "descrever_extra": x.descrever_extra,
        "autoaprovar": x.autoaprovar,
        "frase_exata": x.frase_exata,
        "depois": x.depois,
    }
    if opcao.rota is None:
        if id_ == "codex":
            if shutil.which("codex") is None:
                raise Indisponivel("Codex não está instalado")
            return CodexBrain(c["modelo_codex"], [], pasta / "codex", conta=conta, **comum)
        conta = conta or contas.Contas().em_uso("claude")
        return ClaudeBrain(
            c["modelo"],
            ferramentas,
            pasta,
            env={"CLAUDE_CONFIG_DIR": str(conta.onde)},
            **comum,
        )
    chave = omniroute.ler_chave(cfg.caminho("cerebro", "omniroute_arquivo_chave"))
    if chave is None:
        raise Indisponivel("não achei a chave do OmniRoute")
    if not omniroute.no_ar(c["omniroute_endereco"]):
        raise Indisponivel("o OmniRoute está fora do ar")
    rota = opcao.rota or c["omniroute_rota"]
    return ClaudeBrain(
        rota,
        ferramentas,
        pasta,
        env=omniroute.ambiente(c["omniroute_endereco"], chave, rota),
        assinatura=False,
        **comum,
    )


def ler_escolha(arquivo: Path) -> str | None:
    try:
        escolha = arquivo.read_text().strip()
    except OSError:
        return None
    return escolha if escolha in OPCOES else None


def gravar_escolha(arquivo: Path, id_: str) -> None:
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(id_ + "\n")
    temporario.replace(arquivo)


def montar(
    cfg: Config, pasta: Path, escolha: str | None, extras: Extras | None = None
) -> tuple[Brain, str]:
    """O cérebro ao subir: a última escolha, senão a config; indisponível, a reserva."""
    id_ = escolha or inicial(cfg)
    if id_ == "eco":
        return Eco(), "eco"
    try:
        return com_reserva(id_, cfg, pasta, extras), id_
    except Indisponivel as motivo:
        reserva = cfg["cerebro"]["reserva"]
        log.warning("%s: %s; usando a reserva %s", id_, motivo, reserva)
        if reserva == "eco":
            return Eco(), "eco"
        return com_reserva(reserva, cfg, pasta, extras), reserva


def com_reserva(id_: str, cfg: Config, pasta: Path, extras: Extras | None = None) -> Brain:
    cerebro = criar(id_, cfg, pasta, extras)
    cs = contas.Contas()
    alternativas: list[tuple[str, Callable[[], Brain]]] = []
    for agente in ("codex", "claude") if id_ == "claude" else ("claude", "codex"):
        if shutil.which(agente) is None:
            continue
        atual = cs.em_uso(agente)
        candidatas = sorted(cs.listar(agente), key=lambda c: c.id != atual.id)
        for conta in candidatas:
            if not conta.login.is_file() or (agente == id_ and conta.id == atual.id):
                continue
            alternativas.append((conta.id, partial(criar, agente, cfg, pasta, extras, conta)))
    return ComReserva(cerebro, alternativas) if alternativas else cerebro
