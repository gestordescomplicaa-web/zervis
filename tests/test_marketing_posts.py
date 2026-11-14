"""Posts do Instagram (ADR 0093): o carrossel com a marca, a prévia e publicar só com aprovação.
O modelo, o Chromium e a API da Meta são de mentira, menos no teste de desenho (com o Chromium)."""

import http.client
import io
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import marketing
from zervis.marca import CORES_PADRAO, Marca, ler_marca
from zervis.marketing_posts import Post, PostErro, Posts, html_do_slide, interpretar, renderizar
from zervis.portal import publico
from zervis.portal.servidor import Portal
from zervis.redes import instagram_publicar
from zervis.redes.instagram import InstagramErro

RESPOSTA = json.dumps(
    {
        "slides": [
            {"titulo": "Seu atendimento para às 18h?", "texto": "Três sinais."},
            {"titulo": "Mensagens fora do horário", "texto": "Um agente responde na hora."},
            {"titulo": "Dados digitados duas vezes", "texto": "Integração faz uma vez só."},
            {"titulo": "Quer ver no seu processo?", "texto": "Eu mostro por onde começar."},
        ],
        "chamada": "Fale comigo no WhatsApp",
        "legenda": "Seu atendimento para às 18h? Veja três sinais. #automacao",
    }
)


# --- links públicos -----------------------------------------------------------------------


def test_link_publico_so_entrega_o_arquivo_certo_dentro_do_prazo(tmp_path: Path) -> None:
    agora = [0.0]
    links = publico.Publicos(agora=lambda: agora[0])
    slide = tmp_path / "slide-1.jpg"
    slide.write_bytes(b"jpeg")
    (tmp_path / "segredo.txt").write_text("não")
    segredo = links.abrir([slide, tmp_path / "segredo.txt"], prazo_s=60)
    assert links.arquivo(f"/publico/{segredo}/slide-1.jpg") == (b"jpeg", "image/jpeg")
    assert links.arquivo(f"/publico/{segredo}/segredo.txt") is None  # só imagem
    assert links.arquivo(f"/publico/{segredo}/../slide-1.jpg") is None
    assert links.arquivo("/publico/outro/slide-1.jpg") is None
    agora[0] = 61
    assert links.arquivo(f"/publico/{segredo}/slide-1.jpg") is None  # venceu
    segredo = links.abrir([slide])
    links.fechar(segredo)
    assert links.arquivo(f"/publico/{segredo}/slide-1.jpg") is None


def test_o_painel_entrega_o_link_publico_sem_entrar(tmp_path: Path) -> None:
    slide = tmp_path / "slide-1.jpg"
    slide.write_bytes(b"jpeg")
    segredo = publico.PADRAO.abrir([slide])
    p = Portal({}, {}, porta=0)
    p.iniciar()
    try:

        def obter(caminho: str) -> tuple[int, bytes, str]:
            conn = http.client.HTTPConnection("127.0.0.1", p.porta, timeout=5)
            conn.request("GET", caminho, headers={"Host": f"127.0.0.1:{p.porta}"})
            r = conn.getresponse()
            return r.status, r.read(), r.getheader("Content-Type", "")

        assert obter(f"/publico/{segredo}/slide-1.jpg") == (200, b"jpeg", "image/jpeg")
        assert obter("/publico/errado/slide-1.jpg")[0] == 404
        assert obter("/api/marketing")[0] in (401, 403)  # sem o token, o resto continua fechado
    finally:
        p.parar()
        publico.PADRAO.fechar(segredo)


# --- marca --------------------------------------------------------------------------------


