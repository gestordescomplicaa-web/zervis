"""Gera `web/jarvis-mapas.json`: os contornos reais que o bloco mapa desenha (ADR 0050).

O Zé não desenha mapa de cabeça: a tela recebe só o que destacar (estados, países, valores,
cidades) e os contornos vêm daqui. Rode de novo só para trocar as fontes:

    curl -o uf.json 'https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF'
    curl -o ufs.json https://servicodados.ibge.gov.br/api/v1/localidades/estados
    curl -o ne50.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
    python -I zervis/imersivo/gerar_mapas.py uf.json ufs.json ne50.geojson

Estados: malha do IBGE (dados públicos). Países: Natural Earth 1:50m (domínio público).
Coordenadas em centésimos de grau, cada anel em deltas: [x0, y0, dx1, dy1, ...].
"""

import json
import math
import sys
from pathlib import Path
from typing import Any

Ponto = tuple[float, float]
DESTINO = Path(__file__).with_name("web") / "jarvis-mapas.json"
CONTINENTES = {
    "South America": "america_do_sul",
    "North America": "america_do_norte",
    "Europe": "europa",
    "Africa": "africa",
    "Asia": "asia",
    "Oceania": "oceania",
}


def _distancia(p: Ponto, a: Ponto, b: Ponto) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def simplificar(anel: list[Ponto], tolerancia: float) -> list[Ponto]:
    """Douglas-Peucker sem recursão; o anel continua fechado nas pontas."""
    if len(anel) < 5:
        return anel
    manter = [False] * len(anel)
    manter[0] = manter[-1] = True
    pilha = [(0, len(anel) - 1)]
    while pilha:
        i, j = pilha.pop()
        maior, k = 0.0, -1
        for m in range(i + 1, j):
            d = _distancia(anel[m], anel[i], anel[j])
            if d > maior:
                maior, k = d, m
        if k >= 0 and maior > tolerancia:
            manter[k] = True
            pilha += [(i, k), (k, j)]
    return [p for p, ok in zip(anel, manter, strict=True) if ok]


def _area(anel: list[Ponto]) -> float:
    lados = zip(anel, anel[1:] + anel[:1], strict=True)
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in lados)) / 2


def _centro(anel: list[Ponto]) -> list[float]:
    a = cx = cy = 0.0
    for p, q in zip(anel, anel[1:] + anel[:1], strict=True):
        f = p[0] * q[1] - q[0] * p[1]
        a, cx, cy = a + f, cx + (p[0] + q[0]) * f, cy + (p[1] + q[1]) * f
    if not a:
        return [round(anel[0][0], 2), round(anel[0][1], 2)]
    return [round(cx / (3 * a), 2), round(cy / (3 * a), 2)]


def _codificar(anel: list[Ponto]) -> list[int]:
    saida: list[int] = []
    ax = ay = 0
    for x, y in anel:
        ix, iy = round(x * 100), round(y * 100)
        if saida and ix == ax and iy == ay:
            continue
        saida += [ix - ax, iy - ay]
        ax, ay = ix, iy
    return saida


def regiao(geometria: dict[str, Any], tolerancia: float, menor: float) -> dict[str, Any] | None:
    poligonos = geometria["coordinates"]
    if geometria["type"] == "Polygon":
        poligonos = [poligonos]
    feitos, maior, centro = [], 0.0, [0.0, 0.0]
    for poligono in poligonos:
        aneis = [simplificar([(p[0], p[1]) for p in anel], tolerancia) for anel in poligono]
        if len(aneis[0]) < 4 or _area(aneis[0]) < menor:
            continue  # ilhotas que nem aparecem
        if (a := _area(aneis[0])) > maior:
            maior, centro = a, _centro(aneis[0])
        feitos.append([_codificar(anel) for anel in aneis if len(anel) >= 4])
    return {"c": centro, "p": feitos} if feitos else None


def gerar(malha_uf: Path, nomes_uf: Path, paises: Path) -> dict[str, Any]:
    nomes = {str(u["id"]): u for u in json.loads(nomes_uf.read_text())}
    estados = []
    for f in json.loads(malha_uf.read_text())["features"]:
        uf = nomes[f["properties"]["codarea"]]
        r = regiao(f["geometry"], 0.015, 0.0)
        if r:
            estados.append(
                {"id": uf["sigla"], "nome": uf["nome"], "grupo": uf["regiao"]["nome"], **r}
            )
    mundo = []
    for f in json.loads(paises.read_text())["features"]:
        p = f["properties"]
        if p["CONTINENT"] == "Antarctica":
            continue
        r = regiao(f["geometry"], 0.06, 0.02)
        iso = p["ISO_A2_EH"] if p["ISO_A2_EH"] != "-99" else p["ADM0_A3"]
        if r:
            outros = {p["NAME"], p["NAME_EN"], p["NAME_LONG"], p["ISO_A3_EH"], p["ADM0_A3"]}
            mundo.append(
                {
                    "id": iso,
                    "nome": p["NAME_PT"] or p["NAME"],
                    "grupo": CONTINENTES.get(p["CONTINENT"], ""),
                    "outros": sorted(n for n in outros if n and n != "-99"),
                    **r,
                }
            )
    return {
        "fontes": {
            "brasil": "IBGE, malha dos estados",
            "mundo": "Natural Earth, 1:50m, domínio público",
        },
        "brasil": sorted(estados, key=lambda e: e["id"]),
        "mundo": sorted(mundo, key=lambda e: e["id"]),
    }


if __name__ == "__main__":
    dados = gerar(*(Path(a) for a in sys.argv[1:4]))
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(DESTINO, DESTINO.stat().st_size, "bytes", len(dados["brasil"]), len(dados["mundo"]))
