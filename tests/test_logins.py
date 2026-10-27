"""Entrar na conta de um agente pelo painel, num servidor sem tela (ADR 0035)."""

import os
import time
from pathlib import Path

import pytest

from zervis.cerebro import contas, logins

# Como o `claude auth login`: o link num hiperlink de terminal (OSC 8), com cor, e o pedido do
# código; com o código, grava o login na pasta da conta.
CLAUDE_FALSO = r"""#!/bin/sh
[ "$1 $2" = "auth login" ] || exit 2
printf 'Opening browser to sign in\342\200\246\r\n'
printf 'If the browser did not open, visit: \033]8;;https://claude.com/cai/oauth/authorize?code=true&state=abc\033\\https://claude.com/cai/oauth/authorize?code=true&state=abc\033]8;;\033\\\r\n'
printf '\033[1mPaste code here if prompted >\033[0m '
read -r codigo
printf '{"codigo":"%s"}' "$codigo" > "$CLAUDE_CONFIG_DIR/.credentials.json"
printf 'Login successful.\r\n'
"""

# Como o `codex login --device-auth`: o link e o código de uso único; termina quando autorizado.
CODEX_FALSO = r"""#!/bin/sh
[ "$1 $2" = "login --device-auth" ] || exit 2
[ -d "$CODEX_HOME" ] || exit 3
printf 'Open https://auth.openai.com/codex/device and enter the code ABCD-1234\r\n'
sleep 0.3
printf '{}' > "$CODEX_HOME/auth.json"
printf 'Successfully logged in\r\n'
"""


@pytest.fixture
def agentes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "bin"
    pasta.mkdir()
    for nome, script in (("claude", CLAUDE_FALSO), ("codex", CODEX_FALSO)):
        (pasta / nome).write_text(script)
        (pasta / nome).chmod(0o755)
    monkeypatch.setenv("PATH", f"{pasta}:{os.environ['PATH']}")
    return pasta


def _ate(ls: logins.Logins, id_: str, condicao: str) -> dict[str, object]:
    for _ in range(50):
        r = ls.ler(id_, 0.2)
        if condicao in str(r["texto"]) or r["codigo"] is not None:
            return r
        time.sleep(0.05)
    raise AssertionError(f"não apareceu: {condicao}")


def test_claude_mostra_o_link_limpo_e_recebe_o_codigo(tmp_path: Path, agentes: Path) -> None:
    conta = contas.Conta("claude:t", "claude", "Teste", pasta=str(tmp_path / "conta-claude"))
    ls = logins.Logins()
    ls.abrir(conta)
    r = _ate(ls, conta.id, "Paste code")
    assert r["links"] == ["https://claude.com/cai/oauth/authorize?code=true&state=abc"]
    assert "\x1b" not in str(r["texto"]) and "]8;;" not in str(r["texto"])
    assert r["ativo"] is True and r["codigo"] is None
    ls.escrever(conta.id, "  codigo-do-site#abc  ")
    r = _ate(ls, conta.id, "Login successful")
    for _ in range(50):
        if (r := ls.ler(conta.id, 0.2))["codigo"] is not None:
            break
    assert r["codigo"] == 0
    assert conta.login.read_text() == '{"codigo":"codigo-do-site#abc"}'
    ls.fechar(conta.id)
    assert ls.ler(conta.id)["ativo"] is False


def test_codex_mostra_link_e_codigo_e_termina_sozinho(tmp_path: Path, agentes: Path) -> None:
    """Conta nova: a pasta ainda não existe, e o Codex de verdade a recusaria."""
    conta = contas.Conta("codex:t", "codex", "Teste", pasta=str(tmp_path / "conta-codex"))
    ls = logins.Logins()
    ls.abrir(conta)
    r = _ate(ls, conta.id, "Successfully logged in")
    assert r["links"] == ["https://auth.openai.com/codex/device"]
    assert "ABCD-1234" in str(r["texto"])
    for _ in range(50):
        if (r := ls.ler(conta.id, 0.2))["codigo"] is not None:
            break
    assert r["codigo"] == 0 and conta.login.is_file()


def test_codigo_so_com_login_em_andamento_e_sem_quebra_de_linha(
    tmp_path: Path, agentes: Path
) -> None:
    ls = logins.Logins()
    with pytest.raises(contas.ContaErro, match="não está em andamento"):
        ls.escrever("claude:t", "x")
    conta = contas.Conta("claude:t", "claude", "Teste", pasta=str(tmp_path / "c"))
    ls.abrir(conta)
    with pytest.raises(contas.ContaErro, match="Código inválido"):
        ls.escrever(conta.id, "abc\nrm -rf ~")  # uma linha só: nada de comando extra no terminal
    ls.fechar(conta.id)


def test_sem_o_agente_na_maquina(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(contas.ContaErro, match="Claude indisponível"):
        logins.Logins().abrir(contas.Conta("claude:t", "claude", "T", pasta=str(tmp_path / "c")))
