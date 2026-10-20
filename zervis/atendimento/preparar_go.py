"""Prepara um Go compatível com o WaCalls e o deixa visível ao serviço do usuário."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

VERSAO = "1.27.2"
ARQUIVOS = {
    "amd64": "ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5",
    "arm64": "94f3e30b8e374bc285e7dadc11e0865726b9bc6e85b841ccceaabc0214c6b7c8",
}
URL = f"https://go.dev/dl/go{VERSAO}.linux-{{arquitetura}}.tar.gz"
TEMPO_DOWNLOAD_S = 180
TEMPO_COMANDO_S = 10


class PrepararGoErro(RuntimeError):
    """O Go necessário para o WaCalls não pôde ser preparado."""


def _versao_minima() -> tuple[int, int, int]:
    arquivo = Path(__file__).with_name("wacalls") / "go.mod"
    achado = re.search(r"^go (\d+)\.(\d+)(?:\.(\d+))?$", arquivo.read_text(), re.MULTILINE)
    if achado is None:
        raise PrepararGoErro("não encontrei a versão mínima no go.mod do WaCalls")
    major, minor, patch = achado.groups()
    return int(major), int(minor), int(patch or 0)


def _executavel_compativel(programa: str) -> Path | None:
    try:
        versao = subprocess.run(  # noqa: S603 (Go do PATH ou do pacote oficial, verificado)
            [programa, "version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=TEMPO_COMANDO_S,
        ).stdout
        achado = re.search(r"\bgo(\d+)\.(\d+)(?:\.(\d+))?\b", versao)
        if achado is None:
            return None
        major, minor, patch = achado.groups()
        encontrada = int(major), int(minor), int(patch or 0)
        if encontrada < _versao_minima():
            return None
        goroot = subprocess.run(  # noqa: S603 (mesmo executável Go já validado acima)
            [programa, "env", "GOROOT"],
            check=True,
            capture_output=True,
            text=True,
            timeout=TEMPO_COMANDO_S,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    binario = Path(goroot) / "bin" / "go"
    if not binario.is_file():
        return None
    return binario.resolve()


def _baixar(url: str, destino: Path) -> None:
    with (
        urllib.request.urlopen(  # noqa: S310 (URL fixa go.dev; o pacote também exige SHA-256)
            url, timeout=TEMPO_DOWNLOAD_S
        ) as resposta,
        destino.open("wb") as saida,
    ):
        shutil.copyfileobj(resposta, saida)


def _sha256(arquivo: Path) -> str:
    digest = hashlib.sha256()
    with arquivo.open("rb") as conteudo:
        for bloco in iter(lambda: conteudo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _instalar_toolchain(arquitetura: str, raiz: Path) -> Path:
    esperado = ARQUIVOS[arquitetura]
    pasta = raiz / "zervis" / "ferramentas"
    destino = pasta / f"go{VERSAO}"
    binario = destino / "bin" / "go"
    if binario.exists():
        if (compativel := _executavel_compativel(str(binario))) is not None:
            return compativel
        raise PrepararGoErro(f"a instalação local do Go está incompleta: {binario}")

    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    url = URL.format(arquitetura=arquitetura)
    try:
        with tempfile.TemporaryDirectory(prefix=".go-", dir=pasta) as temporario:
            temporario_path = Path(temporario)
            pacote = temporario_path / "go.tar.gz"
            _baixar(url, pacote)
            if _sha256(pacote) != esperado:
                raise PrepararGoErro("o checksum do Go baixado não confere")
            with tarfile.open(pacote, "r:gz") as arquivo:
                arquivo.extractall(temporario_path, filter="data")
            extraido = temporario_path / "go"
            if not (extraido / "bin" / "go").is_file():
                raise PrepararGoErro("o pacote oficial do Go não contém o executável esperado")
            os.replace(extraido, destino)
    except PrepararGoErro:
        raise
    except (OSError, tarfile.TarError, urllib.error.URLError) as erro:
        raise PrepararGoErro(f"falha ao baixar ou instalar Go {VERSAO}: {erro}") from erro

    compativel = _executavel_compativel(str(binario))
    if compativel is None:
        raise PrepararGoErro(f"Go {VERSAO} não iniciou após a instalação em {destino}")
    return compativel


def _criar_atalho(programa: Path, raiz: Path) -> Path:
    pasta = raiz / ".local" / "lib" / "zervis" / "bin"
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    destino = pasta / "go"
    temporario = pasta / ".go-novo"
    temporario.write_text(f'#!/bin/sh\nexec {shlex.quote(str(programa))} "$@"\n')
    temporario.chmod(0o700)
    os.replace(temporario, destino)
    return pasta


def preparar() -> Path:
    """Usa o Go existente ou instala uma cópia oficial verificada no espaço do usuário."""
    home = Path.home()
    if (programa := shutil.which("go")) and (compativel := _executavel_compativel(programa)):
        return _criar_atalho(compativel, home)

    arquitetura_sistema = platform.machine().lower()
    arquitetura = {"x86_64": "amd64", "aarch64": "arm64"}.get(arquitetura_sistema)
    if arquitetura not in ARQUIVOS:
        raise PrepararGoErro(f"arquitetura sem pacote Go verificado: {arquitetura_sistema}")
    raiz_dados = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    instalado = _instalar_toolchain(arquitetura, raiz_dados)
    return _criar_atalho(instalado, home)


def main() -> int:
    try:
        print(preparar())
    except PrepararGoErro as erro:
        print(f"Não foi possível preparar o Go do atendimento: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
