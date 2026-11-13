"""As fotos que esperam o celular (ADR 0087): a câmera viu alguém com o app desconectado.

O celular é a cópia que sai de casa: se o PC for levado, as fotos que já chegaram ao app (e à
galeria dele) ficam. Por isso a foto de movimento que não pôde ser entregue espera aqui, em
ordem, e vai assim que o app conectar, com a hora em que foi tirada. Fica a lista, não a foto:
a foto continua na pasta da câmera; a que sumiu de lá sai da fila.
"""

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAXIMO = 50  # mais que isto esperando: as mais velhas saem (a galeria do PC continua com elas)


class FilaDoCelular:
    def __init__(self, arquivo: Path, maximo: int = MAXIMO) -> None:
        self.arquivo = arquivo
        self.maximo = maximo
        self._trava = threading.Lock()

    def guardar(self, caminho: Path, titulo: str, texto: str = "") -> None:
        with self._trava:
            fila = [p for p in self._ler() if p["caminho"] != str(caminho)]
            fila.append({"caminho": str(caminho), "titulo": titulo, "texto": texto})
            self._gravar(fila[-self.maximo :])

    def pendentes(self) -> list[dict[str, Any]]:
        with self._trava:
            return self._ler()

    def entregar(self, enviar: Callable[[dict[str, Any]], bool]) -> int:
        """Manda em ordem até a primeira que falhar (o app caiu de novo: o resto espera)."""
        with self._trava:
            fila, entregues = self._ler(), 0
            while fila:
                if Path(fila[0]["caminho"]).is_file() and not enviar(fila[0]):
                    break
                entregues += Path(fila[0]["caminho"]).is_file()
                fila.pop(0)
            self._gravar(fila)
            return entregues

    def _ler(self) -> list[dict[str, Any]]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return []
        return (
            [d for d in dados if isinstance(d, dict) and d.get("caminho")]
            if isinstance(dados, list)
            else []
        )

    def _gravar(self, fila: list[dict[str, Any]]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(fila, ensure_ascii=False))
        os.chmod(temporario, 0o600)
        temporario.replace(self.arquivo)
