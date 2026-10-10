"""As ferramentas do cérebro sobre as sessões de código do Zé (sem o Orca, ADR 0015)."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from jarvis.cerebro.ferramentas import LIVRES, SERVIDOR
from jarvis.cerebro.ferramentas import sessoes as g
from jarvis.oficina.sessoes import Sessao, Sessoes


def chamar(ferramentas: dict[str, Any], nome: str, args: dict[str, Any]) -> Any:
    r = asyncio.run(ferramentas[nome](args))
    texto = r["content"][0]["text"]
    return (texto, True) if r.get("is_error") else (json.loads(texto), False)


def test_delegar_acompanhar_e_ler_uma_sessao(tmp_path: Path) -> None:
    projeto = tmp_path / "casa" / "loja"
    projeto.mkdir(parents=True)

    async def rodar(sessoes: Sessoes, s: Sessao, texto: str) -> str:
        sessoes.anotar(s.id, "agente", f"Feito: {texto}")
        return "Feito."

    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), rodar=rodar)
    f = {t.name: t.handler for t in g.ferramentas(sessoes)}
    criada, erro = chamar(
        f, "sessao_criar", {"nome": "Loja", "pasta": str(projeto), "tarefa": "testes"}
    )
    assert not erro and criada["criada"] and criada["pasta"] == str(projeto)
    fim = time.monotonic() + 5
    while sessoes.ler(criada["id"]).estado == "trabalhando" and time.monotonic() < fim:
        time.sleep(0.02)
    (item,) = chamar(f, "sessoes_listar", {})[0]
    assert (
        item["nome"] == "Loja" and item["estado"] == "parada" and item["ultimo_recado"] == "Feito."
    )
    lido, _ = chamar(f, "sessao_ler", {"id": criada["id"]})
    assert [m["quem"] for m in lido["mensagens"]][-2:] == ["usuario", "agente"]
    assert lido["mensagens"][-1]["texto"] == "Feito: testes"
    # Fora das pastas permitidas não vira sessão; sem pasta nem projeto novo, avisa.
    assert chamar(f, "sessao_criar", {"nome": "x", "pasta": "/etc"})[1]
    texto, erro = chamar(f, "sessao_criar", {"nome": "x"})
    assert erro and "pasta do projeto" in texto


def test_ler_e_listar_sao_livres_e_o_resto_pede_aprovacao() -> None:
    livres = {n.removeprefix(f"mcp__{SERVIDOR}__") for n in LIVRES}
    assert {"sessoes_listar", "sessao_ler"} <= livres
    assert not {"sessao_criar", "sessao_enviar", "sessao_parar"} & livres
    assert g.ferramentas(None) == []
