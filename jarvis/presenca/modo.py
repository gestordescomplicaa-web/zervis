"""Quando o Zé escuta o chamado: a escolha "Escuta" da página Voz (ADR 0021).

- **Sempre**: enquanto o Zé estiver rodando, o "Ei Zé" funciona. Vale em qualquer Linux.
- **Com a janela aberta**: só com a janela do Zé aberta. Precisa do Hyprland, que avisa quando a
  janela abre e fecha; sem ele, vale "Sempre".

O padrão segue a máquina: com Hyprland, "Com a janela aberta" (o comportamento de sempre do Zé);
sem ele, "Sempre". A escolha fica em `<config>/escuta.json`. O modo de fala Silencioso continua
desligando o chamado em qualquer caso (ADR 0018).
"""

import json
from pathlib import Path

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "escuta.json"
MODOS = ("sempre", "janela")
NOMES = {"sempre": "Sempre", "janela": "Com a janela aberta"}


def padrao(tem_janela: bool) -> str:
    return "janela" if tem_janela else "sempre"


def ler(tem_janela: bool, arquivo: Path = ARQUIVO) -> str:
    """O modo em vigor: o escolhido, ou o padrão; "janela" sem Hyprland vira "sempre"."""
    try:
        modo = json.loads(arquivo.read_text()).get("modo")
    except (OSError, ValueError, AttributeError):
        modo = None
    if modo not in MODOS:
        modo = padrao(tem_janela)
    return modo if tem_janela else "sempre"


def gravar(modo: str, arquivo: Path = ARQUIVO) -> str:
    if modo not in MODOS:
        raise ValueError("modo de escuta desconhecido")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"modo": modo}))
    temporario.replace(arquivo)
    return modo
