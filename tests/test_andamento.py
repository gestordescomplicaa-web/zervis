"""A barra de carregamento (ADR 0064): o rótulo e o tempo esperado de cada passo, das médias reais
da Atividade e das latências, gravados para a Imersão e o painel."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import tool

from zervis.cerebro import ferramentas
from zervis.rosto import andamento as an


def test_rotulos_e_padrao() -> None:
    assert an.rotulo("mcp__jarvis__pesquisa_profunda") == "Pesquisando a fundo na internet"
    assert an.rotulo("whatsapp_enviar") == "Enviando no WhatsApp"
    assert an.rotulo("mcp__navegador__browser_click") == "Browser click"  # sem rótulo: o nome


def test_esperas_sao_a_mediana_real_de_cada_ferramenta() -> None:
    registros = [
        {"tipo": "execucao", "ferramenta": "mcp__jarvis__internet_pesquisar", "duracao_ms": ms}
        for ms in (9000, 11000, 30000)
    ] + [
        {"tipo": "falha", "ferramenta": "mcp__jarvis__internet_pesquisar", "duracao_ms": 99000},
        {"tipo": "execucao", "ferramenta": "mcp__jarvis__imagem_buscar", "duracao_ms": 2500},
        {"tipo": "execucao", "titulo": "sem ferramenta"},
    ]
    assert an.esperas_da_atividade(registros) == {"internet_pesquisar": 11.0, "imagem_buscar": 2.5}


def test_pensar_e_a_mediana_do_cerebro_ate_a_primeira_frase(tmp_path: Path) -> None:
    linhas = [
        {"etapas_ms": {"cerebro": 1000, "formacao_frase": 1000}},
        {"etapas_ms": {"cerebro": 3000, "formacao_frase": 1000}},
        {"etapas_ms": {"cerebro": 2000}},
        {"etapas_ms": {"fim_de_turno": 900}},  # sem cérebro (comando local): não conta
    ]
    (tmp_path / "2026-11-04.jsonl").write_text(
        "\n".join(json.dumps(x) for x in linhas) + "\nlixo\n"
    )
    assert an.pensar_das_latencias(tmp_path) == 2.0
    assert an.pensar_das_latencias(tmp_path / "vazia") == an.PENSAR_S


def test_grava_o_passo_para_a_tela(tmp_path: Path) -> None:
    a = an.Andamento(tmp_path, agora=lambda: 1000.0)
    a.configurar(tmp_path, {"pagina_ler": 6.0}, 2.5)
    a.ferramenta("mcp__jarvis__pagina_ler")
    assert json.loads((tmp_path / an.NOME).read_text()) == {
        "rotulo": "Lendo a página", "esperado_s": 6.0, "ts": 1000.0,
    }  # fmt: skip
    a.ferramenta("mcp__jarvis__nova_coisa")
    assert a.para_tela()["esperado_s"] == an.FERRAMENTA_S
    a.pensando()
    assert a.para_tela() == {"rotulo": "Pensando na resposta", "esperado_s": 2.5, "ts": 1000.0}


def test_cada_ferramenta_avisa_o_inicio_e_o_fim(monkeypatch: pytest.MonkeyPatch) -> None:
    passos: list[str] = []
    falso = an.Andamento()
    monkeypatch.setattr(falso, "ferramenta", lambda nome: passos.append(f"começou {nome}"))
    monkeypatch.setattr(falso, "pensando", lambda: passos.append("pensando"))
    monkeypatch.setattr(an, "PADRAO", falso)

    @tool("pagina_ler", "Lê.", {"url": str})
    async def pagina_ler(args: dict[str, Any]) -> dict[str, Any]:
        passos.append("rodou")
        return {"content": [{"type": "text", "text": "ok"}]}

    @tool("quebra", "Quebra.", {})
    async def quebra(args: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("caiu")

    async def chamar(f: Any, args: dict[str, Any]) -> Any:
        return await ferramentas.auditada(f).handler(args)

    asyncio.run(chamar(pagina_ler, {"url": "https://a.com"}))
    with pytest.raises(RuntimeError):
        asyncio.run(chamar(quebra, {}))
    assert passos == ["começou pagina_ler", "rodou", "pensando", "começou quebra", "pensando"]
