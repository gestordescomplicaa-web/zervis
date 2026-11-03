"""O Instagram do Zé, só leitura (ADR 0057): o perfil, as publicações e as métricas de cada uma,
para ele analisar com você ("qual post me rendeu mais visualizações?").

Pela API oficial da Meta (v26.0), com a conta Profissional de quem usa. Nada aqui publica,
responde ou comenta: só GET. Vale o token do "Login do Instagram" (começa com IG,
`graph.instagram.com`, renovado sozinho a cada semana) e o do "Login do Facebook" (começa com EAA,
`graph.facebook.com`, achando a conta do Instagram ligada à Página).

O token fica em `<config>/instagram.key` (0600); nunca em log. As métricas vêm em cache
(`<dados>/instagram-cache.json`): post da última semana relido em 1 hora, os outros em 1 dia.
"""

import concurrent.futures
import contextlib
import json
import logging
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import lugares

log = logging.getLogger(__name__)

ARQUIVO = lugares.CONFIG / "instagram.key"
CACHE = lugares.DADOS / "instagram-cache.json"
VERSAO = "v26.0"
HOSTS = {"ig": "https://graph.instagram.com", "fb": "https://graph.facebook.com"}
ESPERA_S = 15.0
RENOVAR_S = 7 * 86400  # o token do Login do Instagram vale 60 dias; renovar toda semana basta
RECENTE_S = 7 * 86400
CACHE_RECENTE_S = 3600
CACHE_ANTIGO_S = 86400
LISTA_S = 3600
MAXIMO_POSTS = 200
PARALELO = 8
CAMPOS_PERFIL = "username,name,followers_count,follows_count,media_count"
CAMPOS_POST = (
    "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"
)
# As métricas de cada tipo (as de "impressions" e "plays" foram descontinuadas pela Meta).
METRICAS = {
    "REELS": "views,reach,likes,comments,saved,shares,total_interactions,ig_reels_avg_watch_time",
    "FEED": "views,reach,likes,comments,saved,shares,total_interactions",
}
METRICAS_CONTA = (
    "reach,views,accounts_engaged,total_interactions,likes,comments,saves,shares,"
    "profile_links_taps,follows_and_unfollows"
)


class InstagramErro(RuntimeError):
    """Mensagem curta, pronta para a tela e a voz."""


def extrair_token(colado: str) -> str:
    """O token do que a pessoa colou: o token puro, uma URL com `access_token=` ou o JSON que o
    Explorador da Graph API mostra."""
    texto = colado.strip()
    na_url = re.search(r"access_token=([A-Za-z0-9._|-]+)", texto)
    if na_url:
        return na_url.group(1)
    no_json = re.search(r'"access_token"\s*:\s*"([A-Za-z0-9._|-]+)"', texto)
    if no_json:
        return no_json.group(1)
    achado = re.search(r"\b((?:IG|EAA)[A-Za-z0-9._|-]{40,})", texto)
    return achado.group(1) if achado else texto


def _gravar_privado(arquivo: Path, dados: dict[str, Any]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=arquivo.parent, delete=False
    ) as saida:
        temporario = Path(saida.name)  # nasce 0600
        try:
            json.dump(dados, saida, ensure_ascii=False)
            saida.flush()
            temporario.replace(arquivo)
        finally:
            temporario.unlink(missing_ok=True)


