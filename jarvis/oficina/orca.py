"""Cliente fino da CLI oficial do Orca (portado de VIBE-CODING/jarvis/orca.py, 06/10/2026).

Atalho de velocidade herdado: o node do Orca em execução roda o `cli/index.js` em ~0,14 s, contra
~1,2 s do AppImage. O caminho muda a cada atualização do Orca, então é achado no processo vivo e
nunca fixado; se falhar, cai no `orca-ide` oficial (nunca no `orca` do PATH, que no Linux é o
leitor de tela do GNOME).

O ambiente é limpo das variáveis `ORCA_*`: o `jarvisd` é o coordenador e não pode se passar pelo
terminal de onde uma prova foi rodada.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CLI = Path.home() / ".local/bin/orca-ide"


class OrcaErro(RuntimeError):
    """A mensagem é falável e não traz dados internos."""


def _rapido() -> list[str] | None:
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            exe = Path(os.readlink(proc / "exe"))
        except OSError:
            continue
        entrada = exe.parent / "resources/app.asar.unpacked/out/cli/index.js"
        if exe.name == "orca-ide" and entrada.is_file():
            return [str(exe), str(entrada)]
    return None


def _ambiente(rapido: bool) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ORCA_")}
    if rapido:
        env["ELECTRON_RUN_AS_NODE"] = "1"
    else:
        env.pop("ELECTRON_RUN_AS_NODE", None)
    return env


class Orca:
    def __init__(self) -> None:
        self._rapido: list[str] | None = None
        self._procurado = False

    def _rodar(self, comando: list[str], args: list[str], rapido: bool, limite_s: float) -> Any:
        try:
            p = subprocess.run(  # noqa: S603 (binário do Orca, argumentos em lista)
                [*comando, *args, "--json"],
                env=_ambiente(rapido),
                capture_output=True,
                text=True,
                timeout=limite_s,
                cwd=Path.home(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        try:
            return json.loads(p.stdout)
        except ValueError:
            return None

    def chamar(self, *args: str, limite_s: float = 30) -> dict[str, Any]:
        """O `result` do pacote JSON; `OrcaErro` se o Orca não respondeu ou recusou."""
        if not self._procurado:
            self._rapido, self._procurado = _rapido(), True
        pacote = None
        if self._rapido and Path(self._rapido[0]).exists():
            pacote = self._rodar(self._rapido, list(args), True, limite_s)
        if pacote is None:
            self._procurado = False  # Orca reiniciado ou atualizado: procura de novo na próxima
            pacote = self._rodar([str(CLI)], list(args), False, limite_s)
        if pacote is None:
            raise OrcaErro("o Orca não respondeu")
        if not pacote.get("ok"):
            erro = pacote.get("error") or {}
            log.info("orca %s recusou: %s", " ".join(args[:2]), json.dumps(erro)[:500])
            raise OrcaErro(
                str(erro.get("message") or erro.get("code") or "o Orca recusou o pedido")
            )
        resultado = pacote.get("result")
        return resultado if isinstance(resultado, dict) else {}
