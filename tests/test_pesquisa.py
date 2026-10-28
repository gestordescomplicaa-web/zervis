"""A pesquisa na internet do próprio Zé (ADR 0044), sem sessão: caso real de 27/10/2026, em que
o Zé com o Codex disse "a ferramenta de pesquisa não está disponível" e uma sessão aberta só
para pesquisar gerou nove pedidos de aprovação."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro import contas, ferramentas, pesquisa
from zervis.cerebro.codex_rpc import CodexErro, comando
from zervis.cerebro.contas import Conta
from zervis.cerebro.ferramentas import pesquisa as g_pesquisa
from zervis.nucleo import autoconhecimento


def _chamar(pesquisar: Any, entrada: dict[str, Any]) -> dict[str, Any]:
    (ferramenta,) = g_pesquisa.ferramentas(pesquisar)

    async def chamar() -> dict[str, Any]:
        return await ferramenta.handler(entrada)

    return asyncio.run(chamar())


def test_a_ferramenta_pesquisa_e_passa_sem_perguntar() -> None:
    pedidos: list[str] = []

    async def pesquisar(pedido: str) -> str:
        pedidos.append(pedido)
        return "O dólar fechou em R$ 5,34.\n\nFontes: https://exemplo.com"

    resposta = _chamar(pesquisar, {"pedido": "  cotação   do dólar hoje "})
    assert pedidos == ["cotação do dólar hoje"]
    assert "5,34" in resposta["content"][0]["text"]
    assert not resposta.get("is_error")
    assert f"mcp__{ferramentas.SERVIDOR}__internet_pesquisar" in ferramentas.LIVRES


def test_sem_pedido_ou_sem_resposta_e_erro_curto() -> None:
    async def falha(_pedido: str) -> str:
        raise pesquisa.PesquisaErro("A pesquisa na internet não respondeu.")

    assert _chamar(falha, {"pedido": ""})["is_error"]
    resposta = _chamar(falha, {"pedido": "notícias"})
    assert resposta["is_error"]
    assert resposta["content"][0]["text"] == "A pesquisa na internet não respondeu."


def test_so_a_consulta_de_pesquisa_liga_a_busca_do_codex(tmp_path: Path) -> None:
    conta = Conta("codex:x", "codex", "X", str(tmp_path))
    assert 'web_search="disabled"' in comando(conta)  # o cérebro continua sem
    busca = comando(conta, busca=True)
    assert 'web_search="live"' in busca
    assert "features.shell_tool=false" in busca  # e a pesquisa não ganha mais nada


def test_conta_de_provedor_ou_sem_login_nao_pesquisa_pelo_codex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conta = Conta("codex:x", "codex", "X", str(tmp_path))

    class Contas:
        def em_uso(self, _agente: str) -> Conta:
            return conta

    monkeypatch.setattr(contas, "Contas", Contas)
    assert pesquisa._conta_codex() is None  # sem login
    (tmp_path / "auth.json").write_text("{}")
    assert pesquisa._conta_codex() is conta
    conta = Conta("codex:y", "codex", "Y", str(tmp_path), provedor="deepseek")
    assert pesquisa._conta_codex() is None  # outro modelo pela chave não tem a busca do Codex


def test_sem_o_codex_a_pesquisa_vai_pelo_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho: list[str] = []

    async def codex(_conta: Conta, _texto: str, _pasta: Path, gastou: Any) -> str:
        caminho.append("codex")
        gastou({"input_tokens": 50}, "Codex")  # a tentativa que falhou também gastou
        raise CodexErro("limite_de_uso")

    async def claude(texto: str, _pasta: Path, modelo: str, gastou: Any) -> str:
        caminho.append(f"claude:{modelo}")
        gastou({"input_tokens": 70}, "Claude")
        assert texto.startswith("[terça-feira, 27/10/2026, 22:03] ")
        return "Resumo.\n\nFontes: https://exemplo.com"

    monkeypatch.setattr(pesquisa, "_conta_codex", lambda: Conta("codex:x", "codex", "X", "/"))
    monkeypatch.setattr(pesquisa, "_pelo_codex", codex)
    monkeypatch.setattr(pesquisa, "_pelo_claude", claude)
    gastos: list[tuple[int, str]] = []
    texto = asyncio.run(
        pesquisa.pesquisar(
            "notícias",
            "[terça-feira, 27/10/2026, 22:03]",
            tmp_path,
            "sonnet",
            lambda uso, por: gastos.append((uso["input_tokens"], por)),
        )
    )
    assert texto.startswith("Resumo.")
    assert caminho == ["codex", "claude:sonnet"]
    assert gastos == [(50, "Codex"), (70, "Claude")]


def test_o_ze_sabe_que_pesquisa_na_internet() -> None:
    retrato = autoconhecimento.Retrato(cerebro="Codex")
    assert "internet_pesquisar" in autoconhecimento.texto(retrato)
    assert "Pesquisa na internet: sim" in autoconhecimento.resumo(retrato)
