"""Os posts do Instagram que o Zé cria (ADR 0093): um carrossel e a legenda, com a marca de quem
usa, a prévia em Marketing e publicar só com a aprovação.

1. **Texto:** o modelo escreve os slides e a legenda a partir de um tema ou de um artigo do blog,
   na linha editorial do manual do site (o mesmo público, o mesmo foco, a mesma oferta).
2. **Slides:** um modelo HTML com as cores, as fontes e o logo da marca, renderizado aqui mesmo
   pelo Chromium (1080 x 1350, o retrato do feed) e salvo em JPEG, o único formato que a API aceita.
3. **Publicar:** com o "sim" de quem usa. Os slides saem por um link público temporário no
   endereço fixo do Zé (a Meta busca as imagens), fechado logo depois.
"""

import asyncio
import base64
import html
import json
import logging
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares, marketing
from zervis.marca import Marca
from zervis.portal import publico
from zervis.redes import instagram_publicar
from zervis.redes.instagram import Instagram, InstagramErro

log = logging.getLogger(__name__)

PASTA = lugares.DADOS / "marketing" / "posts"
TUNEL = lugares.CONFIG / "tunel.json"
LARGURA, ALTURA = 1080, 1350
MINIMO_SLIDES, MAXIMO_SLIDES = 3, 7
LIMITE_TITULO, LIMITE_TEXTO, LIMITE_CHAMADA, LIMITE_LEGENDA = 70, 220, 40, 2000
LIMITE_ARTIGO = 9000
MODELO = "claude-sonnet-5-5"
NAVEGADORES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
ESTADOS = ("criando", "rascunho", "publicando", "publicado", "erro")

SISTEMA = "Você escreve posts de Instagram para empresas. Responda só com o JSON pedido."

PROMPT = """Crie um post em carrossel para o Instagram de {nome}.

Siga a linha editorial do manual do site abaixo: o mesmo público, o mesmo foco e o mesmo jeito \
de fazer a oferta. Não prometa resultado, percentual ou prazo; não invente casos, clientes nem \
números (dado só com a fonte, na legenda).

{pedido}

Responda só com JSON, sem texto em volta:
{{"slides": [{{"titulo": "...", "texto": "..."}}], "chamada": "...", "legenda": "..."}}

- De 5 a 7 slides. O primeiro é a capa: um gancho curto que faz parar de rolar. Cada slide do \
meio traz uma ideia só. O último traz a oferta: o que é feito e o convite para conversar.
- titulo: até 60 caracteres. texto: até 180 caracteres, frases curtas; cada slide se lê em \
poucos segundos. Sem emojis nos slides.
- chamada: o convite do último slide, até 40 caracteres (por exemplo, "Fale comigo no WhatsApp").
- legenda: de 400 a 1.200 caracteres; abre com o gancho, explica em parágrafos curtos e fecha \
com a chamada; no máximo 3 emojis; no fim, até 5 hashtags.
- Português do Brasil, sem jargão técnico.

## Manual do site
{manual}
"""


class PostErro(ValueError):
    """Mensagem curta para o painel e para a voz."""


@dataclass
class Post:
    id: str
    tema: str = ""
    artigo: str = ""  # o slug do artigo de origem, se veio de um
    instrucao: str = ""  # o ajuste pedido na última versão
    slides: list[dict[str, str]] = field(default_factory=list)
    chamada: str = ""
    legenda: str = ""
    estado: str = "criando"
    erro: str = ""
    criado: float = field(default_factory=time.time)
    publicado: float = 0.0
    permalink: str = ""


def _corte(texto: Any, limite: int) -> str:
    limpo = " ".join(str(texto or "").split())
    return limpo if len(limpo) <= limite else limpo[: limite - 1].rsplit(" ", 1)[0] + "…"


def interpretar(saida: str) -> tuple[list[dict[str, str]], str, str]:
    """Os slides, a chamada e a legenda da resposta do modelo, já nos limites."""
    achado = re.search(r"\{.*\}", saida, re.DOTALL)
    try:
        dados = json.loads(achado.group(0)) if achado else {}
    except ValueError:
        dados = {}
    slides = [
        {
            "titulo": _corte(s.get("titulo"), LIMITE_TITULO),
            "texto": _corte(s.get("texto"), LIMITE_TEXTO),
        }
        for s in dados.get("slides") or []
        if isinstance(s, dict) and str(s.get("titulo", "")).strip()
    ][:MAXIMO_SLIDES]
    legenda = str(dados.get("legenda", "")).strip()[:LIMITE_LEGENDA]
    if len(slides) < MINIMO_SLIDES or not legenda:
        raise PostErro("O texto do post veio incompleto. Tente de novo.")
    return slides, _corte(dados.get("chamada"), LIMITE_CHAMADA), legenda


