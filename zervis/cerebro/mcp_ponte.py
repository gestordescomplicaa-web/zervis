"""A ponte local dos conectores com login OAuth (ADR 0037).

O token de um MCP remoto vence (em geral, em uma hora). Se ele fosse direto no cabeçalho do
cérebro ou de uma sessão, cada renovação exigiria recomeçar a conversa. Em vez disso, quem usa o
conector fala com esta ponte (`http://127.0.0.1:<porta>/<conector>`, com o segredo da ponte num
cabeçalho), e ela repassa cada pedido ao servidor com o token em dia (`mcp_oauth.Logins.token`),
renovando antes de vencer ou quando o servidor responde 401.

Só repassa o que o MCP usa (POST, GET do fluxo SSE, DELETE da sessão) e os cabeçalhos do
protocolo; a resposta volta em pedaços, sem esperar o fim (SSE). Sobe na primeira vez que um
conector com login é carregado, numa thread própria, e só escuta em loopback.
"""

import contextlib
import hmac
import json
import logging
import secrets
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from zervis.cerebro import mcp_oauth

log = logging.getLogger(__name__)
CABECALHO = "X-Ze-Ponte"
IDA = ("Content-Type", "Accept", "Mcp-Session-Id", "Mcp-Protocol-Version", "Last-Event-ID")
VOLTA = ("Content-Type", "Mcp-Session-Id", "Cache-Control")
MAXIMO_CORPO = 4 * 1024 * 1024
LIMITE_S = 300.0  # sem nenhum byte do servidor por 5 minutos, a ligação cai (SSE parado)


class Ponte:
    def __init__(
        self,
        destino: Callable[[str], str | None],
        logins: mcp_oauth.Logins | None = None,
    ) -> None:
        self.destino = destino  # conector -> endereço remoto (None: não é um conector com login)
        self.logins = logins or mcp_oauth.PADRAO
        self.segredo = secrets.token_urlsafe(32)
        self._http: ThreadingHTTPServer | None = None
        self._trava = threading.Lock()

    def endereco(self, nome: str) -> tuple[str, dict[str, str]]:
        """O endereço local do conector e o cabeçalho que a ponte exige (sobe na primeira vez)."""
        with self._trava:
            if self._http is None:
                self._http = ThreadingHTTPServer(("127.0.0.1", 0), self._tratador())
                self._http.daemon_threads = True
                threading.Thread(
                    target=self._http.serve_forever, name="ponte-mcp", daemon=True
                ).start()
                log.info("ponte dos conectores com login na porta %d", self._http.server_port)
            porta = self._http.server_port
        return f"http://127.0.0.1:{porta}/{nome}", {CABECALHO: self.segredo}

    def parar(self) -> None:
        with self._trava:
            if self._http is not None:
                self._http.shutdown()
                self._http.server_close()
                self._http = None

    def _tratador(self) -> type[BaseHTTPRequestHandler]:
        ponte = self

        class Tratador(BaseHTTPRequestHandler):
            server_version = "ze-ponte"
            sys_version = ""
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:
                return None

            def _json(self, status: int, dados: dict[str, Any]) -> None:
                corpo = json.dumps(dados).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(corpo)

            def _repassar(self) -> None:
                segredo = self.headers.get(CABECALHO, "")
                if not hmac.compare_digest(segredo, ponte.segredo):
                    self._json(403, {"erro": "ponte"})
                    return
                nome = self.path.split("?", 1)[0].strip("/")
                alvo = ponte.destino(nome) if "/" not in nome else None
                if not alvo:
                    self._json(404, {"erro": "conector"})
                    return
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > MAXIMO_CORPO:
                    self._json(413, {"erro": "grande demais"})
                    return
                corpo = self.rfile.read(tamanho) if tamanho else None
                cabecalhos = {c: v for c in IDA if (v := self.headers.get(c))}
                for tentativa in (False, True):
                    token = ponte.logins.token(nome, renovar=tentativa)
                    if token is None:
                        # 503, não 401: um 401 levaria o cliente (o Claude Code) a tentar um
                        # login OAuth próprio contra a ponte.
                        self._json(503, {"erro": "Entre de novo no conector (Conectores)."})
                        return
                    pedido = urllib.request.Request(  # noqa: S310 (o endereço https do conector)
                        alvo,
                        data=corpo,
                        method=self.command,
                        headers={
                            **cabecalhos,
                            "Authorization": f"Bearer {token}",
                            "User-Agent": mcp_oauth.AGENTE,
                        },
                    )
                    try:
                        resposta = urllib.request.urlopen(pedido, timeout=LIMITE_S)  # noqa: S310
                    except urllib.error.HTTPError as erro:
                        if erro.code == 401 and not tentativa:
                            erro.close()
                            continue  # token recusado antes da hora: renova e tenta uma vez
                        resposta = erro
                    except (urllib.error.URLError, OSError) as erro:
                        self._json(502, {"erro": f"sem conexão ({type(erro).__name__})"})
                        return
                    self._devolver(resposta)
                    return

            def _devolver(self, resposta: Any) -> None:
                """A resposta do servidor aos poucos: o SSE chega evento a evento."""
                with contextlib.closing(resposta):
                    self.send_response(resposta.status)
                    for c in VOLTA:
                        if v := resposta.headers.get(c):
                            self.send_header(c, v)
                    self.send_header("Connection", "close")
                    self.end_headers()
                    ler = getattr(resposta, "read1", None) or resposta.read
                    with contextlib.suppress(OSError, AttributeError):
                        while pedaco := ler(65536):
                            self.wfile.write(pedaco)
                            self.wfile.flush()
                self.close_connection = True

            do_POST = _repassar
            do_GET = _repassar
            do_DELETE = _repassar

        return Tratador


def _destino(nome: str) -> str | None:
    from zervis.cerebro import mcp_externo  # o carregador importa a ponte

    return mcp_externo.url_com_login(nome)


PADRAO = Ponte(_destino)
