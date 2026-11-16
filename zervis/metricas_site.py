"""As métricas do site, só leitura (ADR 0094): como ele aparece no Google (Search Console) e quem
o visita (Google Analytics 4), para o Zé responder "quantas pessoas leram o blog esta semana?".

O acesso é uma conta de serviço do Google Cloud de quem usa: a chave JSON fica em
`<config>/google-metricas.json` (0600), e a pessoa libera o e-mail dela como usuária no Search
Console e como leitora no GA4. O escopo pedido é só de leitura; nada aqui escreve no Google.

O site declara no `zervis.json` o domínio, o começo das páginas do blog e, se quiser, a
propriedade do GA4 (`docs/integrar-site.md`). Sem a propriedade, vale a única que a conta vê.
"""

import base64
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
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from zervis import lugares, marketing

log = logging.getLogger(__name__)

ARQUIVO = lugares.CONFIG / "google-metricas.json"
# Fixo: o `token_uri` da chave não escolhe para onde vai a assinatura.
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (um endereço, não um segredo)
ESCOPOS = (
    "https://www.googleapis.com/auth/webmasters.readonly "
    "https://www.googleapis.com/auth/analytics.readonly"
)
BUSCA = "https://www.googleapis.com/webmasters/v3"
DADOS_GA = "https://analyticsdata.googleapis.com/v1beta"
ADMIN_GA = "https://analyticsadmin.googleapis.com/v1beta"
ESPERA_S = 20.0
CACHE_S = 1800.0
MAXIMO_DIAS_BUSCA = 480  # o Search Console guarda 16 meses
MAXIMO_DIAS_VISITAS = 365
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.iam\.gserviceaccount\.com")
PROPRIEDADE = re.compile(r"\d{4,20}")
DOMINIO = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")
# Os grupos de origem do GA4, em português (os que faltarem aparecem como vêm).
ORIGENS = {
    "Direct": "Direto",
    "Organic Search": "Busca orgânica",
    "Organic Social": "Redes sociais",
    "Paid Search": "Busca paga",
    "Paid Social": "Redes sociais pagas",
    "Referral": "Outros sites",
    "Email": "E-mail",
    "Organic Video": "Vídeo",
    "Unassigned": "Sem origem",
}
APIS = {
    "www.googleapis.com": "Google Search Console API",
    "analyticsdata.googleapis.com": "Google Analytics Data API",
    "analyticsadmin.googleapis.com": "Google Analytics Admin API",
}


class MetricasErro(RuntimeError):
    """Mensagem curta, pronta para a tela e a voz."""


@dataclass(frozen=True)
class Declaracao:
    """O que o `zervis.json` do site declara das métricas."""

    dominio: str = ""
    blog: str = "/blog/"
    ga4: str = ""  # o número da propriedade do GA4 (não o ID de medição G-...)


def ler_declaracao(texto: str) -> Declaracao | None:
    """As métricas declaradas no `zervis.json` (None se não houver ou estiverem malformadas)."""
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    m = dados.get("metricas") if isinstance(dados, dict) else None
    if not isinstance(m, dict):
        return None
    dominio = str(m.get("dominio", "")).strip().lower().removeprefix("www.")
    blog = "/" + str(m.get("blog") or "/blog/").strip().strip("/") + "/"
    ga4 = str(m.get("ga4", "")).strip().removeprefix("properties/")
    return Declaracao(
        dominio=dominio if DOMINIO.fullmatch(dominio) else "",
        blog=blog if re.fullmatch(r"/[\w/-]*", blog) else "/blog/",
        ga4=ga4 if PROPRIEDADE.fullmatch(ga4) else "",
    )


def ler_chave(colado: str) -> dict[str, str]:
    """A chave da conta de serviço que a pessoa colou: só os campos que o Zé usa."""
    try:
        dados = json.loads(colado.strip())
    except ValueError as erro:
        raise MetricasErro("A chave não é um JSON válido.") from erro
    if not isinstance(dados, dict) or dados.get("type") != "service_account":
        raise MetricasErro("A chave precisa ser de uma conta de serviço.")
    email = str(dados.get("client_email", ""))
    privada = str(dados.get("private_key", ""))
    if not EMAIL.fullmatch(email) or "PRIVATE KEY" not in privada:
        raise MetricasErro("A chave está incompleta.")
    try:
        _privada(privada)
    except (ValueError, TypeError) as erro:
        raise MetricasErro("A chave está incompleta.") from erro
    return {"client_email": email, "private_key": privada}


