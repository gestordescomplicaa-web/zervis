"""Login OAuth dos conectores MCP remotos e a ponte local que renova o token (ADR 0037).

Um servidor falso faz o papel do fornecedor: o MCP protegido (401 com `WWW-Authenticate`), os
metadados do recurso e do servidor de autorização, o registro dinâmico e o token com PKCE e
renovação. O navegador da pessoa é simulado pelo código de autorização posto direto no servidor.
"""

import base64
import hashlib
import json
import stat
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from jarvis.cerebro import conectores, mcp_externo, mcp_oauth, mcp_ponte
from jarvis.cerebro.mcp_oauth import Logins, OAuthErro
from jarvis.portal.servidor import Portal

RETORNO = "http://127.0.0.1:8795/oauth/retorno"


class Fornecedor:
    """O estado do fornecedor falso: clientes, códigos e tokens válidos."""

    def __init__(self) -> None:
        self.clientes: dict[str, list[str]] = {}
        self.codigos: dict[str, tuple[str, str]] = {}  # código -> (desafio, retorno)
        self.validos: set[str] = set()
        self.renovacoes: set[str] = set()
        self.emitidos = 0
        self.sse = False  # responder em fluxo SSE, como muitos MCPs remotos
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), self._tratador())
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def _emitir(self) -> dict[str, Any]:
        self.emitidos += 1
        acesso, renovacao = f"acesso-{self.emitidos}", f"renovacao-{self.emitidos}"
        self.validos = {acesso}
        self.renovacoes = {renovacao}
        return {"access_token": acesso, "refresh_token": renovacao, "expires_in": 3600}

    def _tratador(self) -> type[BaseHTTPRequestHandler]:
        f = self

        class Tratador(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return None

            def _json(self, status: int, dados: Any, extra: dict[str, str] | None = None) -> None:
                corpo = json.dumps(dados).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(corpo)

            def do_GET(self) -> None:
                if self.path == "/.well-known/oauth-protected-resource/mcp":
                    self._json(
                        200,
                        {
                            "resource": f"{f.base}/mcp",
                            "authorization_servers": [f.base],
                            "scopes_supported": ["ler"],
                        },
                    )
                elif self.path == "/.well-known/oauth-authorization-server":
                    self._json(
                        200,
                        {
                            "issuer": f.base,
                            "authorization_endpoint": f"{f.base}/authorize",
                            "token_endpoint": f"{f.base}/token",
                            "registration_endpoint": f"{f.base}/register",
                            "code_challenge_methods_supported": ["S256"],
                        },
                    )
                else:
                    self._json(404, {})

            def do_POST(self) -> None:
                corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/register":
                    dados = json.loads(corpo)
                    f.clientes["cliente-1"] = dados["redirect_uris"]
                    self._json(201, {"client_id": "cliente-1"})
                elif self.path == "/token":
                    self._token({k: v[0] for k, v in parse_qs(corpo.decode()).items()})
                elif self.path == "/mcp":
                    self._mcp(json.loads(corpo))

            def _token(self, form: dict[str, str]) -> None:
                if form["grant_type"] == "authorization_code":
                    desafio, retorno = f.codigos.pop(form["code"], ("", ""))
                    resumo = hashlib.sha256(form["code_verifier"].encode()).digest()
                    calculado = base64.urlsafe_b64encode(resumo).rstrip(b"=").decode()
                    if calculado != desafio or retorno != form["redirect_uri"]:
                        self._json(400, {"error": "invalid_grant"})
                        return
                elif form.get("refresh_token") not in f.renovacoes:
                    self._json(400, {"error": "invalid_grant"})
                    return
                self._json(200, f._emitir())

            def _mcp(self, msg: dict[str, Any]) -> None:
                token = self.headers.get("Authorization", "").removeprefix("Bearer ")
                if token not in f.validos:
                    metadados = f"{f.base}/.well-known/oauth-protected-resource/mcp"
                    desafio = f'Bearer resource_metadata="{metadados}", scope="ler"'
                    self._json(401, {"error": "invalid_token"}, {"WWW-Authenticate": desafio})
                    return
                if "id" not in msg:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                resultado: dict[str, Any] = {"protocolVersion": "2025-06-18", "capabilities": {}}
                if msg["method"] == "tools/list":
                    resultado = {"tools": [{"name": "buscar", "description": "Busca páginas"}]}
                if f.sse:
                    evento = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": resultado})
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Mcp-Session-Id", "sessao-1")
                    self.end_headers()
                    self.wfile.write(f"event: message\ndata: {evento}\n\n".encode())
                    self.close_connection = True
                    return
                self._json(
                    200,
                    {"jsonrpc": "2.0", "id": msg["id"], "result": resultado},
                    {"Mcp-Session-Id": "sessao-1"},
                )

        return Tratador


@pytest.fixture
def fornecedor() -> Iterator[Fornecedor]:
    f = Fornecedor()
    yield f
    f.http.shutdown()
    f.http.server_close()


@pytest.fixture
def logins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Logins]:
    monkeypatch.setattr(mcp_externo, "CAMINHO", tmp_path / "mcp.toml")
    monkeypatch.setattr(mcp_externo, "PAINEL", tmp_path / "mcp-painel.json")
    monkeypatch.setattr(mcp_externo, "SEGREDOS", tmp_path / "chaves" / "mcp")
    novos = Logins()
    ponte = mcp_ponte.Ponte(mcp_ponte._destino, novos)
    monkeypatch.setattr(mcp_oauth, "PADRAO", novos)
    monkeypatch.setattr(mcp_ponte, "PADRAO", ponte)
    yield novos
    ponte.parar()


