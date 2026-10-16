"""Provisionamento do Go do WaCalls: usa instalação válida ou baixa pacote conferido."""

import hashlib
import io
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.atendimento import preparar_go


def _pacote_go() -> bytes:
    script = b"""#!/bin/sh
if [ "$1" = version ]; then echo 'go version go1.27.2 linux/amd64'; exit 0; fi
if [ "$1" = env ] && [ "$2" = GOROOT ]; then dirname "$(dirname "$0")"; exit 0; fi
exit 1
"""
    conteudo = io.BytesIO()
    with tarfile.open(fileobj=conteudo, mode="w:gz") as arquivo:
        membro = tarfile.TarInfo("go/bin/go")
        membro.mode = 0o755
        membro.size = len(script)
        arquivo.addfile(membro, io.BytesIO(script))
    return conteudo.getvalue()


def test_usa_go_compativel_existente_e_cria_atalho_para_o_servico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "casa com espaços"
    goroot = tmp_path / "go existente"
    (goroot / "bin").mkdir(parents=True)
    (goroot / "bin" / "go").touch()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/go")

    def rodar(comando: list[str], **_: object) -> SimpleNamespace:
        if comando[-1] == "version":
            return SimpleNamespace(stdout="go version go1.27.1 linux/amd64")
        return SimpleNamespace(stdout=str(goroot))

    monkeypatch.setattr(subprocess, "run", rodar)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("não deveria baixar Go"),
    )

    resultado = preparar_go.preparar()

    assert resultado == home / ".local/lib/zervis/bin"
    atalho = resultado / "go"
    assert atalho.stat().st_mode & 0o111
    assert f"exec '{goroot}/bin/go' \"$@\"" in atalho.read_text()


def test_instala_go_oficial_com_sha256_e_arquitetura_verificados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pacote = _pacote_go()
    monkeypatch.setitem(preparar_go.ARQUIVOS, "amd64", hashlib.sha256(pacote).hexdigest())
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados com espaços"))
    urls: list[str] = []

    def abrir(url: str, *, timeout: int) -> io.BytesIO:
        assert timeout == preparar_go.TEMPO_DOWNLOAD_S
        urls.append(url)
        return io.BytesIO(pacote)

    monkeypatch.setattr(urllib.request, "urlopen", abrir)

    resultado = preparar_go.preparar()

    raiz = tmp_path / "dados com espaços/zervis/ferramentas/go1.27.2"
    assert urls == ["https://go.dev/dl/go1.27.2.linux-amd64.tar.gz"]
    assert (raiz / "bin/go").is_file()
    assert resultado == tmp_path / "casa/.local/lib/zervis/bin"
    assert f"exec '{raiz}/bin/go' \"$@\"" in (resultado / "go").read_text()


def test_recusa_pacote_go_com_checksum_incorreto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pacote = _pacote_go()
    monkeypatch.setitem(preparar_go.ARQUIVOS, "amd64", "0" * 64)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(pacote))

    with pytest.raises(preparar_go.PrepararGoErro, match="checksum"):
        preparar_go.preparar()

    assert not (tmp_path / "dados/zervis/ferramentas/go1.27.2").exists()


def test_arquitetura_sem_binario_conferido_falha_com_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(platform, "machine", lambda: "riscv64")

    with pytest.raises(preparar_go.PrepararGoErro, match="riscv64"):
        preparar_go.preparar()