def _rgba(cor: str, alfa: float) -> str:
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


def html_do_slide(post: Post, n: int, marca: Marca, logo: bytes) -> str:
    """O HTML de um slide (1080 x 1350). Todo texto vem escapado: é do modelo, não do Zé."""
    e = html.escape
    slide, total = post.slides[n], len(post.slides)
    tipo = "capa" if n == 0 else "oferta" if n == total - 1 else "meio"
    fontes = "|".join(
        f"family={f.replace(' ', '+')}:wght@400;500;600;700"
        for f in dict.fromkeys(x for x in (marca.titulo, marca.texto) if x)
    )
    link = (
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        f'{fontes.replace("|", "&")}&display=swap">'
        if fontes
        else ""
    )
    logo_img = (
        f'<img src="data:image/png;base64,{base64.b64encode(logo).decode()}" alt="">'
        if logo
        else ""
    )
    arroba = f"@{e(marca.instagram)}" if marca.instagram else e(marca.nome)
    corpo = {
        "capa": f"<h1>{e(slide['titulo'])}</h1><p>{e(slide['texto'])}</p>",
        "meio": f'<span class="num">{n:02d}</span><h2>{e(slide["titulo"])}</h2>'
        f"<p>{e(slide['texto'])}</p>",
        "oferta": f"<h2>{e(slide['titulo'])}</h2><p>{e(slide['texto'])}</p>"
        + (f'<span class="chamada">{e(post.chamada)}</span>' if post.chamada else ""),
    }[tipo]
    pontos = "".join(f'<i class="{"on" if i == n else ""}"></i>' for i in range(total))
    c = marca.cor
    titulo = f"'{marca.titulo}', " if marca.titulo else ""
    texto = f"'{marca.texto}', " if marca.texto else ""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">{link}<style>
*{{box-sizing:border-box}}
html,body{{margin:0;width:{LARGURA}px;height:{ALTURA}px;overflow:hidden}}
body{{background:{c("fundo")};color:{c("texto")};font-family:{texto}system-ui,sans-serif;position:relative}}
.brilho{{position:absolute;inset:0;background:
 radial-gradient(900px 760px at 105% -5%,{_rgba(c("destaque"), 0.28)},transparent 62%),
 radial-gradient(820px 720px at -5% 105%,{_rgba(c("destaque2"), 0.22)},transparent 60%)}}
.topo{{position:absolute;top:72px;left:84px;right:84px;display:flex;justify-content:space-between;
 align-items:center;font-size:30px;color:{c("suave")}}}
.marca{{display:flex;align-items:center;gap:18px}}
.marca img{{width:64px;height:64px;border-radius:16px;object-fit:contain}}
.corpo{{position:absolute;left:84px;right:84px;top:50%;transform:translateY(-50%)}}
h1,h2{{font-family:{titulo}system-ui,sans-serif;margin:0;letter-spacing:-.025em}}
h1{{font-size:92px;line-height:1.03;font-weight:700}}
h2{{font-size:72px;line-height:1.07;font-weight:600;margin-bottom:36px}}
p{{font-size:42px;line-height:1.36;margin:36px 0 0;color:{c("texto")}}}
.capa p{{color:{c("suave")}}}
.num{{display:inline-block;font-family:{titulo}system-ui,sans-serif;font-size:30px;font-weight:600;
 color:{c("fundo")};background:{c("destaque")};border-radius:999px;padding:10px 28px;
 margin-bottom:44px}}
.chamada{{display:inline-block;margin-top:60px;padding:28px 52px;border-radius:999px;font-size:40px;
 font-weight:600;font-family:{titulo}system-ui,sans-serif;color:#fff;
 background:linear-gradient(90deg,{c("destaque")},{c("destaque2")})}}
.rodape{{position:absolute;bottom:72px;left:84px;right:84px;height:40px;display:flex;justify-content:space-between;
 align-items:center;font-size:28px;color:{c("suave")}}}