def entrar(fornecedor: Fornecedor, logins: Logins, nome: str = "docs") -> str:
    """O login inteiro, com a pessoa aprovando no navegador do fornecedor."""
    url = logins.iniciar(nome, f"{fornecedor.base}/mcp", RETORNO)
    pedido = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert url.startswith(f"{fornecedor.base}/authorize?")
    assert pedido["code_challenge_method"] == "S256" and pedido["redirect_uri"] == RETORNO
    assert pedido["resource"] == f"{fornecedor.base}/mcp" and pedido["scope"] == "ler"
    assert fornecedor.clientes["cliente-1"] == [RETORNO]
    fornecedor.codigos["codigo-1"] = (pedido["code_challenge"], RETORNO)
    return pedido["state"]


def test_login_completo_guarda_os_tokens_0600(fornecedor: Fornecedor, logins: Logins) -> None:
    estado = entrar(fornecedor, logins)
    assert logins.concluir(f"code=codigo-1&state={estado}") == "docs"
    arquivo = mcp_externo.SEGREDOS / "docs" / "oauth.json"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert logins.conectado("docs") and logins.token("docs") == "acesso-1"
    # O `state` vale uma vez só.
    with pytest.raises(OAuthErro, match="expirado"):
        logins.concluir(f"code=codigo-1&state={estado}")
    logins.sair("docs")
    assert not logins.conectado("docs")


def test_login_recusado_ou_adulterado(fornecedor: Fornecedor, logins: Logins) -> None:
    with pytest.raises(OAuthErro, match="expirado"):
        logins.concluir("code=x&state=inventado")
    estado = entrar(fornecedor, logins)
    with pytest.raises(OAuthErro, match="negado"):
        logins.concluir(f"error=access_denied&error_description=negado&state={estado}")
    estado = entrar(fornecedor, logins)
    fornecedor.codigos["codigo-1"] = ("outro-desafio", RETORNO)  # verificador não confere
    with pytest.raises(OAuthErro, match="recusou"):
        logins.concluir(f"code=codigo-1&state={estado}")
    with pytest.raises(OAuthErro, match="volta"):
        logins.iniciar("docs", f"{fornecedor.base}/mcp", "https://outro.site/qualquer")


def test_token_perto_de_vencer_e_renovado(fornecedor: Fornecedor, logins: Logins) -> None:
    logins.concluir(f"code=codigo-1&state={entrar(fornecedor, logins)}")
    arquivo = mcp_externo.SEGREDOS / "docs" / "oauth.json"
    dados = json.loads(arquivo.read_text())
    arquivo.write_text(json.dumps({**dados, "expira_em": time.time() + 30}))
    assert logins.token("docs") == "acesso-2"
    assert json.loads(arquivo.read_text())["refresh_token"] == "renovacao-2"  # noqa: S105


