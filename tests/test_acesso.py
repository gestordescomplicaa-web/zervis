"""O acesso ao Claude: o que o painel cola vence, vai para o ambiente e nunca volta para a tela."""

import os
from pathlib import Path

import pytest

from jarvis import fuso, usuario
from jarvis.cerebro import acesso, rapido


@pytest.fixture
def limpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(acesso, "ORIGINAL", {acesso.TOKEN: "", acesso.CHAVE: ""})
    monkeypatch.delenv(acesso.TOKEN, raising=False)
    monkeypatch.delenv(acesso.CHAVE, raising=False)
    return tmp_path


def test_sem_nada_nao_ha_acesso(limpo: Path) -> None:
    login = limpo / "sem-login.json"
    assert acesso.situacao(limpo, login) == {"metodo": "", "origem": "", "fim": ""}
    assert acesso.aplicar(limpo, login) == ""
    assert acesso.TOKEN not in os.environ and acesso.CHAVE not in os.environ


def test_o_login_feito_no_proprio_agente_vale_sem_o_ze_tocar_na_conta(limpo: Path) -> None:
    login = limpo / ".credentials.json"
    login.write_text("{}")
    assert acesso.situacao(limpo, login) == {"metodo": "login", "origem": "agente", "fim": ""}
    assert acesso.aplicar(limpo, login) == "login"
    assert acesso.TOKEN not in os.environ and acesso.CHAVE not in os.environ


def test_a_chave_colada_vence_o_login_e_sai_ao_remover(
    limpo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    login = limpo / ".credentials.json"
    login.write_text("{}")
    rapido.gravar_chave("anthropic", "sk-ant-painel-1111", limpo)
    assert acesso.situacao(limpo, login) == {"metodo": "chave", "origem": "painel", "fim": "1111"}
    assert acesso.aplicar(limpo, login) == "chave"
    assert os.environ[acesso.CHAVE] == "sk-ant-painel-1111"
    rapido.apagar_chave("anthropic", limpo)
    assert acesso.aplicar(limpo, login) == "login" and acesso.CHAVE not in os.environ
    monkeypatch.setattr(acesso, "ORIGINAL", {acesso.TOKEN: "", acesso.CHAVE: "sk-ambiente"})
    assert acesso.situacao(limpo, login)["origem"] == "ambiente"
    acesso.aplicar(limpo, login)
    assert os.environ[acesso.CHAVE] == "sk-ambiente"


def test_os_agentes_da_maquina_sao_lidos_instalado_e_com_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude, codex = tmp_path / "claude.json", tmp_path / "codex.json"
    codex.write_text("{}")
    monkeypatch.setattr(
        acesso,
        "AGENTES",
        (
            acesso.Agente("claude", "Claude", "programa-que-nao-existe", claude, "claude"),
            acesso.Agente("codex", "Codex", "sh", codex, "codex login"),
        ),
    )
    assert acesso.agentes({}) == [
        {"id": "claude", "nome": "Claude", "instalado": False, "logado": False, "entrar": "claude"},
        {
            "id": "codex",
            "nome": "Codex",
            "instalado": True,
            "logado": True,
            "entrar": "codex login",
        },
    ]


def test_o_fuso_do_perfil_vale_quando_nao_ha_variavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(usuario, "ARQUIVO", tmp_path / "perfil.json")
    monkeypatch.delenv("ZERVIS_FUSO")
    monkeypatch.delenv("TZ", raising=False)
    usuario.gravar(usuario.Perfil("Ana", "", "Europe/Lisbon"))
    assert fuso.local().key == "Europe/Lisbon"
    assert fuso.valido("Europe/Lisbon") and not fuso.valido("Lua/Base")
    assert fuso.nomes()[0] == "UTC"
