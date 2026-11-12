"""O Modo TV (ADR 0084): o que o Zé mostra numa smart TV da casa, pelo navegador dela.

A Imersão inteira pesa demais para uma TV (4 quadros por segundo na prova de 12/11/2026, numa
Samsung de 2021); a peça sólida sozinha roda a 31 (1080p) e a 58 (meia resolução). Então a TV
ganha uma página própria, leve: a peça em 3D sólido girando, o título e as medidas, um relógio
quando não há nada, e um anel que pulsa quando o Zé fala.

- **A página** é servida na rede da casa (`porta`, padrão 8798), só para endereços privados e só
  com a chave da configuração. Ela pergunta o estado duas vezes por segundo e lê os modelos do
  Acervo (só `3d/`, só `.glb`). Não há nada para escrever nela.
- **Abrir na TV**: o navegador de uma Samsung com Tizen não aceita um endereço pela rede (testado
  em 12/11/2026), mas abre e fecha por ela (a API REST da porta 8001, sem pareamento). Então quem
  usa define, uma vez, o endereço da página do Zé como página inicial do navegador da TV.
- **A configuração** (o IP da TV, ligado ou não, a porta e a chave) fica em `<config>/tv.json`.
"""

import contextlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

WEB = Path(__file__).parent / "web"
PORTA = 8798
VISTA_S = 5.0  # a página perguntou há menos que isto: está aberta na TV
NAVEGADORES = ("3202010022079", "org.tizen.browser")  # o Internet da Samsung, novo e antigo
ARQUIVOS = {"tv.js": "text/javascript", "tv.css": "text/css"}


class TVErro(RuntimeError):
    """O que impede de mostrar na TV (o texto vai para a tela e para a voz)."""


