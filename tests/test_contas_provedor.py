"""A conta de outro provedor no Claude Code (a DeepSeek, provada em 27/10/2026): o mesmo terminal,
a voz e a aprovação do Zé, com o modelo do provedor e a chave colada pela pessoa."""

import json
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro import contas, modelos
from zervis.oficina import fallback
from zervis.oficina.sessoes import Sessao, ambiente_da_conta

MODELOS = [("deepseek-flash", "DeepSeek-V4.1-Flash"), ("deepseek-v4-pro", "DeepSeek-V4-Pro")]
CHAVE = "sk-teste-0123456789"


@pytest.fixture
def cs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> contas.Contas:
    monkeypatch.setattr(
        contas,
        "ORIGINAL",
        {"CLAUDE_CONFIG_DIR": str(tmp_path / "claude"), "CODEX_HOME": str(tmp_path / "codex")},
    )
    monkeypatch.setattr(contas, "CHAVES", tmp_path / "chaves")
    return contas.Contas(tmp_path / "contas.json", tmp_path / "pastas")


def consultar(_provedor: contas.Provedor, chave: str) -> list[tuple[str, str]]:
    assert chave == CHAVE
    return MODELOS


def test_a_chave_testada_vira_uma_conta_do_claude_so_com_o_que_ela_usa(cs: contas.Contas) -> None:
    conta = cs.adicionar_provedor("deepseek", f"  {CHAVE}\n", consultar)
    assert (conta.agente, conta.nome, conta.provedor) == ("claude", "DeepSeek", "deepseek")
    assert conta.modelos == tuple(MODELOS)
    # A chave fica num arquivo 0600 fora do contas.json; a pasta já passou da apresentação.
    assert conta.login.read_text().strip() == CHAVE
    assert stat.S_IMODE(conta.login.stat().st_mode) == 0o600
    assert CHAVE not in cs.arquivo.read_text()
    assert json.loads((Path(conta.pasta) / ".claude.json").read_text())["hasCompletedOnboarding"]
    relida = cs.achar(conta.id)
    assert relida == conta
    assert contas.quem(relida) == {"logado": True, "email": "", "plano": "DeepSeek · chave de API"}
    assert [m["id"] for m in modelos.da_conta(relida)] == ["deepseek-flash", "deepseek-v4-pro"]
    # Uma segunda chave ganha outro nome.
    assert cs.adicionar_provedor("deepseek", CHAVE, consultar).nome == "DeepSeek 2"


def test_chave_recusada_ou_errada_nao_cria_nada(cs: contas.Contas) -> None:
    def recusar(provedor: contas.Provedor, _chave: str) -> list[tuple[str, str]]:
        raise contas.ContaErro(f"a {provedor.nome} recusou a chave")

    with pytest.raises(contas.ContaErro, match="recusou"):
        cs.adicionar_provedor("deepseek", CHAVE, recusar)
    for errada in ("", "sk-a b", "x" * 401):
        with pytest.raises(contas.ContaErro):
            cs.adicionar_provedor("deepseek", errada, consultar)
    with pytest.raises(contas.ContaErro):
        cs.adicionar_provedor("outro", CHAVE, consultar)
    assert [c.id for c in cs.listar()] == ["claude:padrao", "codex:padrao"]
    assert not cs.pasta.exists() or not any(cs.pasta.iterdir())


def test_a_sessao_leva_o_provedor_no_ambiente_e_nunca_vira_a_conta_do_cerebro(
    cs: contas.Contas, monkeypatch: pytest.MonkeyPatch
) -> None:
    conta = cs.adicionar_provedor("deepseek", CHAVE, consultar)
    monkeypatch.setattr(contas, "Contas", lambda: cs)
    ambiente = ambiente_da_conta(Sessao(id="00000001", nome="x", pasta="p", conta=conta.id))
    assert ambiente == {
        "CLAUDE_CONFIG_DIR": conta.pasta,
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": CHAVE,
        "ANTHROPIC_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
        "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-flash",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    # O cérebro do Zé e o teste do acesso seguem na conta do Claude, com os modelos dele.
    with pytest.raises(contas.ContaErro, match="só nas sessões"):
        cs.usar(conta.id)
    assert cs.em_uso("claude").id == "claude:padrao"
    # Sessão com modelo do Claude não cai na conta do provedor quando bate o limite, nem o
    # contrário (os modelos não se cruzam).
    assert conta.id not in [
        c.id for c in fallback.candidatas(cs, "claude", "claude-opus-5-5", "high", set())
    ]
    # Sem a chave (apagada à mão), nada de provedor: o Claude Code mostra o erro dele.
    conta.login.unlink()
    assert ambiente_da_conta(Sessao(id="00000001", nome="x", pasta="p", conta=conta.id)) == {
        "CLAUDE_CONFIG_DIR": conta.pasta
    }


def test_remover_apaga_a_chave(cs: contas.Contas) -> None:
    conta = cs.adicionar_provedor("deepseek", CHAVE, consultar)
    cs.remover(conta.id)
    assert not conta.login.exists() and not Path(conta.pasta).exists()
    assert [c.id for c in cs.listar()] == ["claude:padrao", "codex:padrao"]


class _Provedor(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.headers.get("Authorization") != f"Bearer {CHAVE}":
            self.send_response(401)
            self.end_headers()
            return
        corpo = json.dumps({"data": [{"id": i, "name": n} for i, n in MODELOS] + [{"x": 1}]})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(corpo.encode())

    def log_message(self, *_: Any) -> None:
        pass


def test_a_lista_do_provedor_testa_a_chave() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Provedor)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        local = contas.Provedor(
            "Local", "", f"http://127.0.0.1:{servidor.server_port}/models", "", "", ""
        )
        assert contas.modelos_do_provedor(local, CHAVE) == MODELOS
        with pytest.raises(contas.ContaErro, match="recusou a chave"):
            contas.modelos_do_provedor(local, "sk-outra")
    finally:
        servidor.shutdown()
    fora = contas.Provedor("Fora", "", "http://127.0.0.1:1/models", "", "", "")
    with pytest.raises(contas.ContaErro, match="não consegui falar"):
        contas.modelos_do_provedor(fora, CHAVE)
