"""A chave da OpenAI no Codex pelo painel, sem terminal (ADR 0035)."""

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import acesso, contas

CODEX_FALSO = """#!/bin/sh
# Como o Codex: `login --with-api-key` lê a chave da entrada e grava o login da conta.
[ "$1 $2" = "login --with-api-key" ] || exit 2
[ -d "$CODEX_HOME" ] || { echo "CODEX_HOME does not exist" >&2; exit 1; }
read -r chave
[ "${chave#sk-}" != "$chave" ] || { echo "chave inválida" >&2; exit 1; }
printf '{"OPENAI_API_KEY":"%s"}' "$chave" > "$CODEX_HOME/auth.json"
"""


@pytest.fixture
def codex_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "bin"
    pasta.mkdir()
    (pasta / "codex").write_text(CODEX_FALSO)
    (pasta / "codex").chmod(0o755)
    monkeypatch.setenv("PATH", f"{pasta}:{os.environ['PATH']}")
    return pasta


def test_a_chave_chega_ao_codex_da_conta_e_a_conta_fica_com_login(
    tmp_path: Path, codex_falso: Path
) -> None:
    conta = contas.Conta("c1", "codex", "Trabalho", pasta=str(tmp_path / "conta"))
    assert not conta.onde.exists()  # conta nova: o Codex de verdade recusa sem a pasta
    acesso.chave_no_codex("  sk-teste-123  ", conta)
    assert conta.login.read_text() == '{"OPENAI_API_KEY":"sk-teste-123"}'


def test_chave_recusada_pelo_codex_vira_mensagem_curta(tmp_path: Path, codex_falso: Path) -> None:
    conta = contas.Conta("c1", "codex", "Trabalho", pasta=str(tmp_path / "conta"))
    with pytest.raises(acesso.AcessoErro, match=r"^O Codex recusou a chave\.$"):
        acesso.chave_no_codex("nao-e-chave", conta)
    assert not conta.login.exists()


def test_a_chave_vai_pela_entrada_e_nunca_na_linha_de_comando(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Na linha de comando, outro usuário da máquina veria a chave em `ps`."""
    monkeypatch.setattr("jarvis.cerebro.acesso.shutil.which", lambda nome: "/x/codex")
    chamadas: list[dict[str, Any]] = []

    def rodar(args: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append({"args": args, **kw})
        return subprocess.CompletedProcess(args, 0, "", "")

    conta = contas.Conta("c1", "codex", "Trabalho", pasta=str(tmp_path / "trabalho"))
    acesso.chave_no_codex("sk-segredo", conta, rodar)
    [c] = chamadas
    assert c["args"] == ["/x/codex", "login", "--with-api-key"]
    assert c["input"] == "sk-segredo" and "sk-segredo" not in " ".join(c["args"])
    assert c["env"]["CODEX_HOME"] == str(tmp_path / "trabalho") and c["timeout"] == 30


@pytest.mark.parametrize("chave", ["", "   ", "sk com espaço", "x" * 401])
def test_chave_invalida_nem_chega_ao_codex(chave: str) -> None:
    def rodar(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("não devia rodar o Codex")

    with pytest.raises(acesso.AcessoErro, match="Informe a chave"):
        acesso.chave_no_codex(chave, None, rodar)


def test_sem_codex_na_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jarvis.cerebro.acesso.shutil.which", lambda nome: None)
    with pytest.raises(acesso.AcessoErro, match="Codex indisponível"):
        acesso.chave_no_codex("sk-x")
