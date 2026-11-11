"""Os ajustes da abertura: `<config>/abertura.json` e a música em `<dados>/abertura/`.

A música é de quem usa e não vem no repositório: sem ela, a Imersão toca uns poucos tons
sintetizados no lugar. A cidade vazia segue o fuso (America/Fortaleza vira Fortaleza).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from zervis import lugares

ARQUIVO = lugares.CONFIG / "abertura.json"
PASTA_MUSICA = lugares.DADOS / "abertura"
# O formato pelo começo do arquivo, não pelo nome: o que não for áudio conhecido não entra.
TIPOS = {
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}
MAXIMO = 20 * 1024 * 1024


class AjusteErro(ValueError):
    """Mensagem curta, para a tela."""


@dataclass(frozen=True)
class Ajustes:
    ligada: bool = True
    cidade: str = ""


def ler(arquivo: Path | None = None) -> Ajustes:
    try:
        dados = json.loads((arquivo or ARQUIVO).read_text())
    except (OSError, ValueError):
        return Ajustes()
    if not isinstance(dados, dict):
        return Ajustes()
    return Ajustes(dados.get("ligada") is not False, str(dados.get("cidade", "")).strip()[:80])


def gravar(ajustes: Ajustes, arquivo: Path | None = None) -> None:
    destino = arquivo or ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".next")
    temporario.write_text(json.dumps(asdict(ajustes), ensure_ascii=False))
    temporario.replace(destino)


def cidade_do_fuso(zona: str) -> str:
    """`America/Sao_Paulo` -> `Sao Paulo`; um fuso sem cidade (UTC) fica vazio."""
    if "/" not in zona or zona.startswith("Etc/"):
        return ""
    return zona.rsplit("/", 1)[1].replace("_", " ")


def tipo_do_audio(corpo: bytes) -> str | None:
    """A extensão pelo começo do arquivo (MP3, Ogg, WAV ou MP4/M4A); None se não for áudio."""
    if corpo[:3] == b"ID3" or (len(corpo) > 1 and corpo[0] == 0xFF and corpo[1] & 0xE0 == 0xE0):
        return ".mp3"
    if corpo[:4] == b"OggS":
        return ".ogg"
    if corpo[:4] == b"RIFF" and corpo[8:12] == b"WAVE":
        return ".wav"
    if corpo[4:8] == b"ftyp":
        return ".m4a"
    return None


def musica(pasta: Path | None = None) -> Path | None:
    pasta = pasta or PASTA_MUSICA
    for extensao in TIPOS:
        if (arquivo := pasta / f"musica{extensao}").is_file():
            return arquivo
    return None


def guardar_musica(corpo: bytes, pasta: Path | None = None) -> Path:
    if len(corpo) > MAXIMO:
        raise AjusteErro("Arquivo maior que 20 MB.")
    extensao = tipo_do_audio(corpo)
    if extensao is None:
        raise AjusteErro("Formato não suportado. Use MP3, OGG, WAV ou M4A.")
    pasta = pasta or PASTA_MUSICA
    pasta.mkdir(parents=True, exist_ok=True)
    remover_musica(pasta)
    destino = pasta / f"musica{extensao}"
    temporario = destino.with_name(".musica.next")
    temporario.write_bytes(corpo)
    temporario.replace(destino)
    return destino


def remover_musica(pasta: Path | None = None) -> None:
    pasta = pasta or PASTA_MUSICA
    for extensao in TIPOS:
        (pasta / f"musica{extensao}").unlink(missing_ok=True)
