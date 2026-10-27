"""O que o Zé precisa baixar na primeira vez: os modelos de som e a voz.

Os modelos ficam fora do repositório (a voz sozinha tem 63 MB). Na instalação nova, o Zé baixa
o que falta das fontes oficiais e confere a impressão digital (SHA-256) de cada arquivo antes de
usar: o mesmo arquivo testado pelo projeto, sem surpresa. Arquivo que não bate é apagado e o Zé
avisa, sem subir com um modelo errado.

Cada modelo tem mais de uma fonte: o espelho do próprio projeto (uma release no GitHub, em
`ESPELHO` ou em `ZE_MODELOS_URL`) e, se ele faltar ou falhar, a fonte original. Como a impressão
digital é fixa no código, o espelho não precisa ser de confiança: um arquivo trocado é recusado e
a fonte seguinte é tentada (ADR 0034, ponto 13).

    python -m zervis.preparar        # baixa o que falta e mostra o que há
"""

import hashlib
import logging
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from zervis import lugares

log = logging.getLogger(__name__)
# A release do projeto com os modelos (mesmos nomes de arquivo). Vazio até existir uma pública:
# `deploy/publicar-modelos.sh` publica, e o endereço entra aqui. `ZE_MODELOS_URL` tem a vez, para
# quem hospeda os modelos por conta própria (rede sem acesso à internet, por exemplo).
ESPELHO = "https://github.com/gestordescomplicaa-web/zervis-modelos/releases/download/modelos-1"
OWW = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
# Revisão fixa do repositório oficial de vozes do Piper (rhasspy/piper-voices).
VOZES = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/"
    "39ab474be869e9181350af6a65e4953eef67aaa0/pt/pt_BR/cadu/medium"
)


@dataclass(frozen=True)
class Modelo:
    nome: str
    url: str
    sha256: str
    para_que: str


MODELOS = (
    Modelo(
        "silero_vad.onnx",
        f"{OWW}/silero_vad.onnx",
        "a35ebf52fd3ce5f1469b2a36158dba761bc47b973ea3382b3186ca15b1f5af28",
        "detector de voz (Silero, MIT)",
    ),
    Modelo(
        "melspectrogram.onnx",
        f"{OWW}/melspectrogram.onnx",
        "ba2b0e0f8b7b875369a2c89cb13360ff53bac436f2895cced9f479fa65eb176f",
        "palavra de ativação, parte 1 (openWakeWord, Apache-2.0)",
    ),
    Modelo(
        "embedding_model.onnx",
        f"{OWW}/embedding_model.onnx",
        "70d164290c1d095d1d4ee149bc5e00543250a7316b59f31d056cff7bd3075c1f",
        "palavra de ativação, parte 2 (openWakeWord, Apache-2.0)",
    ),
    Modelo(
        "pt_BR-cadu-medium.onnx",
        f"{VOZES}/pt_BR-cadu-medium.onnx",
        "765f0809a6ea9035d4a6d0d008dbf8876e68b2dd32029312672fa8f405bdb535",
        "a voz do Zé, Cadu (Piper, CC0)",
    ),
    Modelo(
        "pt_BR-cadu-medium.onnx.json",
        f"{VOZES}/pt_BR-cadu-medium.onnx.json",
        "5fe03aa3d4901880554905b12075713cd552598c8a350455a1ec73f8b4e6be19",
        "a voz do Zé, configuração",
    ),
    Modelo(
        "smart-turn-v3.2-cpu.onnx",
        "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/smart-turn-v3.2-cpu.onnx",
        "2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f",
        "fim de fala pela entonação (Smart Turn, BSD-2)",
    ),
)


class PrepararErro(RuntimeError):
    pass


def _sha256(arquivo: Path) -> str:
    h = hashlib.sha256()
    with arquivo.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def faltando(pasta: Path) -> list[Modelo]:
    return [m for m in MODELOS if not (pasta / m.nome).is_file()]


def fontes(m: Modelo, espelho: str = "") -> list[str]:
    """Onde buscar o arquivo, em ordem: o espelho (se houver) e a fonte original."""
    base = espelho.rstrip("/")
    return [*([f"{base}/{m.nome}"] if base else []), m.url]


def _baixar_de(url: str, m: Modelo, pasta: Path, abrir: object) -> None:
    temporario = pasta / (m.nome + ".baixando")
    try:
        with abrir(url, timeout=120) as resp, temporario.open("wb") as f:  # type: ignore[operator]
            while bloco := resp.read(1 << 20):
                f.write(bloco)
        if (achado := _sha256(temporario)) != m.sha256:
            raise PrepararErro(f"{m.nome}: impressão digital não confere ({achado[:12]}…)")
        temporario.replace(pasta / m.nome)
    finally:
        temporario.unlink(missing_ok=True)


def baixar(m: Modelo, pasta: Path, abrir: object = None, espelho: str = "") -> None:
    """Baixa `m` da primeira fonte que der certo; o erro é o da última, se nenhuma der."""
    abrir = abrir or urllib.request.urlopen  # na hora da chamada: um padrão fixo não se substitui
    pasta.mkdir(parents=True, exist_ok=True)
    erro: Exception | None = None
    for url in fontes(m, espelho):
        try:
            _baixar_de(url, m, pasta, abrir)
            return
        except (OSError, PrepararErro) as falha:
            erro = falha
            log.warning("%s: %s não serviu (%s)", m.nome, url.split("/")[2], falha)
    assert erro is not None  # noqa: S101 (fontes() sempre devolve ao menos a original)
    raise erro


def garantir(pasta: Path | None = None) -> list[str]:
    """Baixa o que falta; devolve os nomes baixados. Erro claro se não der."""
    pasta = pasta or lugares.DADOS / "modelos"
    espelho = os.environ.get("ZE_MODELOS_URL", ESPELHO)
    baixados = []
    for m in faltando(pasta):
        log.info("baixando %s (%s)", m.nome, m.para_que)
        try:
            baixar(m, pasta, espelho=espelho)
        except (OSError, PrepararErro) as erro:
            raise PrepararErro(f"não consegui baixar {m.nome}: {erro}") from None
        baixados.append(m.nome)
    return baixados


def manifesto() -> str:
    """As impressões digitais fixas, no formato do `sha256sum -c`: quem publica os modelos confere
    os arquivos contra elas antes de subir (`deploy/publicar-modelos.sh`)."""
    return "".join(f"{m.sha256}  {m.nome}\n" for m in MODELOS)


def main(argv: list[str] | None = None) -> int:
    if (sys.argv[1:] if argv is None else argv) == ["--manifesto"]:
        print(manifesto(), end="")
        return 0
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    pasta = lugares.DADOS / "modelos"
    try:
        garantir(pasta)
    except PrepararErro as erro:
        print(f"Falhou: {erro}", file=sys.stderr)
        return 1
    for m in MODELOS:
        print(f"ok  {m.nome:28} {m.para_que}")
    print(f"Pasta: {pasta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
