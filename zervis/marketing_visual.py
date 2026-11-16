"""Os elementos visuais dos slides (ADR 0093): o Zé desenha, com a paleta da marca, o que o modelo
escolhe para cada slide. Sem IA de imagem e sem logo de terceiros.

- `icone`: um ícone da Lucide (ISC; `marca_icones.json`), grande, sobre um disco da cor de destaque;
- `fluxo`: de 2 a 4 passos ligados por setas ("Pedido no WhatsApp → Planilha → Sistema");
- `comparacao`: antes e depois, lado a lado;
- `lista`: de 2 a 4 itens com marcador;
- `conversa`: de 2 a 4 balões de mensagem, sempre com o selo "Ilustração" (nunca uma conversa real).

O modelo escreve o conteúdo; aqui ele é conferido, cortado nos limites e escapado.
"""

import html
import json
from functools import cache
from pathlib import Path
from typing import Any

from zervis.marca import Marca

TIPOS = ("icone", "fluxo", "comparacao", "lista", "conversa")
LIMITES = {"passo": 26, "lado": 70, "item": 48, "mensagem": 80}


@cache
def icones() -> dict[str, str]:
    """O desenho (o miolo do SVG) de cada ícone, pelo nome."""
    dados = json.loads(Path(__file__).with_name("marca_icones.json").read_text())
    return dict(dados["icones"])


def _texto(valor: Any, limite: int) -> str:
    limpo = " ".join(str(valor or "").split())
    return limpo if len(limpo) <= limite else limpo[: limite - 1].rsplit(" ", 1)[0] + "…"


def _lista(valor: Any, limite: int, minimo: int = 2, maximo: int = 4) -> list[str]:
    itens = (
        [_texto(v, limite) for v in valor or [] if str(v or "").strip()]
        if isinstance(valor, list)
        else []
    )
    return itens[:maximo] if len(itens) >= minimo else []


def conferir(visual: Any) -> dict[str, Any]:
    """O visual de um slide, nos limites; vazio se o modelo não deu um que sirva."""
    if not isinstance(visual, dict) or visual.get("tipo") not in TIPOS:
        return {}
    tipo = visual["tipo"]
    if tipo == "icone":
        nome = str(visual.get("icone", ""))
        return {"tipo": tipo, "icone": nome} if nome in icones() else {}
    if tipo == "fluxo":
        passos = _lista(visual.get("passos"), LIMITES["passo"])
        return {"tipo": tipo, "passos": passos} if passos else {}
    if tipo == "comparacao":
        antes, depois = (_texto(visual.get(k), LIMITES["lado"]) for k in ("antes", "depois"))
        return {"tipo": tipo, "antes": antes, "depois": depois} if antes and depois else {}
    if tipo == "lista":
        itens = _lista(visual.get("itens"), LIMITES["item"])
        return {"tipo": tipo, "itens": itens} if itens else {}
    mensagens = [
        {"de": "empresa" if m.get("de") == "empresa" else "cliente",
         "texto": _texto(m.get("texto"), LIMITES["mensagem"])}
        for m in visual.get("mensagens") or []
        if isinstance(m, dict) and str(m.get("texto", "")).strip()
    ][:4]  # fmt: skip
    return {"tipo": tipo, "mensagens": mensagens} if len(mensagens) >= 2 else {}


def svg(nome: str, tamanho: int, cor: str, traco: float = 1.75) -> str:
    miolo = icones().get(nome, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{cor}" stroke-width="{traco}" '
        f'stroke-linecap="round" stroke-linejoin="round">{miolo}</svg>'
    )


def html_do_visual(visual: dict[str, Any], marca: Marca) -> str:
    """O HTML do visual (a CSS está em `css`). Todo texto vem escapado."""
    e, c = html.escape, marca.cor
    tipo = visual.get("tipo")
    if tipo == "icone":
        return f'<div class="v-icone">{svg(visual["icone"], 150, c("texto"))}</div>'
    if tipo == "fluxo":
        seta = f'<span class="v-seta">{svg("arrow-right", 44, c("destaque"), 2.25)}</span>'
        passos = seta.join(f'<span class="v-passo">{e(p)}</span>' for p in visual["passos"])
        return f'<div class="v-fluxo">{passos}</div>'
    if tipo == "comparacao":
        return (
            '<div class="v-comparacao">'
            f'<div class="v-lado antes"><small>Antes</small><span>{e(visual["antes"])}</span></div>'
            '<div class="v-lado depois"><small>Depois</small>'
            f"<span>{e(visual['depois'])}</span></div>"
            "</div>"
        )
    if tipo == "lista":
        # Um marcador neutro: um ✓ ficaria estranho numa lista de problemas.
        itens = "".join(
            f'<li><i class="v-marcador"></i><span>{e(i)}</span></li>' for i in visual["itens"]
        )
        return f'<ul class="v-lista">{itens}</ul>'
    if tipo == "conversa":
        baloes = "".join(
            f'<span class="v-balao {m["de"]}">{e(m["texto"])}</span>' for m in visual["mensagens"]
        )
        return f'<div class="v-conversa"><small>Ilustração</small>{baloes}</div>'
    return ""


def _rgba(cor: str, alfa: float) -> str:
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


def css(marca: Marca, titulo: str) -> str:
    """A CSS dos visuais, com a paleta da marca. `titulo` é a família de fonte dos títulos."""
    c = marca.cor
    return f"""
.visual{{margin-top:56px}}
.v-icone{{width:250px;height:250px;border-radius:64px;display:grid;place-items:center;
 background:linear-gradient(135deg,{c("destaque")},{c("destaque2")})}}
.v-fluxo{{display:flex;align-items:center;flex-wrap:wrap;gap:14px}}
.v-passo{{font-family:{titulo};font-size:32px;font-weight:600;padding:22px 28px;border-radius:24px;
 background:{c("superficie")};border:2px solid {_rgba(c("destaque"), 0.55)}}}
.v-seta{{display:flex}}
.v-comparacao{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
.v-lado{{border-radius:28px;padding:30px 32px;font-size:32px;line-height:1.3;display:grid;gap:12px;
 align-content:start}}
.v-lado small{{font-size:24px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}}
.v-lado.antes{{background:{c("superficie")};color:{c("suave")}}}
.v-lado.depois{{background:{_rgba(c("destaque"), 0.16)};border:2px solid {c("destaque")}}}
.v-lado.depois small{{color:{c("destaque")}}}
.v-lista{{list-style:none;margin:0;padding:0;display:grid;gap:22px}}
.v-lista li{{display:flex;align-items:center;gap:20px;font-size:36px}}
.v-marcador{{flex:none;width:18px;height:18px;border-radius:6px;
 background:linear-gradient(135deg,{c("destaque")},{c("destaque2")})}}
.v-conversa{{display:grid;gap:16px;max-width:820px}}
.v-conversa small{{font-size:22px;color:{c("suave")};letter-spacing:.08em;text-transform:uppercase}}
.v-balao{{font-size:30px;line-height:1.3;padding:20px 26px;border-radius:28px;max-width:640px}}
.v-balao.cliente{{background:{c("superficie")};justify-self:start;border-bottom-left-radius:8px}}
.v-balao.empresa{{background:{c("destaque")};color:#fff;justify-self:end;border-bottom-right-radius:8px}}
"""
