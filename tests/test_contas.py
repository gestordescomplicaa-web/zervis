"""Contas dos agentes: uma pasta de login por conta, o login feito no próprio agente (ADR 0016)."""

import base64
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import contas
from jarvis.oficina.sessoes import Sessao, ambiente_da_conta


@pytest.fixture
def cs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> contas.Contas:
    monkeypatch.setattr(
        contas,
        "ORIGINAL",
        {"CLAUDE_CONFIG_DIR": str(tmp_path / "claude"), "CODEX_HOME": str(tmp_path / "codex")},
    )
    return contas.Contas(tmp_path / "contas.json", tmp_path / "pastas")


def jwt(claims: dict[str, Any]) -> str:
    carga = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"x.{carga}.y"


def test_a_padrao_vem_sempre_e_a_nova_ganha_uma_pasta_so_dela(cs: contas.Contas) -> None:
    assert [c.id for c in cs.listar()] == ["claude:padrao", "codex:padrao"]
    nova = cs.adicionar("codex", "Trabalho")
    pasta = Path(nova.pasta)
    assert pasta.parent == cs.pasta and stat.S_IMODE(pasta.stat().st_mode) == 0o700
    assert nova.ambiente() == {"CODEX_HOME": nova.pasta}
    assert nova.comando_login() == [
        "env",
        f"CODEX_HOME={nova.pasta}",
        "codex",
        "login",
        "--device-auth",
    ]
    assert cs.listar("claude")[0].comando_login() == ["env", "claude", "auth", "login"]
    for errado in (("codex", "trabalho"), ("codex", " "), ("gemini", "x")):
        with pytest.raises(contas.ContaErro):
            cs.adicionar(*errado)


def test_quem_esta_logado_com_email_mascarado_e_plano(cs: contas.Contas) -> None:
    codex = cs.adicionar("codex", "Gratuita")
    assert contas.quem(codex) == {"logado": False, "email": "", "plano": ""}
    claims = {
        "email": "ana.silva@gmail.com",
        "https://api.openai.com/auth": {"chatgpt_plan_type": "free"},
    }
    (Path(codex.pasta) / "auth.json").write_text(json.dumps({"tokens": {"id_token": jwt(claims)}}))
    assert contas.quem(codex) == {"logado": True, "email": "ana…@gmail.com", "plano": "free"}
    claude = cs.listar("claude")[0]  # a padrão: login na pasta, perfil ao lado (~/.claude.json)
    claude.onde.mkdir(parents=True)
    (claude.onde / ".credentials.json").write_text("{}")
    (claude.onde.parent / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"emailAddress": "bob@exemplo.com"}})
    )
    assert contas.quem(claude) == {"logado": True, "email": "bob…@exemplo.com", "plano": ""}


def test_usar_e_remover_sem_apagar_o_que_o_ze_nao_criou(cs: contas.Contas) -> None:
    assert cs.em_uso("claude").id == "claude:padrao"
    nova = cs.adicionar("claude", "Trabalho")
    assert cs.usar(nova.id).id == cs.em_uso("claude").id == nova.id
    cs.remover(nova.id)
    assert not Path(nova.pasta).exists() and cs.em_uso("claude").id == "claude:padrao"
    with pytest.raises(contas.ContaErro):
        cs.remover("claude:padrao")


def test_a_sessao_usa_a_pasta_da_sua_conta(
    cs: contas.Contas, monkeypatch: pytest.MonkeyPatch
) -> None:
    nova = cs.adicionar("claude", "Trabalho")
    monkeypatch.setattr(contas, "Contas", lambda: cs)
    sessao = Sessao(id="00000001", nome="x", pasta="projeto", conta=nova.id)
    assert ambiente_da_conta(sessao) == {"CLAUDE_CONFIG_DIR": nova.pasta}
    assert ambiente_da_conta(Sessao(id="00000002", nome="x", pasta="projeto")) == {}
