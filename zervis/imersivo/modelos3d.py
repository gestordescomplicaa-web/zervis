"""Modelos 3D prontos e livres para o Acervo (ADR 0049): buscar e baixar, com travas.

"Mostra um cavalo em 3D" pede um cavalo de verdade, não um feito de esferas (ADR 0048). Os
acervos livres têm milhares de modelos `.glb`; o Zé busca, baixa um para `Acervo/3d/baixados/` e o
mostra no cartão holográfico que a pinça gira. Fontes, ambas livres e sem chave: os modelos
oficiais da NASA (domínio público; naves, sondas, foguetes, astronautas) e o 3DAssets.dev (CC0,
de tudo, mas muito dele é simples e feito por IA). Cada achado diz a qualidade e traz a prévia,
para o Zé olhar antes de escolher (ADR 0052).

O arquivo vem da internet, então: só HTTPS e só os domínios da fonte (também nos
redirecionamentos), até 40 MB, só `.glb` versão 2 inteiro em si (sem arquivo externo) e sem
textura KTX2, que a Imersão não lê (Draco e meshopt ela abre). Ao lado do modelo fica um `.json`
com a fonte, a licença e o autor: o crédito nunca se perde.
"""

import contextlib
import json
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PASTA = Path("3d") / "baixados"  # dentro do Acervo
MAX_BYTES = 40 * 1024 * 1024
TEMPO_S = 20.0
API = "https://3dassets.dev/api/v1"
NASA_REPO = "/nasa/NASA-3D-Resources/"
NASA_ARVORE = "https://api.github.com/repos/nasa/NASA-3D-Resources/git/trees/master?recursive=1"
NASA_ARQUIVOS = "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/"
NASA_INDICE = Path("3d") / "nasa-indice.json"  # dentro do Acervo, renovado a cada semana
NASA_VALIDADE_S = 7 * 24 * 3600
# Os domínios de cada fonte; no GitHub, só o repositório da NASA.
HOSTS = frozenset(
    {"3dassets.dev", "cdn.3dassets.dev", "api.github.com", "raw.githubusercontent.com"}
)
SO_O_REPOSITORIO = {"api.github.com": "/repos" + NASA_REPO, "raw.githubusercontent.com": NASA_REPO}
# O canal com o cérebro aceita até 1 MB por mensagem (o SDK do Claude), e a imagem vai em
# base64: as prévias somadas ficam bem abaixo disso.
PREVIA_MAX = 200 * 1024
PREVIAS_MAX = 450 * 1024
SIMPLES = 3000  # triângulos: abaixo disto, um modelo low-poly
DETALHADO = 20000
VAZIAS = frozenset({"the", "a", "an", "of", "3d", "model", "nasa", "and", "with", "in"})
# Draco e meshopt a Imersão abre (ADR 0052); KTX2 pediria outro decodificador
NAO_LE = frozenset({"KHR_texture_basisu"})
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}$")
AGENTE = "Zervis/0.1 (+https://github.com/gestordescomplicaa-web/zervis)"


class ModeloErro(Exception):
    pass


@dataclass(frozen=True)
class Achado:
    id: str  # "nasa:<slug>" ou "3dassets:<slug>"
    titulo: str
    resumo: str
    licenca: str
    credito_obrigatorio: bool
    autor: str
    triangulos: int
    animado: bool
    feito_por_ia: bool
    pagina: str
    fonte: str = "3DAssets.dev"
    qualidade: str = ""  # oficial, detalhado, médio, simples
    previa: str = ""  # a imagem do modelo, para o Zé olhar antes de baixar


def _qualidade(triangulos: int, por_ia: bool) -> str:
    nivel = (
        "simples" if triangulos < SIMPLES else "detalhado" if triangulos > DETALHADO else "médio"
    )
    return nivel + (", feito por IA" if por_ia else "")


