"""Login OAuth dos conectores MCP remotos (ADR 0037), feito pelo Zé e não por cada agente.

O fluxo da especificação de autorização do MCP (2025-06-18):
1. **Descoberta:** o servidor MCP responde 401 e aponta os metadados do recurso
   (`/.well-known/oauth-protected-resource`), que dizem qual é o servidor de autorização; deste
   vêm os endereços de autorização, de token e de registro. Os endereços candidatos, na ordem da
   especificação, vêm do SDK oficial do MCP.
2. **Registro dinâmico do cliente** (RFC 7591): o Zé se registra com o endereço de volta do
   painel. Servidores que não aceitam isso exigem um app cadastrado à mão no fornecedor: o
   Client ID (e o secret, se houver) fica em `<chaves>/mcp/<conector>/cliente.json` (0600) e
   vale no lugar do registro; o secret vai no corpo do pedido ou no `Authorization: Basic`,
   conforme o que o servidor declara aceitar (`token_endpoint_auth_methods_supported`).
3. **Autorização com PKCE** (S256) e `resource` (RFC 8707): a pessoa entra no navegador; o
   servidor volta ao painel com o código, que só vale junto do verificador guardado aqui.
4. **Tokens** em `<chaves>/mcp/<conector>/oauth.json` (0600), renovados pelo `refresh_token`
   antes de vencer. Quem usa o token é a ponte local (`mcp_ponte.py`), nunca o cérebro.

Cada login em andamento vive 10 minutos e o `state` vale uma vez só.
"""

import base64
import contextlib
import hashlib
import json
import logging
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
)

from jarvis.cerebro import mcp_externo

log = logging.getLogger(__name__)
ARQUIVO = "oauth.json"
CLIENTE = "cliente.json"  # o app cadastrado à mão (Client ID e secret), ao lado dos tokens
TEXTO_DO_CLIENTE = re.compile(r"[\x21-\x7e]{1,2000}")  # imprimível, sem espaço
VALIDADE_DO_LOGIN_S = 600
RENOVAR_ANTES_S = 120
LIMITE_S = 15.0
RETORNO = "/oauth/retorno"
CAMPO_WWW = re.compile(r'(\w+)="([^"]*)"')
# Alguns fornecedores barram o "Python-urllib" padrão (o Notion responde 403; visto em 19/10/2026).
AGENTE = "Ze/1 (Zervis)"


class OAuthErro(mcp_externo.McpInvalido):
    """Mensagem curta para a tela."""


@dataclass
class Login:
    nome: str
    verificador: str
    retorno: str
    cliente: dict[str, Any]
    token_endpoint: str
    recurso: str
    criado: float
    metodo: str = "post"  # como o secret vai ao servidor: "post" (no corpo) ou "basic"


def _seguro(url: str) -> bool:
    partes = urlsplit(url)
    local = partes.hostname in ("127.0.0.1", "localhost", "::1")
    return partes.scheme == "https" or (partes.scheme == "http" and local)


