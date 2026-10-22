"""O Teclado do Núcleo: pedidos escritos na tela e a resposta mostrada embaixo deles.

Contrato pela pasta de estado do Barehands, como o resto do rosto:
- `teclado.json`: a página grava `{id, texto, ts}` (POST /teclado) a cada pedido escrito;
- `teclado-resposta.json`: o Zé grava `{pedido, texto, fim}` conforme fala a resposta.

O pedido escrito entra na máquina de estados como fala autorizada (`Digitado`); o que o Zé
fala até o fim da resposta (inclusive a pergunta de confirmação) vai para a tela também.
"""

import json
import time
from pathlib import Path
from typing import Any

from jarvis.rosto.hud import Hud

VALIDO_S = 30.0  # pedido escrito mais velho que isso (Zé parado, reinício) não roda


class Teclado:
    def __init__(self, pasta: Path, hud: Hud) -> None:
        self.arquivo = pasta / "teclado.json"
        self.hud = hud
        self.pedido: str | None = None
        self.fim = True
        self._frases: list[str] = []
        self._mtime = self._modificado()
        self._visto = str(self._ler().get("id") or "")  # o que já estava lá é de antes

    def _modificado(self) -> float:
        try:
            return self.arquivo.stat().st_mtime
        except OSError:
            return 0.0

    def _ler(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def novo(self) -> str | None:
        """O texto de um pedido escrito novo, uma vez só (barato: só lê se o arquivo mudou)."""
        if (mtime := self._modificado()) == self._mtime:
            return None
        self._mtime = mtime
        dados = self._ler()
        pedido = str(dados.get("id") or "")
        texto = str(dados.get("texto") or "").strip()
        if not pedido or pedido == self._visto:
            return None
        self._visto = pedido
        if not texto or time.time() - float(dados.get("ts", 0)) > VALIDO_S:
            return None
        self.pedido, self.fim, self._frases = pedido, False, []
        self._gravar()
        return texto

    def falou(self, texto: str) -> None:
        if self.pedido and not self.fim:
            self._frases.append(texto)
            self._gravar()

    def terminou(self) -> None:
        if self.pedido and not self.fim:
            self.fim = True
            self._gravar()

    def avisar(self, texto: str) -> None:
        """Responde na tela sem passar pela máquina (pedido que não pôde rodar)."""
        self._frases, self.fim = [texto], True
        self._gravar()

    def _gravar(self) -> None:
        self.hud.gravar(
            "teclado-resposta",
            {"pedido": self.pedido, "texto": " ".join(self._frases), "fim": self.fim},
            time.time(),
        )
