"""Os contornos do bloco mapa (ADR 0050): o gerador e o arquivo que vai com a Imersão."""

import json
from pathlib import Path

from zervis.imersivo import gerar_mapas


def _decodificar(anel: list[int]) -> list[tuple[float, float]]:
    pontos, x, y = [], 0, 0
    for i in range(0, len(anel), 2):
        x, y = x + anel[i], y + anel[i + 1]
        pontos.append((x / 100, y / 100))
    return pontos


def test_simplifica_sem_perder_os_cantos_e_codifica_em_deltas() -> None:
    quadrado = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.001), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]
    assert gerar_mapas.simplificar(quadrado, 0.01) == [q for q in quadrado if q != (1.0, 0.0)]
    r = gerar_mapas.regiao({"type": "Polygon", "coordinates": [quadrado]}, 0.01, 0.0)
    assert r is not None and r["c"] == [1.0, 1.0]
    assert _decodificar(r["p"][0][0]) == [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]


def test_ilhotas_menores_que_o_minimo_somem() -> None:
    ilhota = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1), (0.0, 0.0)]
    assert gerar_mapas.regiao({"type": "Polygon", "coordinates": [ilhota]}, 0.0, 0.02) is None


def test_o_arquivo_da_imersao_tem_os_27_estados_e_os_paises() -> None:
    dados = json.loads(Path(gerar_mapas.DESTINO).read_text())
    siglas = {e["id"] for e in dados["brasil"]}
    assert len(siglas) == 27 and {"SP", "DF", "AC", "RS"} <= siglas
    sp = next(e for e in dados["brasil"] if e["id"] == "SP")
    assert sp["nome"] == "São Paulo" and sp["grupo"] == "Sudeste"
    lon, lat = sp["c"]
    assert -53.5 < lon < -44 and -25.5 < lat < -19.5  # o centro cai dentro do estado
    paises = {e["id"]: e for e in dados["mundo"]}
    assert paises["BR"]["nome"] == "Brasil" and paises["BR"]["grupo"] == "america_do_sul"
    assert {"PT", "AO", "MZ", "US", "FR", "DE", "JP"} <= set(paises)
    assert "IBGE" in dados["fontes"]["brasil"] and "Natural Earth" in dados["fontes"]["mundo"]
