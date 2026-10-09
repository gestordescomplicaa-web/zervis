"""O Foco na tela (08/10/2026): o quadro que a página mostra e as marcações que ela devolve.

O jarvisd grava o quadro em `state/foco.json` (lido pela vista Foco do Mapa no Barehands). Quando
o usuário marca o "V" com a pinça ou o clique, a página faz `POST /foco` e o servidor do
Barehands acrescenta a marcação em `state/foco-acoes.jsonl`; o jarvisd lê só o que é novo
(posição no arquivo), aplica no Foco e responde falando, curto.
"""

import json
from pathlib import Path
from typing import Any

from jarvis.foco.frentes import Foco, FocoErro

ACOES = ("passo", "concluir", "pausar", "focar")


def ler_acoes(arquivo: Path, desde: int) -> tuple[list[dict[str, Any]], int]:
    """As marcações escritas depois da posição `desde`, e a nova posição."""
    try:
        tamanho = arquivo.stat().st_size
    except OSError:
        return [], 0
    if tamanho < desde:  # o arquivo foi recriado: recomeça do início
        desde = 0
    if tamanho == desde:
        return [], desde
    with arquivo.open("rb") as f:
        f.seek(desde)
        bruto = f.read()
    completo = bruto[: bruto.rfind(b"\n") + 1]  # uma linha pela metade fica para a próxima
    acoes = []
    for linha in completo.decode(errors="replace").splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("acao") in ACOES and isinstance(d.get("id"), str):
            acoes.append(d)
    return acoes, desde + len(completo)


def aplicar(foco: Foco, acao: dict[str, Any]) -> str:
    """A marcação no Foco; devolve a fala curta do Zé."""
    try:
        f = foco.por_id(str(acao["id"]))
        if acao["acao"] == "passo":
            f, feito = foco.passo_feito(f.id)
            inicio = f"Boa! {feito[0].upper() + feito[1:]}: feito." if feito else "Boa!"
            return f"{inicio} Qual é o próximo passo de {f.titulo}?"
        if acao["acao"] == "concluir":
            foco.concluir(f.id)
            proxima = foco.atual()
            return f"{f.titulo}: concluída!" + (  # a festa na tela vem do _foco_mudou
                f" Agora é {proxima.titulo}." if proxima else ""
            )
        if acao["acao"] == "pausar":
            foco.atualizar(f.id, estado="pausada")
            return f"Pausei {f.titulo}."
        foco.focar(f.id)
        return f"Foco agora: {f.resumo()}."
    except FocoErro as erro:
        return f"Não deu: {erro}."