def _ler(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _tipo(post: dict[str, Any]) -> str:
    """reels, carrossel, post ou story."""
    produto = str(post.get("media_product_type", "")).upper()
    if produto == "REELS":
        return "reels"
    if produto == "STORY":
        return "story"
    return "carrossel" if post.get("media_type") == "CAROUSEL_ALBUM" else "post"


class Instagram:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        cache: Path = CACHE,
        abrir: Callable[..., Any] = urllib.request.urlopen,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self.arquivo = arquivo
        self.cache = cache
        self.abrir = abrir
        self.agora = agora
        self._trava = threading.RLock()

    # --- a conta ------------------------------------------------------------------------------

    @property
    def conta(self) -> dict[str, Any]:
        return _ler(self.arquivo)

    @property
    def conectado(self) -> bool:
        return bool(self.conta.get("token"))

    def _pedir(self, base: str, caminho: str, params: dict[str, str], token: str) -> Any:
        consulta = urllib.parse.urlencode({**params, "access_token": token})
        url = f"{HOSTS[base]}/{VERSAO}/{caminho.lstrip('/')}?{consulta}"
        if caminho.startswith("refresh_access_token"):
            url = f"{HOSTS[base]}/{caminho}?{consulta}"  # a renovação não leva a versão
        try:
            pedido = urllib.request.Request(url)  # noqa: S310 (sempre um dos HOSTS, https)
            with self.abrir(pedido, timeout=ESPERA_S) as resposta:
                return json.loads(resposta.read() or b"{}")
        except urllib.error.HTTPError as erro:
            raise self._recusa(erro) from erro
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise InstagramErro("Sem conexão com o Instagram.") from erro

    @staticmethod
    def _recusa(erro: urllib.error.HTTPError) -> InstagramErro:
        """A recusa da Meta na frase da tela; o registro leva o código, nunca o token."""
        detalhe: dict[str, Any] = {}
        with contextlib.suppress(ValueError, OSError, AttributeError):
            detalhe = json.loads(erro.read() or b"{}").get("error", {})
        codigo = detalhe.get("code")
        log.warning("instagram: recusado (%s, código %s)", erro.code, codigo)
        if codigo == 190:
            return InstagramErro("Token inválido ou vencido. Cole um novo.")
        if codigo in (10, 200) or erro.code == 403:
            return InstagramErro("O token não tem permissão para as métricas do Instagram.")
        if codigo in (4, 17, 32, 613):
            return InstagramErro("Limite de consultas do Instagram. Tente em alguns minutos.")
        return InstagramErro("O Instagram recusou a consulta.")

    def conectar(self, colado: str) -> str:
        """Confere o token colado, descobre a conta e guarda. Devolve "@usuario"."""
        token = extrair_token(colado)
        # O formato do que chegou (nunca o token): diz se colaram o ID ou a chave do app.
        log.info("instagram: conectando (%s…, %d caracteres)", token[:4], len(token))
        if len(token) < 40 or not token.startswith(("IG", "EAA")):
            raise InstagramErro(
                "Token de acesso não reconhecido: ele começa com IG ou EAA e é longo. "
                "O ID e a chave secreta do app não servem."
            )
        base, conta, usuario = "", "", ""
        if token.startswith("IG"):
            eu = self._pedir("ig", "me", {"fields": "user_id,username"}, token)
            base, usuario = "ig", str(eu.get("username", ""))
            conta = str(eu.get("user_id") or eu.get("id") or "")
        else:
            paginas = self._pedir(
                "fb", "me/accounts", {"fields": "instagram_business_account{id,username}"}, token
            )
            for p in paginas.get("data", []) if isinstance(paginas, dict) else []:
                ig = p.get("instagram_business_account") if isinstance(p, dict) else None
                if isinstance(ig, dict) and ig.get("id"):
                    base, conta, usuario = "fb", str(ig["id"]), str(ig.get("username", ""))
                    break
        if not conta:
            raise InstagramErro("Nenhuma conta Profissional do Instagram nesse token.")
        agora = self.agora()
        _gravar_privado(
            self.arquivo,
            {"token": token, "base": base, "conta": conta, "usuario": usuario,
             "guardado": agora, "renovado": agora},
        )  # fmt: skip
        self.cache.unlink(missing_ok=True)  # métricas de outra conta não servem
        log.info("instagram: conectado (login %s)", "Instagram" if base == "ig" else "Facebook")
        return f"@{usuario}" if usuario else "a conta"

    def desconectar(self) -> None:
        self.arquivo.unlink(missing_ok=True)
        self.cache.unlink(missing_ok=True)

    def _token(self) -> tuple[str, str, str]:
        """(base, conta, token), renovando o do Login do Instagram quando passa de uma semana."""
        c = self.conta
        if not c.get("token"):
            raise InstagramErro("Instagram não conectado.")
        if c.get("base") == "ig" and self.agora() - float(c.get("renovado", 0)) > RENOVAR_S:
            try:
                novo = self._pedir(
                    "ig", "refresh_access_token", {"grant_type": "ig_refresh_token"}, c["token"]
                )
                if isinstance(novo, dict) and novo.get("access_token"):
                    c = {**c, "token": novo["access_token"], "renovado": self.agora()}
                    _gravar_privado(self.arquivo, c)
                    log.info("instagram: token renovado")
            except InstagramErro as erro:
                log.warning("instagram: não renovou o token: %s", erro)
        return str(c["base"]), str(c["conta"]), str(c["token"])

    # --- leituras -----------------------------------------------------------------------------

    def perfil(self) -> dict[str, Any]:
        base, conta, token = self._token()
        dados = self._pedir(base, "me" if base == "ig" else conta, {"fields": CAMPOS_PERFIL}, token)
        return dados if isinstance(dados, dict) else {}

    def conta_no_periodo(self, dias: int = 30) -> dict[str, int]:
        """Os totais da conta no período (até 30 dias, o limite da Meta): alcance, contas
        engajadas, interações, visitas aos links e seguidores ganhos e perdidos."""
        base, conta, token = self._token()
        dias = max(1, min(30, dias))
        ate = int(self.agora())
        params = {
            "metric": METRICAS_CONTA, "period": "day", "metric_type": "total_value",
            "since": str(ate - dias * 86400), "until": str(ate),
        }  # fmt: skip
        dados = self._pedir(base, f"{'me' if base == 'ig' else conta}/insights", params, token)
        saida: dict[str, int] = {}
        for m in dados.get("data", []) if isinstance(dados, dict) else []:
            total = (m.get("total_value") or {}).get("value") if isinstance(m, dict) else None
            if isinstance(total, int | float):
                saida[str(m.get("name"))] = int(total)
        return saida

    def _lista(self, base: str, conta: str, token: str) -> list[dict[str, Any]]:
        caminho = f"{'me' if base == 'ig' else conta}/media"
        params: dict[str, str] = {"fields": CAMPOS_POST, "limit": "50"}
        posts: list[dict[str, Any]] = []
        while len(posts) < MAXIMO_POSTS:
            pagina = self._pedir(base, caminho, params, token)
            posts += [p for p in pagina.get("data", []) if isinstance(p, dict) and p.get("id")]
            depois = ((pagina.get("paging") or {}).get("cursors") or {}).get("after")
            if not depois or not (pagina.get("paging") or {}).get("next"):
                break
            params = {**params, "after": str(depois)}
        return posts[:MAXIMO_POSTS]

    def _metricas(self, base: str, token: str, post: dict[str, Any]) -> dict[str, float]:
        metricas = METRICAS["REELS" if _tipo(post) == "reels" else "FEED"]
        try:
            dados = self._pedir(base, f"{post['id']}/insights", {"metric": metricas}, token)
        except InstagramErro as erro:
            log.info("instagram: sem métricas de um post (%s)", erro)
            return {}
        saida: dict[str, float] = {}
        for m in dados.get("data", []) if isinstance(dados, dict) else []:
            if not isinstance(m, dict):
                continue
            valores = m.get("values") or []
            valor = valores[0].get("value") if valores and isinstance(valores[0], dict) else None
            if valor is None:
                valor = (m.get("total_value") or {}).get("value")
            if isinstance(valor, int | float):
                saida[str(m.get("name"))] = valor
        return saida

    def posts(self) -> list[dict[str, Any]]:
        """As publicações (sem os stories), cada uma com as métricas, do cache quando valem."""
        with self._trava:
            base, conta, token = self._token()
            cache = _ler(self.cache)
            if cache.get("conta") != conta:
                cache = {"conta": conta}
            agora = self.agora()
            if agora - float(cache.get("lista_em", 0)) > LISTA_S or "lista" not in cache:
                cache["lista"] = [p for p in self._lista(base, conta, token) if _tipo(p) != "story"]
                cache["lista_em"] = agora
            metricas: dict[str, Any] = cache.setdefault("metricas", {})
            vencidos = [p for p in cache["lista"] if self._vencido(p, metricas.get(p["id"]), agora)]
            if vencidos:
                with concurrent.futures.ThreadPoolExecutor(PARALELO) as grupo:
                    lidas = list(grupo.map(lambda p: self._metricas(base, token, p), vencidos))
                for p, m in zip(vencidos, lidas, strict=True):
                    metricas[p["id"]] = {"valores": m, "lido": agora}
            _gravar_privado(self.cache, cache)
            return [
                {
                    **p,
                    "tipo": _tipo(p),
                    "metricas": (metricas.get(p["id"]) or {}).get("valores", {}),
                }
                for p in cache["lista"]
            ]

    @staticmethod
    def _vencido(post: dict[str, Any], guardado: Any, agora: float) -> bool:
        if not isinstance(guardado, dict):
            return True
        idade = agora - _epoch(post.get("timestamp"))
        prazo = CACHE_RECENTE_S if idade < RECENTE_S else CACHE_ANTIGO_S
        return agora - float(guardado.get("lido", 0)) > prazo


def _epoch(carimbo: Any) -> float:
    """O `timestamp` da Meta ("2026-11-03T13:42:00+0000") em epoch; 0 se não vier."""
    try:
        return datetime.strptime(str(carimbo), "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except ValueError:
        return 0.0
