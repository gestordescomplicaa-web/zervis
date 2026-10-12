"""OmniRoute como provedor: chave, ambiente, reserva e aprovação sempre pelo `can_use_tool`."""

import socket
from pathlib import Path

import pytest

from jarvis.cerebro import catalogo, omniroute
from jarvis.cerebro.claude import ClaudeBrain
from jarvis.cerebro.eco import Eco
from jarvis.config import validar


def test_chave_vem_so_da_linha_dela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(omniroute.VARIAVEL_CHAVE, raising=False)
    arquivo = tmp_path / ".env"
    arquivo.write_text("OUTRA=segredo\nexport OMNIROUTER_API_KEY='abc'\n")
    assert omniroute.ler_chave(arquivo) == "abc"
    assert omniroute.ler_chave(tmp_path / "nao-existe") is None
    monkeypatch.setenv(omniroute.VARIAVEL_CHAVE, "do-ambiente")
    assert omniroute.ler_chave(arquivo) == "do-ambiente"


def test_ambiente_aponta_o_cli_para_o_gateway() -> None:
    env = omniroute.ambiente("http://127.0.0.1:20128", "k", "auto/subscription")
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:20128"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "k"  # noqa: S105 (chave falsa)
    assert env["ANTHROPIC_API_KEY"] == ""


def test_no_ar() -> None:
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        porta = servidor.getsockname()[1]
        assert omniroute.no_ar(f"http://127.0.0.1:{porta}")
    assert not omniroute.no_ar(f"http://127.0.0.1:{porta}", 0.2)


@pytest.fixture
def cfg_omniroute(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.setenv(omniroute.VARIAVEL_CHAVE, "k")
    return {"cerebro": {"provedor": "omniroute"}}


def test_omniroute_no_ar_vira_claude_brain_pelo_gateway(
    cfg_omniroute: dict[str, object], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(omniroute, "no_ar", lambda endereco: True)
    cerebro, provedor = catalogo.montar(validar(cfg_omniroute, "teste"), tmp_path, None)
    assert provedor == "auto"
    assert isinstance(cerebro, ClaudeBrain)
    assert cerebro.modelo == "auto/subscription"
    assert cerebro.env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:20128"
    assert not cerebro.assinatura


def test_omniroute_fora_do_ar_usa_a_reserva(
    cfg_omniroute: dict[str, object], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(omniroute, "no_ar", lambda endereco: False)
    cerebro, provedor = catalogo.montar(validar(cfg_omniroute, "teste"), tmp_path, None)
    assert provedor == "claude"
    assert isinstance(cerebro, ClaudeBrain)
    assert "CLAUDE_CONFIG_DIR" in cerebro.env
    assert "ANTHROPIC_BASE_URL" not in cerebro.env

    cfg_omniroute["cerebro"] = {"provedor": "omniroute", "reserva": "eco"}
    cerebro, provedor = catalogo.montar(validar(cfg_omniroute, "teste"), tmp_path, None)
    assert (provedor, type(cerebro)) == ("eco", Eco)


@pytest.mark.parametrize("env", [{}, omniroute.ambiente("http://127.0.0.1:1", "k", "rota")])
def test_aprovacao_explicita_em_todo_provedor(tmp_path: Path, env: dict[str, str]) -> None:
    """Regressão da Prova 4 (ADR 0008): sem isto, via OmniRoute a ferramenta rodou sem perguntar."""
    cerebro = ClaudeBrain("m", ["WebSearch"], tmp_path, env=env)
    opcoes = cerebro.opcoes()
    assert opcoes.permission_mode == "default"
    assert opcoes.can_use_tool is not None
    assert opcoes.allowed_tools == []
    assert opcoes.setting_sources == []
    assert opcoes.strict_mcp_config


@pytest.mark.parametrize(
    ("modelo", "nome"),
    [
        ("claude-sonnet-5-5", "Sonnet 5.5"),
        ("cx/gpt-6-luna", "GPT-6 Luna"),
        ("agy/gemini-3.1-pro-high", "Gemini 3.1 Pro"),
        ("claude-opus-4-6-thinking", "Opus 4.6"),
        ("claude-haiku-4-5-20251001", "Haiku 4.5"),
    ],
)
def test_rotulo_legivel_do_modelo(modelo: str, nome: str) -> None:
    assert catalogo.rotulo(modelo) == nome