def test_a_marca_vem_do_site_e_a_paleta_pode_ser_propria(tmp_path: Path) -> None:
    texto = json.dumps(
        {
            "zervis": 1,
            "marca": {
                "nome": "Loja Exemplo",
                "instagram": "@loja.exemplo",
                "logo": "public/logo.png",
                "cores": {"fundo": "#0A0A0F", "destaque": "#5B8CFF", "texto": "vermelho"},
                "fontes": {"titulo": "Space Grotesk", "texto": "Inter; drop"},
            },
        }
    )
    m = ler_marca(texto)
    assert m is not None and m.instagram == "loja.exemplo" and m.logo == "public/logo.png"
    assert m.cor("fundo") == "#0A0A0F" and m.cor("texto") == CORES_PADRAO["texto"]
    assert m.titulo == "Space Grotesk" and m.texto == ""  # fonte com símbolo é recusada
    assert ler_marca('{"zervis": 1}') is None
    assert ler_marca(json.dumps({"marca": {"logo": "../fora.png"}})).logo == ""  # type: ignore[union-attr]
    site = marketing.Marketing(tmp_path / "marketing.json")
    site.marca_do_site = lambda: m  # type: ignore[method-assign]
    assert site.paleta()["paleta"] == "site" and site.marca().cor("destaque") == "#5B8CFF"
    site.guardar_paleta("propria", {"destaque": "#FF6600", "fundo": "não"})
    assert site.marca().cor("destaque") == "#FF6600" and site.marca().cor("fundo") == "#0A0A0F"
    with pytest.raises(marketing.MarketingErro):
        site.guardar_paleta("propria", {})
    site.guardar_paleta("site", {})
    assert site.marca().cor("destaque") == "#5B8CFF"


# --- o texto e os slides ------------------------------------------------------------------


def test_o_texto_do_modelo_e_conferido() -> None:
    slides, chamada, legenda = interpretar("Aqui está:\n" + RESPOSTA)
    assert (
        len(slides) == 4 and chamada == "Fale comigo no WhatsApp" and legenda.endswith("#automacao")
    )
    longo = json.dumps(
        {"slides": [{"titulo": "x " * 80, "texto": "y"}] * 9, "legenda": "z", "chamada": ""}
    )
    slides, _, _ = interpretar(longo)
    assert len(slides) == 7 and len(slides[0]["titulo"]) <= 70 and slides[0]["titulo"].endswith("…")
    with pytest.raises(PostErro):
        interpretar(json.dumps({"slides": [{"titulo": "a", "texto": "b"}], "legenda": "c"}))
    with pytest.raises(PostErro):
        interpretar("não é json")


def test_o_slide_escapa_o_texto_do_modelo() -> None:
    post = Post(
        "a1b2c3d4",
        slides=[{"titulo": "<script>x()</script>", "texto": "a & b"}] * 3,
        chamada="<b>oi</b>",
    )
    marca = Marca(instagram="loja", titulo="Space Grotesk")
    capa = html_do_slide(post, 0, marca, b"")
    assert "<script>x()" not in capa and "&lt;script&gt;" in capa and "a &amp; b" in capa
    assert "family=Space+Grotesk" in capa and "@loja" in capa
    assert "&lt;b&gt;oi&lt;/b&gt;" in html_do_slide(post, 2, marca, b"")


@pytest.mark.skipif(shutil.which("chromium") is None, reason="sem Chromium na máquina")
def test_os_slides_saem_em_jpeg_no_tamanho_do_feed(tmp_path: Path) -> None:
    from PIL import Image

    slides, chamada, legenda = interpretar(RESPOSTA)
    post = Post("a1b2c3d4", slides=slides[:3], chamada=chamada, legenda=legenda)
    feitos = renderizar(post, Marca(), b"", tmp_path)
    assert [f.name for f in feitos] == ["slide-1.jpg", "slide-2.jpg", "slide-3.jpg"]
    with Image.open(feitos[0]) as imagem:
        assert imagem.format == "JPEG" and imagem.size == (1080, 1350)


# --- criar, refazer e publicar ------------------------------------------------------------


class Site(marketing.Marketing):
    def __init__(self, tmp: Path) -> None:
        super().__init__(tmp / "marketing.json")
        self.avisos: list[str] = []
        self.avisar = self.avisos.append

    def marca(self) -> Marca:
        return Marca(nome="Loja", instagram="loja")

    def manual(self) -> str:
        return "Público: donos de pequena empresa."

    def artigo(self, slug: str) -> str:
        return "## Um artigo\n\nTexto do artigo." if slug == "um-artigo" else ""

    def logo(self) -> bytes:
        return b""


