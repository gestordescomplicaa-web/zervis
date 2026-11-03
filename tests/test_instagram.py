"""O Instagram do Zé, só leitura (ADR 0057): conectar, ler, guardar em cache e analisar."""

import asyncio
import io
import json
import logging
import stat
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import instagram as ferramentas_ig
from zervis.redes import analise
from zervis.redes import instagram as ig

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 3, 12, 0, tzinfo=FUSO).timestamp()
TOKEN_IG = "IGAA" + "x" * 60
TOKEN_FB = "EAAB" + "y" * 60


def _quando(dias_atras: float) -> str:
    return datetime.fromtimestamp(AGORA - dias_atras * 86400, ZoneInfo("UTC")).strftime(
        "%Y-%m-%dT%H:%M:%S+0000"
    )


POSTS = [
    {"id": "1", "caption": "Bastidores da automação do cliente", "media_type": "VIDEO",
     "media_product_type": "REELS", "timestamp": _quando(2), "permalink": "https://ig/p/1",
     "like_count": 300, "comments_count": 40},
    {"id": "2", "caption": "Carrossel: 5 erros no atendimento", "media_type": "CAROUSEL_ALBUM",
     "media_product_type": "FEED", "timestamp": _quando(10), "permalink": "https://ig/p/2",
     "like_count": 120, "comments_count": 8},
    {"id": "3", "caption": "", "media_type": "IMAGE", "media_product_type": "FEED",
     "timestamp": _quando(60), "permalink": "https://ig/p/3", "like_count": 50,
     "comments_count": 2},
    {"id": "4", "caption": "story", "media_type": "IMAGE", "media_product_type": "STORY",
     "timestamp": _quando(0.5), "permalink": "https://ig/p/4"},
]  # fmt: skip
VIEWS = {"1": 12000, "2": 3000, "3": 900}


