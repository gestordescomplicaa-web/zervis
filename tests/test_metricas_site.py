"""As métricas do site, só leitura (ADR 0094): a chave da conta de serviço, o Search Console, o
GA4, o cache e o texto que a voz recebe."""

import asyncio
import base64
import io
import json
import stat
import urllib.error
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from zervis import metricas_site as ms
from zervis.cerebro.ferramentas import LIVRES, SERVIDOR, de_fora
from zervis.cerebro.ferramentas import metricas as ferramentas_metricas

AGORA = 1_794_000_000.0
HOJE = date(2026, 11, 16)
_PRIVADA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = _PRIVADA.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
EMAIL = "ze@meu-projeto.iam.gserviceaccount.com"
CHAVE = json.dumps(
    {
        "type": "service_account",
        "project_id": "meu-projeto",
        "client_email": EMAIL,
        "private_key": PEM,
        "token_uri": "https://ataque.exemplo/token",  # ignorado: o Zé só assina para o Google
    }
)


def _b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


class GoogleFalso:
    """O Google, o bastante: o token, o Search Console, o GA4 e o Admin do GA4."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, str, Any]] = []
        self.sites = ["https://outro.com.br/", "sc-domain:exemplo.com.br"]
        self.propriedades = ["properties/123456"]
        self.recusar: dict[str, tuple[int, str]] = {}

    def __call__(self, pedido: Any, timeout: float = 0) -> Any:
        url = urllib.parse.urlsplit(pedido.full_url)
        corpo = pedido.data
        dados = (
            dict(urllib.parse.parse_qsl(corpo.decode()))
            if url.hostname == "oauth2.googleapis.com"
            else (json.loads(corpo) if corpo else None)
        )
        self.chamadas.append((url.hostname or "", url.path, dados))
        for trecho, (codigo, texto) in self.recusar.items():
            if trecho in url.path or trecho == url.hostname:
                raise urllib.error.HTTPError(
                    pedido.full_url,
                    codigo,
                    "x",
                    {},  # type: ignore[arg-type]
                    io.BytesIO(texto.encode()),
                )
        if url.hostname != "oauth2.googleapis.com":
            assert pedido.get_header("Authorization") == "Bearer tk-1"
        return io.BytesIO(json.dumps(self.responder(url.path, dados or {})).encode())

    def responder(self, caminho: str, d: dict[str, Any]) -> Any:
        if caminho == "/token":
            return {"access_token": "tk-1", "expires_in": 3599}
        if caminho == "/webmasters/v3/sites":
            return {"siteEntry": [{"siteUrl": s} for s in self.sites]}
        if caminho.endswith("/searchAnalytics/query"):
            if not d.get("dimensions"):
                return {
                    "rows": [{"clicks": 42, "impressions": 1830, "ctr": 0.02295, "position": 14.63}]
                }
            return {
                "rows": [
                    {"keys": ["automação"], "clicks": 12, "impressions": 340, "position": 8.21}
                ]
            }
        if caminho == "/v1beta/accountSummaries":
            return {
                "accountSummaries": [
                    {"propertySummaries": [{"property": p} for p in self.propriedades]}
                ]
            }
        if caminho.endswith(":runReport"):
            nomes = [m["name"] for m in d["metrics"]]
            if not d.get("dimensions"):
                return {
                    "rows": [
                        {"metricValues": [{"value": v} for v in ("310", "402", "960", "22940")]}
                    ]
                }
            dim = d["dimensions"][0]["name"]
            if dim == "pagePath":
                return {
                    "rows": [
                        {
                            "dimensionValues": [{"value": "/blog/a"}, {"value": "Artigo A"}],
                            "metricValues": [{"value": "120"}, {"value": "98"}, {"value": "9310"}],
                        }
                    ]
                }
            if dim == "sessionDefaultChannelGroup":
                return {
                    "rows": [
                        {
                            "dimensionValues": [{"value": "Organic Search"}],
                            "metricValues": [{"value": "150"}, {"value": "130"}],
                        }
                    ]
                }
            assert nomes == ["eventCount", "activeUsers"]
            return {
                "rows": [
                    {
                        "dimensionValues": [{"value": "wa.me"}],
                        "metricValues": [{"value": "17"}, {"value": "15"}],
                    }
                ]
            }
        raise AssertionError(caminho)  # fmt: skip


def _metricas(
    tmp_path: Path, google: GoogleFalso, declaracao: ms.Declaracao | None = None
) -> ms.Metricas:
    relogio = [AGORA]
    m = ms.Metricas(
        tmp_path / "google-metricas.json",
        declaracao=lambda: declaracao,
        abrir=google,
        agora=lambda: relogio[0],
        hoje=lambda: HOJE,
    )
    m.relogio = relogio  # type: ignore[attr-defined]
    return m


DECLARADA = ms.Declaracao(dominio="exemplo.com.br", blog="/blog/")


def test_le_a_declaracao_do_zervis_json() -> None:
    declarada = {"dominio": "WWW.Exemplo.com.br", "blog": "artigos", "ga4": "properties/987654"}
    texto = json.dumps({"zervis": 1, "metricas": declarada})
    assert ms.ler_declaracao(texto) == ms.Declaracao("exemplo.com.br", "/artigos/", "987654")
    assert ms.ler_declaracao('{"zervis": 1}') is None
    assert ms.ler_declaracao("não é json") is None
    ruim = json.dumps({"metricas": {"dominio": "a b", "blog": "/x?y", "ga4": "G-ABC123"}})
    assert ms.ler_declaracao(ruim) == ms.Declaracao("", "/blog/", "")


def test_a_chave_precisa_ser_de_conta_de_servico() -> None:
    with pytest.raises(ms.MetricasErro, match="JSON"):
        ms.ler_chave("{")
    with pytest.raises(ms.MetricasErro, match="conta de serviço"):
        ms.ler_chave(json.dumps({"type": "authorized_user"}))
    with pytest.raises(ms.MetricasErro, match="incompleta"):
        ms.ler_chave(json.dumps({"type": "service_account", "client_email": EMAIL}))
    falsa = "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n"
    with pytest.raises(ms.MetricasErro, match="incompleta"):
        ms.ler_chave(
            json.dumps({"type": "service_account", "client_email": EMAIL, "private_key": falsa})
        )
    assert ms.ler_chave(CHAVE) == {"client_email": EMAIL, "private_key": PEM}


def test_a_assinatura_e_um_jwt_rs256_valido_so_de_leitura() -> None:
    jwt = ms.assinatura(ms.ler_chave(CHAVE), AGORA)
    cabeca, corpo, assinado = jwt.split(".")
    assert json.loads(_b64(cabeca)) == {"alg": "RS256", "typ": "JWT"}
    claims = json.loads(_b64(corpo))
    assert claims["iss"] == EMAIL
    assert claims["aud"] == ms.TOKEN_URL
    assert claims["exp"] - claims["iat"] == 3600
    assert all(e.endswith(".readonly") for e in claims["scope"].split())
    _PRIVADA.public_key().verify(
        _b64(assinado), f"{cabeca}.{corpo}".encode(), padding.PKCS1v15(), hashes.SHA256()
    )


def test_guardar_confere_no_google_e_grava_0600_sem_o_resto_da_chave(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g)
    assert not m.configurado
    assert m.guardar(CHAVE) == EMAIL
    assert g.chamadas[0][:2] == ("oauth2.googleapis.com", "/token")  # nunca o token_uri da chave
    assert stat.S_IMODE(m.arquivo.stat().st_mode) == 0o600
    assert set(json.loads(m.arquivo.read_text())) == {"client_email", "private_key"}
    assert m.configurado and m.conta == EMAIL
    m.remover()
    assert not m.arquivo.exists() and not m.configurado


def test_chave_recusada_pelo_google_nao_e_guardada(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.recusar["/token"] = (400, '{"error": "invalid_grant"}')
    m = _metricas(tmp_path, g)
    with pytest.raises(ms.MetricasErro, match=r"^Chave inválida\.$"):
        m.guardar(CHAVE)
    assert not m.arquivo.exists()


def test_busca_acha_o_site_pelo_dominio_e_soma_o_periodo(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    b = m.busca(7, "buscas", 5)
    assert b["site"] == "sc-domain:exemplo.com.br"
    assert (b["cliques"], b["impressoes"], b["ctr"], b["posicao"]) == (42, 1830, 2.3, 14.6)
    assert b["linhas"] == [{"nome": "automação", "cliques": 12, "impressoes": 340, "posicao": 8.2}]
    consulta = next(d for h, c, d in g.chamadas if c.endswith("/query") and d.get("dimensions"))
    assert consulta["startDate"] == "2026-11-10" and consulta["endDate"] == "2026-11-16"
    assert consulta["dimensions"] == ["query"] and consulta["rowLimit"] == ms.LINHAS_BUSCA
    assert "/sites/sc-domain%3Aexemplo.com.br/" in next(c for _, c, _ in g.chamadas if "query" in c)
    texto = ms.texto_busca(b)
    assert "42 cliques" in texto and "- automação: 12 cliques" in texto


def test_busca_sem_dominio_declarado_pede_a_declaracao_se_houver_varios(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g)
    m.guardar(CHAVE)
    with pytest.raises(ms.MetricasErro, match="Declare o domínio"):
        m.busca()
    g.sites = ["https://so-um.com.br/"]
    m._cache.clear()
    assert m.busca()["site"] == "https://so-um.com.br/"
    g.sites = []
    m._cache.clear()
    with pytest.raises(ms.MetricasErro, match="Nenhum site"):
        m.busca()


def test_dominio_declarado_que_a_conta_nao_ve_e_dito(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.sites = ["https://outro.com.br/"]
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    with pytest.raises(ms.MetricasErro, match=r"não tem o site exemplo\.com\.br"):
        m.busca()


def test_visitas_das_paginas_do_blog_com_o_tempo_medio(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    v = m.visitas(7, "paginas", 5, so_blog=True)
    assert (v["visitantes"], v["visitas"], v["visualizacoes"], v["tempo_medio_s"]) == (
        310,
        402,
        960,
        74,
    )
    pagina = {"nome": "/blog/a", "titulo": "Artigo A", "visualizacoes": 120, "visitantes": 98}
    assert v["linhas"] == [{**pagina, "tempo_medio_s": 95}]
    relatorios = [(c, d) for _, c, d in g.chamadas if c.endswith(":runReport")]
    assert all(c == "/v1beta/properties/123456:runReport" for c, _ in relatorios)
    filtro = {
        "fieldName": "pagePath",
        "stringFilter": {"matchType": "BEGINS_WITH", "value": "/blog/"},
    }
    assert all(d["dimensionFilter"]["filter"] == filtro for _, d in relatorios)
    assert relatorios[0][1]["dateRanges"] == [{"startDate": "6daysAgo", "endDate": "today"}]
    texto = ms.texto_visitas(v)
    assert texto.startswith("Blog, últimos 7 dias: 310 visitantes")
    assert "Artigo A (/blog/a): 120 visualizações" in texto and "1 min 35 s" in texto


def test_visitas_por_origem_e_cliques_no_whatsapp(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    origens = m.visitas(28, "origens")
    assert origens["linhas"] == [{"nome": "Busca orgânica", "visitas": 150, "visitantes": 130}]
    cliques = m.visitas(28, "cliques")
    assert cliques["linhas"] == [{"nome": "wa.me", "cliques": 17, "visitantes": 15}]
    assert "- wa.me: 17 cliques" in ms.texto_visitas(cliques)


def test_propriedade_declarada_dispensa_o_admin(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.recusar["/v1beta/accountSummaries"] = (403, '{"error": {"status": "SERVICE_DISABLED"}}')
    m = _metricas(tmp_path, g, ms.Declaracao("exemplo.com.br", "/blog/", "777777"))
    m.guardar(CHAVE)
    m.visitas()
    assert any(c == "/v1beta/properties/777777:runReport" for _, c, _ in g.chamadas)


def test_sem_propriedade_declarada_e_varias_visiveis_pede_a_declaracao(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.propriedades = ["properties/1111", "properties/2222"]
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    with pytest.raises(ms.MetricasErro, match="Declare a propriedade"):
        m.visitas()


def test_api_desligada_diz_qual_ativar(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.recusar["analyticsdata.googleapis.com"] = (
        403,
        '{"error": {"message": "Google Analytics Data API has not been used in project 1"}}',
    )
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    with pytest.raises(
        ms.MetricasErro, match=r"^Ative a Google Analytics Data API no Google Cloud\.$"
    ):
        m.visitas()


def test_cache_de_meia_hora_e_token_reaproveitado(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    m.busca()
    feitas = len(g.chamadas)
    m.busca()
    assert len(g.chamadas) == feitas  # do cache
    m.relogio[0] += ms.CACHE_S + 1  # type: ignore[attr-defined]
    m.busca()
    tokens = [c for _, c, _ in g.chamadas if c == "/token"]
    assert len(tokens) == 1  # o token vale 1 hora; o Zé troca 2 minutos antes
    assert len(g.chamadas) == feitas + 3  # o site e as duas consultas


def test_sem_conexao_e_sem_chave(tmp_path: Path) -> None:
    def sem_rede(pedido: Any, timeout: float = 0) -> Any:
        raise urllib.error.URLError("sem rede")

    m = ms.Metricas(tmp_path / "k.json", abrir=sem_rede)
    with pytest.raises(ms.MetricasErro, match="não estão configuradas"):
        m.busca()
    with pytest.raises(ms.MetricasErro, match=r"^Sem conexão com o Google\.$"):
        m.guardar(CHAVE)


def test_resumo_mostra_cada_fonte_com_o_seu_erro(tmp_path: Path) -> None:
    g = GoogleFalso()
    g.recusar["analyticsdata.googleapis.com"] = (403, "{}")
    m = _metricas(tmp_path, g, DECLARADA)
    assert m.resumo() == {"configurado": False, "conta": "", "dias": 28}
    m.guardar(CHAVE)
    r = m.resumo()
    assert r["busca"]["cliques"] == 42
    assert r["visitas"] == {"erro": "Sem permissão no Google para a conta de serviço."}


def test_so_fala_com_os_enderecos_do_google(tmp_path: Path) -> None:
    m = _metricas(tmp_path, GoogleFalso())
    with pytest.raises(ms.MetricasErro, match="inesperado"):
        m._pedir("https://ataque.exemplo/v1")


def test_as_ferramentas_passam_sem_perguntar_e_contam_como_de_fora(tmp_path: Path) -> None:
    g = GoogleFalso()
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    fs: dict[str, Any] = {f.name: f for f in ferramentas_metricas.ferramentas(m)}
    assert set(fs) == {"site_google", "site_visitas"}
    for nome in fs:
        assert f"mcp__{SERVIDOR}__{nome}" in LIVRES
        assert de_fora(f"mcp__{SERVIDOR}__{nome}")
    r = asyncio.run(fs["site_visitas"].handler({"por": "cliques", "dias": 7}))
    assert "wa.me: 17 cliques" in r["content"][0]["text"]
    r = asyncio.run(fs["site_google"].handler({"por": "paginas"}))
    assert "Páginas do topo" in r["content"][0]["text"]
    vazio = ms.Metricas(tmp_path / "nada.json", abrir=g)
    sem_chave: Any = ferramentas_metricas.ferramentas(vazio)[0]
    erro = asyncio.run(sem_chave.handler({}))
    assert erro.get("is_error") and "não estão configuradas" in erro["content"][0]["text"]


def test_buscas_do_topo_por_cliques_e_depois_impressoes(tmp_path: Path) -> None:
    """Caso real de 16/11/2026: com tudo em zero clique, o Google devolveu "gestor" (5
    impressões) depois de buscas com 1, e o corte em 5 podia deixá-la de fora."""
    g = GoogleFalso()
    linhas = [
        {"keys": ["automacoes"], "clicks": 0, "impressions": 1, "position": 12.0},
        {"keys": ["automação de ia"], "clicks": 0, "impressions": 1, "position": 11.0},
        {"keys": ["e gestor"], "clicks": 0, "impressions": 3, "position": 2.0},
        {"keys": ["gestor"], "clicks": 0, "impressions": 5, "position": 7.2},
        {"keys": ["gestor descomplica"], "clicks": 2, "impressions": 4, "position": 1.0},
    ]
    original = g.responder

    def responder(caminho: str, d: dict[str, Any]) -> Any:
        if caminho.endswith("/searchAnalytics/query") and d.get("dimensions"):
            assert d["rowLimit"] == ms.LINHAS_BUSCA
            return {"rows": linhas}
        return original(caminho, d)

    g.responder = responder  # type: ignore[method-assign]
    m = _metricas(tmp_path, g, DECLARADA)
    m.guardar(CHAVE)
    nomes = [r["nome"] for r in m.busca(28, "buscas", 3)["linhas"]]
    assert nomes == ["gestor descomplica", "gestor", "e gestor"]