def ip_local() -> str:
    """O IP desta máquina na rede local (o UDP não envia nada: só escolhe a rota)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))
        return str(s.getsockname()[0])


# ---- a TV Samsung pela rede (a API REST da porta 8001) ------------------------------------


def _rest(ip: str, caminho: str, metodo: str = "GET") -> Any:
    pedido = urllib.request.Request(f"http://{ip}:8001/api/v2/{caminho}", method=metodo)
    with urllib.request.urlopen(pedido, timeout=5) as resposta:  # noqa: S310 (http da TV, na LAN)
        return json.loads(resposta.read() or b"null")


def nome_da_tv(ip: str) -> str | None:
    """O nome da Samsung nesse IP (None se não responder como uma)."""
    try:
        dados = _rest(ip, "")
    except (OSError, ValueError, urllib.error.URLError):
        return None
    device = dados.get("device") if isinstance(dados, dict) else None
    return str((device or {}).get("name") or dados.get("name") or "TV Samsung")


def descobrir() -> list[dict[str, str]]:
    """As TVs Samsung na mesma rede /24 desta máquina."""
    rede = ipaddress.ip_network(f"{ip_local()}/24", strict=False)
    if not rede.is_private:
        return []

    def porta_aberta(ip: str) -> bool:
        try:
            with socket.create_connection((ip, 8001), 0.4):
                return True
        except OSError:
            return False

    with ThreadPoolExecutor(64) as fila:
        hosts = [str(h) for h in rede.hosts()]
        abertos = [ip for ip, sim in zip(hosts, fila.map(porta_aberta, hosts), strict=True) if sim]
        nomes = list(fila.map(nome_da_tv, abertos))
    return [{"ip": ip, "nome": n} for ip, n in zip(abertos, nomes, strict=True) if n]


def navegador(ip: str) -> str:
    """O identificador do navegador nesta TV."""
    for id_ in NAVEGADORES:
        with contextlib.suppress(OSError, ValueError, urllib.error.URLError):
            if isinstance(_rest(ip, f"applications/{id_}"), dict):
                return id_
    raise TVErro("Navegador da TV não encontrado.")


def abrir_navegador(ip: str) -> None:
    try:
        _rest(ip, f"applications/{navegador(ip)}", "POST")
    except (OSError, ValueError, urllib.error.URLError):
        raise TVErro("A TV não respondeu. Ela está ligada?") from None


def fechar_navegador(ip: str) -> None:
    with contextlib.suppress(OSError, ValueError, urllib.error.URLError, TVErro):
        _rest(ip, f"applications/{navegador(ip)}", "DELETE")


# ---- o que a TV mostra -------------------------------------------------------------------


class TelaTV:
    def __init__(
        self,
        arquivo: Path,
        acervo: Path,
        falando: Callable[[], bool] = lambda: False,
        abrir: Callable[[str], None] = abrir_navegador,
        fechar: Callable[[str], None] = fechar_navegador,
    ) -> None:
        self.arquivo = arquivo
        self.acervo = acervo.expanduser()
        self.falando = falando
        self._abrir, self._fechar = abrir, fechar
        self._trava = threading.Lock()
        self._cena: dict[str, Any] = {"tipo": "relogio"}
        self._seq = 0
        self._visto = 0.0
        self._servidor: ThreadingHTTPServer | None = None

    # ---- a configuração de quem usa ----

    def ajustes(self) -> dict[str, Any]:
        try:
            d = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            d = {}
        return {
            "ip_tv": str(d.get("ip_tv") or ""),
            "ligado": bool(d.get("ligado")),
            "porta": int(d.get("porta") or PORTA),
            "chave": str(d.get("chave") or ""),
        }

    def guardar(self, ip_tv: str, ligado: bool) -> None:
        ip_tv = ip_tv.strip()
        if ip_tv:
            try:
                if not ipaddress.ip_address(ip_tv).is_private:
                    raise TVErro("A TV precisa estar na rede local.")
            except ValueError:
                raise TVErro("Endereço IP inválido.") from None
        if ligado and not ip_tv:
            raise TVErro("Informe o IP da TV.")
        atual = self.ajustes()
        dados = {
            "ip_tv": ip_tv,
            "ligado": ligado,
            "porta": atual["porta"],
            "chave": atual["chave"] or secrets.token_urlsafe(18),
        }
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados))
        os.chmod(temporario, 0o600)
        temporario.replace(self.arquivo)
        if ligado:
            self.ligar()
        else:
            self.desligar()

    def endereco(self) -> str:
        a = self.ajustes()
        return f"http://{ip_local()}:{a['porta']}/tv?chave={a['chave']}" if a["chave"] else ""

    def aberta(self) -> bool:
        """A página está aberta na TV agora (perguntou o estado há pouco)."""
        return time.time() - self._visto < VISTA_S

    def para_tela(self) -> dict[str, Any]:
        a = self.ajustes()
        return {
            "ip_tv": a["ip_tv"],
            "ligado": a["ligado"],
            "endereco": self.endereco() if a["ligado"] else "",
            "aberta": self.aberta(),
        }

    # ---- o que mostrar ----

    def mostrar_modelo(self, arquivo: str, titulo: str, detalhe: str = "") -> None:
        """`arquivo`: um GLB no Acervo (`3d/...`), como a Imersão recebe."""
        if not self._no_acervo(arquivo):
            raise TVErro("Modelo não encontrado.")
        self._trocar({"tipo": "modelo", "arquivo": arquivo, "titulo": titulo, "detalhe": detalhe})

    def limpar(self) -> None:
        self._trocar({"tipo": "relogio"})

    def _trocar(self, cena: dict[str, Any]) -> None:
        with self._trava:
            self._seq += 1
            self._cena = {**cena, "seq": self._seq}

    def estado(self) -> dict[str, Any]:
        self._visto = time.time()
        with self._trava:
            cena = dict(self._cena)
        return {"cena": cena, "falando": bool(self.falando())}

    def _no_acervo(self, arquivo: str) -> Path | None:
        alvo = (self.acervo / arquivo).resolve()
        raiz = (self.acervo / "3d").resolve()
        if alvo.suffix.lower() != ".glb" or not alvo.is_relative_to(raiz) or not alvo.is_file():
            return None
        return alvo

    # ---- a TV ----

    def abrir(self) -> None:
        """Liga o servidor (se preciso) e abre o navegador da TV, que tem a página do Zé como
        página inicial. Já aberta, não faz nada."""
        a = self.ajustes()
        if not a["ligado"] or not a["ip_tv"]:
            raise TVErro("Modo TV desligado. Ligue em Perfil.")
        self.ligar()
        if not self.aberta():
            self._abrir(a["ip_tv"])

    def fechar(self) -> None:
        if ip := self.ajustes()["ip_tv"]:
            self._fechar(ip)
        self.limpar()

    # ---- o servidor da página, na rede da casa ----

    def ligar(self) -> None:
        a = self.ajustes()
        if self._servidor is not None or not a["ligado"] or not a["chave"]:
            return
        tela = self

        class Pagina(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                tela._responder(self)

            def log_message(self, *_: Any) -> None:
                pass

        try:
            self._servidor = ThreadingHTTPServer(("0.0.0.0", a["porta"]), Pagina)  # noqa: S104
        except OSError as erro:
            raise TVErro(f"A porta {a['porta']} está em uso.") from erro
        threading.Thread(target=self._servidor.serve_forever, name="tela-tv", daemon=True).start()

    def desligar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None

    def _responder(self, pedido: BaseHTTPRequestHandler) -> None:
        def enviar(codigo: int, corpo: bytes = b"", tipo: str = "text/plain") -> None:
            pedido.send_response(codigo)
            pedido.send_header("Content-Type", tipo)
            pedido.send_header("Cache-Control", "no-store")
            pedido.send_header("Content-Length", str(len(corpo)))
            pedido.end_headers()
            pedido.wfile.write(corpo)

        with contextlib.suppress(ValueError):
            if not ipaddress.ip_address(pedido.client_address[0]).is_private:
                return enviar(403)
        url = urllib.parse.urlsplit(pedido.path)
        consulta = dict(urllib.parse.parse_qsl(url.query))
        nome = url.path.lstrip("/")
        if nome in ARQUIVOS:  # o código da página: sem nada de quem usa, sem chave
            return enviar(200, (WEB / nome).read_bytes(), ARQUIVOS[nome])
        chave = self.ajustes()["chave"]
        if not chave or not hmac.compare_digest(consulta.get("chave", ""), chave):
            return enviar(403)
        if nome == "tv":
            return enviar(200, (WEB / "tv.html").read_bytes(), "text/html; charset=utf-8")
        if nome == "tv/estado":
            return enviar(200, json.dumps(self.estado()).encode(), "application/json")
        if nome == "tv/modelo" and (alvo := self._no_acervo(consulta.get("arquivo", ""))):
            return enviar(200, alvo.read_bytes(), "model/gltf-binary")
        return enviar(404)
