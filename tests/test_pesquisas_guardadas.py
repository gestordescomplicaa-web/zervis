"""As pesquisas guardadas (ADR 0060): gravar, listar, buscar sem acento, abrir, apagar, a resumida
também guardada, e as ferramentas que reabrem pela voz."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import profunda as ferramentas_profunda
from zervis.pesquisa.guardadas import Guardadas, guardando
from zervis.portal.acoes.pagina import Servicos
from zervis.portal.acoes.pesquisas import AcoesPesquisas
from zervis.portal.servidor import PedidoInvalido

EMBALAGENS = {
    "pergunta": "Fornecedores de embalagens sustentáveis em São Paulo",
    "consultas": ["embalagem biodegradável SP"],
    "fontes": [
        {"n": 1, "titulo": "G6", "url": "https://g6.exemplo/", "site": "g6.exemplo",
         "trechos": ["Polpa moldada sob medida."]},
        {"n": 2, "titulo": "Oeko", "url": "https://oeko.exemplo/", "site": "oeko.exemplo",
         "trechos": ["Bioplástico compostável."]},
    ],
    "outros_resultados": [{"titulo": "x", "url": "https://x.exemplo/", "trecho": ""}],
}  # fmt: skip


class Relogio:
    t = 1_793_740_500.0

    def __call__(self) -> float:
        self.t += 60
        return self.t


def test_grava_lista_das_mais_novas_e_abre(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())
    a = g.gravar(EMBALAGENS)
    b = g.gravar(
        {
            "tipo": "resumida",
            "pergunta": "Notícias do varejo",
            "resumo": "Fontes: https://a.exemplo https://b.exemplo",
        }
    )
    lista = g.listar()
    assert [p["id"] for p in lista] == [b, a]
    assert lista[1]["fontes"] == 2 and lista[1]["sites"] == ["g6.exemplo", "oeko.exemplo"]
    assert lista[0]["tipo"] == "resumida" and lista[0]["fontes"] == 2  # os links do resumo
    aberta = g.ler(a)
    assert aberta["pergunta"].startswith("Fornecedores") and aberta["tipo"] == "profunda"


def test_busca_sem_acento_pelos_trechos_e_pela_pergunta(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())
    a = g.gravar(EMBALAGENS)
    g.gravar({"pergunta": "Concorrentes da Loja X", "fontes": []})
    assert [p["id"] for p in g.listar("embalagens sao paulo")] == [a]
    assert [p["id"] for p in g.listar("compostavel")] == [a]  # está só num trecho
    assert g.listar("bicicleta") == []


def test_id_invalido_ou_apagado_nao_abre_e_nao_sai_da_pasta(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())
    a = g.gravar(EMBALAGENS)
    for errado in ("../../etc/passwd", "", "20261103-191500-zzzzzz"):
        with pytest.raises(ValueError):
            g.ler(errado)
    g.apagar(a)
    with pytest.raises(ValueError, match="não existe mais"):
        g.ler(a)
    assert g.listar() == []


def test_a_resumida_tambem_fica_guardada(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())

    async def pesquisar(pedido: str) -> str:
        return f"Resumo de {pedido}. Fontes: https://a.exemplo"

    async def pedir() -> str:
        return await guardando(pesquisar, g)("preço do aço hoje")

    texto = asyncio.run(pedir())
    assert texto.startswith("Resumo de preço do aço")
    [p] = g.listar("aço")
    assert p["tipo"] == "resumida" and g.ler(p["id"])["resumo"] == texto


def test_reabrir_pela_voz(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())
    a = g.gravar(EMBALAGENS)
    f: dict[str, Any] = {
        t.name: t.handler for t in ferramentas_profunda.ferramentas(SimpleNamespace(), pesquisas=g)
    }
    achadas = json.loads(
        asyncio.run(f["pesquisas_guardadas"]({"busca": "embalagens"}))["content"][0]["text"]
    )
    assert [p["id"] for p in achadas["pesquisas"]] == [a]
    assert achadas["pesquisas"][0]["em"].count("/") == 2  # a data legível, para falar
    aberta = json.loads(asyncio.run(f["pesquisa_guardada"]({"id": a}))["content"][0]["text"])
    assert aberta["fontes"][0]["trechos"] == ["Polpa moldada sob medida."]
    assert "outros_resultados" not in aberta and "Fontes:" in aberta["dica"]
    erro = asyncio.run(f["pesquisa_guardada"]({"id": "nada"}))
    assert erro["is_error"]
    nada = json.loads(
        asyncio.run(f["pesquisas_guardadas"]({"busca": "bicicleta"}))["content"][0]["text"]
    )
    assert nada["pesquisas"] == []
    for nome in ("pesquisas_guardadas", "pesquisa_guardada"):
        assert f"mcp__jarvis__{nome}" in LIVRES


def test_pagina_do_painel(tmp_path: Path) -> None:
    g = Guardadas(tmp_path, Relogio())
    a = g.gravar(EMBALAGENS)
    pagina = AcoesPesquisas(SimpleNamespace(), Servicos({"pesquisas": lambda: g}))
    assert [p["id"] for p in pagina.lista_de_pesquisas()["pesquisas"]] == [a]
    assert pagina.buscar_pesquisas({"busca": "  oeko  "})["pesquisas"][0]["id"] == a
    assert pagina.ler_pesquisa({"id": a})["fontes"][1]["site"] == "oeko.exemplo"
    with pytest.raises(PedidoInvalido):
        pagina.ler_pesquisa({"id": "../x"})
    assert pagina.apagar_pesquisa({"id": a}) == {"pesquisas": []}
