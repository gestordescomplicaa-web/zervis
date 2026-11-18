"""A narração de um vídeo com a voz do Zé: a escolhida no painel (Fish Audio, ElevenLabs ou o Cadu).

Uso: narrar.py <roteiro.json> <pasta de saída>

O roteiro é {"falas": ["Oi, eu sou o Zé.", ...]}. Cada fala é sintetizada à parte, sem o silêncio
das pontas, e começa numa batida da música (120 BPM): o corte da cena cai junto. Saem:
- `narracao.wav` (48 kHz, mono), a voz já no lugar;
- `narracao.js` (`window.NARRACAO`), com o início e a duração de cada fala, a duração do vídeo e
  o volume da voz por quadro, para a página desenhar a onda e as legendas no tempo certo.

Usa a chave e a voz que o Zé já usa (`<config>/voz.json` e a chave do provedor); nada é impresso.
"""

import json
import math
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np

from zervis.voz import nuvem

TAXA = 48000
FPS = 30
BATIDA = 0.5  # 120 BPM
INICIO_S = 0.5  # a primeira fala entra na segunda batida
PAUSA_S = 0.3  # o respiro mínimo entre duas falas
CAUDA_S = 2.0  # o fecho segura depois da última fala
LIMIAR = 0.015  # abaixo disto, nas pontas, é silêncio


def sintetizar(motor: nuvem.Motor, texto: str) -> tuple[int, bytes]:
    """PCM 16 bits mono da fala, pelo provedor ativo; sem provedor, pela voz local (Cadu)."""
    provedor = motor.ativo
    if provedor is None:
        taxa, fluxo = motor.local.abrir_fluxo(texto)
        return int(taxa), b"".join(iter(lambda: fluxo.read1(65536), b""))
    p = motor.provedores[provedor]
    voz = motor.escolha.voz(provedor)
    caminho, corpo, cabecalhos = p.pedido(
        texto, voz["id"], voz.get("modelo", ""), motor.chaves[provedor] or ""
    )
    if "latency" in corpo:
        corpo["latency"] = "normal"  # gravação: a qualidade vale mais que a pressa
    conexao = nuvem.conexao(p.ENDERECO, 90)
    try:
        resposta = nuvem.pedir(conexao, "POST", caminho, cabecalhos, p.motivo, corpo)
        return int(p.TAXA), resposta.read()
    finally:
        conexao.close()


def para_48k(pcm: bytes, taxa: int) -> np.ndarray:
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768
    if taxa != TAXA:
        t = np.arange(round(len(x) * TAXA / taxa)) * taxa / TAXA
        x = np.interp(t, np.arange(len(x)), x)
    forte = np.flatnonzero(np.abs(x) > LIMIAR)
    if len(forte) == 0:
        return x[:0]
    margem = int(0.03 * TAXA)
    return x[max(0, forte[0] - margem) : forte[-1] + margem]


def envelope(voz: np.ndarray, quadros: int) -> list[float]:
    passo = TAXA // FPS
    rms = [
        float(np.sqrt(np.mean(voz[i * passo : (i + 1) * passo] ** 2) + 1e-12))
        for i in range(quadros)
    ]
    topo = float(np.percentile([r for r in rms if r > 1e-4] or [1.0], 95))
    return [round(min(1.0, r / topo), 3) for r in rms]


def main(roteiro: Path, saida: Path) -> None:
    falas: list[str] = json.loads(roteiro.read_text())["falas"]
    motor = nuvem.Motor()
    print(f"voz: {motor.titulo(motor.ativo) if motor.ativo else 'Cadu (local)'}")
    pedacos: list[tuple[float, np.ndarray]] = []
    marcas: list[dict[str, Any]] = []
    t = INICIO_S
    for texto in falas:
        taxa, pcm = sintetizar(motor, texto)
        x = para_48k(pcm, taxa)
        inicio = math.ceil(t / BATIDA - 1e-9) * BATIDA
        dur = len(x) / TAXA
        pedacos.append((inicio, x))
        marcas.append({"texto": texto, "inicio": inicio, "dur": round(dur, 3)})
        print(f"{inicio:5.1f}s +{dur:4.1f}s  {texto}")
        t = inicio + dur + PAUSA_S
    duracao = math.ceil((t - PAUSA_S + CAUDA_S) / BATIDA) * BATIDA
    voz = np.zeros(int(duracao * TAXA))
    for inicio, x in pedacos:
        i = int(inicio * TAXA)
        voz[i : i + len(x)] += x[: len(voz) - i]
    saida.mkdir(parents=True, exist_ok=True)
    with wave.open(str(saida / "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes((np.clip(voz, -1, 1) * 32767).astype("<i2").tobytes())
    dados = {
        "duracao": duracao,
        "fps": FPS,
        "falas": marcas,
        "volume": envelope(voz, round(duracao * FPS)),
    }
    (saida / "narracao.js").write_text(
        f"window.NARRACAO = {json.dumps(dados, ensure_ascii=False)};\n"
    )
    print(f"duração do vídeo: {duracao}s")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
