"""O ai-memory embutido: o da máquina se houver, senão o binário oficial conferido (ADR 0016)."""

import hashlib
import io
import json
import shlex
import subprocess
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
    assert shlex.split(comando) == [
        "/opt/am/ai-memory",
        "--data-dir",
        "/d",
        "hook",
        "--agent",
        "claude-code",
        "--server-url",
        "http://127.0.0.1:5000",
        "--project-strategy",
        "repo-root",
        "--event",
        "post-tool-use",
    ]
    monkeypatch.setattr(aimemory, "no_ar", lambda url=None, abrir=None: False)
    assert aimemory.hooks_claude() == {}  # sem servidor: a sessão segue sem memória longa


def test_com_o_servidor_da_maquina_no_ar_o_ze_nao_sobe_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aimemory, "no_ar", lambda url=None, abrir=None: True)
    m = aimemory.AiMemory("http://127.0.0.1:5000")
    m.iniciar()
    assert m.filho is None


def test_codex_registra_pedido_e_fim_sem_consumir_handoff_nem_fechar_conversa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eventos: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(aimemory, "binario", lambda: Path("/opt/ai-memory"))

    def executar(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 5
        assert cmd[cmd.index("--project-strategy") + 1] == "repo-root"
        assert cmd[cmd.index("--data-dir") + 1] == str(aimemory.DADOS)
        eventos.append((cmd[cmd.index("--event") + 1], json.loads(kwargs["input"])))
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", executar)
    aimemory.registrar_codex(
        "fio-original", tmp_path, "Corrija só a rolagem.", "Falta testar a voz."
    )
    assert eventos == [
        (
            "user-prompt-submit",
            {"session_id": "fio-original", "cwd": str(tmp_path), "prompt": "Corrija só a rolagem."},
        ),
        (
            "stop",
            {
                "session_id": "fio-original",
                "cwd": str(tmp_path),
                "last_assistant_message": "Falta testar a voz.",
            },
        ),
    ]


def test_falha_da_memoria_nao_derruba_a_sessao_nem_expoe_conteudo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(aimemory, "binario", lambda: Path("/opt/ai-memory"))

    def falhar(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired("ai-memory", 5)

    monkeypatch.setattr(subprocess, "run", falhar)
    aimemory.registrar_codex("fio", tmp_path, "informação privada", "outra informação privada")
    assert "captura Codex indisponível" in caplog.text
    assert "informação privada" not in caplog.text


def test_busca_usa_projeto_original_e_mesma_memoria_independente_da_conta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aimemory, "binario", lambda: tmp_path / "bin com espaço/ai-memory")
    projeto = tmp_path / "Projeto d'Água"
    texto = aimemory.orientacao(projeto)
    assert f"cd -- {shlex.quote(str(projeto))}" in texto
    assert shlex.join(aimemory.comando()) in texto
    assert "search" in texto and "read-page" in texto
    assert "dados históricos" in texto


def test_encerramento_real_envia_so_session_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eventos: list[str] = []
    monkeypatch.setattr(aimemory, "binario", lambda: Path("/opt/ai-memory"))

    def executar(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        eventos.append(cmd[cmd.index("--event") + 1])
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", executar)
    aimemory.registrar_codex("fio-original", tmp_path, "", "", encerrar=True)
    assert eventos == ["session-end"]