class MetaFalsa:
    """A Graph API da Meta, o bastante: responde pelo caminho e conta as chamadas."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.recusar: int | None = None

    def __call__(self, pedido: Any, timeout: float = 0) -> Any:
        url = urllib.parse.urlsplit(pedido.full_url)
        caminho, q = url.path, dict(urllib.parse.parse_qsl(url.query))
        self.chamadas.append(caminho)
        if self.recusar is not None:
            corpo = json.dumps({"error": {"message": "x", "code": self.recusar}}).encode()
            raise urllib.error.HTTPError(pedido.full_url, 400, "Bad", {}, io.BytesIO(corpo))  # type: ignore[arg-type]
        return io.BytesIO(json.dumps(self.responder(caminho, q)).encode())

    def responder(self, caminho: str, q: dict[str, str]) -> Any:
        if caminho == "/refresh_access_token":
            return {"access_token": "IGAA" + "z" * 60, "expires_in": 5184000}
        if caminho.endswith("/me") and "user_id" in q.get("fields", ""):
            return {"user_id": "17841400000000000", "username": "gabriel.auto"}
        if caminho.endswith("/me/accounts"):
            return {"data": [{"id": "p1"}, {"id": "p2", "instagram_business_account": {
                "id": "1784", "username": "loja.oficial"}}]}  # fmt: skip
        if caminho.endswith("/media"):
            if "after" not in q:
                return {"data": POSTS[:2], "paging": {"cursors": {"after": "c1"}, "next": "x"}}
            return {"data": POSTS[2:], "paging": {"cursors": {"after": "c2"}}}
        if caminho.endswith("/insights") and "/me/" not in caminho and "1784/" not in caminho:
            post = caminho.rsplit("/", 2)[-2]
            metricas = q["metric"].split(",")
            assert "impressions" not in metricas and "plays" not in metricas
            valores = {"views": VIEWS[post], "reach": VIEWS[post] // 2, "saved": 10}
            return {
                "data": [{"name": m, "values": [{"value": valores.get(m, 1)}]} for m in metricas]
            }
        if caminho.endswith("/insights"):
            totais = {"reach": 25000, "follows_and_unfollows": 42}
            return {"data": [{"name": k, "total_value": {"value": v}} for k, v in totais.items()]}
        return {"username": "gabriel.auto", "followers_count": 15300, "follows_count": 410,
                "media_count": 3}  # fmt: skip


def _ig(tmp_path: Path, meta: MetaFalsa, relogio: list[float]) -> ig.Instagram:
    return ig.Instagram(
        tmp_path / "instagram.key", tmp_path / "cache.json", meta, lambda: relogio[0]
    )


def test_o_token_de_qualquer_jeito_que_vier_colado() -> None:
    assert ig.extrair_token(f"  {TOKEN_IG}\n") == TOKEN_IG
    assert (
        ig.extrair_token(f"https://graph.instagram.com/me?fields=id&access_token={TOKEN_IG}")
        == TOKEN_IG
    )
    assert (
        ig.extrair_token(json.dumps({"access_token": TOKEN_FB, "token_type": "bearer"})) == TOKEN_FB
    )
    assert ig.extrair_token(f"Token: {TOKEN_FB} (vale 60 dias)") == TOKEN_FB


def test_conecta_pelos_dois_logins_e_guarda_privado(tmp_path: Path) -> None:
    meta, relogio = MetaFalsa(), [AGORA]
    conta = _ig(tmp_path, meta, relogio)
    assert not conta.conectado
    assert conta.conectar(TOKEN_IG) == "@gabriel.auto"
    assert conta.conta["base"] == "ig" and conta.conta["conta"] == "17841400000000000"
    assert stat.S_IMODE((tmp_path / "instagram.key").stat().st_mode) == 0o600
    assert conta.conectar(TOKEN_FB) == "@loja.oficial"  # a Página que tem o Instagram
    assert conta.conta["base"] == "fb" and conta.conta["conta"] == "1784"
    with pytest.raises(ig.InstagramErro, match="Cole o token"):
        conta.conectar("abc")
    conta.desconectar()
    assert not conta.conectado
    with pytest.raises(ig.InstagramErro, match="não conectado"):
        conta.perfil()


@pytest.mark.parametrize(
    ("codigo", "frase"),
    [(190, "vencido"), (10, "permissão"), (4, "Limite"), (1, "recusou")],
)
def test_a_recusa_da_meta_em_frase_e_sem_o_token_no_registro(
    tmp_path: Path, codigo: int, frase: str, caplog: pytest.LogCaptureFixture
) -> None:
    meta = MetaFalsa()
    meta.recusar = codigo
    with caplog.at_level(logging.INFO), pytest.raises(ig.InstagramErro, match=frase):
        _ig(tmp_path, meta, [AGORA]).conectar(TOKEN_IG)
    assert TOKEN_IG not in caplog.text


def test_posts_com_metricas_sem_story_e_do_cache(tmp_path: Path) -> None:
    meta, relogio = MetaFalsa(), [AGORA]
    conta = _ig(tmp_path, meta, relogio)
    conta.conectar(TOKEN_IG)
    posts = conta.posts()
    assert [p["id"] for p in posts] == ["1", "2", "3"]  # o story some (expira em 24 h)
    assert [p["tipo"] for p in posts] == ["reels", "carrossel", "post"]
    assert posts[0]["metricas"]["views"] == 12000
    assert "ig_reels_avg_watch_time" in posts[0]["metricas"]  # só nos reels
    antes = len(meta.chamadas)
    conta.posts()
    assert len(meta.chamadas) == antes  # tudo do cache
    relogio[0] += 2 * 3600  # duas horas: a lista e o post recente voltam; os antigos, não
    conta.posts()
    novas = meta.chamadas[antes:]
    assert sum(c.endswith("/insights") for c in novas) == 1


def test_renova_o_token_do_login_do_instagram_toda_semana(tmp_path: Path) -> None:
    meta, relogio = MetaFalsa(), [AGORA]
    conta = _ig(tmp_path, meta, relogio)
    conta.conectar(TOKEN_IG)
    conta.perfil()
    assert "/refresh_access_token" not in meta.chamadas
    relogio[0] += 8 * 86400
    conta.perfil()
    assert "/refresh_access_token" in meta.chamadas
    assert conta.conta["token"].startswith("IGAAzzz")


def test_ranking_e_resumo_ja_contados(tmp_path: Path) -> None:
    meta, relogio = MetaFalsa(), [AGORA]
    conta = _ig(tmp_path, meta, relogio)
    conta.conectar(TOKEN_IG)
    posts = conta.posts()
    texto = analise.ranking(posts, "visualizacoes", 0, "todos", 2, AGORA, FUSO)
    linhas = texto.splitlines()
    assert (
        linhas[0]
        == "As publicações de todas as publicações lidas com mais visualizações (3 no total):"
    )
    assert linhas[1].startswith("1. reels de 01/11/2026: 12 mil visualizações, 6 mil alcance")
    assert '"Bastidores da automação do cliente"' in linhas[1] and len(linhas) == 3
    so_reels = analise.ranking(posts, "alcance", 30, "reels", 5, AGORA, FUSO)
    assert "1. reels" in so_reels and "carrossel" not in so_reels
    assert analise.ranking(posts, "curtidas", 1, "todos", 5, AGORA, FUSO) == (
        "Nenhuma publicação dos últimos 1 dias."
    )
    resumo = analise.resumo(conta.perfil(), conta.conta_no_periodo(30), posts, 30, AGORA)
    assert resumo.splitlines()[0] == "@gabriel.auto: 15,3 mil seguidores, segue 410, 3 publicações."
    assert "25 mil alcance" in resumo and "42 seguidores ganhos menos perdidos" in resumo
    assert "Publicou 2 vezes no período (1 reels, 1 carrossel)" in resumo
    assert "média de 7,5 mil visualizações" in resumo


def test_ferramentas_so_de_leitura(tmp_path: Path) -> None:
    assert {"mcp__jarvis__instagram_perfil", "mcp__jarvis__instagram_posts"} <= set(LIVRES)
    meta, relogio = MetaFalsa(), [AGORA]
    conta = _ig(tmp_path, meta, relogio)
    f: dict[str, Any] = {t.name: t.handler for t in ferramentas_ig.ferramentas(conta)}
    assert set(f) == {"instagram_perfil", "instagram_posts"}  # nada que publique ou responda
    sem = asyncio.run(f["instagram_posts"]({}))
    assert sem["is_error"] and "não conectado" in sem["content"][0]["text"]
    conta.conectar(TOKEN_IG)
    texto = asyncio.run(f["instagram_posts"]({"ordem": "visualizacoes", "quantos": 1}))
    assert "12 mil visualizações" in texto["content"][0]["text"]
    perfil = asyncio.run(f["instagram_perfil"]({"dias": 30}))["content"][0]["text"]
    assert perfil.startswith("@gabriel.auto")
    assert all(c.split("/")[-1] != "media_publish" for c in meta.chamadas)
