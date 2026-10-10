"""O ai-memory embutido: o da máquina se houver, senão o binário oficial conferido (ADR 0016)."""

import hashlib
import io
import tarfile
from pathlib import Path
from typing import Any

import pytest

from jarvis.memoria import aimemory
from jarvis.preparar import Modelo, PrepararErro


def pacote(arquivos: dict[str, bytes]) -> bytes:
    saida = io.BytesIO()
    with tarfile.open(fileobj=saida, mode="w:gz") as tar:
        for nome, dados in arquivos.items():
            info = tarfile.TarInfo(nome)
            info.size = len(dados)
            tar.addfile(info, io.BytesIO(dados))
    return saida.getvalue()


class Resposta(io.BytesIO):
    status = 200

    def __enter__(self) -> "Resposta":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def test_baixa_confere_e_extrai_so_quando_a_maquina_nao_tem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dados = pacote(
        {"./ai-memory": b"#!/bin/sh\n", "./LICENSE": b"MIT", "./hooks/codex/stop.sh": b""}
    )
    modelo = Modelo("am.tar.gz", "https://x/am.tar.gz", hashlib.sha256(dados).hexdigest(), "t")
    monkeypatch.setattr(aimemory, "PACOTES", {"x86_64": modelo, "aarch64": modelo})
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    monkeypatch.setattr("shutil.which", lambda _: None)
    pasta = tmp_path / "ai-memory" / "9.9"
    assert aimemory.garantir(pasta, lambda *a, **k: Resposta(dados))
    assert (pasta / "ai-memory").stat().st_mode & 0o111 and (pasta / "hooks/codex/stop.sh").exists()
    assert not (pasta.parent / "am.tar.gz").exists()  # o pacote some depois de extraído
    assert aimemory.binario(pasta) == pasta / "ai-memory"
    assert not aimemory.garantir(pasta, lambda *a, **k: Resposta(b""))  # já tem: não baixa
    # Impressão digital errada: não extrai nada.
    outra = tmp_path / "outra" / "9.9"
    with pytest.raises(PrepararErro):
        aimemory.garantir(outra, lambda *a, **k: Resposta(b"adulterado"))
    assert not outra.exists()


def test_o_da_maquina_vence_o_baixado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ai-memory")
    assert aimemory.binario(tmp_path) == Path("/usr/bin/ai-memory")


def test_os_hooks_da_sessao_apontam_para_o_servidor_e_somem_sem_ele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aimemory, "binario", lambda pasta=None: Path("/opt/am/ai-memory"))
    monkeypatch.setattr(aimemory, "no_ar", lambda url=None, abrir=None: True)
    h = aimemory.hooks_claude("http://127.0.0.1:5000", Path("/d"))["hooks"]
    assert set(h) == set(aimemory.EVENTOS_CLAUDE)
    comando = h["PostToolUse"][0]["hooks"][0]["command"]
    assert comando == (
        '"/opt/am/ai-memory" --data-dir "/d" hook --agent claude-code '
        "--server-url http://127.0.0.1:5000 --event post-tool-use"
    )
    monkeypatch.setattr(aimemory, "no_ar", lambda url=None, abrir=None: False)
    assert aimemory.hooks_claude() == {}  # sem servidor: a sessão segue sem memória longa


def test_com_o_servidor_da_maquina_no_ar_o_ze_nao_sobe_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aimemory, "no_ar", lambda url=None, abrir=None: True)
    m = aimemory.AiMemory("http://127.0.0.1:5000")
    m.iniciar()
    assert m.filho is None
