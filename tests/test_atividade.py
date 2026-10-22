"""A atividade do Zé (ADR 0025): o que ele executou, como foi autorizado e onde tropeçou."""

import asyncio
import stat
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import SdkMcpTool

from zervis import atividade
from zervis.atividade import Atividade, e_correcao, limpar, titulo_da_ferramenta
from zervis.cerebro.ferramentas import auditada
from zervis.sistema import catalogo


def test_segredos_nunca_entram_e_texto_longo_e_cortado() -> None:
    limpo = limpar(
        {
            "senha": "uma senha boa",
            "api_key": "x",
            "texto": "use sk-ant-api03-abcdefghijk e pronto",
            "longo": "a" * 1000,
            "lista": [{"token": "t"}],
        }
    )
    coberto = "•••"
    assert limpo["senha"] == limpo["api_key"] == coberto and limpo["lista"][0]["token"] == coberto
    assert "sk-ant" not in limpo["texto"] and len(limpo["longo"]) == atividade.TEXTO_MAX


def test_registra_lista_resume_e_guarda_so_para_quem_usa(tmp_path: Path) -> None:
    a = Atividade(tmp_path / "atividade.jsonl")
    a.registrar("execucao", "Omarchy: brightness-display 50%", autorizacao="livre (risco baixo)")
    a.origem = "voz remota"
    a.registrar("negada", "Omarchy: system-shutdown", motivo="sem a frase exata")
    a.registrar("estranho", "tipo desconhecido vira falha")
    itens = a.listar()
    assert [i["tipo"] for i in itens] == ["falha", "negada", "execucao"]
    assert itens[1]["origem"] == "voz remota" and itens[2]["origem"] == "voz"
    assert a.listar(tipos=("execucao",))[0]["autorizacao"] == "livre (risco baixo)"
    assert a.resumo()["negada"] == 1
    assert stat.S_IMODE(a.arquivo.stat().st_mode) == 0o600


def test_historico_crescente_continua_busca_sem_perder_registros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(atividade, "LIMITE_BYTES", 200)
    a = Atividade(tmp_path / "atividade.jsonl")
    for n in range(10):
        a.registrar("pedido", f"pedido número {n}")
    assert len(a.listar()) == 10
    assert a.buscar("pedido número 0")[0]["titulo"] == "pedido número 0"


def test_correcao_da_pessoa() -> None:
    assert e_correcao("Não, eu disse suspender") and e_correcao("você não entendeu")
    assert not e_correcao("Não quero mais") and not e_correcao("que horas são?")


def test_titulo_legivel_da_ferramenta() -> None:
    sistema = {"acao": "system-shutdown", "argumentos": []}
    assert (
        titulo_da_ferramenta("mcp__jarvis__sistema_executar", sistema) == "Omarchy: system-shutdown"
    )
    assert titulo_da_ferramenta("sessao_enviar", {"sessao": "Loja", "texto": "rode os testes"}) == (
        "sessao_enviar: Loja · rode os testes"
    )


def _ferramenta(resposta: Any) -> SdkMcpTool[Any]:
    async def fazer(entrada: dict[str, Any]) -> dict[str, Any]:
        if isinstance(resposta, Exception):
            raise resposta
        return dict(resposta)

    return SdkMcpTool("sistema_executar", "teste", {}, fazer)


def _rodar(ferramenta: SdkMcpTool[Any], entrada: dict[str, Any]) -> Any:
    async def chamar() -> Any:
        return await ferramenta.handler(entrada)

    return asyncio.run(chamar())


def test_cada_execucao_registrada_com_a_autorizacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = Atividade(tmp_path / "atividade.jsonl")
    monkeypatch.setattr(atividade, "PADRAO", a)
    entrada = {"acao": "system-suspend", "argumentos": []}
    a.autorizada("sistema_executar", "aprovada")
    ok = auditada(_ferramenta({"content": [{"type": "text", "text": "feito"}]}))
    _rodar(ok, entrada)
    erro = auditada(
        _ferramenta({"content": [{"type": "text", "text": "falhou"}], "is_error": True})
    )
    _rodar(erro, entrada)
    quebra = auditada(_ferramenta(RuntimeError("caiu")))
    with pytest.raises(RuntimeError):
        _rodar(quebra, entrada)
    falha_dura, falha, feito = a.listar()
    assert feito["tipo"] == "execucao" and feito["autorizacao"] == "aprovada"
    assert feito["titulo"] == "Omarchy: system-suspend" and feito["resultado"] == "feito"
    assert (
        falha["tipo"] == "falha" and falha["autorizacao"] == "livre"
    )  # a autorização é de uma vez
    assert falha_dura["erro"] == "RuntimeError: caiu"
    assert a.listar()[-1]["entrada"]


def test_suspender_existe_com_confirmacao_falada(tmp_path: Path) -> None:
    (tmp_path / "systemctl").write_text("#!/bin/sh\n")
    # Sem Omarchy (um servidor): suspender deixaria a máquina fora do ar até religá-la.
    assert "system-suspend" not in catalogo.carregar(tmp_path)
    (tmp_path / "omarchy-menu").write_text("#!/bin/sh\n")
    acao = catalogo.carregar(tmp_path)["system-suspend"]
    assert (acao.risco, acao.fixos, acao.caminho.name) == (2, ("suspend",), "systemctl")
    assert "system-suspend" not in catalogo.carregar(tmp_path / "vazia")
