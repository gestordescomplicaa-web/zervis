"""Onde o Zé procura os programas de quem usa (`codex`, `claude`, `ai-memory`, `cloudflared`).

O systemd sobe o serviço do usuário com um PATH mínimo (`/usr/local/bin:/usr/bin`), e no boot ele
pode subir antes de a sessão gráfica carregar o ambiente da pessoa. Os agentes costumam ficar em
pastas pessoais (`~/.local/bin`, mise, npm, bun, volta, cargo): sem elas no PATH, o Zé dizia que o
Codex não estava instalado (teste de 13/10/2026, depois de reiniciar o computador).

Na subida, o Zé completa o PATH com o do shell de login da pessoa e com essas pastas conhecidas,
na ordem: o que já havia, o shell, as pastas. O PATH completo vale para o próprio Zé e passa
adiante para os agentes, as sessões e os hooks.
"""

import logging
import os
import pwd
import shutil
import subprocess
from collections.abc import MutableMapping
from pathlib import Path

log = logging.getLogger(__name__)

PASTAS = (
    "~/.local/bin",
    "~/bin",
    "~/.local/share/mise/shims",
    "~/.asdf/shims",
    "~/.npm-global/bin",
    "~/.local/share/pnpm",
    "~/.bun/bin",
    "~/.volta/bin",
    "~/.cargo/bin",
    "~/.deno/bin",
    "~/go/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/snap/bin",
)


def do_shell(shell: str = "", espera_s: float = 3.0) -> list[str]:
    """O PATH que o shell de login da pessoa monta (vazio se não der em `espera_s`)."""
    shell = shell or os.environ.get("SHELL") or pwd.getpwuid(os.getuid()).pw_shell
    if not shell or not Path(shell).is_file():
        return []
    comando = "string join : $PATH" if shell.endswith("fish") else 'printf "%s" "$PATH"'
    try:
        r = subprocess.run(  # noqa: S603 (o shell da própria pessoa, comando fixo)
            [shell, "-lc", comando],
            capture_output=True,
            text=True,
            timeout=espera_s,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    linhas = r.stdout.strip().splitlines()
    return [p for p in (linhas[-1] if linhas else "").split(":") if p]


def completar(
    ambiente: MutableMapping[str, str] = os.environ,
    do_login: list[str] | None = None,
    pastas: tuple[str, ...] = PASTAS,
) -> list[str]:
    """Completa o PATH de `ambiente`; devolve as pastas acrescentadas."""
    atual = [p for p in ambiente.get("PATH", "").split(":") if p]
    candidatas = [
        *(do_shell() if do_login is None else do_login),
        *(os.path.expanduser(p) for p in pastas),
    ]
    novas: list[str] = []
    for pasta in candidatas:
        if pasta not in atual and pasta not in novas and Path(pasta).is_dir():
            novas.append(pasta)
    ambiente["PATH"] = ":".join([*atual, *novas])
    if novas:
        log.info("PATH completado com %d pastas (%s)", len(novas), ", ".join(novas[:4]))
    return novas


def claude() -> str:
    """O `claude` das sessões de código: o da pessoa, se houver no PATH; senão o Claude Code que
    vem com o `claude-agent-sdk`. Numa VPS nova ele é o único, e criar uma sessão falhava com
    FileNotFoundError (lição de 16/10/2026)."""
    if shutil.which("claude"):
        return "claude"
    import claude_agent_sdk

    embutido = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    return str(embutido) if embutido.is_file() else "claude"
