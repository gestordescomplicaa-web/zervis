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
    slides, chamada, legenda, foto = interpretar("Aqui está:\n" + RESPOSTA)
    assert (
        len(slides) == 4 and chamada == "Fale comigo no WhatsApp" and legenda.endswith("#automacao")
    )
    assert foto == "" and slides[0]["visual"] == {}
    longo = json.dumps(
        {"slides": [{"titulo": "x " * 80, "texto": "y"}] * 9, "legenda": "z", "chamada": ""}
    )
    slides, _, _, _ = interpretar(longo)
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

    slides, chamada, legenda, _ = interpretar(RESPOSTA)
    slides[1]["visual"] = {"tipo": "fluxo", "passos": ["Pedido", "Planilha", "Sistema"]}
    post = Post("a1b2c3d4", slides=slides[:3], chamada=chamada, legenda=legenda, foto="eu.jpg")
    foto = io.BytesIO()
    Image.new("RGB", (800, 1000), "#336699").save(foto, "JPEG")
    feitos = renderizar(post, Marca(), b"", tmp_path, foto.getvalue())
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

    def desenhar(
        post: Post, _marca: Marca, _logo: bytes, pasta: Path, _foto: bytes = b""
    ) -> list[Path]:
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
    opcoes["fotos"] = tmp_path / "fotos"
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


def _processo_que_parou() -> int:
    import subprocess

    filho = subprocess.Popen(["/usr/bin/true"])
    filho.wait()
    return filho.pid


def _deixar_em(posts: Posts, id_: str, estado: str, ha_s: float) -> None:
    """Como um reinício do Zé deixa o post: o estado em andamento, de um processo que parou."""
    import time

    arquivo = posts.pasta / id_ / "post.json"
    dados = json.loads(arquivo.read_text())
    dados.update(estado=estado, processo=_processo_que_parou(), desde=time.time() - ha_s)
    arquivo.write_text(json.dumps(dados))


def test_reinicio_no_meio_da_publicacao_nao_deixa_o_post_preso(tmp_path: Path) -> None:
    """17/11/2026: o Zé reiniciou 39 s depois de começar a publicar um carrossel, e o post ficou
    em "publicando" para sempre, sem erro. Agora quem lê o post confere no Instagram se saiu."""
    procurados: list[tuple[str, float]] = []
    achado = {"link": ""}

    def procurar(_ig: Any, legenda: str, desde: float) -> str:
        procurados.append((legenda, desde))
        return achado["link"]

    enviados: list[list[str]] = []

    def publicar(_ig: Any, urls: list[str], _legenda: str) -> str:
        enviados.append(urls)
        return "https://www.instagram.com/p/novo/"

    posts, site, _ = _posts(tmp_path, procurar=procurar, publicar=publicar)
    p = posts.criar(tema="planilhas copiadas à mão", esperar=True)

    _deixar_em(posts, p.id, "publicando", ha_s=30)  # recente: a Meta pode ainda não listar
    assert posts.ler(p.id).estado == "publicando" and not procurados

    _deixar_em(posts, p.id, "publicando", ha_s=600)
    (lido,) = posts.listar()
    assert lido.estado == "rascunho" and "não saiu" in lido.erro and "publicar de novo" in lido.erro
    assert procurados[-1][0] == lido.legenda and "não saiu" in site.avisos[-1]
    assert posts.publicar(p.id, esperar=True).estado == "publicado" and len(enviados) == 1

    q = posts.criar(tema="outro tema", esperar=True)
    _deixar_em(posts, q.id, "publicando", ha_s=600)
    achado["link"] = "https://www.instagram.com/p/saiu/"
    feito = posts.ler(q.id)
    assert feito.estado == "publicado" and feito.permalink == "https://www.instagram.com/p/saiu/"
    with pytest.raises(PostErro):
        posts.publicar(q.id)  # já saiu: publicar de novo duplicaria
    assert len(enviados) == 1


def test_sem_conferir_no_instagram_o_post_pede_para_conferir(tmp_path: Path) -> None:
    def procurar(*_a: Any) -> str:
        raise InstagramErro("Sem conexão com o Instagram.")

    posts, _, _ = _posts(tmp_path, procurar=procurar)
    p = posts.criar(tema="x", esperar=True)
    _deixar_em(posts, p.id, "publicando", ha_s=600)
    lido = posts.ler(p.id)
    assert lido.estado == "rascunho" and "Confira no Instagram" in lido.erro


def test_reinicio_no_meio_da_criacao_vira_erro_e_pode_refazer(tmp_path: Path) -> None:
    posts, _, _ = _posts(tmp_path)
    p = posts.criar(tema="x", esperar=True)
    _deixar_em(posts, p.id, "criando", ha_s=5)
    lido = posts.ler(p.id)
    assert lido.estado == "erro" and "interrompida" in lido.erro
    assert posts.refazer(p.id, "de novo", esperar=True).estado == "rascunho"


def test_o_post_que_este_processo_publica_nao_e_mexido(tmp_path: Path) -> None:
    import threading

    publicando, solta = threading.Event(), threading.Event()

    def publicar(*_a: Any) -> str:
        publicando.set()
        solta.wait(10)
        return "https://www.instagram.com/p/abc/"

    def procurar(*_a: Any) -> str:
        raise AssertionError("não confere um post que ainda está sendo publicado")

    posts, _, _ = _posts(tmp_path, publicar=publicar, procurar=procurar)
    p = posts.criar(tema="x", esperar=True)
    posts.publicar(p.id)
    assert publicando.wait(10)
    assert posts.ler(p.id).estado == "publicando"
    solta.set()


