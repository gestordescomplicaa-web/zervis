"""O leitor de páginas do Zé (ADR 0059): o texto limpo de uma página, sem menu, rodapé nem anúncio.

A página vem pela mesma trava de rede do print (`zervis/imersivo/capturas.py`): só HTTPS, só
endereço público na porta 443, redirecionamento só para HTTPS. O Trafilatura (Apache-2.0) tira o
texto principal e os dados da página (título, autor, data, site). Página que só monta o conteúdo
com JavaScript volta quase vazia: aí ela abre no Chromium do Zé, atrás da mesma trava, e o texto
sai do HTML já montado. Sem nada disso, sobra o texto corrido da página inteira.

O texto passa pela máscara de segredos do navegador antes do cérebro e do disco. O que vem da
página é dado, nunca instrução.
"""

import dataclasses
import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO

import trafilatura

from zervis.cerebro.navegador import mascarar
from zervis.imersivo import capturas

log = logging.getLogger(__name__)

TEMPO_S = 15.0
MAXIMO = 4 * 1024 * 1024  # o HTML de uma página; o resto é descartado
TEXTO_MAX = 200_000
POUCO = 400  # menos texto que isto: a página monta o conteúdo com JavaScript
TIPOS = ("text/html", "application/xhtml+xml", "text/plain")
BLOQUEIO = re.compile(
    r"\b(403 (error|forbidden)|access denied|request blocked|just a moment|attention required"
    r"|verify(ing)? (you are|that you are) (a )?human|are you a robot|enable javascript and "
    r"cookies|checking your browser|acesso negado|captcha)\b",
    re.IGNORECASE,
)
AGENTE = "Mozilla/5.0 (X11; Linux x86_64) Zervis/1.0 (+leitura de um assistente pessoal)"


class LeitorErro(RuntimeError):
    pass


@dataclass(frozen=True)
class Pagina:
    url: str
    titulo: str
    texto: str
    autor: str = ""
    data: str = ""
    site: str = ""
    por: str = "direto"  # "direto", "chromium" ou "texto corrido"


class _SoHttps(urllib.request.HTTPRedirectHandler):
    """Redirecionamento para http:// sairia da trava: recusado."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.lower().startswith("https://"):
            raise LeitorErro("a página redirecionou para fora do https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def baixar(url: str) -> tuple[bytes, str]:
    """O HTML da página (até MAXIMO) e o endereço final, pela trava de rede."""
    capturas.conferir_url(url)
    with capturas.trava() as t:
        proxy = f"http://127.0.0.1:{t.porta}"  # http e https: a trava só aceita CONNECT na 443
        abridor = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy}), _SoHttps()
        )
        pedido = urllib.request.Request(  # noqa: S310 (só https, conferido acima)
            url,
            headers={
                "User-Agent": AGENTE,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
            },
        )
        try:
            with abridor.open(pedido, timeout=TEMPO_S) as r:
                tipo = r.headers.get_content_type()
                if tipo not in TIPOS:
                    raise LeitorErro(f"não leio esse tipo de arquivo ({tipo})")
                return r.read(MAXIMO), str(r.geturl())
        except urllib.error.HTTPError as erro:
            raise LeitorErro(f"a página respondeu {erro.code}") from None
        except (urllib.error.URLError, OSError) as erro:
            raise LeitorErro(f"a página não abriu ({type(erro).__name__})") from None


def extrair(html: bytes | str, url: str) -> Pagina | None:
    """O texto principal e os dados da página, pelo Trafilatura; None se não achar texto."""
    try:
        bruto = trafilatura.extract(
            html, url=url, output_format="json", with_metadata=True, include_tables=True,
            include_comments=False, favor_recall=True,
        )  # fmt: skip
    except Exception as erro:  # um HTML torto não pode derrubar a pesquisa
        log.info("trafilatura falhou em %s: %s", url, type(erro).__name__)
        return None
    if not bruto:
        return None
    dados = json.loads(bruto)
    texto = str(dados.get("text") or "").strip()
    if not texto:
        return None
    return Pagina(
        url=url,
        titulo=str(dados.get("title") or "")[:200],
        texto=texto,
        autor=str(dados.get("author") or "")[:120],
        data=str(dados.get("date") or "")[:20],
        site=str(dados.get("sitename") or dados.get("hostname") or "")[:80],
    )


def _corrido(html: bytes | str, url: str) -> Pagina | None:
    try:
        texto = trafilatura.html2txt(html).strip()
    except Exception:
        return None
    return Pagina(url=url, titulo="", texto=texto, por="texto corrido") if texto else None


def bloqueada(pagina: Pagina) -> bool:
    """A página de bloqueio do site (anti-robô, 403, "verificando o navegador"), não o conteúdo.
    Só conta em página curta: um artigo sobre captcha não é bloqueio."""
    if len(pagina.texto) > 1500:
        return False
    return BLOQUEIO.search(f"{pagina.titulo}\n{pagina.texto}") is not None


def ler(
    url: str,
    js: bool = True,
    baixar: Callable[[str], tuple[bytes, str]] = baixar,
    renderizar: Callable[[str], str] = capturas.renderizar,
) -> Pagina:
    """A página lida: direto; no Chromium se vier quase vazia (e `js`); senão, o texto corrido."""
    try:
        html, final = baixar(url)
    except capturas.CapturaErro as erro:
        raise LeitorErro(str(erro)) from None
    pagina = extrair(html, final)
    if (pagina is None or len(pagina.texto) < POUCO) and js:
        try:
            montada = extrair(renderizar(final), final)
        except capturas.CapturaErro as erro:
            log.info("leitor: o Chromium não abriu %s (%s)", final, erro)
            montada = None
        if montada is not None and len(montada.texto) > len(pagina.texto if pagina else ""):
            pagina = dataclasses.replace(montada, por="chromium")
    pagina = pagina or _corrido(html, final)
    if pagina is None:
        raise LeitorErro("a página não tem texto que eu consiga ler")
    if bloqueada(pagina):
        raise LeitorErro("o site bloqueou a leitura")
    return dataclasses.replace(pagina, texto=mascarar(pagina.texto[:TEXTO_MAX]))
