"""O print de uma página para a Imersão (ADR 0058): "mostra o site da loja", "mostra a notícia".

O Chromium da máquina, sem tela e com um perfil descartável (sem as senhas nem as sessões de quem
usa), abre a página e tira o print. Uma página da internet não pode virar porta para a rede de
casa: todo o tráfego do Chromium passa por uma trava local (`Trava`), que só deixa conectar a
endereço público na porta 443, resolvendo o nome uma vez só (contra a troca de endereço no meio
do caminho). O painel do Zé, o roteador, o Tailscale e qualquer serviço da máquina ficam de fora.
Só HTTPS. O print vai para `Acervo/imagens/capturas/`, com a página de origem ao lado.
"""

import contextlib
import ipaddress
import json
import re
import select
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

PASTA = Path("imagens") / "capturas"  # dentro do Acervo
NAVEGADORES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
LARGURA, ALTURA = 1280, 800
TEMPO_S = 45.0
OCIOSO_S = 30.0  # uma conexão parada por mais que isto é fechada pela trava
PNG = b"\x89PNG\r\n\x1a\n"

Resolver = Callable[[str, int], list[str]]


class CapturaErro(Exception):
    pass


def resolver(host: str, porta: int) -> list[str]:
    try:
        return sorted(
            {str(i[4][0]) for i in socket.getaddrinfo(host, porta, type=socket.SOCK_STREAM)}
        )
    except OSError:
        return []


def publico(ip: str) -> bool:
    """Endereço da internet: nem local, nem privado, nem o CGNAT do Tailscale, nem reservado."""
    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(endereco, ipaddress.IPv6Address) and endereco.ipv4_mapped:
        endereco = endereco.ipv4_mapped
    return endereco.is_global and not endereco.is_multicast


