"""As fotos dos vídeos (ADR 0112): as da marca, que quem usa envia em Marketing, e as livres, da
Wikimedia, sempre com o crédito na tela e na legenda do Instagram.

O diretor escolhe pelo nome (as fotos da marca têm nomes que as descrevem) ou pede "busca: <o que
mostrar, em inglês>". Aqui a escolha vira um arquivo na pasta do vídeo. A busca é só no Commons
(os nomes dos arquivos descrevem a foto; a Wikipédia em português devolve páginas sem relação para
uma busca em inglês) e só aceita a foto cujo título tem as palavras do pedido (duas, se o pedido
tiver duas ou mais). Sem foto que sirva, a cena vira um ícone que se desenha: o vídeo nunca falha
por falta de foto.
"""

import logging
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis.imersivo import imagens
from zervis.video import biblioteca

log = logging.getLogger(__name__)

BUSCA = "busca:"
POR_VIDEO = 2  # no máximo duas fotos livres por vídeo (cada uma é uma ida à rede)
_PALAVRA = re.compile(r"[a-z0-9]{3,}")


def _palavras(texto: str) -> set[str]:
    return set(_PALAVRA.findall(texto.lower()))


def _buscar_no_commons(busca: str) -> list[imagens.Achado]:
    return imagens.buscar_commons(busca, quantos=8)


def _nota(achado: imagens.Achado, pedidas: set[str]) -> int:
    """Quantas palavras do pedido o título tem (valem o dobro) e a descrição tem."""
    return 2 * len(pedidas & _palavras(achado.titulo)) + len(pedidas & _palavras(achado.descricao))


def _serve(achado: imagens.Achado, pedidas: set[str]) -> bool:
    """O título (ou a descrição) tem as palavras do pedido: duas, ou a única que houver."""
    iguais = pedidas & _palavras(f"{achado.titulo} {achado.descricao}")
    return achado.tipo == "foto" and len(iguais) >= min(2, len(pedidas))


def _limpo(credito: str) -> str:
    """Sem o "(talk)" que o Commons põe ao lado do autor."""
    return re.sub(r"\s*\(\s*(talk|discuss[aã]o|contribs?)\s*\)", "", credito, flags=re.I)


def _da_marca() -> list[str]:
    from zervis import marketing_posts  # só quem faz vídeo com foto carrega os posts

    return marketing_posts.PADRAO.fotos()


def _pasta_da_marca() -> Path:
    from zervis import marketing_posts

    return marketing_posts.PADRAO.pasta_fotos


class Fotos:
    """De onde vêm as fotos. Tudo injetável, para testar sem rede nem painel."""

    def __init__(
        self,
        da_marca: Callable[[], list[str]] = _da_marca,
        pasta_da_marca: Callable[[], Path] = _pasta_da_marca,
        buscar: Callable[[str], list[imagens.Achado]] = _buscar_no_commons,
        baixar: Callable[[str, Path], dict[str, Any]] = imagens.baixar,
    ) -> None:
        self.da_marca = da_marca
        self.pasta_da_marca = pasta_da_marca
        self.buscar = buscar
        self.baixar = baixar

    def nomes(self) -> list[str]:
        """Os nomes das fotos da marca, para o diretor (vazio se o painel não tiver nenhuma)."""
        try:
            return self.da_marca()
        except OSError:
            return []

    def resolver(self, cenas: list[dict[str, Any]], pasta: Path) -> list[str]:
        """Troca o pedido de cada cena de foto pelo arquivo (`imagem`, o endereço local) e o
        crédito; a que não achar foto vira um ícone. Devolve os créditos, para a legenda."""
        creditos: list[str] = []
        livres = 0
        for c in cenas:
            if c.get("tipo") != "foto":
                continue
            pedido = str(c.get("foto", "")).strip()
            achada: tuple[Path, str] | None = None
            if pedido.lower().startswith(BUSCA):
                busca = pedido[len(BUSCA) :].strip()
                if livres < POR_VIDEO:
                    livres += 1
                    achada = self._livre(busca, pasta)
            else:
                achada = self._da_marca_na_pasta(pedido, pasta)
            if achada is None:
                log.info("sem foto para '%s': a cena vira ícone", pedido)
                self._virar_icone(c, pedido)
                continue
            arquivo, credito = achada
            c["imagem"] = arquivo.resolve().as_uri()
            if credito:
                c["credito"] = credito
                creditos.append(credito)
        return creditos

    def _da_marca_na_pasta(self, nome: str, pasta: Path) -> tuple[Path, str] | None:
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
        return destino, ""

    def _livre(self, busca: str, pasta: Path) -> tuple[Path, str] | None:
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
                registro = self.baixar(a.id, pasta)
                return pasta / registro["arquivo"], _limpo(imagens.credito(registro))
        except (imagens.ImagemErro, OSError, KeyError) as erro:
            log.info("foto livre '%s' não veio: %s", busca, erro)
        return None

    @staticmethod
    def _virar_icone(cena: dict[str, Any], pedido: str) -> None:
        objeto = pedido[len(BUSCA) :] if pedido.lower().startswith(BUSCA) else pedido
        objeto = re.sub(r"[-_]+", " ", Path(objeto).stem)
        icone = cena.get("icone") if cena.get("icone") not in (None, "", "sparkles") else None
        cena.update(tipo="icone", composicao="heroi", icone=icone or biblioteca.achar(objeto))
        cena.pop("foto", None)


PADRAO = Fotos()
