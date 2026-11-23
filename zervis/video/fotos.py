"""As fotos dos vídeos (ADR 0112): as da marca, que quem usa envia em Marketing, e as livres, da
Wikimedia, só as que a licença dispensa de crédito (domínio público, CC0; ADR 0121): o vídeo e a
legenda do Instagram ficam sem lista de fontes.

O diretor escolhe pelo nome (as fotos da marca têm nomes que as descrevem) ou pede "busca: <o que
mostrar, em inglês>". Aqui a escolha vira um arquivo na pasta do vídeo. A busca é só no Commons
(os nomes dos arquivos descrevem a foto; a Wikipédia em português devolve páginas sem relação para
uma busca em inglês) e só aceita a foto cujo título tem as palavras do pedido (duas, se o pedido
tiver duas ou mais). Sem foto que sirva, a cena vira um ícone que se desenha: o vídeo nunca falha
por falta de foto.
"""

import concurrent.futures
import logging
import re
import shutil
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis.imersivo import capturas, imagens
from zervis.video import biblioteca

log = logging.getLogger(__name__)

BUSCA = "busca:"
LOGO = "logo:"
SITE = "site:"
SITES_POR_VIDEO = 3  # prints de site por vídeo (cada um abre o Chromium)
POR_VIDEO = 12  # buscas livres por vídeo (cada uma é uma ida à rede; em paralelo)
RESULTADOS = 20  # por busca: só uns 45% dispensam o crédito, então vêm mais
SIMPLE_ICONS = "https://cdn.simpleicons.org/"  # os logos das marcas, na cor delas (CC0)
LOGO_MAX = 64 * 1024
_PALAVRA = re.compile(r"[a-z0-9]{3,}")


def _palavras(texto: str) -> set[str]:
    return set(_PALAVRA.findall(texto.lower()))


def _buscar_no_commons(busca: str) -> list[imagens.Achado]:
    return imagens.buscar_commons(busca, quantos=RESULTADOS)


def _nota(achado: imagens.Achado, pedidas: set[str]) -> int:
    """Quantas palavras do pedido o título tem (valem o dobro) e a descrição tem."""
    return 2 * len(pedidas & _palavras(achado.titulo)) + len(pedidas & _palavras(achado.descricao))


def _serve(achado: imagens.Achado, pedidas: set[str]) -> bool:
    """Uma foto que dispensa o crédito e cujo título (ou descrição) tem as palavras do pedido:
    duas, ou a única que houver."""
    iguais = pedidas & _palavras(f"{achado.titulo} {achado.descricao}")
    return achado.tipo == "foto" and not achado.atribuicao and len(iguais) >= min(2, len(pedidas))


def _da_marca() -> list[str]:
    from zervis import marketing_posts  # só quem faz vídeo com foto carrega os posts

    return marketing_posts.PADRAO.fotos()


def _pasta_da_marca() -> Path:
    from zervis import marketing_posts

    return marketing_posts.PADRAO.pasta_fotos


def slug_do_logo(nome: str) -> str:
    """O nome da marca no jeito do Simple Icons ("Google Calendar" → "googlecalendar")."""
    sem = unicodedata.normalize("NFKD", nome.lower()).encode("ascii", "ignore").decode()
    sem = sem.replace("+", "plus").replace(".", "dot").replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", sem)[:40]


def _chave(pedido: str) -> str:
    """O mesmo pedido escrito de outro jeito ("logo: WhatsApp" e "logo: whatsapp") é um só."""
    p = pedido.strip()
    return f"{LOGO} {slug_do_logo(p[len(LOGO) :])}" if p.lower().startswith(LOGO) else p


def _capturar_site(url: str, pasta: Path) -> dict[str, Any]:
    return capturas.capturar(url, pasta)  # só HTTPS, atrás da trava de rede (ADR 0058)


def endereco_do_site(texto: str) -> str:
    """ "notion.so" ou "https://www.notion.so/produto" → o endereço https, sem nada além."""
    t = texto.strip().split()[0] if texto.strip() else ""
    t = re.sub(r"^https?://", "", t, flags=re.I)
    return f"https://{t}" if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}(/[\w\-./]*)?", t, re.I) else ""