def test_a_ponte_entrega_com_o_token_e_renova_no_401(
    fornecedor: Fornecedor, logins: Logins
) -> None:
    conectores.salvar(
        "docs",
        {"tipo": "http", "url": f"{fornecedor.base}/mcp", "oauth": True},
        mcp_externo.PAINEL,
        mcp_externo.CAMINHO,
    )
    assert conectores.testar("docs", mcp_externo.CAMINHO, mcp_externo.PAINEL, env={}) == {
        "ok": False,
        "erro": "falta entrar",
    }
    logins.concluir(f"code=codigo-1&state={entrar(fornecedor, logins)}")
    carregado = mcp_externo.carregar(mcp_externo.CAMINHO, env={}, painel=mcp_externo.PAINEL)
    config = carregado.servidores["docs"]
    assert config["url"].startswith("http://127.0.0.1:") and "acesso" not in json.dumps(config)
    r = conectores.testar("docs", mcp_externo.CAMINHO, mcp_externo.PAINEL, env={})
    assert r["ok"] and [f["nome"] for f in r["ferramentas"]] == ["buscar"]
    fornecedor.validos.clear()  # o servidor recusa o token antes da hora
    r = conectores.testar("docs", mcp_externo.CAMINHO, mcp_externo.PAINEL, env={})
    assert r["ok"] and logins.token("docs") == "acesso-2"
    fornecedor.sse = True
    r = conectores.testar("docs", mcp_externo.CAMINHO, mcp_externo.PAINEL, env={})
    assert r["ok"] and [f["nome"] for f in r["ferramentas"]] == ["buscar"]
    # Sem o segredo da ponte, nada passa.
    sem_segredo = urllib.request.Request(config["url"], data=b"{}", method="POST")  # noqa: S310
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(sem_segredo, timeout=5)  # noqa: S310 (loopback do teste)
    assert erro.value.code == 403
    (listado,) = conectores.listar(mcp_externo.CAMINHO, mcp_externo.PAINEL, env={})
    assert listado["oauth"] and listado["conectado"] and listado["segredos"] == {}
    # Sem como renovar (a pessoa saiu), a ponte pede um novo login sem responder 401.
    logins.sair("docs")
    r = conectores.testar("docs", mcp_externo.CAMINHO, mcp_externo.PAINEL, env={})
    assert r == {"ok": False, "erro": "falta entrar"}
    com_segredo = urllib.request.Request(  # noqa: S310
        config["url"], data=b"{}", method="POST", headers=config["headers"]
    )
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(com_segredo, timeout=5)  # noqa: S310 (loopback do teste)
    assert erro.value.code == 503


def test_conector_com_login_nao_leva_segredo_proprio(logins: Logins) -> None:
    with pytest.raises(mcp_externo.McpInvalido, match="OAuth"):
        conectores.salvar(
            "docs",
            {
                "tipo": "http",
                "url": "https://mcp.docs.com/mcp",
                "oauth": True,
                "cabecalhos": {"Authorization": "DOCS_AUTH"},
            },
            mcp_externo.PAINEL,
            mcp_externo.CAMINHO,
        )


def test_a_volta_do_login_abre_sem_cookie_so_no_endereco_do_painel() -> None:
    vistos: list[str] = []

    def concluir(consulta: str) -> tuple[bool, str]:
        vistos.append(consulta)
        return True, "Conector <docs> conectado."

    portal = Portal({}, {}, porta=0, retorno_oauth=concluir)
    portal.iniciar()
    try:
        url = f"http://127.0.0.1:{portal.porta}/oauth/retorno?code=c&state=s"
        with urllib.request.urlopen(url, timeout=5) as resposta:
            pagina = resposta.read().decode()
        assert vistos == ["code=c&state=s"] and "Conector &lt;docs&gt; conectado." in pagina
        # A aba do login fecha sozinha ou, se não der, volta ao painel pelo link; o script vem
        # do próprio painel (a CSP não deixa script na página) e abre sem o cookie.
        assert 'href="/#conectores"' in pagina and 'data-ok="1"' in pagina
        assert '<script src="/oauth-retorno.js"' in pagina
        with urllib.request.urlopen(f"http://127.0.0.1:{portal.porta}/oauth-retorno.js") as js:
            assert b"window.close()" in js.read()
        de_fora = urllib.request.Request(url, headers={"Host": "outro.site"})
        with pytest.raises(urllib.error.HTTPError) as erro:
            urllib.request.urlopen(de_fora, timeout=5)  # noqa: S310
        assert erro.value.code == 403 and len(vistos) == 1
    finally:
        portal.parar()