class _SoHosts(urllib.request.HTTPRedirectHandler):
    """Segue redirecionamento só para HTTPS num domínio da fonte."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _conferir_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _conferir_url(url: str) -> None:
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ""
    if p.scheme != "https" or host not in HOSTS:
        raise ModeloErro(f"endereço fora das fontes permitidas: {host or url}")
    if host in SO_O_REPOSITORIO and not p.path.startswith(SO_O_REPOSITORIO[host]):
        raise ModeloErro("no GitHub, só o repositório de modelos da NASA")


def _abrir(url: str) -> Any:
    _conferir_url(url)
    # HTTPS e domínio da fonte conferidos acima (e em cada redirecionamento, por _SoHosts)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "*/*"})  # noqa: S310
    try:
        return urllib.request.build_opener(_SoHosts()).open(pedido, timeout=TEMPO_S)
    except urllib.error.HTTPError as erro:
        raise ModeloErro(f"a fonte respondeu {erro.code}") from None
    except (urllib.error.URLError, OSError) as erro:
        raise ModeloErro(f"a fonte não respondeu ({erro})") from None


def _ler(url: str, limite: int) -> bytes:
    with _abrir(url) as r:
        tamanho = int(r.headers.get("Content-Length") or 0)
        if tamanho > limite:
            raise ModeloErro(f"arquivo grande demais ({tamanho // 1024 // 1024} MB)")
        dados: bytes = r.read(limite + 1)
    if len(dados) > limite:
        raise ModeloErro("arquivo grande demais")
    return dados


def _palavras(texto: str) -> set[str]:
    return {p.removesuffix("s") for p in re.findall(r"[a-z0-9]+", texto.lower()) if p not in VAZIAS}


def _slug(nome: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")[:118]


def indice_nasa(
    acervo: Path | None, ler: Any = _ler, agora: float | None = None
) -> list[dict[str, Any]]:
    """Os modelos `.glb` do repositório da NASA (nome, caminho, tamanho, prévia), guardados no
    Acervo por uma semana: a API do GitHub sem conta atende 60 pedidos por hora."""
    agora = time.time() if agora is None else agora
    guardado = acervo / NASA_INDICE if acervo is not None else None
    if guardado is not None and guardado.is_file():
        with contextlib.suppress(ValueError, OSError):
            dados = json.loads(guardado.read_text())
            if agora - float(dados.get("em", 0)) < NASA_VALIDADE_S:
                return list(dados["modelos"])
    try:
        arvore = json.loads(ler(NASA_ARVORE, 5 * 1024 * 1024)).get("tree") or []
    except ValueError:
        raise ModeloErro("a NASA respondeu algo que não é JSON") from None
    tamanhos = {
        x.get("path", ""): int(x.get("size") or 0) for x in arvore if x.get("type") == "blob"
    }
    modelos = []
    for caminho, tamanho in tamanhos.items():
        if not caminho.lower().endswith(".glb") or not 0 < tamanho <= MAX_BYTES:
            continue
        nome = caminho.rsplit("/", 1)[-1][:-4]
        pasta = caminho.rsplit("/", 1)[0] + "/"
        previas = [
            c
            for c, t in tamanhos.items()
            if c.startswith(pasta)
            and "/" not in c[len(pasta) :]
            and t <= PREVIA_MAX
            and c.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
        modelos.append(
            {
                "slug": _slug(nome),
                "nome": nome,
                "caminho": caminho,
                "bytes": tamanho,
                "previa": sorted(previas)[0] if previas else "",
            }
        )
    if guardado is not None:
        guardado.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        guardado.write_text(json.dumps({"em": agora, "modelos": modelos}, ensure_ascii=False))
    return modelos


def _url_nasa(caminho: str) -> str:
    return NASA_ARQUIVOS + urllib.parse.quote(caminho)


def buscar_nasa(busca: str, acervo: Path | None, ler: Any = _ler) -> list[Achado]:
    """Os modelos da NASA cujo nome tem as palavras da busca (metade delas, no mínimo)."""
    pedidas = _palavras(busca)
    if not pedidas:
        return []
    notas = []
    for m in indice_nasa(acervo, ler):
        nome = _palavras(m["nome"])
        nota = len(pedidas & nome) / len(pedidas)
        if nota >= 0.5:
            notas.append((-nota, len(m["nome"]), m))  # mais palavras certas, depois o nome curto
    if any(n[0] == -1 for n in notas):  # o nome tem todas as palavras: só esses
        notas = [n for n in notas if n[0] == -1]
    return [
        Achado(
            id=f"nasa:{m['slug']}",
            titulo=m["nome"][:80],
            resumo="Modelo oficial da NASA",
            licenca="Domínio público (NASA)",
            credito_obrigatorio=False,
            autor="NASA",
            triangulos=0,
            animado=False,
            feito_por_ia=False,
            pagina="https://github.com/nasa/NASA-3D-Resources",
            fonte="NASA",
            qualidade="oficial",
            previa=_url_nasa(m["previa"]) if m["previa"] else "",
        )
        for _, _, m in sorted(notas, key=lambda n: n[:2])
    ][:4]


def buscar_3dassets(busca: str, ler: Any = _ler) -> list[Achado]:
    url = f"{API}/assets?" + urllib.parse.urlencode({"q": busca, "limit": 24})
    try:
        corpo = json.loads(ler(url, 2 * 1024 * 1024))
    except ValueError:
        raise ModeloErro("a fonte respondeu algo que não é JSON") from None
    achados = []
    for a in corpo.get("data") or []:
        stats = a.get("stats") or {}
        slug = str(a.get("slug") or "")
        if not SLUG.match(slug) or NAO_LE & set(stats.get("extensionsUsed") or []):
            continue
        if stats.get("hasKTX2"):
            continue
        lic = a.get("license") or {}
        autor = a.get("contributor") or {}
        triangulos, por_ia = int(stats.get("triangles") or 0), bool(a.get("aiGenerated"))
        previa = str(a.get("thumbnailUrl") or "")
        achados.append(
            Achado(
                id=f"3dassets:{slug}",
                titulo=str(a.get("title") or slug)[:80],
                resumo=str(a.get("summary") or "")[:200],
                licenca=str(lic.get("name") or lic.get("slug") or "?")[:60],
                credito_obrigatorio=bool(lic.get("attributionRequired")),
                autor=str(autor.get("name") or autor.get("username") or "")[:60],
                triangulos=triangulos,
                animado=bool(stats.get("animations")),
                feito_por_ia=por_ia,
                pagina=str(a.get("url") or "")[:200],
                qualidade=_qualidade(triangulos, por_ia),
                previa=previa if previa.startswith("https://cdn.3dassets.dev/") else "",
            )
        )
    # na ordem da fonte, mas o simples e o feito por IA vão para o fim
    return sorted(achados, key=lambda x: (x.feito_por_ia, x.triangulos < SIMPLES))


def buscar(
    busca: str, limite: int = 6, ler: Any = _ler, acervo: Path | None = None
) -> list[Achado]:
    """Os modelos que a Imersão consegue mostrar: os oficiais da NASA primeiro, depois os do
    3DAssets.dev do mais caprichado ao mais simples. Uma fonte fora do ar não derruba a outra."""
    termo = " ".join(str(busca).split())[:80]
    if not termo:
        raise ModeloErro("diga o que buscar")
    achados: list[Achado] = []
    falhas = []
    for fonte in ("nasa", "3dassets"):
        # o oficial com todas as palavras no nome é a escolha: o resto só distrai (e as prévias
        # dele faziam o cérebro comentar a comparação em voz alta)
        if any(a.fonte == "NASA" and _palavras(termo) <= _palavras(a.titulo) for a in achados):
            break
        try:
            achados += (
                buscar_nasa(termo, acervo, ler) if fonte == "nasa" else buscar_3dassets(termo, ler)
            )
        except ModeloErro as erro:
            falhas.append(erro)
    if not achados and falhas:
        raise falhas[0]
    return achados[: max(1, min(limite, 12))]


def previas(achados: list[Achado], ler: Any = _ler, total: int = 6) -> list[tuple[str, bytes]]:
    """As imagens dos primeiros achados (id, bytes), para o Zé ver antes de escolher; um modelo
    oficial sem prévia pequena vai sem ela."""
    vistas: list[tuple[str, bytes]] = []
    soma = 0
    for a in achados:
        if len(vistas) >= total or not a.previa:
            continue
        with contextlib.suppress(ModeloErro):
            imagem = ler(a.previa, PREVIA_MAX)
            if soma + len(imagem) <= PREVIAS_MAX:
                vistas.append((a.id, imagem))
                soma += len(imagem)
    return vistas


def conferir_glb(dados: bytes) -> dict[str, Any]:
    """O cabeçalho e o JSON de um `.glb`: versão 2, inteiro em si, sem compressão não lida."""
    if len(dados) < 20 or dados[:4] != b"glTF":
        raise ModeloErro("não é um arquivo .glb")
    versao, total = struct.unpack("<II", dados[4:12])
    tam, tipo = struct.unpack("<I4s", dados[12:20])
    if versao != 2 or total > len(dados) or tipo != b"JSON" or 20 + tam > len(dados):
        raise ModeloErro(".glb incompleto ou de versão que a Imersão não lê")
    try:
        gltf = json.loads(dados[20 : 20 + tam])
    except ValueError:
        raise ModeloErro(".glb com JSON inválido") from None
    externos = [
        x.get("uri")
        for x in (gltf.get("buffers") or []) + (gltf.get("images") or [])
        if isinstance(x, dict) and x.get("uri") and not str(x["uri"]).startswith("data:")
    ]
    if externos:
        raise ModeloErro("o modelo depende de arquivos externos")
    if bloqueadas := NAO_LE & set(
        gltf.get("extensionsRequired") or gltf.get("extensionsUsed") or []
    ):
        raise ModeloErro(f"compressão que a Imersão não lê: {', '.join(sorted(bloqueadas))}")
    if not gltf.get("meshes"):
        raise ModeloErro("o modelo não tem malha")
    return dict(gltf)


def _gravar(acervo: Path, nome: str, dados: bytes, registro: dict[str, Any]) -> dict[str, Any]:
    pasta = acervo / PASTA
    arquivo, ficha = pasta / f"{nome}.glb", pasta / f"{nome}.json"
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = arquivo.with_suffix(".parcial")
    temporario.write_bytes(dados)
    temporario.replace(arquivo)
    ficha.write_text(json.dumps(registro, ensure_ascii=False, indent=1))
    return {**registro, "arquivo": (PASTA / f"{nome}.glb").as_posix(), "reusado": False}


def _baixar_nasa(slug: str, acervo: Path, ler: Any) -> dict[str, Any]:
    modelo = next((m for m in indice_nasa(acervo, ler) if m["slug"] == slug), None)
    if modelo is None:
        raise ModeloErro("modelo da NASA desconhecido; use o id que a busca devolveu")
    dados = ler(_url_nasa(modelo["caminho"]), MAX_BYTES)
    gltf = conferir_glb(dados)
    registro = {
        "titulo": modelo["nome"][:80],
        "fonte": "NASA",
        "pagina": "https://github.com/nasa/NASA-3D-Resources",
        "licenca": "Domínio público (NASA)",
        "licenca_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
        "credito_obrigatorio": False,
        "autor": "NASA",
        "feito_por_ia": False,
        "malhas": len(gltf.get("meshes") or []),
        "baixado_em": time.strftime("%Y-%m-%d %H:%M"),
    }
    return _gravar(acervo, f"nasa-{slug}", dados, registro)


def baixar(id_: str, acervo: Path, ler: Any = _ler) -> dict[str, Any]:
    """Baixa (ou reusa) o modelo e devolve onde ficou no Acervo, com a licença e o crédito."""
    fonte, _, slug = str(id_).partition(":")
    if fonte not in ("3dassets", "nasa") or not SLUG.match(slug):
        raise ModeloErro("modelo desconhecido; use o id que a busca devolveu")
    nome = f"nasa-{slug}" if fonte == "nasa" else slug
    pasta = acervo / PASTA
    arquivo, ficha = pasta / f"{nome}.glb", pasta / f"{nome}.json"
    relativo = (PASTA / f"{nome}.glb").as_posix()
    if arquivo.is_file() and ficha.is_file():
        return {**json.loads(ficha.read_text()), "arquivo": relativo, "reusado": True}
    if fonte == "nasa":
        return _baixar_nasa(slug, acervo, ler)
    try:
        info = json.loads(ler(f"{API}/assets/{slug}", 2 * 1024 * 1024))
    except ValueError:
        raise ModeloErro("a fonte respondeu algo que não é JSON") from None
    info = info.get("data", info) if isinstance(info, dict) else {}
    url = str(
        info.get("cdnUrl") or info.get("downloadUrl") or f"https://3dassets.dev/download/{slug}"
    )
    dados = ler(url, MAX_BYTES)
    gltf = conferir_glb(dados)
    lic, autor = info.get("license") or {}, info.get("contributor") or {}
    registro = {
        "titulo": str(info.get("title") or slug)[:80],
        "fonte": "3DAssets.dev",
        "pagina": str(info.get("url") or f"https://3dassets.dev/assets/{slug}")[:200],
        "licenca": str(lic.get("name") or lic.get("slug") or "?")[:60],
        "licenca_url": str(lic.get("url") or "")[:200],
        "credito_obrigatorio": bool(lic.get("attributionRequired")),
        "autor": str(autor.get("name") or autor.get("username") or "")[:60],
        "feito_por_ia": bool(info.get("aiGenerated")),
        "malhas": len(gltf.get("meshes") or []),
        "baixado_em": time.strftime("%Y-%m-%d %H:%M"),
    }
    return _gravar(acervo, slug, dados, registro)


def para_resposta(achados: list[Achado]) -> list[dict[str, Any]]:
    return [asdict(a) for a in achados]
