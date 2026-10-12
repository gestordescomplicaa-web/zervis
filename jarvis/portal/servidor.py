"""O servidor do painel do Zé (docs/plano-painel.md, 09/10/2026).

HTTP da biblioteca padrão, só em loopback, numa thread do `jarvisd`. Duas proteções contra
outros sites abertos no navegador, que também alcançam 127.0.0.1:
- o `Host` precisa ser o endereço local (barra o DNS rebinding);
- toda chamada de API leva o cabeçalho `X-Ze-Token`, um segredo por sessão que só aparece
  dentro da própria página (outro site não consegue lê-la).
As respostas nunca trazem segredo: a chave colada no painel só entra.
"""

import hmac
import json
import logging
import os
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

log = logging.getLogger(__name__)
WEB = Path(__file__).with_name("web")
PORTA = int(os.environ.get("JARVIS_PAINEL_PORTA", "8795"))  # o perfil limpo usa outra
IMERSIVO = "http://127.0.0.1:8794"  # o modo imersivo (Barehands), embutido na aba Imersão
# A sala LiveKit da voz remota: no próprio PC e, pelo celular, a do `tailscale serve` (8443).
VOZ_REMOTA = "ws://127.0.0.1:7880 http://127.0.0.1:7880 wss://*.ts.net:8443 https://*.ts.net:8443"
MAXIMO_CORPO = 64 * 1024
TIPOS = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
ARQUIVOS = {
    "/": "index.html",
    "/painel.css": "painel.css",
    "/painel.js": "painel.js",
    "/ze.webp": "ze.webp",  # o ícone do Zé (menu lateral e aba)
    # O terminal das sessões (xterm.js, MIT; ver THIRD_PARTY.md), servido daqui, sem CDN.
    "/vendor/xterm/xterm.js": "vendor/xterm/xterm.js",
    "/vendor/xterm/xterm.css": "vendor/xterm/xterm.css",
    "/vendor/xterm/addon-fit.js": "vendor/xterm/addon-fit.js",
    # O cliente da voz remota (livekit-client, Apache-2.0; ver THIRD_PARTY.md).
    "/vendor/livekit/livekit-client.umd.js": "vendor/livekit/livekit-client.umd.js",
}

Leitura = Callable[[], Any]
Escrita = Callable[[dict[str, Any]], Any]
Envio = Callable[[bytes, dict[str, str]], Any]  # corpo cru (um arquivo) e os parâmetros da URL
MAXIMO_ENVIO = 20 * 1024 * 1024


class PedidoInvalido(ValueError):
    """Erro com mensagem para mostrar na tela (vira 400)."""


