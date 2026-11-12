"""Fatiar pelo Bambu Studio em linha de comando (ADR 0083): o STL vira um 3MF com o G-code,
para a impressora, e o tempo e o filamento previstos, para o Zé dizer antes de imprimir.

O Bambu Studio é o da máquina (o pacote do sistema ou o Flatpak `com.bambulab.BambuStudio`), com
os perfis que vêm com ele. A linha de comando não aceita perfil que herda de outro: o Zé junta a
cadeia de `inherits` num perfil completo. Tudo roda numa pasta de trabalho do projeto, que é
também a pasta corrente: o Bambu Studio grava um `result.json` onde estiver.
"""

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FLATPAK = "com.bambulab.BambuStudio"
PRAZO_S = 300.0
# O perfil do Bambu Studio de cada modelo e o sufixo dos perfis de processo e de filamento.
MAQUINAS = {
    "A1": ("Bambu Lab A1 0.4 nozzle", "A1"),
    "A1 mini": ("Bambu Lab A1 mini 0.4 nozzle", "A1M"),
    "P1P": ("Bambu Lab P1P 0.4 nozzle", "P1P"),
    "P1S": ("Bambu Lab P1S 0.4 nozzle", "P1P"),
    "X1 Carbon": ("Bambu Lab X1 Carbon 0.4 nozzle", "X1C"),
}
PROCESSO = "0.20mm Standard @BBL {sufixo}"

Rodar = Callable[..., subprocess.CompletedProcess[str]]


class FatiadorErro(RuntimeError):
    """O que impede de fatiar (o texto vai para a tela e para a voz)."""


@dataclass(frozen=True)
class BambuStudio:
    comando: tuple[str, ...]  # o executável (ou o `flatpak run`), sem os argumentos
    perfis: Path  # .../profiles/BBL
    flatpak: bool


def encontrar(rodar: Rodar = subprocess.run) -> BambuStudio | None:
    for nome in ("bambu-studio", "BambuStudio"):
        if caminho := shutil.which(nome):
            for base in (Path(caminho).resolve().parent.parent, Path("/usr"), Path("/opt")):
                perfis = base / "share" / "BambuStudio" / "profiles" / "BBL"
                if perfis.is_dir():
                    return BambuStudio((caminho,), perfis, False)
    if shutil.which("flatpak"):
        onde = rodar(
            ["flatpak", "info", "--show-location", FLATPAK],
            capture_output=True, text=True, timeout=20, check=False,
        )  # fmt: skip
        perfis = Path(onde.stdout.strip()) / "files" / "share" / "BambuStudio" / "profiles" / "BBL"
        if onde.returncode == 0 and perfis.is_dir():
            return BambuStudio(("flatpak", "run", FLATPAK), perfis, True)
    return None


def _perfis(pasta: Path) -> dict[str, dict[str, Any]]:
    achados: dict[str, dict[str, Any]] = {}
    for arquivo in pasta.glob("*.json"):
        try:
            dados = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(dados, dict) and dados.get("name"):
            achados[str(dados["name"])] = dados
    return achados


def completo(nome: str, perfis: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """O perfil com tudo o que herda, do mais geral para o mais específico."""
    cadeia: list[dict[str, Any]] = []
    while nome:
        if nome not in perfis or len(cadeia) > 20:
            raise FatiadorErro(f"Perfil não encontrado: {nome}.")
        cadeia.append(perfis[nome])
        nome = str(perfis[nome].get("inherits") or "")
    tudo: dict[str, Any] = {}
    for parte in reversed(cadeia):
        tudo.update(parte)
    tudo.pop("inherits", None)
    return tudo


def filamento(sufixo: str, tipo: str, marca: str, nomes: set[str]) -> str:
    """O perfil de filamento para o que está na bandeja: o da marca, senão o genérico do tipo."""
    for candidato in (
        f"Bambu {marca} @BBL {sufixo}" if marca else "",
        f"Generic {tipo} @BBL {sufixo}" if tipo else "",
        f"Bambu PLA Basic @BBL {sufixo}",
    ):
        if candidato in nomes:
            return candidato
    raise FatiadorErro("Nenhum perfil de filamento para esta impressora.")


@dataclass(frozen=True)
class Fatiado:
    arquivo: Path  # o 3MF com o G-code
    minutos: int
    gramas: float
    filamento: str

    def para_json(self) -> dict[str, Any]:
        return {
            "arquivo": str(self.arquivo),
            "minutos": self.minutos,
            "gramas": round(self.gramas, 1),
            "filamento": self.filamento,
        }


def fatiar(
    stl: Path,
    trabalho: Path,
    modelo: str,
    tipo: str = "PLA",
    marca: str = "",
    estudio: BambuStudio | None = None,
    rodar: Rodar = subprocess.run,
) -> Fatiado:
    """Fatia `stl` para o `modelo` da impressora, com o filamento da bandeja, em `trabalho`."""
    estudio = estudio or encontrar(rodar)
    if estudio is None:
        raise FatiadorErro("Bambu Studio não encontrado.")
    if modelo not in MAQUINAS:
        raise FatiadorErro("Modelo de impressora sem perfil.")
    maquina, sufixo = MAQUINAS[modelo]
    trabalho.mkdir(parents=True, exist_ok=True)
    for velho in ("result.json", "fatiado.3mf"):
        (trabalho / velho).unlink(missing_ok=True)
    filamentos = _perfis(estudio.perfis / "filament")
    nome_filamento = filamento(sufixo, tipo, marca, set(filamentos))
    partes = {
        "maquina.json": completo(maquina, _perfis(estudio.perfis / "machine")),
        "processo.json": completo(
            PROCESSO.format(sufixo=sufixo), _perfis(estudio.perfis / "process")
        ),
        "filamento.json": completo(nome_filamento, filamentos),
    }
    for nome, dados in partes.items():
        if nome != "maquina.json":
            dados["from"] = (
                "User"  # o Bambu Studio só aceita perfil de processo e de filamento assim
            )
        (trabalho / nome).write_text(json.dumps(dados))
    shutil.copyfile(stl, trabalho / "modelo.stl")
    acesso = [f"--filesystem={trabalho}"] if estudio.flatpak else []
    comando = [
        *estudio.comando[:2], *acesso, *estudio.comando[2:],
        "--slice", "0",
        "--load-settings", f"{trabalho / 'maquina.json'};{trabalho / 'processo.json'}",
        "--load-filaments", str(trabalho / "filamento.json"),
        "--export-3mf", str(trabalho / "fatiado.3mf"),
        str(trabalho / "modelo.stl"),
    ]  # fmt: skip
    try:
        rodar(comando, cwd=trabalho, capture_output=True, text=True, timeout=PRAZO_S, check=False)
    except subprocess.TimeoutExpired:
        raise FatiadorErro("O fatiamento demorou demais.") from None
    try:
        resultado = json.loads((trabalho / "result.json").read_text())
    except (OSError, ValueError):
        raise FatiadorErro("O Bambu Studio não fatiou o modelo.") from None
    placas = resultado.get("sliced_plates") or []
    if resultado.get("return_code") != 0 or not placas or not (trabalho / "fatiado.3mf").is_file():
        raise FatiadorErro(f"O Bambu Studio recusou: {resultado.get('error_string', '')}".strip())
    placa = placas[0]
    gramas = sum(float(f.get("total_used_g") or 0) for f in placa.get("filaments") or [])
    return Fatiado(
        trabalho / "fatiado.3mf",
        round(float(placa.get("total_predication") or 0) / 60),
        gramas,
        nome_filamento,
    )
