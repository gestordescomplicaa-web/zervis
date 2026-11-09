"""Quanto cada tarefa de uma sessão de código gastou (plano de maturidade, Frente 3).

Os próprios agentes gravam o gasto na conversa deles, e o Zé só lê, no fim do turno:
- **Claude** (`projects/<pasta>/<id>.jsonl`): cada resposta traz `message.usage`; o turno é a
  soma desde o último pedido de quem usa. A mesma resposta aparece em várias linhas (uma por
  bloco), com o mesmo `message.id`: conta uma vez só.
- **Codex** (`sessions/.../rollout-*.jsonl`): os eventos `token_count` trazem o total acumulado
  da conversa; o turno é o total no fim menos o total antes do pedido.

Os campos são os do consumo do Zé (`zervis/cerebro/consumo.py`): entrada, cache lido, cache
criado e saída. Nada disso gasta token: é leitura de um arquivo que já existe.
"""

import json
from pathlib import Path
from typing import Any

CAUDA = 2 * 1024 * 1024  # o turno está no fim da conversa; não lê arquivos enormes inteiros
CAMPOS = ("entrada", "cache_lido", "cache_criado", "saida")


def _linhas(arquivo: Path) -> list[dict[str, Any]]:
    try:
        with arquivo.open("rb") as f:
            f.seek(max(0, arquivo.stat().st_size - CAUDA))
            brutas = f.read().splitlines()
    except OSError:
        return []
    linhas = []
    for bruta in brutas:
        try:
            d = json.loads(bruta)
        except (ValueError, UnicodeError):
            continue
        if isinstance(d, dict):
            linhas.append(d)
    return linhas


def _pedido_claude(d: dict[str, Any]) -> bool:
    """Um pedido de quem usa (não o resultado de uma ferramenta, que também vem como "user")."""
    if d.get("type") != "user" or d.get("isMeta"):
        return False
    conteudo = (d.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        return bool(conteudo.strip())
    return isinstance(conteudo, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in conteudo
    )


def _claude(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    inicio = max((i for i, d in enumerate(linhas) if _pedido_claude(d)), default=-1)
    if inicio < 0:
        return None
    vistos: set[str] = set()
    soma = dict.fromkeys(CAMPOS, 0)
    modelo = ""
    for d in linhas[inicio + 1 :]:
        mensagem = d.get("message") or {}
        uso = mensagem.get("usage")
        if d.get("type") != "assistant" or not isinstance(uso, dict):
            continue
        chave = str(mensagem.get("id") or id(d))
        if chave in vistos:
            continue
        vistos.add(chave)
        if str(mensagem.get("model") or "") not in ("", "<synthetic>"):
            modelo = str(mensagem["model"])
        soma["entrada"] += int(uso.get("input_tokens") or 0)
        soma["cache_lido"] += int(uso.get("cache_read_input_tokens") or 0)
        soma["cache_criado"] += int(uso.get("cache_creation_input_tokens") or 0)
        soma["saida"] += int(uso.get("output_tokens") or 0)
    return {**soma, "modelo": modelo} if vistos else None


def _total_codex(p: dict[str, Any]) -> dict[str, int] | None:
    total = (p.get("info") or {}).get("total_token_usage")
    if not isinstance(total, dict):
        return None
    lidos = int(total.get("cached_input_tokens") or 0)
    return {
        "entrada": max(0, int(total.get("input_tokens") or 0) - lidos),
        "cache_lido": lidos,
        "cache_criado": int(total.get("cache_write_input_tokens") or 0),
        "saida": int(total.get("output_tokens") or 0),
    }


def _codex(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    antes: dict[str, int] = dict.fromkeys(CAMPOS, 0)
    depois: dict[str, int] | None = None
    modelo = ""
    pedido = False  # o pedido ficou antes da cauda lida: não dá para separar o turno
    for d in linhas:
        p = d.get("payload")
        if not isinstance(p, dict):
            continue
        if d.get("type") == "turn_context":
            modelo = str(p.get("model") or modelo)
        elif p.get("type") == "user_message":
            antes, depois = depois or antes, None  # o turno recomeça neste pedido
            pedido = True
        elif p.get("type") == "token_count" and (total := _total_codex(p)) is not None:
            depois = total
    if depois is None or not pedido:
        return None
    return {**{c: max(0, depois[c] - antes[c]) for c in CAMPOS}, "modelo": modelo}


def do_turno(arquivo: Path | None, motor: str) -> dict[str, Any] | None:
    """O gasto do último turno da conversa; None se não der para saber."""
    if arquivo is None:
        return None
    linhas = _linhas(arquivo)
    return _codex(linhas) if motor == "codex" else _claude(linhas)


def total(gasto: dict[str, Any]) -> int:
    return sum(int(gasto.get(c) or 0) for c in CAMPOS)
