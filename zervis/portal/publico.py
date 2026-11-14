"""Links públicos temporários: um arquivo que alguém de fora precisa buscar sem entrar no painel.

O Instagram não recebe a imagem de um post: recebe um link, e os servidores da Meta a buscam
(ADR 0093). O Zé abre um link com um segredo longo (`token_urlsafe(32)`), só para os arquivos
daquele post e por poucos minutos, e o fecha assim que publica. Nada mais do painel fica aberto:
a rota só entrega um arquivo registrado, pelo nome exato, dentro do prazo.
"""

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PREFIXO = "/publico/"
PRAZO_S = 15 * 60.0
TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@dataclass(frozen=True)
class _Link:
    arquivos: dict[str, Path]  # o nome na URL e o arquivo
    vence: float


class Publicos:
    def __init__(self, agora: Callable[[], float] = time.monotonic) -> None:
        self._links: dict[str, _Link] = {}
        self._trava = threading.Lock()
        self._agora = agora

    def abrir(self, arquivos: list[Path], prazo_s: float = PRAZO_S) -> str:
        """Abre um link para estes arquivos e devolve o segredo dele."""
        nomes = {a.name: a for a in arquivos if a.suffix.lower() in TIPOS}
        if not nomes:
            raise ValueError("nada para abrir")
        segredo = secrets.token_urlsafe(32)
        with self._trava:
            self._limpar()
            self._links[segredo] = _Link(nomes, self._agora() + prazo_s)
        return segredo

    def fechar(self, segredo: str) -> None:
        with self._trava:
            self._links.pop(segredo, None)

    def arquivo(self, caminho: str) -> tuple[bytes, str] | None:
        """O conteúdo e o tipo de `/publico/<segredo>/<nome>`, ou None (fechado, vencido, outro)."""
        partes = caminho.removeprefix(PREFIXO).split("/")
        if not caminho.startswith(PREFIXO) or len(partes) != 2:
            return None
        segredo, nome = partes
        with self._trava:
            self._limpar()
            link = next(
                (v for k, v in self._links.items() if secrets.compare_digest(k, segredo)), None
            )
        alvo = link.arquivos.get(nome) if link else None
        if alvo is None:
            return None
        try:
            return alvo.read_bytes(), TIPOS[alvo.suffix.lower()]
        except OSError:
            return None

    def _limpar(self) -> None:
        agora = self._agora()
        for segredo in [k for k, v in self._links.items() if v.vence <= agora]:
            del self._links[segredo]


PADRAO = Publicos()