class Trava(socketserver.ThreadingTCPServer):
    """Um proxy HTTP local que só aceita CONNECT para um endereço público na porta 443."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        resolve: Resolver = resolver,
        permitido: Callable[[str], bool] = publico,
        conectar: Callable[[tuple[str, int]], socket.socket] | None = None,
    ):
        self.resolve = resolve
        self.permitido = permitido
        self.conectar = conectar or (lambda destino: socket.create_connection(destino, timeout=15))
        self.recusados: list[str] = []
        super().__init__(("127.0.0.1", 0), _Tunel)

    @property
    def porta(self) -> int:
        return int(self.server_address[1])


class _Tunel(socketserver.BaseRequestHandler):
    server: Trava

    def handle(self) -> None:
        cliente: socket.socket = self.request
        cliente.settimeout(OCIOSO_S)
        cabeca = b""
        with contextlib.suppress(OSError):
            while b"\r\n\r\n" not in cabeca and len(cabeca) < 8192:
                pedaco = cliente.recv(1024)
                if not pedaco:
                    return
                cabeca += pedaco
        linha = cabeca.split(b"\r\n", 1)[0].decode("latin-1")
        achado = re.fullmatch(
            r"CONNECT ([A-Za-z0-9.-]+|\[[0-9a-fA-F:]+\]):(\d+) HTTP/1\.[01]", linha
        )
        host, porta = (achado.group(1).strip("[]"), int(achado.group(2))) if achado else ("", 0)
        ips = [ip for ip in self.server.resolve(host, porta)] if porta == 443 else []
        if not ips or not all(self.server.permitido(ip) for ip in ips):
            self.server.recusados.append(host or linha[:60])
            with contextlib.suppress(OSError):
                cliente.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        try:
            destino = self.server.conectar((ips[0], porta))  # o IP já conferido, não o nome
        except OSError:
            with contextlib.suppress(OSError):
                cliente.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        with destino:
            cliente.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            _encanar(cliente, destino)


def _encanar(a: socket.socket, b: socket.socket) -> None:
    pares = {a: b, b: a}
    while True:
        prontos, _, _ = select.select(list(pares), [], [], OCIOSO_S)
        if not prontos:
            return
        for s in prontos:
            try:
                dados = s.recv(65536)
            except OSError:
                return
            if not dados:
                return
            pares[s].sendall(dados)


@contextlib.contextmanager
def trava(
    resolve: Resolver = resolver,
    permitido: Callable[[str], bool] = publico,
    conectar: Callable[[tuple[str, int]], socket.socket] | None = None,
) -> Iterator[Trava]:
    servidor = Trava(resolve, permitido, conectar)
    fio = threading.Thread(target=servidor.serve_forever, name="captura-trava", daemon=True)
    fio.start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()


def navegador() -> str | None:
    return next((n for n in map(shutil.which, NAVEGADORES) if n), None)


def conferir_url(url: str, resolve: Resolver = resolver) -> str:
    """Só HTTPS para um nome que resolve para endereço público; devolve o host."""
    partes = urllib.parse.urlsplit(url.strip())
    host = partes.hostname or ""
    if partes.scheme != "https" or not host or partes.username or partes.password:
        raise CapturaErro("só endereços https da internet")
    ips = resolve(host, partes.port or 443)
    if not ips:
        raise CapturaErro(f"{host} não foi encontrado")
    if not all(publico(ip) for ip in ips):
        raise CapturaErro("endereço da rede local: fica de fora")
    return host


def _chromium(binario: str, perfil: str, porta: int, saida: str, url: str) -> list[str]:
    """O Chromium sem tela, com perfil descartável e todo o tráfego atrás da trava."""
    return [
        binario, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--disable-quic", "--disable-background-networking",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        f"--user-data-dir={perfil}", f"--proxy-server=http://127.0.0.1:{porta}",
        "--proxy-bypass-list=<-loopback>", f"--window-size={LARGURA},{ALTURA}",
        "--virtual-time-budget=6000", saida, url,
    ]  # fmt: skip


def renderizar(url: str, executar: Any = subprocess.run, limite: int = 6 * 1024 * 1024) -> str:
    """O HTML da página depois do JavaScript (para o leitor da pesquisa, ADR 0059), pelo mesmo
    Chromium e a mesma trava do print."""
    conferir_url(url)
    binario = navegador()
    if binario is None:
        raise CapturaErro("Chromium não encontrado nesta máquina")
    with tempfile.TemporaryDirectory(prefix="ze-leitura-") as perfil, trava() as t:
        try:
            r = executar(
                _chromium(binario, perfil, t.porta, "--dump-dom", url),
                capture_output=True, timeout=TEMPO_S, check=False,
            )  # fmt: skip
        except subprocess.TimeoutExpired:
            raise CapturaErro("a página demorou demais para abrir") from None
    html = (r.stdout or b"")[:limite]
    return html.decode("utf-8", "replace") if isinstance(html, bytes) else str(html)


def capturar(url: str, acervo: Path, executar: Any = subprocess.run) -> dict[str, Any]:
    """Abre a página no Chromium sem tela, atrás da trava, e guarda o print no Acervo."""
    host = conferir_url(url)
    binario = navegador()
    if binario is None:
        raise CapturaErro("Chromium não encontrado nesta máquina")
    nome = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")[:60] + time.strftime(
        "-%Y%m%d-%H%M%S"
    )
    destino = acervo / PASTA
    destino.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="ze-captura-") as perfil, trava() as t:
        saida = Path(perfil) / "print.png"
        comando = _chromium(binario, perfil, t.porta, f"--screenshot={saida}", url)
        try:
            executar(comando, capture_output=True, timeout=TEMPO_S, check=False)
        except subprocess.TimeoutExpired:
            raise CapturaErro("a página demorou demais para abrir") from None
        imagem = saida.read_bytes() if saida.is_file() else b""
    if not imagem.startswith(PNG) or len(imagem) < 2000:
        raise CapturaErro("a página não abriu")
    alvo = destino / f"{nome}.png"
    alvo.write_bytes(imagem)
    registro = {
        "titulo": host,
        "legenda": f"Página {host}",
        "tipo": "foto",
        "fonte": host,
        "pagina": url[:240],
        "licenca": "Captura de tela",
        "licenca_url": "",
        "autor": host,
        "baixado_em": time.strftime("%Y-%m-%d %H:%M"),
    }
    alvo.with_suffix(".json").write_text(json.dumps(registro, ensure_ascii=False, indent=1))
    return {**registro, "arquivo": (PASTA / alvo.name).as_posix()}
