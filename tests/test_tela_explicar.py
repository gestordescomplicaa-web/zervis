"""tela_explicar: a cena que o Zé escreve chega à tela como uma ação só (ADR 0047)."""

import asyncio
import json
from pathlib import Path
from typing import Any

from zervis.cerebro.ferramentas import LEITURA
from zervis.cerebro.ferramentas import tela as ferramentas_da_tela
from zervis.rosto.tela import CENA, Tela, TelaErro


class TelaFalsa(Tela):
    def __init__(self) -> None:
        super().__init__(Path("/nao-existe"))
        self.pedidos: list[tuple[list[dict[str, Any]], bool]] = []

    def agir(
        self,
        acoes: list[dict[str, Any]],
        trazer: bool = True,
        espera_s: float | None = None,
        esperar_fim: bool | None = None,
    ) -> dict[str, Any]:
        self.pedidos.append((acoes, trazer))
        return {"resultados": [{"acao": CENA, "ok": True, "blocos": 2}], "estado": {"x": 1}}


def _explicar(tela: Tela | None, entrada: dict[str, Any]) -> dict[str, Any]:
    ferramenta = next(f for f in ferramentas_da_tela.ferramentas(tela) if f.name == "tela_explicar")

    async def rodar() -> dict[str, Any]:
        return await ferramenta.handler(entrada)

    return asyncio.run(rodar())


CENA_MCP = {
    "titulo": "Como funciona o MCP",
    "passos": [
        {"fala": "MCP liga a IA a ferramentas.", "blocos": [{"tipo": "titulo", "texto": "MCP"}]},
        {"fala": "Cada sistema vira um servidor.", "blocos": [{"tipo": "rede", "nos": ["n8n"]}]},
    ],
}


def test_a_cena_vai_inteira_numa_acao_e_volta_so_o_resultado() -> None:
    tela = TelaFalsa()
    resposta = _explicar(tela, {**CENA_MCP, "trazer": False})
    assert tela.pedidos == [([{"acao": "explicar", "cena": CENA_MCP}], False)]
    assert json.loads(resposta["content"][0]["text"]) == {"resultados": tela.agir([])["resultados"]}


def test_cena_sem_passos_ou_grande_demais_nem_chega_na_tela() -> None:
    tela = TelaFalsa()
    assert _explicar(tela, {"titulo": "x", "passos": []}).get("is_error")
    enorme = {"titulo": "x", "passos": [{"fala": "a" * 20_000}]}
    assert _explicar(tela, enorme).get("is_error")
    assert _explicar(None, CENA_MCP).get("is_error")
    assert tela.pedidos == []


def test_explicar_e_aceito_pela_tela_e_livre_como_as_outras_da_tela(tmp_path: Path) -> None:
    tela = Tela(tmp_path)
    try:
        tela.agir([{"acao": "explicar", "cena": CENA_MCP}])
    except TelaErro as erro:
        assert "fechada" in str(erro)  # passou da checagem das ações; só a janela está fechada
    assert "tela_explicar" in LEITURA


def test_o_holograma_3d_tem_as_pecas_no_esquema_sem_referencias() -> None:
    # O modelo só preenche o que o esquema lista (teste de 29/10/2026): as peças precisam estar
    # lá por extenso, e sem $ref, que nem todo cliente de ferramentas resolve.
    ferramenta = next(f for f in ferramentas_da_tela.ferramentas(None) if f.name == "tela_explicar")
    esquema = ferramenta.input_schema
    bloco = esquema["properties"]["passos"]["items"]["properties"]["blocos"]["items"]
    assert "holograma" in bloco["properties"]["tipo"]["enum"]
    peca = bloco["properties"]["pecas"]["items"]["properties"]
    assert {"forma", "pos", "tam", "cor", "anim", "orbita", "de", "ate", "filhos"} <= set(peca)
    assert (
        "ligacao" in peca["forma"]["enum"] and "filhos" not in peca["filhos"]["items"]["properties"]
    )
    assert "$ref" not in json.dumps(esquema)


def test_o_mapa_pede_so_o_que_destacar_e_os_contornos_vem_do_arquivo() -> None:
    # ADR 0050: o modelo nunca desenha o mapa; diz a região, os destaques pelo nome e as cidades.
    ferramenta = next(f for f in ferramentas_da_tela.ferramentas(None) if f.name == "tela_explicar")
    passo = ferramenta.input_schema["properties"]["passos"]["items"]
    campos = passo["properties"]["blocos"]["items"]["properties"]
    assert "mapa" in campos["tipo"]["enum"]
    assert {"regiao", "destaques", "relevo", "pontos", "ligar"} <= set(campos)
    assert set(campos["destaques"]["items"]["properties"]) == {"nome", "valor", "rotulo"}
    assert "nunca desenhe mapa com peças" in ferramenta.description
