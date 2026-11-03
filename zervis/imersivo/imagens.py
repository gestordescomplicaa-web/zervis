"""Imagens e vídeos reais para a Imersão (ADR 0058): a foto de quem é, o lugar, a coisa de verdade,
ao lado dos hologramas e dos gráficos.

Fontes gratuitas e com licença em cada arquivo, sem chave:
- **Wikipédia** (pt, depois en): a foto principal da página. É a melhor para pessoas públicas,
  lugares, empresas e obras ("quem é fulano?").
- **Wikimedia Commons**: fotos e vídeos de qualquer assunto; o vídeo vem na versão leve (480p,
  webm), não o original.

Como os modelos 3D (ADR 0049), o arquivo vem da internet, então: só HTTPS e só os domínios da
Wikimedia (também nos redirecionamentos), com teto de tamanho, e o conteúdo conferido (JPEG, PNG,
WebP, GIF ou WebM de verdade). Imagem marcada como não livre (uso justo) é recusada. Ao lado de
cada arquivo fica um `.json` com a fonte, a licença e o autor: o crédito vai para a tela.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from zervis.imersivo.modelos3d import AGENTE

PASTA_FOTOS = Path("imagens") / "web"  # dentro do Acervo
PASTA_VIDEOS = Path("videos") / "web"
TEMPO_S = 20.0
FOTO_MAX = 8 * 1024 * 1024
VIDEO_MAX = 40 * 1024 * 1024
LARGURA = 1280  # a foto vem nesta largura (o Commons redimensiona e converte SVG em PNG)
PREVIA_LARGURA = 240
PREVIA_MAX = 60 * 1024
HOSTS = frozenset(
    {
        "pt.wikipedia.org",
        "en.wikipedia.org",
        "commons.wikimedia.org",
        "upload.wikimedia.org",
        "thumb.wikimedia.org",
    }
)
WIKIS = ("pt", "en")
COMMONS = "https://commons.wikimedia.org/w/api.php"
ID = re.compile(r"^(?:wiki:(?:pt|en):.{1,200}|commons:File:.{1,240})$")
_TAG = re.compile(r"<[^>]+>")


class ImagemErro(Exception):
    pass


@dataclass(frozen=True)
class Achado:
    id: str  # "wiki:pt:Marina Silva" ou "commons:File:Nome.jpg"
    titulo: str
    descricao: str
    tipo: str  # foto | video
    licenca: str
    autor: str
    previa: str  # a miniatura (para o Zé olhar antes de escolher)
    pagina: str


class _SoHosts(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _conferir(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _conferir(url: str) -> None:
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or (p.hostname or "") not in HOSTS:
        raise ImagemErro(f"endereço fora das fontes permitidas: {p.hostname or url}")


def _ler(url: str, limite: int) -> bytes:
    _conferir(url)
    # HTTPS e domínio da Wikimedia conferidos acima (e em cada redirecionamento, por _SoHosts)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310
    try:
        with urllib.request.build_opener(_SoHosts()).open(pedido, timeout=TEMPO_S) as r:
            tamanho = int(r.headers.get("Content-Length") or 0)
            if tamanho > limite:
                raise ImagemErro(f"arquivo grande demais ({tamanho // 1024 // 1024} MB)")
            dados: bytes = r.read(limite + 1)
    except urllib.error.HTTPError as erro:
        raise ImagemErro(f"a Wikimedia respondeu {erro.code}") from None
    except (urllib.error.URLError, OSError) as erro:
        raise ImagemErro(f"a Wikimedia não respondeu ({erro})") from None
    if len(dados) > limite:
        raise ImagemErro("arquivo grande demais")
    return dados


def _json(url: str, ler: Any) -> dict[str, Any]:
    try:
        dados = json.loads(ler(url, 2 * 1024 * 1024))
    except ValueError:
        raise ImagemErro("a Wikimedia respondeu algo que não é JSON") from None
    return dados if isinstance(dados, dict) else {}


def _sem_html(texto: Any, n: int = 120) -> str:
    return " ".join(_TAG.sub(" ", str(texto or "")).split())[:n]


def tipo_do_arquivo(dados: bytes) -> str | None:
    """A extensão pelo conteúdo, não pelo nome: jpg, png, webp, gif ou webm."""
    if dados[:3] == b"\xff\xd8\xff":
        return "jpg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if dados[:4] == b"\x1a\x45\xdf\xa3" and b"webm" in dados[:64]:
        return "webm"
    return None


# --- os metadados de um arquivo da Wikimedia ---------------------------------------------------


def _info(arquivo: str, ler: Any, video: bool = False) -> dict[str, Any]:
    """A licença, o autor, a descrição e os endereços (a foto em LARGURA, ou o vídeo leve)."""
    params = {
        "action": "query", "titles": arquivo, "format": "json", "formatversion": "2",
        "prop": "videoinfo" if video else "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": str(LARGURA),
        "viprop": "url|extmetadata|mime|derivatives",
    }  # fmt: skip
    dados = _json(f"{COMMONS}?{urllib.parse.urlencode(params)}", ler)
    paginas = (dados.get("query") or {}).get("pages") or []
    pagina = paginas[0] if paginas else {}
    infos = pagina.get("videoinfo" if video else "imageinfo") or []
    if not infos:
        raise ImagemErro("arquivo não encontrado na Wikimedia")
    info = infos[0]
    meta = info.get("extmetadata") or {}

    def campo(nome: str, n: int = 120) -> str:
        return _sem_html((meta.get(nome) or {}).get("value"), n)

    if campo("NonFree").lower() == "true":
        raise ImagemErro("imagem não livre (uso justo): não serve")
    saida = {
        "licenca": campo("LicenseShortName", 40) or "?",
        "licenca_url": campo("LicenseUrl", 200),
        "autor": campo("Artist", 80),
        "descricao": campo("ImageDescription", 160),
        "pagina": str(info.get("descriptionurl") or "")[:240],
        "mime": str(info.get("mime") or ""),
    }
    if video:
        leves = [
            d for d in info.get("derivatives") or []
            if "webm" in str(d.get("type", "")) and 0 < int(d.get("height") or 0) <= 480
        ]  # fmt: skip
        leves.sort(key=lambda d: -int(d.get("height") or 0))
        if not leves:
            raise ImagemErro("o vídeo não tem uma versão leve em webm")
        saida["url"] = str(leves[0].get("src") or "")
    else:
        saida["url"] = str(info.get("thumburl") or info.get("url") or "")
        saida["previa"] = re.sub(r"/\d+px-", f"/{PREVIA_LARGURA}px-", saida["url"])
    return saida


def _arquivo_da_url(url: str) -> str:
    """O arquivo da foto pela URL: ".../2/20/Ana_crop.jpg" -> "File:Ana crop.jpg"."""
    caminho = urllib.parse.urlsplit(url).path
    nome = caminho.rsplit("/", 1)[-1]
    if "/thumb/" in caminho:  # .../thumb/2/20/Nome.jpg/330px-Nome.jpg: o nome é o penúltimo
        nome = caminho.rsplit("/", 2)[-2]
    return "File:" + urllib.parse.unquote(nome).replace("_", " ")


# --- buscar -------------------------------------------------------------------------------------


def _maior(miniatura: str) -> str:
    """A miniatura da busca (60 px) na largura da prévia: pequena demais para o Zé julgar."""
    url = "https:" + miniatura if miniatura.startswith("//") else miniatura
    return re.sub(r"/\d+px-", f"/{PREVIA_LARGURA}px-", url)


def buscar_wikipedia(busca: str, ler: Any = _ler, quantos: int = 3) -> list[Achado]:
    """As páginas que casam com a busca e têm foto: a foto principal de cada uma."""
    achados: list[Achado] = []
    for wiki in WIKIS:
        params = urllib.parse.urlencode({"q": busca, "limit": str(quantos)})
        dados = _json(f"https://{wiki}.wikipedia.org/w/rest.php/v1/search/page?{params}", ler)
        for p in dados.get("pages") or []:
            miniatura = (p.get("thumbnail") or {}).get("url") if isinstance(p, dict) else None
            if not miniatura:
                continue
            titulo = str(p.get("title", ""))
            achados.append(
                Achado(
                    id=f"wiki:{wiki}:{titulo}",
                    titulo=titulo[:80],
                    descricao=_sem_html(p.get("description"), 120),
                    tipo="foto",
                    licenca="(na hora de baixar)",
                    autor="",
                    previa=_maior(miniatura),
                    pagina=f"https://{wiki}.wikipedia.org/wiki/{urllib.parse.quote(titulo)}",
                )
            )
        if achados:
            break  # achou na Wikipédia em português: não precisa da inglesa
    return achados[:quantos]


def buscar_commons(
    busca: str, video: bool = False, ler: Any = _ler, quantos: int = 4
) -> list[Achado]:
    filtro = "filetype:video" if video else "filetype:bitmap"
    params = {
        "action": "query", "format": "json", "formatversion": "2", "generator": "search",
        "gsrsearch": f"{filtro} {busca}", "gsrnamespace": "6", "gsrlimit": str(quantos),
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": str(PREVIA_LARGURA),
    }  # fmt: skip
    dados = _json(f"{COMMONS}?{urllib.parse.urlencode(params)}", ler)
    achados = []
    for p in (dados.get("query") or {}).get("pages") or []:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if _sem_html((meta.get("NonFree") or {}).get("value")).lower() == "true":
            continue
        titulo = str(p.get("title", ""))
        achados.append(
            Achado(
                id=f"commons:{titulo}",
                titulo=titulo.removeprefix("File:").rsplit(".", 1)[0][:80],
                descricao=_sem_html((meta.get("ImageDescription") or {}).get("value"), 120),
                tipo="video" if video else "foto",
                licenca=_sem_html((meta.get("LicenseShortName") or {}).get("value"), 40) or "?",
                autor=_sem_html((meta.get("Artist") or {}).get("value"), 60),
                previa=str(info.get("thumburl") or ""),
                pagina=str(info.get("descriptionurl") or "")[:240],
            )
        )
    return achados


def buscar(busca: str, tipo: str = "foto", ler: Any = _ler) -> list[Achado]:
    """Foto: a Wikipédia primeiro (pessoa, lugar, empresa), depois o Commons; vídeo: o Commons."""
    busca = " ".join(busca.split())[:120]
    if not busca:
        raise ImagemErro("diga o que buscar")
    if tipo == "video":
        return buscar_commons(busca, True, ler)
    return [*buscar_wikipedia(busca, ler), *buscar_commons(busca, False, ler, 3)][:6]


def previas(achados: list[Achado], ler: Any = _ler) -> list[tuple[str, bytes]]:
    """A miniatura de cada achado (pequena), para o Zé olhar antes de escolher."""
    vistas = []
    for a in achados[:6]:
        if not a.previa:
            continue
        try:
            imagem = ler(a.previa, PREVIA_MAX)
        except ImagemErro:
            continue
        if tipo_do_arquivo(imagem) in ("jpg", "png", "webp", "gif"):
            vistas.append((a.id, imagem))
    return vistas


# --- baixar -------------------------------------------------------------------------------------


def _nome(texto: str) -> str:
    sem = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return sem[:80] or "imagem"


def baixar(id_: str, acervo: Path, ler: Any = _ler) -> dict[str, Any]:
    """Baixa (ou reusa) a foto ou o vídeo e devolve onde ficou no Acervo, com o crédito."""
    id_ = str(id_).strip()
    if not ID.match(id_):
        raise ImagemErro("imagem desconhecida; use o id que imagem_buscar devolveu")
    fonte, _, resto = id_.partition(":")
    if fonte == "wiki":
        wiki, _, titulo = resto.partition(":")
        video, nome_base = False, titulo
    else:
        arquivo = resto
        video = bool(re.search(r"\.(webm|ogv|mpg|mpeg|mp4|mov)$", arquivo, re.IGNORECASE))
        nome_base = arquivo.removeprefix("File:").rsplit(".", 1)[0]
    pasta = PASTA_VIDEOS if video else PASTA_FOTOS
    nome = _nome(nome_base)
    for existente in (acervo / pasta).glob(f"{nome}.*"):  # já baixado: nem consulta a rede
        if existente.suffix != ".json" and existente.with_suffix(".json").is_file():
            ficha = json.loads(existente.with_suffix(".json").read_text())
            return {**ficha, "arquivo": (pasta / existente.name).as_posix(), "reusado": True}
    legenda = ""
    if fonte == "wiki":
        resumo = _json(
            f"https://{wiki}.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(titulo.replace(" ", "_"), safe=""),
            ler,
        )
        original = (resumo.get("originalimage") or resumo.get("thumbnail") or {}).get("source")
        if not original:
            raise ImagemErro("a página não tem foto")
        arquivo = _arquivo_da_url(str(original))
        legenda = _sem_html(resumo.get("description"), 120)
    info = _info(arquivo, ler, video)
    dados = ler(info["url"], VIDEO_MAX if video else FOTO_MAX)
    extensao = tipo_do_arquivo(dados)
    if extensao is None or (extensao == "webm") != video:
        raise ImagemErro("o arquivo baixado não é uma imagem ou um vídeo que a tela mostre")
    registro = {
        "titulo": (titulo if fonte == "wiki" else nome_base)[:80],
        "legenda": legenda or info["descricao"],
        "tipo": "video" if video else "foto",
        "fonte": "Wikipédia" if fonte == "wiki" else "Wikimedia Commons",
        "pagina": info["pagina"],
        "licenca": info["licenca"],
        "licenca_url": info["licenca_url"],
        "autor": info["autor"],
        "baixado_em": time.strftime("%Y-%m-%d %H:%M"),
    }
    destino = acervo / pasta
    destino.mkdir(parents=True, exist_ok=True, mode=0o700)
    alvo = destino / f"{nome}.{extensao}"
    temporario = alvo.with_suffix(".parcial")
    temporario.write_bytes(dados)
    temporario.replace(alvo)
    alvo.with_suffix(".json").write_text(json.dumps(registro, ensure_ascii=False, indent=1))
    return {**registro, "arquivo": (pasta / alvo.name).as_posix(), "reusado": False}


def credito(registro: dict[str, Any]) -> str:
    """A linha do rodapé: "Foto: Fulano · CC BY 2.0 · Wikimedia Commons"."""
    tipo = "Vídeo" if registro.get("tipo") == "video" else "Foto"
    partes = [f"{tipo}: {registro['autor']}" if registro.get("autor") else tipo]
    partes += [p for p in (registro.get("licenca"), registro.get("fonte")) if p and p != "?"]
    return " · ".join(partes)[:120]


def para_resposta(achados: list[Achado]) -> list[dict[str, Any]]:
    return [{k: v for k, v in asdict(a).items() if k != "previa"} for a in achados]
