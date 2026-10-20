# SPDX-License-Identifier: AGPL-3.0-or-later
"""barehands-jarvis: the hands calibration profile and the camera's light.

Two jobs, both with the original kept as the way back:

- The calibrated hand profile lives in state/maos-perfil.json. The default
  profile lives in the page code and is never written, so deleting the file
  (or any invalid value) brings the default back. Each save keeps the
  previous profile in state/maos-perfil.anterior.json.
- The camera's own controls (gain, exposure, brightness...) are changed
  through v4l2-ctl, the first time saving every original value in
  state/camera-original.json. That file is never overwritten. Restoring
  puts those values back; so does a watchdog when the tracker page stops.
"""

import json
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

Json = dict[str, Any]

# The page validates the same bounds; out of range means "use the default".
LIMITES = {
    "pincaFrontal": (0.22, 0.40),
    "pincaPerfil": (0.30, 0.42),
    "contraste": (0.08, 0.28),
    "arco": (1.15, 1.40),
    "soltar": (0.45, 0.65),
    "soltarRapido": (0.60, 0.85),
    "tremor": (12, 48),
    "fantasma": (700, 1800),
    "toqueMs": (300, 900),
    "toque3": (0, 0.40),  # 0 = off (original): no 3D touch requirement
}
# Only image controls. Focus, zoom and power-line stay with the camera.
CONTROLES = (
    "brightness",
    "contrast",
    "saturation",
    "gamma",
    "gain",
    "sharpness",
    "backlight_compensation",
    "auto_exposure",
    "exposure_time_absolute",
)


def _escrever(arquivo: Path, dados: Any) -> None:
    tmp = arquivo.with_suffix(".next")
    tmp.write_text(json.dumps(dados, ensure_ascii=False))
    tmp.replace(arquivo)


def perfil_valido(p: Any) -> bool:
    if not isinstance(p, dict) or set(p) - set(LIMITES) - {"versao"}:
        return False
    p = {"toque3": 0, **p}  # profiles saved before the 3D touch existed
    for chave, (a, b) in LIMITES.items():
        v = p.get(chave)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not a <= v <= b:
            return False
    return bool(p["soltar"] >= max(p["pincaFrontal"], p["pincaPerfil"]) + 0.08)


class Perfil:
    def __init__(self, pasta: Path) -> None:
        self.arquivo = Path(pasta) / "maos-perfil.json"
        self.anterior = Path(pasta) / "maos-perfil.anterior.json"

    def ler(self) -> Json:
        try:
            d = json.loads(self.arquivo.read_text())
            if perfil_valido(d.get("perfil")):
                return dict(d)
        except (OSError, ValueError, AttributeError):
            pass
        return {"perfil": None, "origem": "padrao"}

    def gravar(self, perfil: Any, origem: Any, resumo: Any = None) -> None:
        if origem not in ("calibrado", "ajustado") or not perfil_valido(perfil):
            raise ValueError("perfil inválido")
        if self.arquivo.exists():
            shutil.copyfile(self.arquivo, self.anterior)
        _escrever(
            self.arquivo,
            {
                "perfil": perfil,
                "origem": origem,
                "resumo": resumo if isinstance(resumo, dict) else {},
                "ts": time.time(),
            },
        )

    def padrao(self) -> None:
        if self.arquivo.exists():
            shutil.copyfile(self.arquivo, self.anterior)
            self.arquivo.unlink()


def ler_controles(texto: str) -> dict[str, dict[str, int]]:
    """`v4l2-ctl -l` output -> {name: {valor, min, max, padrao}}."""
    out: dict[str, dict[str, int]] = {}
    for linha in texto.splitlines():
        m = re.match(r"\s*(\w+) 0x[0-9a-f]+ \((int|menu|bool)\)\s*:(.*)", linha)
        if not m:
            continue
        campos: dict[str, str] = dict(re.findall(r"(\w+)=(-?\d+)", m.group(3)))
        if "value" not in campos:
            continue
        lo, hi = (
            (0, 1)
            if m.group(2) == "bool"
            else (int(campos.get("min", 0)), int(campos.get("max", 0)))
        )
        out[m.group(1)] = {
            "valor": int(campos["value"]),
            "min": lo,
            "max": hi,
            "padrao": int(campos.get("default", campos["value"])),
        }
    return out


