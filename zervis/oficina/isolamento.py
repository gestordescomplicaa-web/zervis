"""O isolamento das sessões de código (plano de maturidade, Frente 2; ADR 0074).

Uma sessão protegida roda o agente dentro do bubblewrap (`bwrap`): o sistema fica visível só
para leitura, e a pasta pessoal é trocada por uma vazia. Dela voltam só:

- com escrita: a pasta do projeto, a da sessão no Zé (os eventos que o agente conta) e a de
  login da conta do agente;
- só para leitura: o que faz os programas rodarem (o `mise` e as instalações dele, o Claude Code,
  o `~/.local/bin`, o `~/.gitconfig`) e o Python do próprio Zé (um gancho usa).

Fora ficam o `~/.ssh`, o resto do `~/.config`, os dados do Zé e das outras sessões, as chaves e o
navegador. A rede continua: o agente precisa da API do modelo, e o gancho de permissão fala com
o Zé por `127.0.0.1`. Não é um contêiner: o processo é do mesmo usuário, só não enxerga o resto.
"""

import functools
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
) -> list[str]:
    """O `comando` dentro do isolamento. Caminhos que não existem ficam de fora."""
    casa = casa or Path.home()
    args = [
        "bwrap",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",  # noqa: S108 (um /tmp novo e vazio, só dentro do isolamento)
        "--tmpfs", str(casa),
    ]  # fmt: skip
    vistos: set[str] = set()

    def ligar(opcao: str, caminho: Path) -> None:
        if str(caminho) in vistos or not caminho.exists():
            return
        vistos.add(str(caminho))
        args.extend([opcao, str(caminho), str(caminho)])

    for relativo in DA_CASA:
        ligar("--ro-bind", casa / relativo)
    for caminho in [*leitura, *_python_do_ze()]:
        ligar("--ro-bind", caminho)
    for caminho in escrita:  # por último: valem por cima de uma leitura que as contenha
        vistos.discard(str(caminho))
        ligar("--bind", caminho)
    args += ["--die-with-parent"]
    if pasta is not None:
        args += ["--chdir", str(pasta)]
    return [*args, "--", *comando]
