"""O acesso ao Claude: o que o painel cola vence, vai para o ambiente e nunca volta para a tela."""

import os
import stat
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


def test_o_login_do_claude_code_vale_sem_mexer_no_ambiente(limpo: Path) -> None:
    login = limpo / ".credentials.json"
    login.write_text("{}")
    assert acesso.situacao(limpo, login) == {"metodo": "assinatura", "origem": "login", "fim": ""}
    assert acesso.aplicar(limpo, login) == "assinatura"
    assert acesso.TOKEN not in os.environ


def test_o_token_colado_vence_e_tira_a_chave_do_ambiente(
    limpo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acesso, "ORIGINAL", {acesso.TOKEN: "", acesso.CHAVE: "sk-ambiente"})
    rapido.gravar_chave("anthropic", "sk-ant-painel-1111", limpo)
    acesso.gravar_token("oat-segredo-2222", limpo)
    arquivo = acesso.arquivo_do_token(limpo)
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert acesso.situacao(limpo) == {"metodo": "assinatura", "origem": "painel", "fim": "2222"}
    assert acesso.aplicar(limpo) == "assinatura"
    assert os.environ[acesso.TOKEN] == "oat-segredo-2222" and acesso.CHAVE not in os.environ
    # Sem o token, a chave colada; sem ela, a do ambiente volta.
    acesso.apagar_token(limpo)
    assert acesso.aplicar(limpo) == "chave"
    assert os.environ[acesso.CHAVE] == "sk-ant-painel-1111" and acesso.TOKEN not in os.environ
    rapido.apagar_chave("anthropic", limpo)
    assert acesso.situacao(limpo)["origem"] == "ambiente"
    acesso.aplicar(limpo)
    assert os.environ[acesso.CHAVE] == "sk-ambiente"
    with pytest.raises(ValueError):
        acesso.gravar_token("com espaço", limpo)


def test_o_fuso_do_perfil_vale_quando_nao_ha_variavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(usuario, "ARQUIVO", tmp_path / "perfil.json")
    monkeypatch.delenv("JARVIS_FUSO")
    monkeypatch.delenv("TZ", raising=False)
    usuario.gravar(usuario.Perfil("Ana", "", "Europe/Lisbon"))
    assert fuso.local().key == "Europe/Lisbon"
    assert fuso.valido("Europe/Lisbon") and not fuso.valido("Lua/Base")
    assert fuso.nomes()[0] == "UTC"
