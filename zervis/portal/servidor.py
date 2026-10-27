"""O servidor do painel do Zé (docs/plano-painel.md, 09/10/2026).

HTTP da biblioteca padrão, só em loopback, numa thread do `jarvisd`. Duas proteções contra
outros sites abertos no navegador, que também alcançam 127.0.0.1:
- o `Host` precisa ser o endereço local (barra o DNS rebinding);
- toda chamada REST leva o cabeçalho `X-Ze-Token`; os WebSockets conferem o mesmo segredo na
  primeira mensagem. Ele só aparece dentro da própria página (outro site não consegue lê-lo).
As respostas nunca trazem segredo: a chave colada no painel só entra.

Outro aparelho (celular, outro computador) só chega por um nome permitido (o `tailscale serve`
repassa o dele) e passa pela tela "Entrar": sem o cookie do aparelho (`zervis/portal/senha.py`),
só a tela de entrada e o que ela usa ficam abertos.

O app de voz do Android (`zervis/portal/voz_app.py`) também não usa o cookie: pareia em
`/voz-app/parear` com o código de uso único que o painel mostra e abre a voz em `/voz-app/ws` com
a chave que recebeu, no cabeçalho `Authorization`. A chave só abre a voz, nada do painel.

A volta do login de um conector (`/oauth/retorno`, ADR 0037) também abre sem o cookie: ela vem
de outro site, e o cookie `SameSite=Strict` não acompanha. Só serve a quem traz o `state` de um
login que o próprio painel começou, e o código só vale com o verificador que fica no Zé.
"""

import contextlib
import hmac
import html
import json
import logging
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from zervis import ambiente
from zervis.portal.senha import Acesso, SenhaErro
from zervis.portal.voz_app import AparelhosDeVoz, PareamentoErro
from zervis.transporte import websocket

log = logging.getLogger(__name__)
WEB = Path(__file__).with_name("web")
# Ajustes que só valem pelo próprio PC, mesmo num servidor: desligar as proteções ou o acesso
# pelo qual se entrou deixaria a pessoa trancada fora, ou um invasor sem barreira.
SEMPRE_NO_PC = frozenset({"acesso/codigo/desligar", "tunel/desativar", "remoto/desativar"})
LIGAR_CODIGO = frozenset({"acesso/codigo/preparar", "acesso/codigo/confirmar"})
PORTA = int(ambiente.ler("PAINEL_PORTA", "8795"))  # o perfil limpo usa outra
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
    ".webmanifest": "application/manifest+json",
}
ARQUIVOS = {
    "/": "index.html",
    "/painel.css": "painel.css",
    "/painel.js": "painel.js",
    "/modulos/acoes.js": "modulos/acoes.js",
    "/modulos/imersao.js": "modulos/imersao.js",
    "/modulos/modelos.js": "modulos/modelos.js",
    "/modulos/navegacao.js": "modulos/navegacao.js",
    "/modulos/terminal.js": "modulos/terminal.js",
    "/modulos/conectores-sessao.js": "modulos/conectores-sessao.js",
    "/modulos/voz.js": "modulos/voz.js",
    "/paginas/automacoes.js": "paginas/automacoes.js",
    "/paginas/configurar.js": "paginas/configurar.js",
    "/paginas/foco.js": "paginas/foco.js",
    "/paginas/inicio.js": "paginas/inicio.js",
    "/paginas/modelos.js": "paginas/modelos.js",
    "/paginas/perfil.js": "paginas/perfil.js",
    "/paginas/sessoes.js": "paginas/sessoes.js",
    "/paginas/voz.js": "paginas/voz.js",
    "/ze.webp": "ze.webp",  # o ícone do Zé (menu lateral e aba)
    # O terminal das sessões (xterm.js, MIT; ver THIRD_PARTY.md), servido daqui, sem CDN.
    "/vendor/xterm/xterm.js": "vendor/xterm/xterm.js",
    "/vendor/xterm/xterm.css": "vendor/xterm/xterm.css",
    "/vendor/xterm/addon-fit.js": "vendor/xterm/addon-fit.js",
    # O cliente da voz remota (livekit-client, Apache-2.0; ver THIRD_PARTY.md).
    "/vendor/livekit/livekit-client.umd.js": "vendor/livekit/livekit-client.umd.js",
    # O microfone do navegador em pedaços de 80 ms a 16 kHz (voz pelo HTTPS do painel).
    "/voz-captura.js": "voz-captura.js",
    # A página de volta do login de um conector (aberta sem o cookie; ver `_retorno_oauth`).
    "/oauth-retorno.js": "oauth-retorno.js",
    "/paginas/atividade.js": "paginas/atividade.js",  # páginas carregadas sob demanda
    "/paginas/melhorias.js": "paginas/melhorias.js",
    "/paginas/conectores.js": "paginas/conectores.js",
    "/paginas/conversa.js": "paginas/conversa.js",
    "/paginas/skills.js": "paginas/skills.js",
    "/paginas/memoria.js": "paginas/memoria.js",
    "/paginas/atendimento.js": "paginas/atendimento.js",
    "/paginas/atualizacoes.js": "paginas/atualizacoes.js",
    # O ícone na tela inicial do celular (instalar como app).
    "/manifest.webmanifest": "manifest.webmanifest",
    "/icones/ze-192.webp": "icones/ze-192.webp",
    "/icones/ze-512.webp": "icones/ze-512.webp",
    # O holograma da Imersão no celular.
    "/imagens/holograma.webp": "imagens/holograma.webp",
}

