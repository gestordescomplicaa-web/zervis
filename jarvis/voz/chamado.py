"""Como a pessoa chama o Zé: a escolha "Ativação" da página Voz (ADR 0022).

- **"Ei Zé"** (padrão): o chamado falado, e também o botão de falar;
- **Só o botão**: o detector do chamado fica desligado; o pedido abre ao apertar o botão (painel,
  espaço ou o botão do fone) e fecha ao soltar. No celular, o microfone só transmite enquanto o
  botão está apertado, o que poupa bateria.

Independe do modo de fala (ADR 0018), que diz só quando o Zé fala sem ser chamado. A escolha fica
em `<config>/chamado.json`.
"""

import json
from pathlib import Path

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "chamado.json"
MODOS = ("voz", "botao")
NOMES = {"voz": "“Ei Zé”", "botao": "Só o botão"}
PADRAO = "voz"


def ler(arquivo: Path = ARQUIVO) -> str:
    try:
        modo = json.loads(arquivo.read_text()).get("modo")
    except (OSError, ValueError, AttributeError):
        return PADRAO
    return modo if modo in MODOS else PADRAO


def gravar(modo: str, arquivo: Path = ARQUIVO) -> str:
    if modo not in MODOS:
        raise ValueError("ativação desconhecida")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"modo": modo}))
    temporario.replace(arquivo)
    return modo