def dispositivo_por_nome(
    nome: str | None, raiz: Path = Path("/sys/class/video4linux")
) -> tuple[str | None, str | None]:
    """Chromium labels a camera "<V4L2 name> (<usb id>)": match the capture node."""
    nome = (nome or "").strip()
    achados: list[tuple[str | None, str | None]] = []
    for d in sorted(raiz.glob("video*"), key=lambda p: int(p.name[5:] or 0)):
        try:
            n = (d / "name").read_text().strip()
            indice = int((d / "index").read_text().strip() or 0)
        except (OSError, ValueError):
            continue
        if n and nome and (nome.startswith(n) or n.startswith(nome.split(" (")[0])) and indice == 0:
            achados.append(("/dev/" + d.name, n))
    return achados[0] if achados else (None, None)


class Camera:
    """The camera's controls with a write-once backup of the originals."""

    def __init__(
        self,
        pasta: Path,
        executar: Callable[[list[str]], str] | None = None,
        v4l2: str | None = None,
    ) -> None:
        self.backup = Path(pasta) / "camera-original.json"
        self.v4l2 = v4l2 or shutil.which("v4l2-ctl")
        self.executar = executar or (
            lambda args: (
                subprocess.run(  # noqa: S603 (fixed binary)
                    args, capture_output=True, text=True, timeout=3, check=False
                ).stdout
            )
        )
        self.trava = threading.Lock()
        self.alterada: dict[str, str | None] = {}  # device -> values we set (for the watchdog)
        self.batimento = time.time()

    def info(self, nome: str) -> Json:
        disp, n = dispositivo_por_nome(nome)
        if not self.v4l2 or not disp:
            return {"disponivel": False}
        ctl = {
            k: v
            for k, v in ler_controles(self.executar([self.v4l2, "-d", disp, "-l"])).items()
            if k in CONTROLES
        }
        return {
            "disponivel": bool(ctl),
            "nome": n,
            "controles": ctl,
            "original": n in self._backups(),
            "alterada": disp in self.alterada,
        }

    def _backups(self) -> Json:
        try:
            return dict(json.loads(self.backup.read_text()))
        except (OSError, ValueError):
            return {}

    def _aplicar(self, disp: str, valores: dict[str, Any]) -> None:
        # Manual exposure must be selected before its time can be set.
        if not self.v4l2:
            return
        ordem = sorted(valores, key=lambda k: k != "auto_exposure")
        for k in ordem:
            self.executar([self.v4l2, "-d", disp, "-c", f"{k}={valores[k]}"])

    def ajustar(self, nome: str, valores: Any) -> Json:
        disp, n = dispositivo_por_nome(nome)
        if not self.v4l2 or not disp or not isinstance(valores, dict):
            raise ValueError("câmera indisponível")
        n = n or ""
        with self.trava:
            ctl = ler_controles(self.executar([self.v4l2, "-d", disp, "-l"]))
            pedido: dict[str, int] = {}
            for k, v in valores.items():
                if (
                    k not in CONTROLES
                    or k not in ctl
                    or isinstance(v, bool)
                    or not isinstance(v, int)
                ):
                    raise ValueError(f"controle recusado: {k}")
                if not ctl[k]["min"] <= v <= ctl[k]["max"]:
                    raise ValueError(f"fora da faixa: {k}")
                pedido[k] = v
            backups = self._backups()
            if n not in backups:  # the first touch saves every original, once
                backups[n] = {k: c["valor"] for k, c in ctl.items() if k in CONTROLES}
                _escrever(self.backup, backups)
            mudar = {k: v for k, v in pedido.items() if ctl[k]["valor"] != v}
            if mudar:
                self._aplicar(disp, mudar)
            self.alterada[disp] = n
        return {"aplicado": mudar}

    def restaurar(self, nome: str | None = None) -> Json:
        backups = self._backups()
        with self.trava:
            alvos = list(self.alterada.items())
            if nome:
                disp, n = dispositivo_por_nome(nome)
                alvos = [(disp, n)] if disp else []
            for disp, n in alvos:
                if n in backups and self.v4l2:
                    self._aplicar(disp, backups[n])
                self.alterada.pop(disp, None)
        return {"restaurado": [n for _, n in alvos if n in backups]}

    def vigiar(self, sem_batimento_s: float = 20) -> None:
        """A closed or frozen tracker page must not leave the camera tuned."""

        def laco() -> None:
            while True:
                time.sleep(5)
                if self.alterada and time.time() - self.batimento > sem_batimento_s:
                    self.restaurar()

        threading.Thread(target=laco, daemon=True).start()
