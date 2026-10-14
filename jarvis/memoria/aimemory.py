"""O ai-memory embutido no Zé: a memória longa comum a todos os agentes (ADR 0016).

O ai-memory (akitaonrails/ai-memory, MIT; ver THIRD_PARTY.md) guarda as sessões do Claude e do
Codex num wiki pesquisável e leva de uma sessão para a outra o que importa. O Zé:

- usa o ai-memory da máquina, se houver (instalado ou já rodando);
- senão, baixa o binário oficial na versão fixada abaixo, confere o SHA-256 e o roda como
  processo filho (`serve --transport http`);
- liga os hooks dele nas sessões de código do Zé (`hooks_claude`), sem mexer nas configurações
  globais de quem usa: o que as sessões fazem entra na memória.

Os dados ficam onde o ai-memory guarda por padrão (`~/.local/share/ai-memory`, ou
`AI_MEMORY_DATA_DIR`): a mesma memória das sessões que a pessoa abre fora do Zé. Sem o ai-memory,
o Zé funciona sem memória longa.
"""

import logging
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

from jarvis import lugares
from jarvis.filho import Filho
from jarvis.preparar import Modelo, PrepararErro, baixar

log = logging.getLogger(__name__)

VERSAO = "2.6.3"
_BASE = f"https://github.com/akitaonrails/ai-memory/releases/download/v{VERSAO}"
PACOTES = {
    "x86_64": Modelo(
        "ai-memory-linux-x86_64.tar.gz",
        f"{_BASE}/ai-memory-linux-x86_64.tar.gz",
        "933be9bb8fe6930336933f0b8adf0695007e644f945898f9f030fd312326f0f3",
        "memória longa (ai-memory, MIT)",
    ),
    "aarch64": Modelo(
        "ai-memory-linux-aarch64.tar.gz",
        f"{_BASE}/ai-memory-linux-aarch64.tar.gz",
        "e4e01409fe80148a4d561aef98ac5d526c488c4a621faa759f9d0b3ed2606088",
        "memória longa (ai-memory, MIT)",
    ),
}
PASTA = lugares.DADOS / "ai-memory" / VERSAO  # o binário que o Zé trouxe, com os hooks
DADOS = Path(
    os.environ.get("AI_MEMORY_DATA_DIR") or Path.home() / ".local/share/ai-memory"
).expanduser()
URL = os.environ.get("AI_MEMORY_SERVER_URL") or "http://127.0.0.1:49374"
# Evento do Claude Code -> evento do ai-memory (o mapa do `install-hooks --agent claude-code`).
EVENTOS_CLAUDE = {
    "SessionStart": "session-start",
    "UserPromptSubmit": "user-prompt-submit",
    "PreToolUse": "pre-tool-use",
    "PostToolUse": "post-tool-use",
    "PreCompact": "pre-compact",
    "Stop": "stop",
    "SessionEnd": "session-end",
}


def binario(pasta: Path = PASTA) -> Path | None:
    """O ai-memory da máquina, senão o que o Zé baixou; None se não houver nenhum."""
    if achado := shutil.which("ai-memory"):
        return Path(achado)
    proprio = pasta / "ai-memory"
    return proprio if proprio.is_file() else None


def comando(*args: str, dados: Path | None = None) -> list[str]:
    """Leitura e publicação usam o mesmo binário e a mesma raiz da memória longa."""
    return [str(binario() or "ai-memory"), "--data-dir", str(dados or DADOS), *args]


def garantir(pasta: Path = PASTA, abrir: Any = urllib.request.urlopen) -> bool:
    """Baixa e extrai o ai-memory se a máquina não tiver; True se baixou agora."""
    if binario(pasta) is not None:
        return False
    pacote = PACOTES.get(platform.machine())
    if pacote is None:
        raise PrepararErro(f"sem ai-memory pronto para {platform.machine()}")
    baixar(pacote, pasta.parent, abrir)
    arquivo = pasta.parent / pacote.nome
    try:
        with tarfile.open(arquivo) as tar:
            tar.extractall(pasta, filter="data")  # nada fora da pasta, sem links perigosos
    finally:
        arquivo.unlink(missing_ok=True)
    (pasta / "ai-memory").chmod(0o755)
    return True


def no_ar(url: str = URL, abrir: Any = urllib.request.urlopen) -> bool:
    try:
        with abrir(f"{url}/healthz", timeout=2) as resp:
            return bool(resp.status == 200)
    except OSError:
        return False


def _porta(url: str) -> str:
    return url.rsplit(":", 1)[-1].split("/")[0]


class AiMemory:
    """O servidor do ai-memory: o da máquina, se já estiver no ar, ou um filho do Zé."""

    def __init__(self, url: str = URL, dados: Path = DADOS) -> None:
        self.url = url
        self.dados = dados
        self.filho: Filho | None = None

    def iniciar(self) -> None:
        if no_ar(self.url):
            log.info("ai-memory: usando o servidor da máquina em %s", self.url)
            return
        bin_ = binario()
        if bin_ is None:
            log.warning("ai-memory ausente: o Zé segue sem memória longa")
            return
        if not (self.dados / "db").is_dir():
            subprocess.run(  # noqa: S603 (o binário resolvido acima)
                [str(bin_), "--data-dir", str(self.dados), "init"],
                capture_output=True,
                timeout=60,
                check=False,
            )
        self.filho = Filho(
            "ai-memory",
            [
                str(bin_),
                "--data-dir",
                str(self.dados),
                "serve",
                "--transport",
                "http",
                "--bind",
                f"127.0.0.1:{_porta(self.url)}",
            ],
            {},
        )
        self.filho.iniciar()

    def parar(self) -> None:
        if self.filho is not None:
            self.filho.parar()


def situacao(url: str = URL, dados: Path = DADOS) -> dict[str, Any]:
    """Para a página Memória: se a memória dos projetos está no ar e quantas páginas guarda
    (lido só para contar, sem mexer no banco do ai-memory)."""
    import sqlite3

    paginas = None
    banco = dados / "db" / "memory.sqlite"
    if banco.is_file():
        try:
            with sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=1) as con:
                paginas = int(
                    con.execute("select count(*) from pages where is_latest").fetchone()[0]
                )
        except sqlite3.Error:
            paginas = None
    return {"ativa": no_ar(url), "paginas": paginas}


def hooks_claude(url: str = URL, dados: Path = DADOS) -> dict[str, Any]:
    """As configurações que ligam o ai-memory numa sessão do Claude (o `settings` do Agent SDK);
    vazio sem o ai-memory no ar, e a sessão segue sem memória longa."""
    bin_ = binario()
    if bin_ is None or not no_ar(url):
        return {}
    base = f'"{bin_}" --data-dir "{dados}" hook --agent claude-code --server-url {url}'
    return {
        "hooks": {
            evento: [
                {"matcher": "", "hooks": [{"type": "command", "command": f"{base} --event {e}"}]}
            ]
            for evento, e in EVENTOS_CLAUDE.items()
        }
    }
