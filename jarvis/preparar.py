"""O que o Zé precisa baixar na primeira vez (docs/plano-distribuicao.md, 09/10/2026).

Os modelos de som ficam fora do repositório. Na instalação nova, o Zé baixa o que falta das
fontes oficiais e confere a impressão digital (SHA-256) de cada arquivo antes de usar: o mesmo
arquivo que roda na máquina do usuário desde 06/10/2026, sem surpresa. Arquivo que não bate é
apagado e o Zé avisa, sem subir com um modelo errado.

    python -m jarvis.preparar        # baixa o que falta e mostra o que há
"""

import hashlib
import logging
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from jarvis import lugares

log = logging.getLogger(__name__)
OWW = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"


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


def baixar(m: Modelo, pasta: Path, abrir: object = urllib.request.urlopen) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = pasta / (m.nome + ".baixando")
    try:
        with abrir(m.url, timeout=120) as resp, temporario.open("wb") as f:  # type: ignore[operator]
            while bloco := resp.read(1 << 20):
                f.write(bloco)
        if (achado := _sha256(temporario)) != m.sha256:
            raise PrepararErro(f"{m.nome}: impressão digital não confere ({achado[:12]}…)")
        temporario.replace(pasta / m.nome)
    finally:
        temporario.unlink(missing_ok=True)


def garantir(pasta: Path | None = None) -> list[str]:
    """Baixa o que falta; devolve os nomes baixados. Erro claro se não der."""
    pasta = pasta or lugares.DADOS / "modelos"
    baixados = []
    for m in faltando(pasta):
        log.info("baixando %s (%s)", m.nome, m.para_que)
        try:
            baixar(m, pasta)
        except (OSError, PrepararErro) as erro:
            raise PrepararErro(f"não consegui baixar {m.nome}: {erro}") from None
        baixados.append(m.nome)
    return baixados


def main() -> int:
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