.pontos{{display:flex;gap:12px}}
.pontos i{{width:14px;height:14px;border-radius:50%;background:{_rgba(c("texto"), 0.25)}}}
.pontos i.on{{background:{c("destaque")};width:40px;border-radius:999px}}
</style></head><body><div class="brilho"></div>
<div class="topo"><span class="marca">{logo_img}<span>{arroba}</span></span>
<span>{n + 1}/{total}</span></div>
<div class="corpo {tipo}">{corpo}</div>
<div class="rodape"><span class="pontos">{pontos}</span>
<span>{"arraste para o lado" if tipo == "capa" else ""}</span></div>
</body></html>"""


def renderizar(post: Post, marca: Marca, logo: bytes, pasta: Path) -> list[Path]:
    """Os slides em JPEG (1080 x 1350), pelo Chromium sem tela."""
    from PIL import Image

    binario = next((b for b in map(shutil.which, NAVEGADORES) if b), None)
    if binario is None:
        raise PostErro("Chromium não encontrado nesta máquina.")
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    for velho in pasta.glob("slide-*.jpg"):
        velho.unlink()
    feitos = []
    with tempfile.TemporaryDirectory(prefix="ze-post-") as tmp:
        for n in range(len(post.slides)):
            pagina = Path(tmp) / f"slide-{n + 1}.html"
            pagina.write_text(html_do_slide(post, n, marca, logo))
            png = Path(tmp) / f"slide-{n + 1}.png"
            subprocess.run(  # noqa: S603 (o Chromium, com o nosso próprio HTML)
                [
                    binario, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--mute-audio", "--no-first-run", "--disable-extensions",
                    f"--user-data-dir={tmp}/perfil", f"--window-size={LARGURA},{ALTURA}",
                    "--virtual-time-budget=5000", f"--screenshot={png}", pagina.as_uri(),
                ],
                capture_output=True, timeout=60, check=False,
            )  # fmt: skip
            if not png.is_file():
                raise PostErro("Não consegui desenhar os slides.")
            destino = pasta / f"slide-{n + 1}.jpg"
            with Image.open(png) as imagem:
                imagem.convert("RGB").crop((0, 0, LARGURA, ALTURA)).save(destino, quality=92)
            feitos.append(destino)
    return feitos


def endereco_publico(arquivo: Path = TUNEL) -> str:
    """O endereço fixo do Zé na internet (o túnel), por onde a Meta busca as imagens."""
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return ""
    fixo = str(dados.get("fixo", "")) if isinstance(dados, dict) and dados.get("ativo") else ""
    return fixo.rstrip("/") if fixo.startswith("https://") else ""


def _perguntar_ao_modelo(prompt: str) -> str:
    from zervis.habilidades import revisao

    saida, _uso = asyncio.run(
        revisao.perguntar_ao_modelo(prompt, MODELO, lugares.DADOS / "cerebro", 0, SISTEMA)
    )
    return saida


class Posts:
    def __init__(
        self,
        pasta: Path = PASTA,
        site: marketing.Marketing | None = None,
        perguntar: Callable[[str], str] = _perguntar_ao_modelo,
        desenhar: Callable[[Post, Marca, bytes, Path], list[Path]] = renderizar,
        instagram: Instagram | None = None,
        links: publico.Publicos = publico.PADRAO,
        endereco: Callable[[], str] = endereco_publico,
        publicar: Callable[..., str] = instagram_publicar.publicar,
    ) -> None:
        self.pasta = pasta
        self.site = site or marketing.PADRAO
        self.perguntar = perguntar
        self.desenhar = desenhar
        self.instagram = instagram or Instagram()
        self.links = links
        self.endereco = endereco
        self._publicar = publicar
        self._trava = threading.Lock()

    # --- guardar --------------------------------------------------------------------------

    def _dir(self, id_: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{8}", id_):
            raise PostErro("Post desconhecido.")
        return self.pasta / id_

    def ler(self, id_: str) -> Post:
        try:
            dados = json.loads((self._dir(id_) / "post.json").read_text())
            return Post(**{k: v for k, v in dados.items() if k in Post.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            raise PostErro("Post desconhecido.") from None

    def _gravar(self, post: Post) -> Post:
        pasta = self._dir(post.id)
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = pasta / "post.next"
        temporario.write_text(json.dumps(asdict(post), ensure_ascii=False))
        temporario.replace(pasta / "post.json")
        return post

    def listar(self) -> list[Post]:
        posts = []
        for arquivo in self.pasta.glob("*/post.json") if self.pasta.is_dir() else []:
            try:
                posts.append(self.ler(arquivo.parent.name))
            except PostErro:
                continue
        return sorted(posts, key=lambda p: p.criado, reverse=True)

    def slides(self, id_: str) -> list[Path]:
        return sorted(self._dir(id_).glob("slide-*.jpg"), key=lambda p: int(p.stem.split("-")[1]))

    def descartar(self, id_: str) -> None:
        post = self.ler(id_)
        if post.estado == "publicando":
            raise PostErro("O post está sendo publicado.")
        shutil.rmtree(self._dir(id_), ignore_errors=True)

    # --- criar ----------------------------------------------------------------------------

    def criar(
        self, tema: str = "", artigo: str = "", instrucao: str = "", esperar: bool = False
    ) -> Post:
        """Começa um post (o texto e os slides levam um ou dois minutos). Sem `esperar`, volta
        logo, e o Zé avisa quando a prévia estiver pronta."""
        tema, artigo = " ".join(tema.split())[:200], artigo.strip()
        if not tema and not artigo:
            raise PostErro("Diga o tema do post ou o artigo de origem.")
        if artigo and not self.site.artigo(artigo):
            raise PostErro("Artigo não encontrado no blog.")
        post = self._gravar(Post(uuid.uuid4().hex[:8], tema, artigo, instrucao))
        return self._comecar(post, esperar)

    def refazer(self, id_: str, instrucao: str, esperar: bool = False) -> Post:
        post = self.ler(id_)
        if post.estado in ("criando", "publicando", "publicado"):
            raise PostErro("Este post não pode ser refeito agora.")
        post.instrucao, post.estado, post.erro = " ".join(instrucao.split())[:400], "criando", ""
        return self._comecar(self._gravar(post), esperar)

    def _comecar(self, post: Post, esperar: bool) -> Post:
        if esperar:
            self._fazer(post)
            return self.ler(post.id)
        threading.Thread(target=self._fazer, args=(post,), name="post", daemon=True).start()
        return post

    def _pedido(self, post: Post) -> str:
        if post.artigo:
            partes = [
                "Transforme este artigo do blog num carrossel que leve ao artigo e à oferta.",
                "## Artigo",
                self.site.artigo(post.artigo)[:LIMITE_ARTIGO],
            ]
        else:
            partes = [f"Tema: {post.tema}"]
        if post.instrucao and post.slides:
            anterior = json.dumps(
                {"slides": post.slides, "legenda": post.legenda}, ensure_ascii=False
            )
            partes += [f"Versão anterior: {anterior}", f"Ajuste pedido: {post.instrucao}"]
        return "\n\n".join(partes)

    def _fazer(self, post: Post) -> None:
        marca = self.site.marca()
        try:
            prompt = PROMPT.format(
                nome=f"{marca.nome} (@{marca.instagram})"
                if marca.instagram
                else marca.nome or "uma empresa",
                pedido=self._pedido(post),
                manual=self.site.manual()
                or "(o site não tem manual; use um tom profissional e direto)",
            )
            post.slides, post.chamada, post.legenda = interpretar(self.perguntar(prompt))
            self.desenhar(post, marca, self.site.logo(), self._dir(post.id))
            post.estado, post.erro = "rascunho", ""
            texto = f"O post {post.tema or post.artigo} está pronto para revisar em Marketing."
        except (PostErro, OSError, subprocess.SubprocessError, ValueError) as erro:
            log.warning("post %s: %s", post.id, erro)
            post.estado, post.erro = "erro", str(erro) if isinstance(erro, PostErro) else "Falhou."
            texto = f"Não consegui criar o post: {post.erro}"
        self._gravar(post)
        self._avisar(texto)

    # --- publicar -------------------------------------------------------------------------

    def publicar(self, id_: str, esperar: bool = False) -> Post:
        """Publica no Instagram. Só com a aprovação de quem usa: quem chama já a recebeu."""
        with self._trava:
            post = self.ler(id_)
            if post.estado != "rascunho":
                raise PostErro("Só um rascunho pronto pode ser publicado.")
            if not self.instagram.conectado:
                raise PostErro("Conecte o Instagram em Redes sociais.")
            if not self.endereco():
                raise PostErro("Publicar exige o acesso de qualquer lugar com endereço fixo.")
            if not self.slides(id_):
                raise PostErro("O post não tem slides.")
            post.estado, post.erro = "publicando", ""
            self._gravar(post)
        if esperar:
            self._enviar(post)
            return self.ler(id_)
        threading.Thread(
            target=self._enviar, args=(post,), name="post-publicar", daemon=True
        ).start()
        return post

    def _enviar(self, post: Post) -> None:
        arquivos = self.slides(post.id)
        segredo = self.links.abrir(arquivos)
        try:
            base = self.endereco()
            urls = [f"{base}{publico.PREFIXO}{segredo}/{a.name}" for a in arquivos]
            post.permalink = self._publicar(self.instagram, urls, post.legenda)
            post.estado, post.publicado, post.erro = "publicado", time.time(), ""
            texto = "O post foi publicado no Instagram."
        except InstagramErro as erro:
            post.estado, post.erro = "rascunho", str(erro)
            texto = f"Não publiquei o post: {erro}"
        finally:
            self.links.fechar(segredo)
        self._gravar(post)
        self._avisar(texto)

    def _avisar(self, texto: str) -> None:
        if self.site.avisar is not None:
            self.site.avisar(texto)

    def para_tela(self, post: Post, com_imagens: bool = False) -> dict[str, Any]:
        dados = {
            k: getattr(post, k)
            for k in (
                "id",
                "tema",
                "artigo",
                "estado",
                "erro",
                "legenda",
                "chamada",
                "permalink",
                "criado",
            )
        }
        dados["slides"] = len(post.slides)
        if com_imagens:
            dados["imagens"] = [
                "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
                for p in self.slides(post.id)
            ]
        return dados


PADRAO = Posts()