def test_defeito_inesperado_ao_publicar_nao_deixa_o_post_preso(tmp_path: Path) -> None:
    def quebrar(*_a: Any) -> str:
        raise KeyError("id")

    posts, site, _ = _posts(tmp_path, publicar=quebrar)
    p = posts.criar(tema="x", esperar=True)
    feito = posts.publicar(p.id, esperar=True)
    assert feito.estado == "rascunho" and "Confira no Instagram" in feito.erro
    assert site.avisos[-1].startswith("Não publiquei o post")


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


def test_procurar_acha_o_post_pela_legenda_e_pela_hora() -> None:
    pedidos: list[str] = []
    lista = {
        "data": [
            {"caption": "Legenda  nova", "timestamp": "2026-11-17T20:51:00+0000",
             "permalink": "https://www.instagram.com/p/novo/"},
            {"caption": "Legenda nova", "timestamp": "2026-11-16T12:00:00+0000",
             "permalink": "https://www.instagram.com/p/velho/"},
        ]
    }  # fmt: skip

    def abrir(pedido: Any, timeout: float) -> Any:
        pedidos.append(pedido.full_url)
        return io.BytesIO(json.dumps(lista).encode())

    ig: Any = SimpleNamespace(abrir=abrir, _token=lambda: ("ig", "1784", "IGtoken"))
    desde = 1_794_948_600.0  # 17/11/2026 20:50 UTC
    assert instagram_publicar.procurar(ig, "Legenda nova", desde) == (
        "https://www.instagram.com/p/novo/"
    )
    assert instagram_publicar.procurar(ig, "Outra legenda", desde) == ""
    assert instagram_publicar.procurar(ig, "Legenda nova", desde + 86400) == ""
    assert "/me/media?" in pedidos[0] and "caption" in pedidos[0]


# --- os visuais e as fotos ----------------------------------------------------------------


def test_o_visual_de_cada_slide_e_conferido() -> None:
    from zervis.marketing_visual import conferir, icones

    assert len(icones()) >= 60 and "workflow" in icones()
    icone = {"tipo": "icone", "icone": "workflow"}
    assert conferir(icone) == icone
    assert conferir({"tipo": "icone", "icone": "nao-existe"}) == {}
    passos = ["Pedido no WhatsApp " * 3, "Planilha", "", "Sistema", "a", "b"]
    fluxo = conferir({"tipo": "fluxo", "passos": passos})
    assert len(fluxo["passos"]) == 4 and len(fluxo["passos"][0]) <= 26
    assert conferir({"tipo": "fluxo", "passos": ["só um"]}) == {}
    assert conferir({"tipo": "comparacao", "antes": "a", "depois": ""}) == {}
    mensagens = [{"de": "cliente", "texto": "oi"}, {"de": "x", "texto": "olá"}]
    conversa = conferir({"tipo": "conversa", "mensagens": mensagens})
    assert [m["de"] for m in conversa["mensagens"]] == ["cliente", "cliente"]
    assert conferir({"tipo": "video"}) == {} and conferir("icone") == {}


def test_o_visual_escapa_o_texto_e_a_conversa_leva_o_selo() -> None:
    from zervis.marketing_visual import html_do_visual

    marca = Marca()
    lista = html_do_visual({"tipo": "lista", "itens": ["<b>a</b>", "c & d"]}, marca)
    assert "&lt;b&gt;a&lt;/b&gt;" in lista and "c &amp; d" in lista
    mensagens = [{"de": "cliente", "texto": "oi"}, {"de": "empresa", "texto": "olá"}]
    assert "Ilustração" in html_do_visual({"tipo": "conversa", "mensagens": mensagens}, marca)
    assert "<svg" in html_do_visual({"tipo": "icone", "icone": "zap"}, marca)


def test_a_foto_da_capa_so_vale_se_existir() -> None:
    resposta = json.loads(RESPOSTA)
    resposta["foto"] = "eu-explicando.jpg"
    assert interpretar(json.dumps(resposta), ("eu-explicando.jpg",))[3] == "eu-explicando.jpg"
    assert interpretar(json.dumps(resposta), ("outra.jpg",))[3] == ""


def test_as_fotos_da_marca(tmp_path: Path) -> None:
    from PIL import Image

    posts, _, prompts = _posts(tmp_path)
    grande = io.BytesIO()
    Image.new("RGB", (3000, 2000), "#884422").save(grande, "PNG")
    nome = posts.adicionar_foto("Eu Explicando o Fluxo.PNG", grande.getvalue())
    assert nome == "eu-explicando-o-fluxo.jpg"
    segunda = posts.adicionar_foto("eu explicando o fluxo.jpg", grande.getvalue())
    assert segunda == "eu-explicando-o-fluxo-2.jpg"
    with Image.open(io.BytesIO(posts.foto(nome))) as salva:
        assert salva.format == "JPEG" and max(salva.size) == 1600
    with pytest.raises(PostErro, match="não é uma imagem"):
        posts.adicionar_foto("texto.png", b"nada")
    posts.criar(tema="x", esperar=True)
    assert "eu-explicando-o-fluxo.jpg" in prompts[-1] and "workflow" in prompts[-1]
    posts.remover_foto(segunda)
    assert posts.fotos() == [nome]
    with pytest.raises(PostErro):
        posts.remover_foto("../post.json")


def test_carrossel_agendado_tema_da_vez_e_publicar_sozinho(tmp_path: Path) -> None:
    posts, _, _ = _posts(tmp_path)
    texto = Posts.pedido_agendado("Cobrança\n\n Estoque ", True)
    assert json.loads(texto) == {"temas": ["Cobrança", "Estoque"], "publicar": True}
    assert posts.proximo_tema(["Cobrança", "Estoque"]) == ("Cobrança", "")
    posts.criar(tema="Cobrança", esperar=True)
    assert posts.proximo_tema(["cobrança", "Estoque"]) == ("Estoque", "")