def _baixar_logo(slug: str) -> bytes:
    from zervis.imersivo.modelos3d import AGENTE  # o nome genérico do Zé nos pedidos à rede

    pedido = urllib.request.Request(SIMPLE_ICONS + slug, headers={"User-Agent": AGENTE})  # noqa: S310
    with urllib.request.urlopen(pedido, timeout=8) as r:  # noqa: S310 (endereço fixo)
        return bytes(r.read(LOGO_MAX + 1))


def _svg_limpo(dados: bytes) -> bool:
    """Um logo do Simple Icons: um SVG pequeno só com o desenho (nada que rode)."""
    texto = dados[:LOGO_MAX].decode("utf-8", "ignore")
    return (
        len(dados) <= LOGO_MAX
        and texto.lstrip().startswith("<svg")
        and not re.search(r"<script|on\w+=|href|<foreign", texto, re.I)
    )


class Fotos:
    """De onde vêm as imagens: as fotos da marca, as livres (Commons) e os logos das marcas
    (Simple Icons). Tudo injetável, para testar sem rede nem painel."""

    def __init__(
        self,
        da_marca: Callable[[], list[str]] = _da_marca,
        pasta_da_marca: Callable[[], Path] = _pasta_da_marca,
        buscar: Callable[[str], list[imagens.Achado]] = _buscar_no_commons,
        baixar: Callable[[str, Path], dict[str, Any]] = imagens.baixar,
        logo: Callable[[str], bytes] = _baixar_logo,
        capturar: Callable[[str, Path], dict[str, Any]] | None = None,
    ) -> None:
        self.da_marca = da_marca
        self.pasta_da_marca = pasta_da_marca
        self.buscar = buscar
        self.baixar = baixar
        self.logo = logo
        self.capturar = capturar or _capturar_site

    def nomes(self) -> list[str]:
        """Os nomes das fotos da marca, para o diretor (vazio se o painel não tiver nenhuma)."""
        try:
            return self.da_marca()
        except OSError:
            return []

    def achar(self, pedido: str, pasta: Path) -> tuple[Path, str] | None:
        """O arquivo de um pedido ("logo: whatsapp", "busca: office building", "site: ..." ou o
        nome de uma foto da marca) e o tipo ("logo", "site" ou "foto"); None se não houver."""
        p = pedido.strip()
        if p.lower().startswith(LOGO):
            achado = self._logo(p[len(LOGO) :], pasta)
            return (achado, "logo") if achado else None
        if p.lower().startswith(BUSCA):
            livre = self._livre(p[len(BUSCA) :].strip(), pasta)
            return (livre, "foto") if livre else None
        if p.lower().startswith(SITE):
            site = self._site(p[len(SITE) :], pasta)
            return (site, "site") if site else None
        da_marca = self._da_marca_na_pasta(p, pasta)
        return (da_marca, "foto") if da_marca else None

    def resolver(self, cenas: list[dict[str, Any]], pasta: Path) -> None:
        """Troca cada pedido de imagem pelo arquivo (`imagem`, o endereço local, e `imagem_tipo`):
        a cena de foto, as batidas da cena visual e a imagem do item. Os pedidos saem em
        paralelo; o que não vier vira ícone."""
        alvos: list[tuple[dict[str, Any], str, dict[str, Any]]] = []  # (onde, pedido, cena)
        for c in cenas:
            if c.get("tipo") == "foto":
                alvos.append((c, str(c.get("foto", "")), c))
            for b in c.get("batidas") or []:
                alvos.append((b, str(b.get("mostrar", "")), c))
            if c.get("tipo") == "item" and c.get("mostrar"):
                alvos.append((c, str(c["mostrar"]), c))
        pedidos = list(dict.fromkeys(_chave(p) for _, p, _ in alvos if p.strip()))
        livres = [p for p in pedidos if p.lower().startswith(BUSCA)][:POR_VIDEO]
        sites = [p for p in pedidos if p.lower().startswith(SITE)][:SITES_POR_VIDEO]
        pedidos = [
            p
            for p in pedidos
            if (not p.lower().startswith(BUSCA) or p in livres)
            and (not p.lower().startswith(SITE) or p in sites)
        ]
        with concurrent.futures.ThreadPoolExecutor(6) as grupo:
            achados = dict(
                zip(pedidos, grupo.map(lambda p: self.achar(p, pasta), pedidos), strict=True)
            )
        for onde, pedido, cena in alvos:
            achado = achados.get(_chave(pedido))
            if achado is None:
                log.info("sem imagem para '%s': fica um ícone", pedido)
                if onde is cena and cena.get("tipo") == "foto":
                    self._virar_icone(cena, pedido)
                else:
                    onde["icone"] = self._icone_de(onde, pedido)
                continue
            arquivo, tipo = achado
            onde["imagem"], onde["imagem_tipo"] = arquivo.resolve().as_uri(), tipo
            if tipo == "site":  # a barra do navegador mostra o endereço
                onde["site"] = endereco_do_site(pedido.strip()[len(SITE) :]).removeprefix(
                    "https://"
                )

    def _site(self, texto: str, pasta: Path) -> Path | None:
        url = endereco_do_site(texto)
        if not url:
            return None
        try:
            registro = self.capturar(url, pasta)
            return pasta / str(registro["arquivo"])
        except (capturas.CapturaErro, OSError, KeyError) as erro:  # não abriu: fica um ícone
            log.info("print de '%s' não veio: %s", url, erro)
            return None

    def _logo(self, nome: str, pasta: Path) -> Path | None:
        slug = slug_do_logo(nome)
        if not slug:
            return None
        destino = pasta / "logos" / f"{slug}.svg"
        try:
            dados = self.logo(slug)
        except (urllib.error.URLError, OSError, ValueError) as erro:
            log.info("logo '%s' não veio: %s", slug, erro)
            return None
        if not _svg_limpo(dados):
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
        return destino

    def _da_marca_na_pasta(self, nome: str, pasta: Path) -> Path | None:
        nome = Path(nome).name  # só o nome: nada de caminho vindo do modelo
        if not nome.endswith(".jpg"):
            nome += ".jpg"
        if nome not in self.nomes():
            return None
        destino = pasta / "fotos" / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(self.pasta_da_marca() / nome, destino)
        except OSError:
            return None
        return destino

    def _livre(self, busca: str, pasta: Path) -> Path | None:
        if not busca:
            return None
        pedidas = _palavras(busca)
        if not pedidas:
            return None
        try:
            achados = sorted(self.buscar(busca), key=lambda a: -_nota(a, pedidas))
            for a in achados:
                if not _serve(a, pedidas):
                    continue
                return pasta / str(self.baixar(a.id, pasta)["arquivo"])
        except (imagens.ImagemErro, OSError, KeyError) as erro:
            log.info("foto livre '%s' não veio: %s", busca, erro)
        return None

    @staticmethod
    def _objeto(pedido: str) -> str:
        p = pedido.strip()
        for prefixo in (BUSCA, LOGO, SITE):
            if p.lower().startswith(prefixo):
                p = p[len(prefixo) :]
        return re.sub(r"[-_]+", " ", Path(p.strip()).stem)

    def _icone_de(self, onde: dict[str, Any], pedido: str) -> str:
        atual = onde.get("icone")
        if atual not in (None, "", "sparkles"):
            return str(atual)
        return self._icone_do_objeto(self._objeto(pedido))

    @staticmethod
    def _icone_do_objeto(objeto: str) -> str:
        """O ícone do objeto: primeiro a palavra que é o nome de um ícone ("smartphone"), do fim
        para o começo; depois a mais parecida, sem as palavras genéricas ("close up", "night")."""
        genericas = {"close", "view", "with", "from", "photo", "image", "shot", "detail", "night",
                     "closed", "open", "empty", "unread", "modern", "small", "large"}  # fmt: skip
        palavras = [w for w in objeto.lower().split() if len(w) >= 3 and w not in genericas]
        for w in reversed(palavras):
            if w in (achado := biblioteca.achar(w)).split("-"):
                return achado
        return biblioteca.achar(" ".join(palavras)) if palavras else biblioteca.RESERVA

    def _virar_icone(self, cena: dict[str, Any], pedido: str) -> None:
        objeto = self._objeto(pedido)
        icone = cena.get("icone") if cena.get("icone") not in (None, "", "sparkles") else None
        cena.update(tipo="icone", composicao="heroi", icone=icone or self._icone_do_objeto(objeto))
        cena.pop("foto", None)


PADRAO = Fotos()