def _posts(tmp_path: Path, **extra: Any) -> tuple[Posts, Site, list[str]]:
    site = Site(tmp_path)
    prompts: list[str] = []

    def perguntar(prompt: str) -> str:
        prompts.append(prompt)
        return RESPOSTA

    def desenhar(post: Post, _marca: Marca, _logo: bytes, pasta: Path) -> list[Path]:
        pasta.mkdir(parents=True, exist_ok=True)
        feitos = []
        for n in range(len(post.slides)):
            (pasta / f"slide-{n + 1}.jpg").write_bytes(b"jpeg")
            feitos.append(pasta / f"slide-{n + 1}.jpg")
        return feitos

    ig = SimpleNamespace(conectado=True)
    opcoes: dict[str, Any] = {
        "site": site, "perguntar": perguntar, "desenhar": desenhar, "instagram": ig,
        "links": publico.Publicos(), "endereco": lambda: "https://ze.exemplo.com",
    }  # fmt: skip
    return Posts(tmp_path / "posts", **{**opcoes, **extra}), site, prompts


def test_criar_a_partir_do_tema_ou_do_artigo_e_refazer(tmp_path: Path) -> None:
    posts, site, prompts = _posts(tmp_path)
    p = posts.criar(tema="atendimento fora do horário", esperar=True)
    assert p.estado == "rascunho" and len(p.slides) == 4 and len(posts.slides(p.id)) == 4
    assert "Tema: atendimento fora do horário" in prompts[0] and "Público: donos" in prompts[0]
    assert site.avisos[-1].endswith("pronto para revisar em Marketing.")
    tela = posts.para_tela(posts.ler(p.id), com_imagens=True)
    assert tela["slides"] == 4 and tela["imagens"][0].startswith("data:image/jpeg;base64,")
    a = posts.criar(artigo="um-artigo", esperar=True)
    assert "Texto do artigo." in prompts[1] and a.artigo == "um-artigo"
    with pytest.raises(PostErro, match="Artigo"):
        posts.criar(artigo="nao-existe")
    with pytest.raises(PostErro, match="tema"):
        posts.criar()
    r = posts.refazer(p.id, "slide 2 mais curto", esperar=True)
    assert r.estado == "rascunho" and "Ajuste pedido: slide 2 mais curto" in prompts[-1]
    assert "Versão anterior" in prompts[-1]
    assert len(posts.listar()) == 2
    posts.descartar(a.id)
    assert {x.id for x in posts.listar()} == {p.id}


def test_texto_ruim_vira_erro_e_nada_e_publicado(tmp_path: Path) -> None:
    posts, site, _ = _posts(tmp_path, perguntar=lambda _p: "sem json")
    p = posts.criar(tema="x", esperar=True)
    assert p.estado == "erro" and "incompleto" in p.erro
    assert site.avisos[-1].startswith("Não consegui criar o post")
    with pytest.raises(PostErro, match="rascunho"):
        posts.publicar(p.id)


def test_publicar_abre_o_link_so_durante_a_publicacao(tmp_path: Path) -> None:
    enviados: list[tuple[list[str], str]] = []
    links = publico.Publicos()

    def publicar(_ig: Any, urls: list[str], legenda: str) -> str:
        enviados.append((urls, legenda))
        assert links.arquivo(urls[0].removeprefix("https://ze.exemplo.com")) == (
            b"jpeg",
            "image/jpeg",
        )  # a Meta consegue buscar enquanto publica
        return "https://www.instagram.com/p/abc/"

    posts, site, _ = _posts(tmp_path, publicar=publicar, links=links)
    p = posts.criar(tema="x", esperar=True)
    feito = posts.publicar(p.id, esperar=True)
    assert feito.estado == "publicado" and feito.permalink == "https://www.instagram.com/p/abc/"
    ((urls, legenda),) = enviados
    assert len(urls) == 4 and urls[0].startswith("https://ze.exemplo.com/publico/")
    assert urls[0].endswith("/slide-1.jpg") and legenda.endswith("#automacao")
    assert links.arquivo(urls[0].removeprefix("https://ze.exemplo.com")) is None  # fechado
    assert site.avisos[-1] == "O post foi publicado no Instagram."
    with pytest.raises(PostErro):
        posts.publicar(p.id)  # já publicado


