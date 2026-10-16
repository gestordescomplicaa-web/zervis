"""Os agentes que vêm com o Zé: o Claude Code e o Codex prontos, sem instalar nada à parte.

- **Claude Code:** o que vem dentro do `claude-agent-sdk` (a Anthropic distribui pelo PyPI, e o uv o
  instala como dependência; o cérebro e as sessões já usam ele).
- **Codex:** o binário oficial (github.com/openai/codex, Apache-2.0; ver THIRD_PARTY.md), versão
  fixa, baixado e conferido por SHA-256 na primeira subida, como o ai-memory.

O da máquina sempre tem a vez. Sem ele, o Zé põe a pasta do que trouxe no fim do PATH, e o painel,
o cérebro e as sessões passam a achar `claude` e `codex` (ADR 0035). Numa VPS nova, sem isso, os
dois apareciam como "Não instalado" e o Codex exigia o terminal.

    python -m jarvis.cerebro.agentes_nativos   # baixa o que falta; comandos em ~/.local/bin
"""

import logging
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from jarvis import lugares
from jarvis.preparar import Modelo, PrepararErro, baixar

log = logging.getLogger(__name__)

CODEX_VERSAO = "0.163.0"
_BASE = f"https://github.com/openai/codex/releases/download/rust-v{CODEX_VERSAO}"
CODEX_PACOTES = {
    "x86_64": Modelo(
        "codex-x86_64-unknown-linux-musl.tar.gz",
        f"{_BASE}/codex-x86_64-unknown-linux-musl.tar.gz",
        "beb339e8ecd9ba057a6bb2dc81ad8ca474812edfbf0fc5056ca818797648dde4",
        "Codex (OpenAI, Apache-2.0)",
    ),
    "aarch64": Modelo(
        "codex-aarch64-unknown-linux-musl.tar.gz",
        f"{_BASE}/codex-aarch64-unknown-linux-musl.tar.gz",
        "a7261e65f4a96d8f4ca65a069c6cf2dc2c33defc341e48078acefda9461fffe4",
        "Codex (OpenAI, Apache-2.0)",
    ),
}
CODEX_PASTA = lugares.DADOS / "codex" / CODEX_VERSAO
COMANDOS = Path("~/.local/bin").expanduser()  # onde o terminal acha os comandos do usuário


def claude_embutido() -> Path | None:
    """O Claude Code que vem no `claude-agent-sdk`, se o pacote o trouxe."""
    import claude_agent_sdk

    caminho = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    return caminho if caminho.is_file() else None


def codex_proprio(pasta: Path = CODEX_PASTA) -> Path | None:
    caminho = pasta / "codex"
    return caminho if caminho.is_file() else None


def garantir_codex(pasta: Path = CODEX_PASTA, abrir: Any = None) -> bool:
    """Baixa e confere o Codex se a máquina não tiver nenhum; True se baixou agora."""
    if shutil.which("codex") or codex_proprio(pasta):
        return False
    pacote = CODEX_PACOTES.get(platform.machine())
    if pacote is None:
        raise PrepararErro(f"sem Codex pronto para {platform.machine()}")
    baixar(pacote, pasta.parent, abrir or urllib.request.urlopen)
    arquivo = pasta.parent / pacote.nome
    try:
        with tarfile.open(arquivo) as tar:
            membros = [m for m in tar.getmembers() if m.isfile() and m.name.startswith("codex")]
            if len(membros) != 1:
                raise PrepararErro(f"{pacote.nome}: esperava um binário, achei {len(membros)}")
            tar.extractall(pasta, members=membros, filter="data")  # nada fora da pasta
        (pasta / membros[0].name).replace(pasta / "codex")
    finally:
        arquivo.unlink(missing_ok=True)
    (pasta / "codex").chmod(0o755)
    return True


def no_path(ambiente: MutableMapping[str, str] = os.environ) -> list[str]:
    """Põe no fim do PATH a pasta do agente que o Zé trouxe, para os que faltam na máquina."""
    caminho = ambiente.get("PATH", "")
    pastas = [p for p in caminho.split(":") if p]
    novas = []
    for nome, proprio in (("claude", claude_embutido()), ("codex", codex_proprio())):
        if proprio is None or shutil.which(nome, path=caminho):
            continue
        if str(proprio.parent) not in pastas and str(proprio.parent) not in novas:
            novas.append(str(proprio.parent))
    if novas:
        ambiente["PATH"] = ":".join([*pastas, *novas])
        log.info("agentes que vêm com o Zé no PATH: %s", ", ".join(novas))
    return novas


def criar_comandos(destino: Path = COMANDOS) -> list[str]:
    """Cria `claude` e `codex` em ~/.local/bin, para o terminal, quando a máquina não tem."""
    criados = []
    for nome, proprio in (("claude", claude_embutido()), ("codex", codex_proprio())):
        alvo = destino / nome
        if proprio is None or shutil.which(nome) or alvo.exists():
            continue
        destino.mkdir(parents=True, exist_ok=True)
        alvo.symlink_to(proprio)
        criados.append(nome)
    return criados


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if garantir_codex():
            print(f"Codex {CODEX_VERSAO} baixado e conferido.")
    except (OSError, PrepararErro) as erro:
        print(f"Codex não baixou: {erro}", file=sys.stderr)
    if criados := criar_comandos():
        print(f"Comandos criados em ~/.local/bin: {', '.join(criados)}")
    for nome in ("claude", "codex"):
        achado = shutil.which(nome) or {"claude": claude_embutido(), "codex": codex_proprio()}[nome]
        print(f"{nome:7} {achado or 'indisponível'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
