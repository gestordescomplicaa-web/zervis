"""A narração de um vídeo de `docs/video` com a voz do Zé (a escolhida no painel).

Uso: narrar.py <roteiro.json> <pasta de saída>

Usa `zervis.video.narracao` (o mesmo da função de Marketing). O roteiro é {"falas": [...]}. Saem
`narracao.wav` (48 kHz, mono) e `narracao.js` (`window.NARRACAO`: o início e a duração de cada
fala, a duração do vídeo e o volume da voz por quadro), que as páginas daqui leem.
"""

import json
import sys
from pathlib import Path

from zervis.video import narracao


def main(arquivo: Path, saida: Path) -> None:
    falas: list[str] = json.loads(arquivo.read_text())["falas"]
    n = narracao.narrar(falas, narracao.sintetizador(_motor()))
    saida.mkdir(parents=True, exist_ok=True)
    narracao.gravar_wav(n.voz, saida / "narracao.wav")
    dados = {"duracao": n.duracao, "fps": narracao.FPS, "falas": n.falas, "volume": n.volume}
    (saida / "narracao.js").write_text(
        f"window.NARRACAO = {json.dumps(dados, ensure_ascii=False)};\n"
    )
    for f in n.falas:
        print(f"{f['inicio']:5.1f}s +{f['dur']:4.1f}s  {f['texto']}")
    print(f"duração do vídeo: {n.duracao}s")


def _motor() -> object:
    from zervis.voz import nuvem

    return nuvem.Motor()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