def test_publicar_exige_instagram_e_endereco_e_a_recusa_volta_a_rascunho(tmp_path: Path) -> None:
    def recusar(*_a: Any) -> str:
        raise InstagramErro("O token não tem permissão para publicar no Instagram.")

    posts, _, _ = _posts(tmp_path, publicar=recusar)
    p = posts.criar(tema="x", esperar=True)
    feito = posts.publicar(p.id, esperar=True)
    assert feito.estado == "rascunho" and "permissão" in feito.erro
    sem_endereco, _, _ = _posts(tmp_path / "b", endereco=lambda: "")
    q = sem_endereco.criar(tema="x", esperar=True)
    with pytest.raises(PostErro, match="endereço fixo"):
        sem_endereco.publicar(q.id)
    sem_ig, _, _ = _posts(tmp_path / "c", instagram=SimpleNamespace(conectado=False))
    r = sem_ig.criar(tema="x", esperar=True)
    with pytest.raises(PostErro, match="Conecte o Instagram"):
        sem_ig.publicar(r.id)


# --- a API do Instagram -------------------------------------------------------------------


class Meta:
    """A Graph API de mentira: guarda os pedidos e responde na ordem do carrossel."""

    def __init__(self, estados: list[str]) -> None:
        self.pedidos: list[tuple[str, str, dict[str, list[str]]]] = []
        self.estados = estados
        self.n = 0

    def __call__(self, pedido: Any, timeout: float) -> Any:
        from urllib.parse import parse_qs, urlsplit

        partes = urlsplit(pedido.full_url)
        dados = parse_qs(pedido.data.decode() if pedido.data else partes.query)
        metodo = pedido.get_method()
        self.pedidos.append((metodo, partes.path, dados))
        if partes.path.endswith("/media") and metodo == "POST":
            self.n += 1
            corpo: dict[str, Any] = {"id": f"c{self.n}"}
        elif partes.path.endswith("/media_publish"):
            corpo = {"id": "post1"}
        elif "status_code" in dados.get("fields", [""])[0]:
            corpo = {"status_code": self.estados.pop(0)}
        else:
            corpo = {"permalink": "https://www.instagram.com/p/xyz/"}
        return io.BytesIO(json.dumps(corpo).encode())


def _ig(meta: Meta) -> Any:
    return SimpleNamespace(abrir=meta, _token=lambda: ("ig", "1784", "IGtoken"))


def test_o_carrossel_vai_para_a_api_na_ordem_certa() -> None:
    meta = Meta(["IN_PROGRESS", "FINISHED"])
    urls = [
        "https://ze.exemplo.com/publico/s/slide-1.jpg",
        "https://ze.exemplo.com/publico/s/slide-2.jpg",
    ]
    link = instagram_publicar.publicar(_ig(meta), urls, "Legenda", dormir=lambda _s: None)
    assert link == "https://www.instagram.com/p/xyz/"
    itens = [d for m, c, d in meta.pedidos if c.endswith("/1784/media") and "is_carousel_item" in d]
    assert [d["image_url"] for d in itens] == [[urls[0]], [urls[1]]]
    carrossel = next(d for m, c, d in meta.pedidos if d.get("media_type") == ["CAROUSEL"])
    assert carrossel["children"] == ["c1,c2"] and carrossel["caption"] == ["Legenda"]
    publicar = next(d for m, c, d in meta.pedidos if c.endswith("/media_publish"))
    assert publicar["creation_id"] == ["c3"]
    assert all("IGtoken" not in c for _m, c, _d in meta.pedidos)  # o token não vai no caminho


def test_uma_imagem_so_e_foto_e_erro_da_meta_nao_publica() -> None:
    meta = Meta(["FINISHED"])
    instagram_publicar.publicar(_ig(meta), ["https://x/1.jpg"], "L", dormir=lambda _s: None)
    assert not any("is_carousel_item" in d for _m, _c, d in meta.pedidos)
    ruim = Meta(["ERROR"])
    with pytest.raises(InstagramErro, match="preparar"):
        instagram_publicar.publicar(_ig(ruim), ["https://x/1.jpg"], "L", dormir=lambda _s: None)
    assert not any(c.endswith("/media_publish") for _m, c, _d in ruim.pedidos)
    with pytest.raises(InstagramErro, match="de 1 a 10"):
        instagram_publicar.publicar(_ig(Meta([])), [], "L")
