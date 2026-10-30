"""Modelos 3D prontos e livres para o Acervo (ADR 0049): buscar e baixar, com travas.

"Mostra um cavalo em 3D" pede um cavalo de verdade, não um feito de esferas (ADR 0048). Os
acervos livres têm milhares de modelos `.glb`; o Zé busca, baixa um para `Acervo/3d/baixados/` e o
mostra no cartão holográfico que a pinça gira. Primeira fonte: o 3DAssets.dev (CC0, busca e
download sem chave).

O arquivo vem da internet, então: só HTTPS e só os domínios da fonte (também nos
redirecionamentos), até 40 MB, só `.glb` versão 2 inteiro em si (sem arquivo externo) e sem
compressão que a Imersão não lê (Draco, meshopt, KTX2). Ao lado do modelo fica um `.json` com a
fonte, a licença e o autor: o crédito nunca se perde.
"""

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
HOSTS = frozenset({"3dassets.dev", "cdn.3dassets.dev"})
NAO_LE = frozenset({"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"})
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}$")
AGENTE = "Zervis/0.1 (+https://github.com/gestordescomplicaa-web/zervis)"


class ModeloErro(Exception):
    pass


@dataclass(frozen=True)
class Achado:
    id: str  # "3dassets:<slug>"
    titulo: str
    resumo: str
    licenca: str
    credito_obrigatorio: bool
    autor: str
    triangulos: int
    animado: bool
    feito_por_ia: bool
    pagina: str


class _SoHosts(urllib.request.HTTPRedirectHandler):
    """Segue redirecionamento só para HTTPS num domínio da fonte."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _conferir_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _conferir_url(url: str) -> None:
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or (p.hostname or "") not in HOSTS:
        raise ModeloErro(f"endereço fora das fontes permitidas: {p.hostname or url}")


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


def buscar(busca: str, limite: int = 6, ler: Any = _ler) -> list[Achado]:
    """Os modelos que a Imersão consegue mostrar, na ordem de relevância da fonte."""
    termo = " ".join(str(busca).split())[:80]
    if not termo:
        raise ModeloErro("diga o que buscar")
    url = f"{API}/assets?" + urllib.parse.urlencode({"q": termo, "limit": 24})
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
        if stats.get("hasDraco") or stats.get("hasMeshopt") or stats.get("hasKTX2"):
            continue
        lic = a.get("license") or {}
        autor = a.get("contributor") or {}
        achados.append(
            Achado(
                id=f"3dassets:{slug}",
                titulo=str(a.get("title") or slug)[:80],
                resumo=str(a.get("summary") or "")[:200],
                licenca=str(lic.get("name") or lic.get("slug") or "?")[:60],
                credito_obrigatorio=bool(lic.get("attributionRequired")),
                autor=str(autor.get("name") or autor.get("username") or "")[:60],
                triangulos=int(stats.get("triangles") or 0),
                animado=bool(stats.get("animations")),
                feito_por_ia=bool(a.get("aiGenerated")),
                pagina=str(a.get("url") or "")[:200],
            )
        )
    return achados[: max(1, min(limite, 12))]


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


def baixar(id_: str, acervo: Path, ler: Any = _ler) -> dict[str, Any]:
    """Baixa (ou reusa) o modelo e devolve onde ficou no Acervo, com a licença e o crédito."""
    fonte, _, slug = str(id_).partition(":")
    if fonte != "3dassets" or not SLUG.match(slug):
        raise ModeloErro("modelo desconhecido; use o id que a busca devolveu")
    pasta = acervo / PASTA
    arquivo, ficha = pasta / f"{slug}.glb", pasta / f"{slug}.json"
    relativo = (PASTA / f"{slug}.glb").as_posix()
    if arquivo.is_file() and ficha.is_file():
        return {**json.loads(ficha.read_text()), "arquivo": relativo, "reusado": True}
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
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = arquivo.with_suffix(".parcial")
    temporario.write_bytes(dados)
    temporario.replace(arquivo)
    ficha.write_text(json.dumps(registro, ensure_ascii=False, indent=1))
    return {**registro, "arquivo": relativo, "reusado": False}


def para_resposta(achados: list[Achado]) -> list[dict[str, Any]]:
    return [asdict(a) for a in achados]
