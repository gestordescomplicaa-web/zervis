"""Quanto o Zé espera antes de achar que a pessoa terminou de falar: a escolha "Espera" da
página Voz.

Dois relógios fecham o pedido (`jarvis/voz/escuta.py`): o modelo de fim de turno, consultado
depois de uma pausa curta, e o silêncio longo, que fecha de qualquer jeito. Quem pensa enquanto
fala ("quero uma automação... que toda segunda...") precisa de pausas maiores; quem dá ordens
curtas quer resposta rápida. A escolha fica em `<config>/espera.json`.
"""

import json
from pathlib import Path

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "espera.json"
MODOS = ("rapida", "normal", "longa")
NOMES = {"rapida": "Rápida", "normal": "Normal", "longa": "Longa"}
PADRAO = "normal"
# (pausa até consultar o modelo, silêncio que fecha sempre), em segundos. Rápida é o valor
# antigo: 0,64 s fechava pedidos longos no meio, com notas de 0,94 a 0,99 (14/10/2026).
TEMPOS = {"rapida": (0.64, 2.5), "normal": (1.0, 3.0), "longa": (1.6, 4.5)}


def ler(arquivo: Path = ARQUIVO) -> str:
    try:
        modo = json.loads(arquivo.read_text()).get("modo")
    except (OSError, ValueError, AttributeError):
        return PADRAO
    return modo if modo in MODOS else PADRAO


def gravar(modo: str, arquivo: Path = ARQUIVO) -> str:
    if modo not in MODOS:
        raise ValueError("espera desconhecida")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"modo": modo}))
    temporario.replace(arquivo)
    return modo