def _pedir(
    url: str,
    form: dict[str, str] | None = None,
    corpo: dict[str, Any] | None = None,
    cabecalhos: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET (sem corpo) ou POST (formulário ou JSON) que devolve o JSON da resposta."""
    if not _seguro(url):
        raise OAuthErro("endereço sem https")
    dados = None
    cab = {"Accept": "application/json", "User-Agent": AGENTE, **(cabecalhos or {})}
    if form is not None:
        dados = urlencode(form).encode()
        cab["Content-Type"] = "application/x-www-form-urlencoded"
    elif corpo is not None:
        dados = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    pedido = urllib.request.Request(url, data=dados, headers=cab)  # noqa: S310 (https conferido)
    with urllib.request.urlopen(pedido, timeout=LIMITE_S) as resposta:  # noqa: S310
        resultado = json.loads(resposta.read().decode("utf-8", "replace") or "{}")
    if not isinstance(resultado, dict):
        raise OAuthErro("resposta inesperada do servidor de login")
    return resultado


def _metodo(autorizacao: dict[str, Any], com_segredo: bool) -> str:
    """Basic só quando o servidor declara aceitar só ele; sem declaração, o corpo do pedido."""
    aceitos = autorizacao.get("token_endpoint_auth_methods_supported") or []
    if com_segredo and "client_secret_post" not in aceitos and "client_secret_basic" in aceitos:
        return "basic"
    return "post"


def _credenciais(cliente: dict[str, Any], metodo: str) -> tuple[dict[str, str], dict[str, str]]:
    """O que identifica o cliente num pedido de token: campos do corpo e cabeçalhos."""
    corpo = {"client_id": str(cliente["client_id"])}
    cabecalhos: dict[str, str] = {}
    if segredo := cliente.get("client_secret"):
        if metodo == "basic":  # RFC 6749 2.3.1: id e secret em urlencoded, depois em base64
            par = f"{quote(str(cliente['client_id']), safe='')}:{quote(str(segredo), safe='')}"
            cabecalhos["Authorization"] = "Basic " + base64.b64encode(par.encode()).decode()
        else:
            corpo["client_secret"] = str(segredo)
    return corpo, cabecalhos


def _primeiro(urls: list[str]) -> dict[str, Any] | None:
    for url in urls:
        with contextlib.suppress(urllib.error.URLError, OSError, ValueError, OAuthErro):
            return _pedir(url)
    return None


def _desafio_www(url_mcp: str) -> dict[str, str]:
    """Os campos do `WWW-Authenticate` do 401 que o servidor MCP dá a quem chega sem token."""
    inicio = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "ze", "version": "1"},
        },
    }
    try:
        _pedir(url_mcp, corpo=inicio, cabecalhos={"Accept": "application/json, text/event-stream"})
    except urllib.error.HTTPError as erro:
        if erro.code == 401:
            return dict(CAMPO_WWW.findall(erro.headers.get("WWW-Authenticate", "")))
        raise OAuthErro(f"o servidor respondeu HTTP {erro.code}") from None
    except (urllib.error.URLError, OSError) as erro:
        raise OAuthErro(f"sem conexão com o servidor ({type(erro).__name__})") from None
    except ValueError:
        pass  # respondeu sem JSON (fluxo SSE): sem 401, não pede login
    raise OAuthErro("este servidor não pede login")


def descobrir(url_mcp: str) -> tuple[dict[str, Any], str, str]:
    """Os metadados do servidor de autorização, o recurso e o escopo a pedir."""
    www = _desafio_www(url_mcp)
    prm = _primeiro(
        build_protected_resource_metadata_discovery_urls(www.get("resource_metadata"), url_mcp)
    )
    servidores = (prm or {}).get("authorization_servers") or [None]
    autorizacao = _primeiro(
        build_oauth_authorization_server_metadata_discovery_urls(servidores[0], url_mcp)
    )
    if not autorizacao or not autorizacao.get("authorization_endpoint"):
        raise OAuthErro("o servidor não publica como entrar")
    escopos = (prm or {}).get("scopes_supported") or []
    escopo = www.get("scope") or " ".join(str(e) for e in escopos)
    recurso = str((prm or {}).get("resource") or url_mcp)
    return autorizacao, recurso, escopo


def _pkce() -> tuple[str, str]:
    verificador = secrets.token_urlsafe(64)
    resumo = hashlib.sha256(verificador.encode()).digest()
    return verificador, base64.urlsafe_b64encode(resumo).rstrip(b"=").decode()


class Logins:
    def __init__(self) -> None:
        self._andamento: dict[str, Login] = {}
        self._trava = threading.Lock()
        self._travas: dict[str, threading.Lock] = {}

    # --- arquivo ----------------------------------------------------------------------------

    @staticmethod
    def _arquivo(nome: str, arquivo: str = ARQUIVO) -> Path:
        if not mcp_externo.NOME.fullmatch(nome):
            raise OAuthErro("conector inválido")
        return mcp_externo.SEGREDOS / nome / arquivo

    def cliente_proprio(self, nome: str) -> dict[str, str] | None:
        """O app cadastrado à mão para este conector (Client ID e, se houver, o secret)."""
        try:
            dados = json.loads(self._arquivo(nome, CLIENTE).read_text())
        except (OSError, ValueError):
            return None
        if isinstance(dados, dict) and isinstance(dados.get("client_id"), str):
            return {k: dados[k] for k in ("client_id", "client_secret") if dados.get(k)}
        return None

    def guardar_cliente(self, nome: str, client_id: str, client_secret: str = "") -> None:
        client_id, client_secret = client_id.strip(), client_secret.strip()
        if not TEXTO_DO_CLIENTE.fullmatch(client_id):
            raise OAuthErro("Client ID vazio ou com espaços")
        if client_secret and not TEXTO_DO_CLIENTE.fullmatch(client_secret):
            raise OAuthErro("Client secret com espaços ou grande demais")
        self._gravar(
            nome, {"client_id": client_id, "client_secret": client_secret}, arquivo=CLIENTE
        )

    def apagar_cliente(self, nome: str) -> None:
        self._arquivo(nome, CLIENTE).unlink(missing_ok=True)

    def _ler(self, nome: str) -> dict[str, Any]:
        try:
            dados = json.loads(self._arquivo(nome).read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _gravar(self, nome: str, dados: dict[str, Any], arquivo: str = ARQUIVO) -> None:
        destino = self._arquivo(nome, arquivo)
        destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for pasta in (mcp_externo.SEGREDOS, destino.parent):
            pasta.chmod(0o700)
        temporario = destino.with_suffix(".next")
        temporario.touch(mode=0o600)
        temporario.chmod(0o600)
        temporario.write_text(json.dumps(dados))
        temporario.replace(destino)

    def conectado(self, nome: str) -> bool:
        dados = self._ler(nome)
        return bool(dados.get("refresh_token") or dados.get("expira_em", 0) > time.time())

    def sair(self, nome: str) -> None:
        self._arquivo(nome).unlink(missing_ok=True)

    # --- entrar -----------------------------------------------------------------------------

    def iniciar(self, nome: str, url_mcp: str, retorno: str) -> str:
        """O endereço de login para abrir no navegador; a volta chega em `concluir`."""
        if not _seguro(retorno) or urlsplit(retorno).path != RETORNO:
            raise OAuthErro("endereço de volta inválido")
        autorizacao, recurso, escopo = descobrir(url_mcp)
        metodos = autorizacao.get("code_challenge_methods_supported") or ["S256"]
        if "S256" not in metodos:
            raise OAuthErro("o servidor não aceita PKCE")
        cliente = self.cliente_proprio(nome) or self._registrar(autorizacao, retorno, nome)
        verificador, desafio = _pkce()
        estado = secrets.token_urlsafe(32)
        parametros = {
            "response_type": "code",
            "client_id": str(cliente["client_id"]),
            "redirect_uri": retorno,
            "code_challenge": desafio,
            "code_challenge_method": "S256",
            "state": estado,
            "resource": recurso,
        }
        if escopo:
            parametros["scope"] = escopo
        with self._trava:
            agora = time.time()
            self._andamento = {
                k: v
                for k, v in self._andamento.items()
                if agora - v.criado < VALIDADE_DO_LOGIN_S and v.nome != nome
            }
            self._andamento[estado] = Login(
                nome,
                verificador,
                retorno,
                {k: cliente[k] for k in ("client_id", "client_secret") if cliente.get(k)},
                str(autorizacao["token_endpoint"]),
                recurso,
                agora,
                _metodo(autorizacao, bool(cliente.get("client_secret"))),
            )
        separador = "&" if "?" in str(autorizacao["authorization_endpoint"]) else "?"
        return f"{autorizacao['authorization_endpoint']}{separador}{urlencode(parametros)}"

    @staticmethod
    def _registrar(autorizacao: dict[str, Any], retorno: str, nome: str) -> dict[str, Any]:
        """O registro dinâmico do cliente (RFC 7591), para servidores que o oferecem."""
        registro = autorizacao.get("registration_endpoint")
        if not registro:
            raise OAuthErro(
                "o servidor não aceita o registro automático: guarde o Client ID de um app "
                f"próprio nos detalhes do conector {nome}"
            )
        try:
            cliente = _pedir(
                str(registro),
                corpo={
                    "client_name": "Zé (Zérvis)",
                    "redirect_uris": [retorno],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
        except urllib.error.HTTPError as erro:
            raise OAuthErro(f"registro recusado (HTTP {erro.code})") from None
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise OAuthErro(f"registro sem resposta ({type(erro).__name__})") from None
        if not cliente.get("client_id"):
            raise OAuthErro("registro sem identificador do cliente")
        return cliente

    def concluir(self, consulta: str) -> str:
        """A volta do login (a parte depois do `?`): troca o código pelos tokens; devolve o nome
        do conector."""
        campos = {k: v[0] for k, v in parse_qs(consulta).items()}
        with self._trava:
            login = self._andamento.pop(campos.get("state", ""), None)
        if login is None or time.time() - login.criado > VALIDADE_DO_LOGIN_S:
            raise OAuthErro("login expirado: tente de novo")
        if erro := campos.get("error"):
            raise OAuthErro(campos.get("error_description") or erro)
        if not campos.get("code"):
            raise OAuthErro("o servidor não devolveu o código")
        corpo, cabecalhos = _credenciais(login.cliente, login.metodo)
        tokens = self._trocar(
            login.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": campos["code"],
                "redirect_uri": login.retorno,
                "code_verifier": login.verificador,
                "resource": login.recurso,
                **corpo,
            },
            cabecalhos,
        )
        self._gravar(
            login.nome,
            {
                **tokens,
                "token_endpoint": login.token_endpoint,
                "cliente": login.cliente,
                "metodo": login.metodo,
                "recurso": login.recurso,
            },
        )
        log.info("conector %s: login feito", login.nome)
        return login.nome

    @staticmethod
    def _trocar(
        endpoint: str, form: dict[str, str], cabecalhos: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            resposta = _pedir(endpoint, form=form, cabecalhos=cabecalhos)
        except urllib.error.HTTPError as erro:
            raise OAuthErro(f"o servidor recusou o token (HTTP {erro.code})") from None
        except (urllib.error.URLError, OSError) as erro:
            raise OAuthErro(f"sem conexão com o servidor ({type(erro).__name__})") from None
        if not resposta.get("access_token"):
            raise OAuthErro("o servidor não devolveu o token")
        tokens = {"access_token": str(resposta["access_token"])}
        if resposta.get("refresh_token"):
            tokens["refresh_token"] = str(resposta["refresh_token"])
        validade = resposta.get("expires_in")
        expira = time.time() + float(validade) if isinstance(validade, int | float) else 0.0
        return {**tokens, "expira_em": expira}

    # --- usar -------------------------------------------------------------------------------

    def token(self, nome: str, renovar: bool = False) -> str | None:
        """O token de acesso em dia (renova se vence em menos de 2 minutos, ou se `renovar`);
        None se é preciso entrar de novo."""
        with self._trava:
            trava = self._travas.setdefault(nome, threading.Lock())
        with trava:
            dados = self._ler(nome)
            if not dados.get("access_token"):
                return None
            expira = float(dados.get("expira_em") or 0)
            if not renovar and (not expira or expira - time.time() > RENOVAR_ANTES_S):
                return str(dados["access_token"])
            if not dados.get("refresh_token"):
                return None if expira and expira <= time.time() else str(dados["access_token"])
            corpo, cabecalhos = _credenciais(
                dados.get("cliente") or {"client_id": ""}, str(dados.get("metodo", "post"))
            )
            form = {
                "grant_type": "refresh_token",
                "refresh_token": str(dados["refresh_token"]),
                "resource": str(dados.get("recurso", "")),
                **corpo,
            }
            try:
                novos = self._trocar(str(dados["token_endpoint"]), form, cabecalhos)
            except OAuthErro as erro:
                log.warning("conector %s: token não renovado (%s)", nome, erro)
                return None
            novos.setdefault("refresh_token", dados["refresh_token"])
            self._gravar(nome, {**dados, **novos})
            return str(novos["access_token"])


PADRAO = Logins()


def concluir_pela_volta(consulta: str) -> tuple[bool, str]:
    """A rota `/oauth/retorno` do painel: o resultado do login para a página de volta."""
    try:
        nome = PADRAO.concluir(consulta)
    except OAuthErro as erro:
        log.warning("login de conector recusado: %s", erro)
        return False, f"Login não concluído: {erro}."
    return True, f"Conector {nome} conectado."