def _privada(pem: str) -> rsa.RSAPrivateKey:
    chave = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(chave, rsa.RSAPrivateKey):
        raise ValueError("não é RSA")
    return chave


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def assinatura(chave: dict[str, str], agora: float) -> str:
    """O JWT (RS256) que troca a chave da conta de serviço por um token de acesso."""
    cabeca = {"alg": "RS256", "typ": "JWT"}
    corpo = {
        "iss": chave["client_email"],
        "scope": ESCOPOS,
        "aud": TOKEN_URL,
        "iat": int(agora),
        "exp": int(agora) + 3600,
    }
    texto = f"{_b64(json.dumps(cabeca).encode())}.{_b64(json.dumps(corpo).encode())}"
    assinado = _privada(chave["private_key"]).sign(
        texto.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{texto}.{_b64(assinado)}"


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


def _erro_do_google(host: str, codigo: int, corpo: str) -> MetricasErro:
    if "SERVICE_DISABLED" in corpo or "has not been used" in corpo:
        return MetricasErro(f"Ative a {APIS.get(host, 'API')} no Google Cloud.")
    if codigo in (401, 403):
        return MetricasErro("Sem permissão no Google para a conta de serviço.")
    if codigo == 429:
        return MetricasErro("O Google limitou as consultas agora. Tente mais tarde.")
    return MetricasErro(f"O Google recusou a consulta ({codigo}).")


def _numero(valor: Any) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


class Metricas:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        declaracao: Callable[[], Declaracao | None] = lambda: None,
        abrir: Callable[..., Any] = urllib.request.urlopen,
        agora: Callable[[], float] = time.time,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        self.arquivo = arquivo
        self.declaracao = declaracao
        self.abrir = abrir
        self.agora = agora
        self.hoje = hoje
        self._trava = threading.Lock()
        self._token: tuple[str, float] = ("", 0.0)
        self._cache: dict[str, tuple[float, Any]] = {}

    # --- a chave ------------------------------------------------------------------------------

    def _chave(self) -> dict[str, str]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    @property
    def configurado(self) -> bool:
        return bool(self._chave().get("private_key"))

    @property
    def conta(self) -> str:
        return str(self._chave().get("client_email", ""))

    def guardar(self, colado: str) -> str:
        """Confere a chave no Google e guarda. Devolve o e-mail da conta de serviço."""
        chave = ler_chave(colado)
        self._trocar(chave)  # chave recusada não é guardada
        _gravar_privado(self.arquivo, chave)
        with self._trava:
            self._cache.clear()
        return chave["client_email"]

    def remover(self) -> None:
        self.arquivo.unlink(missing_ok=True)
        with self._trava:
            self._token = ("", 0.0)
            self._cache.clear()

    # --- o Google -----------------------------------------------------------------------------

    def _trocar(self, chave: dict[str, str]) -> str:
        corpo = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assinatura(chave, self.agora()),
            }
        ).encode()
        pedido = urllib.request.Request(TOKEN_URL, data=corpo, method="POST")
        pedido.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.abrir(pedido, timeout=ESPERA_S) as resposta:
                dados = json.loads(resposta.read())
        except urllib.error.HTTPError as erro:
            raise MetricasErro("Chave inválida.") from erro
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            raise MetricasErro("Sem conexão com o Google.") from erro
        except ValueError as erro:
            raise MetricasErro("Resposta inesperada do Google.") from erro
        token = str(dados.get("access_token", "")) if isinstance(dados, dict) else ""
        if not token:
            raise MetricasErro("Chave inválida.")
        validade = _numero(dados.get("expires_in")) or 3600.0
        self._token = (token, self.agora() + validade - 120)
        return token

    def _token_atual(self) -> str:
        token, ate = self._token
        if token and self.agora() < ate:
            return token
        chave = self._chave()
        if not chave.get("private_key"):
            raise MetricasErro("As métricas do site não estão configuradas.")
        return self._trocar(chave)

    def _pedir(self, url: str, corpo: dict[str, Any] | None = None) -> Any:
        host = urllib.parse.urlsplit(url).hostname or ""
        if host not in APIS:
            raise MetricasErro("Endereço do Google inesperado.")
        dados = json.dumps(corpo).encode() if corpo is not None else None
        pedido = urllib.request.Request(url, data=dados, method="POST" if dados else "GET")  # noqa: S310
        pedido.add_header("Authorization", f"Bearer {self._token_atual()}")
        if dados:
            pedido.add_header("Content-Type", "application/json")
        try:
            with self.abrir(pedido, timeout=ESPERA_S) as resposta:
                return json.loads(resposta.read() or b"{}")
        except urllib.error.HTTPError as erro:
            texto = ""
            with contextlib.suppress(Exception):
                texto = erro.read().decode(errors="replace")[:2000]
            log.info("google %s: %s", host, erro.code)  # sem o corpo: pode trazer a conta
            raise _erro_do_google(host, erro.code, texto) from erro
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            raise MetricasErro("Sem conexão com o Google.") from erro
        except ValueError as erro:
            raise MetricasErro("Resposta inesperada do Google.") from erro

    def _guardado(self, chave: str, fazer: Callable[[], Any]) -> Any:
        with self._trava:
            achado = self._cache.get(chave)
        if achado and self.agora() - achado[0] < CACHE_S:
            return achado[1]
        valor = fazer()
        with self._trava:
            self._cache[chave] = (self.agora(), valor)
        return valor

    # --- o Search Console ---------------------------------------------------------------------

    def site_na_busca(self) -> str:
        """A propriedade do Search Console: a do domínio declarado ou a única que a conta vê."""

        def achar() -> str:
            dados = self._pedir(f"{BUSCA}/sites")
            sites = [str(s.get("siteUrl", "")) for s in dados.get("siteEntry") or []]
            if not sites:
                raise MetricasErro("Nenhum site do Search Console liberado para a conta.")
            d = self.declaracao()
            dominio = d.dominio if d else ""
            if dominio:
                for preferido in (
                    f"sc-domain:{dominio}",
                    f"https://www.{dominio}/",
                    f"https://{dominio}/",
                    f"http://www.{dominio}/",
                    f"http://{dominio}/",
                ):
                    if preferido in sites:
                        return preferido
                raise MetricasErro(f"O Search Console não tem o site {dominio} liberado.")
            if len(sites) > 1:
                raise MetricasErro("Declare o domínio do site no zervis.json.")
            return sites[0]

        return str(self._guardado("site", achar))

    def _consulta_busca(self, site: str, dias: int, dimensao: str, quantos: int) -> list[Any]:
        fim = self.hoje()
        corpo: dict[str, Any] = {
            "startDate": (fim - timedelta(days=dias - 1)).isoformat(),
            "endDate": fim.isoformat(),
            "dataState": "all",  # os dados dos últimos dias também, ainda que parciais
            "rowLimit": quantos,
        }
        if dimensao:
            corpo["dimensions"] = [dimensao]
        url = f"{BUSCA}/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
        return list(self._pedir(url, corpo).get("rows") or [])

    def busca(self, dias: int = 28, por: str = "buscas", quantos: int = 10) -> dict[str, Any]:
        """Cliques, impressões, CTR e posição média no Google, e as buscas ou páginas do topo."""
        dias = max(1, min(MAXIMO_DIAS_BUSCA, dias))
        dimensao = "page" if por == "paginas" else "query"

        def ler() -> dict[str, Any]:
            site = self.site_na_busca()
            total = self._consulta_busca(site, dias, "", 1)
            linhas = self._consulta_busca(site, dias, dimensao, quantos)
            t = total[0] if total else {}
            return {
                "site": site,
                "dias": dias,
                "cliques": int(_numero(t.get("clicks"))),
                "impressoes": int(_numero(t.get("impressions"))),
                "ctr": round(_numero(t.get("ctr")) * 100, 1),
                "posicao": round(_numero(t.get("position")), 1),
                "por": "paginas" if dimensao == "page" else "buscas",
                "linhas": [
                    {
                        "nome": str((r.get("keys") or [""])[0]),
                        "cliques": int(_numero(r.get("clicks"))),
                        "impressoes": int(_numero(r.get("impressions"))),
                        "posicao": round(_numero(r.get("position")), 1),
                    }
                    for r in linhas
                ],
            }

        return dict(self._guardado(f"busca:{dias}:{dimensao}:{quantos}", ler))

    # --- o Google Analytics 4 -----------------------------------------------------------------

    def propriedade(self) -> str:
        """A propriedade do GA4: a declarada no `zervis.json` ou a única que a conta vê."""
        d = self.declaracao()
        if d and d.ga4:
            return d.ga4

        def achar() -> str:
            dados = self._pedir(f"{ADMIN_GA}/accountSummaries")
            achadas = [
                str(p.get("property", "")).removeprefix("properties/")
                for conta in dados.get("accountSummaries") or []
                for p in conta.get("propertySummaries") or []
            ]
            if not achadas:
                raise MetricasErro("Nenhuma propriedade do GA4 liberada para a conta.")
            if len(achadas) > 1:
                raise MetricasErro("Declare a propriedade do GA4 no zervis.json.")
            return achadas[0]

        return str(self._guardado("propriedade", achar))

    def _relatorio(self, corpo: dict[str, Any]) -> list[list[str]]:
        url = f"{DADOS_GA}/properties/{self.propriedade()}:runReport"
        linhas = self._pedir(url, corpo).get("rows") or []
        return [
            [str(v.get("value", "")) for v in r.get("dimensionValues") or []]
            + [str(v.get("value", "")) for v in r.get("metricValues") or []]
            for r in linhas
        ]

    def visitas(
        self, dias: int = 28, por: str = "paginas", quantos: int = 10, so_blog: bool = False
    ) -> dict[str, Any]:
        """Visitantes, visitas, visualizações e tempo médio; as páginas mais vistas, de onde
        vieram ou para onde clicaram (o WhatsApp, por exemplo)."""
        dias = max(1, min(MAXIMO_DIAS_VISITAS, dias))
        por = por if por in ("paginas", "origens", "cliques") else "paginas"
        d = self.declaracao()
        prefixo = d.blog if d else "/blog/"
        periodo = [{"startDate": f"{dias - 1}daysAgo", "endDate": "today"}]
        filtro_blog = {
            "filter": {
                "fieldName": "pagePath",
                "stringFilter": {"matchType": "BEGINS_WITH", "value": prefixo},
            }
        }

        def ler() -> dict[str, Any]:
            totais: dict[str, Any] = {
                "dateRanges": periodo,
                "metrics": [
                    {"name": n}
                    for n in (
                        "activeUsers",
                        "sessions",
                        "screenPageViews",
                        "userEngagementDuration",
                    )
                ],
            }
            if so_blog:
                totais["dimensionFilter"] = filtro_blog
            t = (self._relatorio(totais) or [["0", "0", "0", "0"]])[0]
            visitantes, sessoes, vistas, engajamento = (int(_numero(v)) for v in t[:4])
            if por == "origens":
                corpo: dict[str, Any] = {
                    "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                    "metrics": [{"name": "sessions"}, {"name": "activeUsers"}],
                }
            elif por == "cliques":
                corpo = {
                    "dimensions": [{"name": "linkDomain"}],
                    "metrics": [{"name": "eventCount"}, {"name": "activeUsers"}],
                    "dimensionFilter": {
                        "filter": {"fieldName": "eventName", "stringFilter": {"value": "click"}}
                    },
                }
            else:
                corpo = {
                    "dimensions": [{"name": "pagePath"}, {"name": "pageTitle"}],
                    "metrics": [
                        {"name": "screenPageViews"},
                        {"name": "activeUsers"},
                        {"name": "userEngagementDuration"},
                    ],
                }
                if so_blog:
                    corpo["dimensionFilter"] = filtro_blog
            corpo["dateRanges"] = periodo
            corpo["limit"] = quantos
            corpo["orderBys"] = [
                {"metric": {"metricName": corpo["metrics"][0]["name"]}, "desc": True}
            ]
            return {
                "dias": dias,
                "blog": so_blog,
                "visitantes": visitantes,
                "visitas": sessoes,
                "visualizacoes": vistas,
                "tempo_medio_s": round(engajamento / visitantes) if visitantes else 0,
                "por": por,
                "linhas": [self._linha(por, r) for r in self._relatorio(corpo)],
            }

        return dict(self._guardado(f"visitas:{dias}:{por}:{quantos}:{so_blog}", ler))

    @staticmethod
    def _linha(por: str, r: list[str]) -> dict[str, Any]:
        if por == "origens":
            return {
                "nome": ORIGENS.get(r[0], r[0]),
                "visitas": int(_numero(r[1])),
                "visitantes": int(_numero(r[2])),
            }
        if por == "cliques":
            return {
                "nome": r[0] or "(sem domínio)",
                "cliques": int(_numero(r[1])),
                "visitantes": int(_numero(r[2])),
            }
        visitantes = int(_numero(r[3]))
        return {
            "nome": r[0],
            "titulo": r[1],
            "visualizacoes": int(_numero(r[2])),
            "visitantes": visitantes,
            "tempo_medio_s": round(_numero(r[4]) / visitantes) if visitantes else 0,
        }

    # --- para o painel ------------------------------------------------------------------------

    def resumo(self, dias: int = 28) -> dict[str, Any]:
        """O cartão de Métricas: as duas fontes, cada uma com o seu erro, sem derrubar a outra."""
        if not self.configurado:
            return {"configurado": False, "conta": "", "dias": dias}
        saida: dict[str, Any] = {"configurado": True, "conta": self.conta, "dias": dias}
        leituras: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
            ("busca", lambda: self.busca(dias, "buscas", 5)),
            ("visitas", lambda: self.visitas(dias, "paginas", 5)),
        )
        for nome, ler in leituras:
            try:
                saida[nome] = ler()
            except MetricasErro as erro:
                saida[nome] = {"erro": str(erro)}
        return saida


