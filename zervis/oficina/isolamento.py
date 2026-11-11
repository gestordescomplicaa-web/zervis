"""O isolamento das sessões de código (plano de maturidade, Frente 2; ADR 0074).

Uma sessão protegida roda o agente dentro do bubblewrap (`bwrap`): o sistema fica visível só
para leitura, e a pasta pessoal é trocada por uma vazia. Dela voltam só:

- com escrita: a pasta do projeto, a da sessão no Zé (os eventos que o agente conta) e a de
  login da conta do agente;
- só para leitura: o que faz os programas rodarem (o `mise` e as instalações dele, o Claude Code,
  o `~/.local/bin`, o `~/.gitconfig`) e o Python do próprio Zé (um gancho usa).

Fora ficam o `~/.ssh`, o resto do `~/.config`, os dados do Zé e das outras sessões, as chaves, o
navegador, o `/run/user/<uid>` (D-Bus, chaveiro, ssh-agent) e os outros processos da máquina.
O ambiente do agente vai sem as variáveis de segredo do Zé (`agentes.sem_segredos`), protegida
ou não. A rede continua: o agente precisa da API do modelo, e o gancho de permissão fala com o
Zé por `127.0.0.1`.
Não é um contêiner: o processo é do mesmo usuário, só não enxerga o resto.
"""

import functools
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# O que da pasta pessoal o agente precisa para rodar (só leitura), relativo a ela.
DA_CASA = (
    ".local/bin",
    ".local/share/mise",
    ".local/share/claude",
    ".codex/packages",  # o Codex instalado pelo instalador dele (o ~/.local/bin/codex aponta aqui)
    ".local/share/uv/python",
    ".config/mise",
    ".config/git",
    ".gitconfig",
    ".npmrc",
)


@functools.cache
def disponivel() -> bool:
    """O bubblewrap existe e consegue criar o espaço isolado (alguns sistemas bloqueiam)."""
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        return False
    try:
        feito = subprocess.run(  # noqa: S603 (caminho resolvido, argumentos fixos)
            [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "true"],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return feito.returncode == 0


def _python_do_ze() -> list[Path]:
    """O ambiente do Zé e o Python de onde ele veio: um gancho da sessão roda `sys.executable`."""
    return [Path(sys.prefix), Path(sys.base_prefix)]


def envolver(
    comando: list[str],
    escrita: Iterable[Path],
    leitura: Iterable[Path] = (),
    casa: Path | None = None,
    pasta: Path | None = None,
    runtime: Path | None = None,
) -> list[str]:
    """O `comando` dentro do isolamento. Caminhos que não existem ficam de fora."""
    casa = casa or Path.home()
    args = [
        "bwrap",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--unshare-pid",  # só os processos da sessão: nem a lista nem os comandos dos outros
        "--proc", "/proc",
        "--tmpfs", "/tmp",  # noqa: S108 (um /tmp novo e vazio, só dentro do isolamento)
        "--tmpfs", str(casa),
    ]  # fmt: skip
    # O XDG_RUNTIME_DIR (/run/user/<uid>) guarda portas para fora do isolamento: o D-Bus
    # (chaveiro; `systemd-run --user` roda um comando lá fora), o ssh-agent e o gpg-agent.
    if runtime is None and (do_ambiente := os.environ.get("XDG_RUNTIME_DIR")):
        runtime = Path(do_ambiente)
    vistos: set[str] = set()
    # O que o isolamento troca por vazio: só o que mora aqui precisa voltar.
    escondidas = [casa.resolve(), Path("/tmp").resolve()]  # noqa: S108
    if runtime is not None and runtime.is_dir():
        args += ["--tmpfs", str(runtime.resolve())]
        escondidas.append(runtime.resolve())

    def escondido(caminho: Path) -> bool:
        return any(caminho.is_relative_to(raiz) for raiz in escondidas)

    def ligar(opcao: str, caminho: Path) -> None:
        if not caminho.exists():
            return
        # Monta sempre o caminho de verdade: no Arch, /usr/sbin é um link para bin, e o bwrap
        # não monta sobre um link ("Can't mount on symlink destination", 09/11/2026).
        real = caminho.resolve()
        if (opcao == "--bind" or escondido(real)) and str(real) not in vistos:
            vistos.add(str(real))  # o resto do sistema já está visível, só para leitura
            args.extend([opcao, str(real), str(real)])
        # Chegando por um link que mora na parte escondida (um ~/.gitconfig que aponta para
        # outro lugar), o mesmo link lá dentro.
        absoluto = caminho.absolute()
        if absoluto != real and escondido(absoluto) and str(absoluto) not in vistos:
            vistos.add(str(absoluto))
            args.extend(["--symlink", str(real), str(absoluto)])

    for relativo in DA_CASA:
        ligar("--ro-bind", casa / relativo)
    for caminho in [*leitura, *_python_do_ze()]:
        ligar("--ro-bind", caminho)
    for caminho in escrita:  # por último: valem por cima de uma leitura que as contenha
        vistos.discard(str(caminho.resolve()))
        ligar("--bind", caminho)
    args += ["--die-with-parent"]
    if pasta is not None:
        args += ["--chdir", str(pasta)]
    return [*args, "--", *comando]
