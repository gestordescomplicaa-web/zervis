"""A análise do Instagram (ADR 0057): o ranking das publicações e o resumo do perfil, em texto
curto para o cérebro. As contas (ordenar, somar, tirar a média) são feitas aqui, não pelo modelo:
ele recebe poucas linhas já prontas.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from zervis.redes.instagram import _epoch

# A métrica pedida (como o cérebro escreve) e a chave na Meta.
ORDENS = {
    "visualizacoes": "views",
    "alcance": "reach",
    "interacoes": "total_interactions",
    "curtidas": "likes",
    "comentarios": "comments",
    "salvamentos": "saved",
    "compartilhamentos": "shares",
    "recentes": "",
}
NOMES = {
    "views": "visualizações",
    "reach": "alcance",
    "total_interactions": "interações",
    "likes": "curtidas",
    "comments": "comentários",
    "saved": "salvamentos",
    "shares": "compartilhamentos",
}
TIPOS = ("reels", "post", "carrossel")
LEGENDA = 90


def valor(post: dict[str, Any], chave: str) -> float:
    """A métrica do post; curtidas e comentários também vêm na lista, sem as métricas."""
    metricas = post.get("metricas") or {}
    if chave in metricas:
        return float(metricas[chave])
    reserva = {"likes": "like_count", "comments": "comments_count"}.get(chave)
    return float(post.get(reserva, 0) or 0) if reserva else 0.0


def curto(n: float) -> str:
    """15300 -> "15,3 mil"; 6000 -> "6 mil"; 250000 -> "250 mil"; 980 -> "980"."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".0", "").replace(".", ",") + " mi"
    if n >= 100_000:
        return f"{n / 1000:.0f} mil"
    if n >= 1000:
        return f"{n / 1000:.1f}".replace(".0", "").replace(".", ",") + " mil"
    return f"{n:.0f}"


def _legenda(post: dict[str, Any]) -> str:
    texto = " ".join(str(post.get("caption") or "").split())
    if not texto:
        return "(sem legenda)"
    return texto if len(texto) <= LEGENDA else texto[: LEGENDA - 1].rsplit(" ", 1)[0] + "…"


def filtrar(
    posts: list[dict[str, Any]], dias: int, tipo: str, agora: float
) -> list[dict[str, Any]]:
    saida = [p for p in posts if tipo in ("", "todos") or p.get("tipo") == tipo]
    if dias > 0:
        saida = [p for p in saida if agora - _epoch(p.get("timestamp")) <= dias * 86400]
    return saida


def ranking(
    posts: list[dict[str, Any]],
    ordem: str,
    dias: int,
    tipo: str,
    quantos: int,
    agora: float,
    fuso: ZoneInfo,
) -> str:
    chave = ORDENS.get(ordem, "views")
    lista = filtrar(posts, dias, tipo, agora)
    periodo = f"dos últimos {dias} dias" if dias > 0 else "de todas as publicações lidas"
    if not lista:
        do_tipo = f" do tipo {tipo}" if tipo not in ("", "todos") else ""
        return f"Nenhuma publicação {periodo}{do_tipo}."
    if chave:
        lista.sort(key=lambda p: valor(p, chave), reverse=True)
        titulo = f"As publicações {periodo} com mais {NOMES[chave]} ({len(lista)} no total):"
    else:
        lista.sort(key=lambda p: _epoch(p.get("timestamp")), reverse=True)
        titulo = f"As publicações mais recentes ({len(lista)} {periodo}):"
    linhas = [titulo]
    for i, p in enumerate(lista[: max(1, min(20, quantos))], 1):
        dia = datetime.fromtimestamp(_epoch(p.get("timestamp")), fuso)
        numeros = ", ".join(
            f"{curto(valor(p, k))} {nome}"
            for k, nome in NOMES.items()
            if k in (p.get("metricas") or {}) or k in ("likes", "comments")
        )
        linhas.append(
            f"{i}. {p.get('tipo', 'post')} de {dia:%d/%m/%Y}: {numeros}. "
            f'Legenda: "{_legenda(p)}" {p.get("permalink", "")}'.rstrip()
        )
    return "\n".join(linhas)


def resumo(
    perfil: dict[str, Any],
    periodo: dict[str, int],
    posts: list[dict[str, Any]],
    dias: int,
    agora: float,
) -> str:
    """O perfil agora, os totais do período e como as publicações do período se saíram."""
    usuario = perfil.get("username", "")
    linhas = [
        f"@{usuario}: {curto(perfil.get('followers_count', 0))} seguidores, segue "
        f"{curto(perfil.get('follows_count', 0))}, {perfil.get('media_count', 0)} publicações."
    ]
    if periodo:
        nomes = {
            "reach": "alcance", "views": "visualizações", "accounts_engaged": "contas engajadas",
            "total_interactions": "interações", "likes": "curtidas", "comments": "comentários",
            "saves": "salvamentos", "shares": "compartilhamentos",
            "profile_links_taps": "toques nos links do perfil",
            "follows_and_unfollows": "seguidores ganhos menos perdidos",
        }  # fmt: skip
        totais = ", ".join(f"{curto(v)} {nomes.get(k, k)}" for k, v in periodo.items())
        linhas.append(f"Nos últimos {dias} dias, a conta teve: {totais}.")
    recentes = filtrar(posts, dias, "", agora)
    if recentes:
        por_tipo = {t: sum(1 for p in recentes if p.get("tipo") == t) for t in TIPOS}
        tipos = ", ".join(f"{n} {t}" for t, n in por_tipo.items() if n)
        media = sum(valor(p, "views") for p in recentes) / len(recentes)
        melhor = max(recentes, key=lambda p: valor(p, "views"))
        linhas.append(
            f"Publicou {len(recentes)} vezes no período ({tipos}), com média de "
            f"{curto(media)} visualizações por publicação. A melhor teve "
            f'{curto(valor(melhor, "views"))}: "{_legenda(melhor)}".'
        )
    else:
        linhas.append(f"Nenhuma publicação nos últimos {dias} dias.")
    return "\n".join(linhas)
