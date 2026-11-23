"""O que alguém de fora (a Meta) alcança sem entrar no painel: os links públicos temporários e a
rota dos avisos do Instagram (ADR 0122).

O Instagram não recebe a imagem de um post nem o vídeo de um Reels: recebe um link, e os
servidores da Meta o buscam (ADR 0093 e 0109). O Zé abre um link com um segredo longo
(`token_urlsafe(32)`), só para os arquivos daquele post e por poucos minutos, e o fecha assim que
publica. Nada mais do painel fica aberto: a rota só entrega um arquivo registrado, pelo nome
exato, dentro do prazo.

Os avisos da Meta chegam em `/instagram/webhook` e quem confere é `redes.instagram_webhook`: o
desafio só com o token de verificação dele, o aviso só assinado com a chave secreta do app.
"""

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PREFIXO = "/publico/"
AVISOS = "/instagram/webhook"  # o mesmo `redes.instagram_webhook.CAMINHO`
MAXIMO_AVISO = 64 * 1024
PRAZO_S = 15 * 60.0
TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


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


def responder_head(pedido: Any) -> None:
    """O HEAD do painel (o `do_HEAD` do servidor): só os links públicos respondem. Quem busca um
    vídeo (a Meta, num Reels) costuma conferir o tamanho e o tipo antes de baixar (ADR 0109)."""
    caminho = str(pedido.path).split("?", 1)[0]
    achado = None
    if pedido._host_local() and caminho.startswith(PREFIXO):
        achado = PADRAO.arquivo(caminho)
    pedido.send_response(200 if achado else 404)
    if achado:
        pedido.send_header("Content-Type", achado[1])
        pedido.send_header("Content-Length", str(len(achado[0])))
        pedido.send_header("Cache-Control", "no-store")
    else:
        pedido.send_header("Content-Length", "0")
    pedido.end_headers()


def e_publico(caminho: str) -> bool:
    return caminho.startswith(PREFIXO) or caminho == AVISOS


def responder(pedido: Any, metodo: str) -> None:
    """O GET de um link público (o arquivo, pelo segredo do link, dentro do prazo, ADR 0093) e o
    GET e o POST dos avisos do Instagram (ADR 0122). `pedido` é o tratador do painel."""
    from zervis.redes import instagram_webhook

    caminho, _, consulta = str(pedido.path).partition("?")
    if caminho != AVISOS:
        achado = PADRAO.arquivo(caminho)
        if achado is None:
            pedido._json(404, {"erro": "não existe"})
        else:
            pedido._enviar(200, *achado)
        return
    avisos = instagram_webhook.PADRAO
    if metodo == "GET":
        desafio = avisos.desafio(consulta)
        if desafio is None:
            pedido._json(403, {"erro": "token"})
        else:
            pedido._enviar(200, desafio.encode(), "text/plain")
        return
    tamanho = int(pedido.headers.get("Content-Length") or 0)
    if tamanho > MAXIMO_AVISO:
        pedido._json(413, {"erro": "grande demais"})
        return
    corpo = pedido.rfile.read(tamanho)
    if avisos.receber(corpo, pedido.headers.get("X-Hub-Signature-256", "")):
        pedido._json(200, {"ok": True})
    else:
        pedido._json(403, {"erro": "assinatura"})
