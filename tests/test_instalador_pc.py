"""Scripts reais em pastas vazias; rede, contas e systemd da máquina ficam fora da prova."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def instalacao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = tmp_path / "codigo com espacos"
    repo.mkdir()
    for pasta in ("deploy", "systemd"):
        shutil.copytree(REPO / pasta, repo / pasta)
    shutil.copy(REPO / "Makefile", repo)
    binarios = tmp_path / "bin"
    binarios.mkdir()
    registro = tmp_path / "comandos"
    # Somente os efeitos externos são falsos: o make, sed e install são os reais.
    falso = """#!/bin/sh
nome=${0##*/}
printf '%s %s\\n' "$nome" "$*" >> "$ZE_TESTE_LOG"
case "$nome" in
  id) case "$1" in -u) echo "${ZE_TESTE_UID:-1000}" ;; -un) echo teste ;; esac ;;
  getconf) echo 'glibc 2.39' ;;
  uname) echo Linux ;;
esac
"""
    for comando in (
        "uv",
        "git",
        "curl",
        "systemctl",
        "loginctl",
        "setsid",
        "id",
        "getconf",
        "uname",
        "chromium",
        "parec",
        "paplay",
        "pactl",
    ):
        arquivo = binarios / comando
        arquivo.write_text(falso)
        arquivo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binarios}:{os.environ['PATH']}")
    monkeypatch.setenv("ZE_TESTE_LOG", str(registro))
    monkeypatch.setenv("HOME", str(tmp_path / "casa vazia"))
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("JARVIS_PAINEL_PORTA", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config com espacos"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados com espacos"))
    return repo, registro


def _rodar(repo: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (scripts do projeto, com efeitos externos falsos)
        [str(repo / "deploy" / script)], cwd=repo, capture_output=True, text=True, timeout=30
    )


def test_pc_instala_servico_atalho_e_abre_painel(instalacao: tuple[Path, Path]) -> None:
    repo, registro = instalacao
    resultado = _rodar(repo, "instalar-pc.sh")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    comandos = registro.read_text()
    assert "uv sync --frozen" in comandos
    assert "uv run python -m jarvis.preparar" in comandos
    assert "uv run python -m jarvis.cerebro.agentes_nativos" in comandos
    assert "systemctl --user import-environment DISPLAY" in comandos
    assert "systemctl --user enable zervis" in comandos
    assert "systemctl --user restart zervis" in comandos
    assert "setsid " in comandos
    assert "primeiro_acesso" not in comandos
    assert "loginctl" not in comandos
    assert "http://127.0.0.1:8795/" in resultado.stdout
    servico = Path(os.environ["XDG_CONFIG_HOME"]) / "systemd/user/zervis.service"
    assert f'ExecStart="{repo}/.venv/bin/python" -m jarvis' in servico.read_text()
    atalho = Path(os.environ["XDG_DATA_HOME"]) / "applications/zervis.desktop"
    assert f'"{repo}/deploy/abrir-painel.sh"' in atalho.read_text()
    assert "@" not in atalho.read_text()


@pytest.mark.parametrize("sem_tela", [False, True])
def test_pc_recusa_root_ou_sessao_sem_tela(
    instalacao: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, sem_tela: bool
) -> None:
    repo, registro = instalacao
    if sem_tela:
        monkeypatch.delenv("DISPLAY")
    else:
        monkeypatch.setenv("ZE_TESTE_UID", "0")
    resultado = _rodar(repo, "instalar-pc.sh")
    assert resultado.returncode != 0
    assert ("sessão gráfica" if sem_tela else "usuário comum") in resultado.stderr
    assert "uv " not in registro.read_text()
    assert "restart" not in registro.read_text()


def test_servidor_preserva_linger_e_primeiro_acesso(instalacao: tuple[Path, Path]) -> None:
    repo, registro = instalacao
    resultado = _rodar(repo, "instalar-servidor.sh")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    comandos = registro.read_text()
    assert "loginctl enable-linger teste" in comandos
    assert "uv run python -m jarvis.portal.primeiro_acesso" in comandos
    assert "setsid " not in comandos
    assert "import-environment" not in comandos


def test_pc_preserva_porta_escolhida_no_servico_atalho_e_conferencia(
    instalacao: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registro = instalacao
    monkeypatch.setenv("JARVIS_PAINEL_PORTA", "8796")
    resultado = _rodar(repo, "instalar-pc.sh")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "http://127.0.0.1:8796/" in resultado.stdout
    assert "http://127.0.0.1:8796/" in registro.read_text()
    servico = Path(os.environ["XDG_CONFIG_HOME"]) / "systemd/user/zervis.service"
    assert "Environment=JARVIS_PAINEL_PORTA=8796" in servico.read_text()
    atalho = Path(os.environ["XDG_DATA_HOME"]) / "applications/zervis.desktop"
    assert "JARVIS_PAINEL_PORTA=8796" in atalho.read_text()


@pytest.mark.parametrize("navegador", ["chromium", "chromium-browser", "google-chrome", "xdg-open"])
def test_painel_detecta_navegador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, navegador: str
) -> None:
    # PATH fechado: não deixa um Chromium da máquina esconder a falta dele no Ubuntu.
    binarios = tmp_path / "bin"
    binarios.mkdir()
    for comando in ("bash", "mkdir"):
        origem = shutil.which(comando)
        assert origem is not None
        (binarios / comando).symlink_to(origem)
    falso = binarios / navegador
    falso.write_text("#!/bin/sh\nprintf '<%s>\\n' \"$@\"\n")
    falso.chmod(0o755)
    monkeypatch.setenv("PATH", str(binarios))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados com espacos"))
    monkeypatch.setenv("JARVIS_PAINEL_PORTA", "8796")
    resultado = _rodar(REPO, "abrir-painel.sh")
    assert resultado.returncode == 0, resultado.stderr
    if navegador == "xdg-open":
        assert resultado.stdout.strip() == "<http://127.0.0.1:8796/>"
    else:
        assert "<--app=http://127.0.0.1:8796/>" in resultado.stdout
        assert f"<--user-data-dir={tmp_path}/dados com espacos/zervis/navegador-painel>" in (
            resultado.stdout
        )