# O que a tela "Entrar" usa, antes de entrar (o manifesto deixa instalar o ícone já ali).
LIVRES = {
    "/painel.css",
    "/oauth-retorno.js",
    "/ze.webp",
    "/manifest.webmanifest",
    "/icones/ze-192.webp",
    "/icones/ze-512.webp",
}
COOKIE = "ze_acesso"

Leitura = Callable[[], Any]
Voz = Callable[[websocket.Conexao, int], None]  # o canal de voz do navegador (bloqueia até fechar)
# O do app de voz: a conexão, a taxa, o modo ("chamado" ou "ao_vivo") e o aparelho pareado.
VozApp = Callable[[websocket.Conexao, int, str, dict[str, Any]], None]
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
        acesso: Acesso | None = None,
        voz: Voz | None = None,
        entrada_terminal: Escrita | None = None,
        so_no_pc: set[str] | None = None,
        servidor: bool = False,
        retorno_oauth: Callable[[str], tuple[bool, str]] | None = None,
        voz_app: VozApp | None = None,
        aparelhos_voz: AparelhosDeVoz | None = None,
    ) -> None:
        self.acesso = acesso
        self.voz_app = voz_app
        self.aparelhos_voz = aparelhos_voz
        self.retorno_oauth = retorno_oauth
        # Num servidor não há o "próprio PC": quem entrou com a senha e o código do autenticador
        # faz os ajustes de fora (menos desligar as proteções e o acesso pelo qual entrou).
        self.servidor = servidor
        # Ajustes de acesso (senha, código, túnel): só pelo próprio PC. Quem entrou de fora não
        # desliga as proteções que o deixaram entrar.
        self.so_no_pc = so_no_pc or set()
        self.voz = voz
        self.entrada_terminal = entrada_terminal
        self.leituras = leituras
        self.escritas = escritas
        self.envios = envios or {}
        self.token = token or secrets.token_urlsafe(32)
        self.http = ThreadingHTTPServer(("127.0.0.1", porta), self._tratador())
        self.http.daemon_threads = True
        self.porta = self.http.server_port
        self.locais = {f"127.0.0.1:{self.porta}", f"localhost:{self.porta}"}
        self.hosts = set(self.locais)

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

            def _cookie(self) -> str:
                for parte in self.headers.get("Cookie", "").split(";"):
                    nome, _, valor = parte.strip().partition("=")
                    if nome == COOKIE:
                        return valor
                return ""

            def _repassado(self) -> bool:
                """Chegou por um túnel ou proxy (Cloudflare, Tailscale): é outro aparelho, mesmo
                que o `Host` diga o endereço local."""
                return any(self.headers.get(c) for c in ("Cf-Connecting-Ip", "X-Forwarded-For"))

            def _entrou(self) -> bool:
                """O próprio PC entra direto; outro aparelho, só com o cookie da senha."""
                if self.headers.get("Host", "") in portal.locais and not self._repassado():
                    return True
                return portal.acesso is not None and portal.acesso.valido(self._cookie())

            def _local(self) -> bool:
                return self.headers.get("Host", "") in portal.locais and not self._repassado()

            def _pode_ajustar(self, rota: str) -> bool:
                """Os ajustes de acesso e do próprio Zé: o PC sempre; num servidor, também quem
                entrou com o código do autenticador. Ligar o código vale para qualquer aparelho
                que entrou, enquanto ele estiver desligado: só aumenta a proteção."""
                if self._local():
                    return True
                if not portal.servidor or portal.acesso is None or rota in SEMPRE_NO_PC:
                    return False
                if rota in LIGAR_CODIGO and not portal.acesso.tem_codigo:
                    return portal.acesso.valido(self._cookie())
                return portal.acesso.confiavel(self._cookie())

            def _autorizado(self) -> bool:
                return (
                    self._host_local()
                    and self._entrou()
                    and hmac.compare_digest(self.headers.get("X-Ze-Token", ""), portal.token)
                )

            def _ir(self, destino: str, cookie: str = "") -> None:
                self.send_response(303)
                self.send_header("Location", destino)
                self.send_header("Cache-Control", "no-store")
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _tela_entrar(self, mensagem: str = "") -> None:
                corpo = (WEB / "entrar.html").read_bytes()
                aviso = f'<p class="resultado erro">{mensagem}</p>' if mensagem else ""
                if portal.acesso is not None and portal.acesso.convite_valido:
                    titulo, sub, botao = (
                        "Primeiro acesso",
                        "Use o código que o instalador mostrou e crie a senha do painel.",
                        "Criar acesso",
                    )
                    campos = (
                        '<label>Código de primeiro acesso<input name="convite" '
                        'autocomplete="off" autocapitalize="characters" spellcheck="false" '
                        'maxlength="9" required autofocus></label>'
                        '<label>Nova senha<input type="password" name="senha" minlength="8" '
                        'autocomplete="new-password" required></label>'
                    )
                else:
                    titulo, sub, botao = (
                        "Entrar",
                        "Acesso de outro aparelho.",
                        "Entrar",
                    )
                    codigo = (
                        '<label>Código do autenticador<input name="codigo" inputmode="numeric" '
                        'autocomplete="one-time-code" pattern="[0-9 ]*" maxlength="7" required>'
                        "</label>"
                        if portal.acesso is not None and portal.acesso.tem_codigo
                        else ""
                    )
                    campos = (
                        '<label>Senha<input type="password" name="senha" '
                        'autocomplete="current-password" required autofocus></label>'
                        + codigo
                        + '<label class="interruptor"><input type="checkbox" name="lembrar" '
                        'value="1" checked> Lembrar este aparelho</label>'
                    )
                for marca, valor in (
                    ("__TITULO__", titulo),
                    ("__SUB__", sub),
                    ("__CAMPOS__", campos),
                    ("__BOTAO__", botao),
                    ("__MENSAGEM__", aviso),
                ):
                    corpo = corpo.replace(marca.encode(), valor.encode())
                self._enviar(200, corpo, "text/html")

            def _origem(self) -> str:
                """O endereço de quem pede: o que o túnel ou proxy informa, senão a conexão."""
                if ip := self.headers.get("Cf-Connecting-Ip"):
                    return ip.strip()
                if repasse := self.headers.get("X-Forwarded-For"):
                    return repasse.split(",")[0].strip()
                return str(self.client_address[0])

            def _entrar(self) -> None:
                tamanho = min(int(self.headers.get("Content-Length") or 0), 4096)
                campos = parse_qs(self.rfile.read(tamanho).decode(errors="replace"))
                senha = campos.get("senha", [""])[0]
                codigo = campos.get("codigo", [""])[0]
                lembrar = campos.get("lembrar", [""])[0] == "1"
                convite = campos.get("convite", [""])[0]
                if portal.acesso is None:
                    self._tela_entrar("Acesso por outro aparelho indisponível.")
                    return
                try:
                    if convite:
                        aparelho, validade = portal.acesso.criar_acesso(
                            convite, senha, self.headers.get("User-Agent", ""), self._origem()
                        )
                    else:
                        aparelho, validade = portal.acesso.entrar(
                            senha,
                            codigo,
                            lembrar,
                            self.headers.get("User-Agent", ""),
                            self._origem(),
                        )
                except SenhaErro as erro:
                    log.warning("painel: entrada recusada de %s (%s)", self._origem(), erro)
                    self._tela_entrar(str(erro))
                    return
                log.info("painel: um aparelho entrou")
                cookie = (
                    f"{COOKIE}={aparelho}; Path=/; HttpOnly; Secure; SameSite=Strict; "
                    f"Max-Age={validade}"
                )
                # Primeiro acesso: a próxima etapa é ligar o código do autenticador (página Voz).
                self._ir("/#voz" if convite else "/", cookie)

            def _mesma_origem(self) -> bool:
                """O WebSocket leva o cookie sozinho: outro site não pode abri-lo em nome de quem
                já entrou (a origem precisa ser o próprio endereço do painel)."""
                return urlsplit(self.headers.get("Origin", "")).netloc == self.headers.get("Host")

            def _voz(self) -> None:
                if portal.voz is None or not self._entrou() or not self._mesma_origem():
                    self._json(403, {"erro": "voz"})
                    return
                conexao = websocket.aceitar(self)
                if conexao is None:
                    self._json(400, {"erro": "esperado WebSocket"})
                    return
                try:
                    self.connection.settimeout(10)  # a primeira mensagem traz o código do painel
                    _, primeira = conexao.receber()
                    self.connection.settimeout(None)
                    dados = json.loads(primeira)
                    if not hmac.compare_digest(str(dados.get("token", "")), portal.token):
                        raise ValueError("token")
                    taxa = int(dados.get("taxa", 16000))
                except (OSError, ValueError, AttributeError, websocket.FechouErro):
                    conexao.fechar()
                    return
                portal.voz(conexao, taxa)

            def _parear_voz_app(self) -> None:
                """O app troca o código do painel pela chave só de voz."""
                if portal.aparelhos_voz is None:
                    self._json(404, {"erro": "não existe"})
                    return
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > 4096:
                    self._json(413, {"erro": "grande demais"})
                    return
                try:
                    dados = json.loads(self.rfile.read(tamanho) or b"{}")
                    chave = portal.aparelhos_voz.parear(
                        str(dados.get("codigo", "")), str(dados.get("nome", ""))
                    )
                except PareamentoErro as erro:
                    self._json(403, {"erro": str(erro)})
                    return
                except (ValueError, AttributeError):
                    self._json(400, {"erro": "JSON inválido"})
                    return
                log.warning("app de voz: aparelho pareado")
                self._json(200, {"chave": chave})

            def _voz_app(self) -> None:
                """A voz do app: a chave do pareamento no cabeçalho, sem cookie nem origem (não é
                um navegador, e a chave não abre mais nada)."""
                autorizacao = self.headers.get("Authorization", "")
                chave = autorizacao[7:] if autorizacao.startswith("Bearer ") else ""
                aparelho = portal.aparelhos_voz.aparelho(chave) if portal.aparelhos_voz else None
                if portal.voz_app is None or aparelho is None:
                    self._json(403, {"erro": "voz"})
                    return
                conexao = websocket.aceitar(self)
                if conexao is None:
                    self._json(400, {"erro": "esperado WebSocket"})
                    return
                try:
                    self.connection.settimeout(10)
                    _, primeira = conexao.receber()
                    self.connection.settimeout(None)
                    dados = json.loads(primeira)
                    taxa = int(dados.get("taxa", 16000))
                    modo = str(dados.get("modo", "chamado"))
                except (OSError, ValueError, AttributeError, websocket.FechouErro):
                    conexao.fechar()
                    return
                portal.voz_app(
                    conexao, taxa, modo if modo in ("chamado", "ao_vivo") else "chamado", aparelho
                )

            def _terminal(self) -> None:
                if portal.entrada_terminal is None:
                    self._json(404, {"erro": "não existe"})
                    return
                if not self._entrou() or not self._mesma_origem():
                    self._json(403, {"erro": "terminal"})
                    return
                conexao = websocket.aceitar(self)
                if conexao is None:
                    self._json(400, {"erro": "esperado WebSocket"})
                    return
                try:
                    self.connection.settimeout(10)
                    tipo, primeira = conexao.receber()
                    if tipo != websocket.TEXTO:
                        raise ValueError("token")
                    dados = json.loads(primeira)
                    if not isinstance(dados, dict):
                        raise ValueError("token")
                    token = dados.get("token")
                    id_ = dados.get("id")
                    if (
                        not isinstance(token, str)
                        or not hmac.compare_digest(token, portal.token)
                        or not isinstance(id_, str)
                        or not id_
                        or len(id_) > 128
                    ):
                        raise ValueError("token")
                    self.connection.settimeout(None)
                    conexao.texto(json.dumps({"tipo": "pronto"}))
                    while True:
                        tipo, entrada = conexao.receber()
                        if tipo != websocket.TEXTO:
                            raise websocket.FechouErro("entrada de terminal inválida")
                        if len(entrada) > MAXIMO_CORPO:
                            raise PedidoInvalido("Entrada do terminal grande demais.")
                        try:
                            texto = entrada.decode("utf-8")
                        except UnicodeDecodeError:
                            raise PedidoInvalido("Entrada do terminal inválida.") from None
                        portal.entrada_terminal({"id": id_, "dados": texto})
                except PedidoInvalido as erro:
                    with contextlib.suppress(websocket.FechouErro):
                        conexao.texto(json.dumps({"tipo": "erro", "erro": str(erro)}))
                except (OSError, ValueError, TypeError, AttributeError, websocket.FechouErro):
                    pass
                except Exception:
                    log.exception("painel: falha na entrada do terminal")
                    with contextlib.suppress(websocket.FechouErro):
                        conexao.texto(json.dumps({"tipo": "erro", "erro": "Falha no terminal."}))
                finally:
                    conexao.fechar()

            def _retorno_oauth(self) -> None:
                if portal.retorno_oauth is None:
                    self._json(404, {"erro": "não existe"})
                    return
                ok, mensagem = portal.retorno_oauth(urlsplit(self.path).query)
                corpo = (
                    '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<title>Conectores</title><link rel="stylesheet" href="/painel.css"></head>'
                    '<body><main class="entrar"><section class="cartao"><h1>Conectores</h1>'
                    f'<p class="resultado {"ok" if ok else "erro"}">{html.escape(mensagem)}</p>'
                    '<a class="acao principal" href="/#conectores">Voltar ao painel</a>'
                    f'<script src="/oauth-retorno.js" data-ok="{int(ok)}"></script>'
                    "</section></main></body></html>"
                )
                self._enviar(200 if ok else 400, corpo.encode(), "text/html")

            def do_GET(self) -> None:
                if not self._host_local():
                    self._json(403, {"erro": "host"})
                    return
                caminho = self.path.split("?", 1)[0]
                if caminho == "/oauth/retorno":
                    self._retorno_oauth()
                    return
                if caminho == "/api/voz/ws":
                    self._voz()
                    return
                if caminho == "/api/terminal/ws":
                    self._terminal()
                    return
                if caminho == "/voz-app/ws":
                    self._voz_app()
                    return
                if caminho == "/entrar":
                    if self._entrou():
                        self._ir("/")
                    else:
                        self._tela_entrar()
                    return
                if not self._entrou() and caminho not in LIVRES:
                    if caminho.startswith("/api/"):
                        self._json(401, {"erro": "entrar"})
                    else:
                        self._ir("/entrar")
                    return
                if caminho in ARQUIVOS:
                    arquivo = WEB / ARQUIVOS[caminho]
                    corpo = arquivo.read_bytes()
                    if arquivo.name == "index.html":
                        corpo = corpo.replace(b"__TOKEN__", portal.token.encode())
                        ajustes = self._local() or (
                            portal.servidor
                            and portal.acesso is not None
                            and portal.acesso.confiavel(self._cookie())
                        )
                        corpo = corpo.replace(b"__AJUSTES__", b"1" if ajustes else b"0")
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
                if caminho == "/voz-app/parear" and self._host_local():
                    self._parear_voz_app()
                    return
                if caminho in ("/entrar", "/sair") and self._host_local():
                    if caminho == "/entrar":
                        self._entrar()
                    else:
                        if portal.acesso is not None:
                            portal.acesso.sair(self._cookie())
                        self._ir("/entrar", f"{COOKIE}=; Path=/; Max-Age=0")
                    return
                if not self._autorizado():
                    self._json(403, {"erro": "token"})
                    return
                if caminho[5:] in portal.so_no_pc and not self._pode_ajustar(caminho[5:]):
                    erro = (
                        "Ligue o código do autenticador e entre de novo para este ajuste."
                        if portal.servidor and caminho[5:] not in SEMPRE_NO_PC
                        else "Ajuste disponível só no computador do Zé."
                    )
                    self._json(403, {"erro": erro})
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
                except (BrokenPipeError, ConnectionResetError):
                    return  # a página saiu antes da resposta (trocou de tela, fechou): não é falha
                except PedidoInvalido as erro:
                    self._json(400, {"erro": str(erro)})
                except Exception:
                    log.exception("painel: falha em %s", self.path)
                    self._json(500, {"erro": "falha interna; veja o log do Zé"})

        return Tratador
