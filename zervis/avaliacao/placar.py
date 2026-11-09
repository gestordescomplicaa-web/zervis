"""O placar do Zé (plano de maturidade, Frente 3): a nota por área, a latência da voz por caminho
e o gasto por cenário, num Markdown que vai para `docs/placar.md` a cada versão.

Também a conferência da rodada noturna: uma área que caiu mais de `QUEDA` pontos desde a última
rodada noturna do mesmo cérebro vira um aviso do Zé.

`zervis placar` escreve o Markdown a partir do último relatório da bateria e dos turnos de voz
dos últimos dias. O repositório é público: o placar só tem números agregados, nunca uma fala,
uma resposta ou um nome.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from zervis import avaliacao, lugares
from zervis.voz import latencia

QUEDA = 5.0  # pontos
DIAS = 7  # a janela da latência no placar


def por_area(relatorio: dict[str, Any]) -> dict[str, float]:
    """A nota (0 a 100) de cada área: a média da taxa de acerto dos cenários com nota."""
    areas: dict[str, list[float]] = {}
    for c in relatorio.get("cenarios", []):
        notas = [r["passou"] for r in c.get("rodadas", []) if r.get("passou") is not None]
        if notas:
            areas.setdefault(c.get("area", "voz"), []).append(sum(notas) / len(notas))
    return {a: sum(v) / len(v) * 100 for a, v in areas.items()}


def geral(relatorio: dict[str, Any]) -> float | None:
    taxas = []
    for c in relatorio.get("cenarios", []):
        notas = [r["passou"] for r in c.get("rodadas", []) if r.get("passou") is not None]
        if notas:
            taxas.append(sum(notas) / len(notas))
    return sum(taxas) / len(taxas) * 100 if taxas else None


def tokens_por_cenario(relatorio: dict[str, Any]) -> float | None:
    valores = [
        r["tokens"]
        for c in relatorio.get("cenarios", [])
        for r in c.get("rodadas", [])
        if r.get("passou") is not None and isinstance(r.get("tokens"), int)
    ]
    return sum(valores) / len(valores) if valores else None


def quedas(
    atual: dict[str, Any], anterior: dict[str, Any], limite: float = QUEDA
) -> list[tuple[str, float, float]]:
    """(área, antes, agora) das áreas que caíram mais de `limite` pontos."""
    agora, antes = por_area(atual), por_area(anterior)
    return [
        (area, antes[area], agora[area])
        for area in avaliacao.AREAS
        if area in agora and area in antes and antes[area] - agora[area] > limite
    ]


def aviso_de_queda(caidas: list[tuple[str, float, float]]) -> str:
    partes = [f"{avaliacao.AREAS[a]}, de {de:.0f} para {para:.0f}" for a, de, para in caidas]
    return "A avaliação noturna caiu em " + "; ".join(partes) + "."


def relatorios(historico: Path) -> list[dict[str, Any]]:
    """Os relatórios guardados, do mais antigo ao mais novo."""
    saida = []
    for arquivo in sorted(historico.glob("*.json")):
        try:
            relatorio = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(relatorio, dict):
            saida.append(relatorio)
    return saida


def ultima_noturna(historico: Path, rotulo: str) -> dict[str, Any] | None:
    noturnas = [r for r in relatorios(historico) if r.get("noturna") and r.get("rotulo") == rotulo]
    return noturnas[-1] if noturnas else None


def completa(historico: Path, total: int) -> dict[str, Any] | None:
    """A rodada que vai para o placar: a última noturna ou, sem ela, a última com ao menos
    metade dos cenários (rodar só alguns não é a nota do Zé)."""
    todos = relatorios(historico)
    noturnas = [r for r in todos if r.get("noturna")]
    if noturnas:
        return noturnas[-1]
    grandes = [r for r in todos if len(r.get("cenarios", [])) * 2 >= total]
    return grandes[-1] if grandes else None


def _s(ms: float) -> str:
    return f"{ms / 1000:.1f} s".replace(".", ",")


def markdown(
    relatorio: dict[str, Any] | None, caminhos: list[dict[str, Any]], versao: str, dias: int
) -> str:
    linhas = [
        "# Placar do Zérvis",
        "",
        f"Versão {versao}. Gerado por `zervis placar` (plano de maturidade, Frente 3), só com",
        "números agregados: nenhuma fala, resposta ou nome.",
        "",
        "## Avaliação do cérebro",
        "",
    ]
    nota = geral(relatorio) if relatorio else None
    if relatorio is None or nota is None:
        linhas += ["Ainda sem rodada completa da bateria (`zervis avaliar --noturna`).", ""]
    else:
        n = sum(
            any(r.get("passou") is not None for r in c.get("rodadas", []))
            for c in relatorio.get("cenarios", [])
        )
        repeticoes = max((len(c.get("rodadas", [])) for c in relatorio["cenarios"]), default=1)
        linhas += [
            f"Rodada de {str(relatorio.get('quando', ''))[:10]}, {relatorio.get('rotulo', '')}, "
            f"{n} cenários, {repeticoes}x cada: **{nota:.0f}%**.",
            "",
            "| Área | Nota |",
            "| --- | --- |",
        ]
        areas = por_area(relatorio)
        linhas += [
            f"| {nome} | {areas[a]:.0f}% |" for a, nome in avaliacao.AREAS.items() if a in areas
        ]
        if (tokens := tokens_por_cenario(relatorio)) is not None:
            mil = f"{tokens / 1000:.1f}".replace(".", ",")
            linhas += ["", f"Gasto: {mil} mil tokens por cenário, em média."]
        linhas.append("")
    linhas += [
        "## Latência da voz",
        "",
        f"Do fim da fala ao primeiro som, nos últimos {dias} dias de uso. Meta inicial: p95",
        "abaixo de 2,5 s na via rápida.",
        "",
    ]
    if not caminhos:
        linhas += ["Ainda sem turnos de voz medidos.", ""]
    else:
        linhas += [
            "| Fala | Caminho | Turnos | p50 | p95 | Falhas |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for g in caminhos:
            linhas.append(
                f"| {latencia.MODOS[g['modo']]} | {latencia.CAMINHOS[g['caminho']]} | "
                f"{g['turnos']} | {_s(g['p50_ms'])} | {_s(g['p95_ms'])} | {g['falhas']} |"
            )
        linhas.append("")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    from zervis.cli import versao

    partes = argparse.ArgumentParser(prog="zervis placar", description=__doc__)
    partes.add_argument("--saida", type=Path, help="grava aqui (padrão: mostra na tela)")
    partes.add_argument("--dias", type=int, default=DIAS, help="a janela da latência")
    args = partes.parse_args(argv)
    texto = markdown(
        completa(lugares.ESTADO / "avaliacao", len(avaliacao.carregar())),
        latencia.por_caminho(latencia.ler_dias(lugares.ESTADO / "latencias", args.dias)),
        versao().split()[0],
        args.dias,
    )
    if args.saida:
        args.saida.write_text(texto)
        print(f"Placar: {args.saida}")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
