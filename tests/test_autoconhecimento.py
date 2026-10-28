"""O Zé por ele mesmo (ADR 0043): o retrato, a ferramenta `ze_sobre` e a nota "Quem sou"."""

import asyncio
from types import SimpleNamespace
from typing import Any

from zervis.cerebro import ferramentas
from zervis.cerebro.ferramentas import sobre
from zervis.nucleo import autoconhecimento as a
from zervis.nucleo.servicos.cerebro import ServicoCerebro
from zervis.rosto import pasta

RETRATO = a.Retrato(
    cerebro="Codex, com o GPT-6 Luna",
    reserva="Claude",
    rapidas="o Claude pela assinatura, com o Sonnet 5.5, só no Live; respondendo agora",
    rapidas_agora=True,
    rapidas_modelo="Sonnet 5.5",
    voz="Fish Audio (Gojo), com o Cadu de reserva",
    escuta="Deepgram nova-3, em português",
    live="conectado agora, pelo navegador",
    modo="Live",
    acesso="pelo celular no endereço https://ze.exemplo.invalid, com senha e código",
    versao="0.1.0",
)


def test_quem_responde_diz_a_via_rapida_e_o_completo() -> None:
    assert a.quem_responde(RETRATO) == (
        "Na conversa, quem responde é a via rápida, com o Sonnet 5.5; o que pede ferramenta ou "
        "ação vai ao cérebro completo (Codex, com o GPT-6 Luna)."
    )
    sem = a.Retrato(cerebro="Claude, com o Sonnet 5.5")
    assert a.quem_responde(sem) == "Quem responde é o cérebro completo: Claude, com o Sonnet 5.5."


def test_texto_traz_o_agora_e_onde_mudar_cada_coisa() -> None:
    t = a.texto(RETRATO)
    assert "## Agora" in t and "## Onde mudar" in t
    assert "Fish Audio (Gojo)" in t and "Live" in t and "0.1.0" in t
    assert "Voz → Voz do Zé" in t and "Modelos → Respostas rápidas" in t
    assert "Reserva do cérebro" in t and "Contas dos agentes" not in t  # campo vazio não entra


def test_resumo_para_a_via_rapida_e_curto_e_manda_nao_inventar() -> None:
    r = a.resumo(RETRATO)
    assert r.startswith("## Você agora")
    assert "Sonnet 5.5" in r and "Gojo" in r and "sem inventar" in r
    assert len(r) < 800  # entra em toda resposta rápida


def test_a_ferramenta_ze_sobre_le_o_retrato_na_hora_e_passa_sem_perguntar() -> None:
    chamadas: list[int] = []

    def ler() -> str:
        chamadas.append(1)
        return a.texto(RETRATO)

    [ferramenta] = sobre.ferramentas(ler)

    async def chamar() -> Any:
        return await ferramenta.handler({})

    resposta = asyncio.run(chamar())
    assert "## Agora" in resposta["content"][0]["text"] and chamadas == [1]
    assert f"mcp__{ferramentas.SERVIDOR}__ze_sobre" in ferramentas.LIVRES
    assert sobre.ferramentas(None) == []


def test_a_nota_quem_sou_usa_o_retrato() -> None:
    nota = pasta.quem_sou(pasta.Conexoes(cerebro="x", agora=a.texto(RETRATO)))
    assert "## Agora" in nota and "## Cérebro agora" not in nota
    antiga = pasta.quem_sou(pasta.Conexoes(cerebro="Codex"))
    assert "## Cérebro agora" in antiga  # sem retrato, o resumo de antes


def test_a_via_rapida_sobe_sabendo_que_e_ela_quem_responde() -> None:
    nucleo = SimpleNamespace(
        retrato=lambda: a.Retrato(cerebro="Codex, com o GPT-6 Luna", voz="Cadu"),
        cfg={"via_rapida": {"ligada": True, "motor": "plano", "modelo": "claude-sonnet-5-5"}},
    )
    voce = ServicoCerebro(nucleo)._voce_agora()
    assert "via rápida, com o Sonnet 5.5" in voce and "Voz: Cadu." in voce
    assert ServicoCerebro(SimpleNamespace())._voce_agora() == ""