class Portal:
    def __init__(
        self,
        leituras: dict[str, Leitura],
        escritas: dict[str, Escrita],
        porta: int = PORTA,
        token: str | None = None,
        envios: dict[str, Envio] | None = None,
    ) -> None:
        self.leituras = leituras
        self.escritas = escritas
        self.envios = envios or {}
        self.token = token or secrets.token_urlsafe(32)
        self.http = ThreadingHTTPServer(("127.0.0.1", porta), self._tratador())
        self.http.daemon_threads = True
        self.porta = self.http.server_port
        self.hosts = {f"127.0.0.1:{self.porta}", f"localhost:{self.porta}"}

    def permitir(self, nome: str) -> None:
        """Aceita o nome da máquina na rede privada (o `tailscale serve` repassa o Host)."""
        self.hosts |= {nome, f"{nome}:443"}

    def proibir(self, nome: str) -> None:
        self.hosts -= {nome, f"{nome}:443"}

    @property
    def endereco(self) -> str:
        return f"http://127.0.0.1:{self.porta}/"

    def iniciar(self) -> None:
        threading.Thread(target=self.http.serve_forever, name="painel", daemon=True).start()
        log.info("painel em %s", self.endereco)

    def parar(self) -> None:
        self.http.shutdown()
        self.http.server_close()

    def _tratador(self) -> type[BaseHTTPRequestHandler]:
        portal = self

        class Tratador(BaseHTTPRequestHandler):
            server_version = "ze-painel"
            sys_version = ""

            def log_message(self, *args: object) -> None:
                return None

            def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
                self.send_response(status)
                texto = tipo.startswith("text/") or tipo.endswith(("json", "svg+xml"))
                self.send_header("Content-Type", f"{tipo}; charset=utf-8" if texto else tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                # Estilo inline: o terminal (xterm.js) gera o CSS de fonte e cores; scripts seguem
                # só do próprio painel.
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; img-src 'self' data: blob:; "
                    "style-src 'self' 'unsafe-inline'; script-src 'self'; "
                    f"connect-src 'self' {VOZ_REMOTA}; "
                    "frame-ancestors 'none'; "
                    f"frame-src {IMERSIVO}",
                )
                self.end_headers()
                self.wfile.write(corpo)

            def _json(self, status: int, dados: Any) -> None:
                self._enviar(
                    status, json.dumps(dados, ensure_ascii=False).encode(), "application/json"
                )

            def _host_local(self) -> bool:
                return self.headers.get("Host", "") in portal.hosts

            def _autorizado(self) -> bool:
                return self._host_local() and hmac.compare_digest(
                    self.headers.get("X-Ze-Token", ""), portal.token
                )

            def do_GET(self) -> None:
                if not self._host_local():
                    self._json(403, {"erro": "host"})
                    return
                caminho = self.path.split("?", 1)[0]
                if caminho in ARQUIVOS:
                    arquivo = WEB / ARQUIVOS[caminho]
                    corpo = arquivo.read_bytes()
                    if arquivo.name == "index.html":
                        corpo = corpo.replace(b"__TOKEN__", portal.token.encode())
                    self._enviar(200, corpo, TIPOS[arquivo.suffix])
                    return
                if not caminho.startswith("/api/"):
                    self._json(404, {"erro": "não existe"})
                    return
                if not self._autorizado():
                    self._json(403, {"erro": "token"})
                    return
                leitura = portal.leituras.get(caminho[5:])
                if leitura is None:
                    self._json(404, {"erro": "não existe"})
                    return
                self._responder(leitura)

            def do_POST(self) -> None:
                caminho = self.path.split("?", 1)[0]
                if not self._autorizado():
                    self._json(403, {"erro": "token"})
                    return
                envio = portal.envios.get(caminho[5:]) if caminho.startswith("/api/") else None
                if envio is not None:
                    self._receber_arquivo(envio)
                    return
                escrita = portal.escritas.get(caminho[5:]) if caminho.startswith("/api/") else None
                if escrita is None:
                    self._json(404, {"erro": "não existe"})
                    return
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > MAXIMO_CORPO:
                    self._json(413, {"erro": "grande demais"})
                    return
                try:
                    dados = json.loads(self.rfile.read(tamanho) or b"{}")
                except ValueError:
                    self._json(400, {"erro": "JSON inválido"})
                    return
                if not isinstance(dados, dict):
                    self._json(400, {"erro": "esperado um objeto"})
                    return
                self._responder(lambda: escrita(dados))

            def _receber_arquivo(self, envio: Envio) -> None:
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > MAXIMO_ENVIO:
                    self._json(413, {"erro": "arquivo maior que 20 MB"})
                    return
                consulta = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items() if v}
                corpo = self.rfile.read(tamanho)
                self._responder(lambda: envio(corpo, consulta))

            def _responder(self, fazer: Callable[[], Any]) -> None:
                try:
                    self._json(200, fazer())
                except PedidoInvalido as erro:
                    self._json(400, {"erro": str(erro)})
                except Exception:
                    log.exception("painel: falha em %s", self.path)
                    self._json(500, {"erro": "falha interna; veja o log do Zé"})

        return Tratador