# --- para a voz: poucas linhas prontas ------------------------------------------------------


def _tempo(segundos: int) -> str:
    if segundos < 60:
        return f"{segundos} s"
    return f"{segundos // 60} min {segundos % 60:02d} s"


def texto_busca(b: dict[str, Any]) -> str:
    linhas = [
        f"Google, últimos {b['dias']} dias ({b['site']}): {b['cliques']} cliques, "
        f"{b['impressoes']} impressões, CTR {b['ctr']}%, posição média {b['posicao']}."
    ]
    rotulo = "Páginas" if b["por"] == "paginas" else "Buscas"
    if b["linhas"]:
        linhas.append(f"{rotulo} do topo:")
        linhas += [
            f"- {r['nome']}: {r['cliques']} cliques, {r['impressoes']} impressões, "
            f"posição {r['posicao']}"
            for r in b["linhas"]
        ]
    else:
        linhas.append(f"{rotulo}: nenhuma no período.")
    return "\n".join(linhas)


def texto_visitas(v: dict[str, Any]) -> str:
    onde = "Blog" if v["blog"] else "Site"
    linhas = [
        f"{onde}, últimos {v['dias']} dias: {v['visitantes']} visitantes, {v['visitas']} visitas, "
        f"{v['visualizacoes']} visualizações, tempo médio {_tempo(v['tempo_medio_s'])}."
    ]
    if not v["linhas"]:
        linhas.append("Nenhum dado no período.")
    elif v["por"] == "origens":
        linhas.append("De onde vieram:")
        linhas += [f"- {r['nome']}: {r['visitas']} visitas" for r in v["linhas"]]
    elif v["por"] == "cliques":
        linhas.append("Cliques para fora do site:")
        linhas += [f"- {r['nome']}: {r['cliques']} cliques" for r in v["linhas"]]
    else:
        linhas.append("Páginas mais vistas:")
        linhas += [
            f"- {r['titulo'] or r['nome']} ({r['nome']}): {r['visualizacoes']} visualizações, "
            f"{r['visitantes']} visitantes, {_tempo(r['tempo_medio_s'])} em média"
            for r in v["linhas"]
        ]
    return "\n".join(linhas)


def _declaracao_do_site() -> Declaracao | None:
    site = marketing.PADRAO.site()
    if not site.pasta or not site.base:
        return None
    texto = marketing.PADRAO._mostrar(site, marketing.MANIFESTO)
    return ler_declaracao(texto) if texto else None


PADRAO = Metricas(declaracao=_declaracao_do_site)
