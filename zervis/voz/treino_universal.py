"""Treino do chamado universal ("Ei Zé" / "Hey Zé"), sem gravar a voz de ninguém (13/10/2026).

O chamado treinado com a voz de uma pessoa só acorda com ela: quem instala o Zé do zero teria de
gravar a própria voz. Aqui, como no openWakeWord (que o Zé já usa para os embeddings), os
exemplos vêm de vozes sintéticas: as do Piper em português e as de vozes com centenas de
falantes (inglês, francês), que recebem a pronúncia em português pelos fonemas. Cada exemplo
varia em velocidade, entonação, volume, eco, ruído e voz de fundo.

Negativos: palavras e frases parecidas ("pois é", "José", "café", "não é"...), fala comum,
silêncio e ruído baixo, a própria voz do Zé (Cadu) dizendo o chamado, e os sons que dispararam o
chamado de verdade sem ninguém chamar (`<dados>/ativacao/falsos`). Teste: falantes separados que
o treino não viu, os sons falsos e, se houver, chamados reais (`<dados>/ativacao/reais`).

    uv run --with scikit-learn python -m zervis.voz.treino_universal

O modelo sai em `zervis/voz/modelos/ei_ze.npz`, no repositório: é o chamado de quem instala.
As vozes do treino são baixadas uma vez em `<dados>/vozes-treino` (centenas de MB) e não vão
para o repositório.
"""

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from zervis import lugares
from zervis.voz.ativacao import Detector, Features, ModeloAtivacao
from zervis.voz.treino_ativacao import (
    CLIP,
    FALSOS,
    FIM,
    MODELOS_ONNX,
    TAXA,
    Audio,
    _carregar,
    _colocar,
    _contar,
    _embeddings,
    _janelas,
    _trecho_de_fala,
)

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOZES_DIR = lugares.DADOS / "vozes-treino"
DESTINO = Path(__file__).resolve().parent / "modelos" / "ei_ze.npz"
REAIS = lugares.DADOS / "ativacao" / "reais"
# Voz: caminho no repositório do Piper. O Cadu é a voz do próprio Zé: só entra como negativo.
VOZES = {
    "faber": "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx",
    "jeff": "pt/pt_BR/jeff/medium/pt_BR-jeff-medium.onnx",
    "edresson": "pt/pt_BR/edresson/low/pt_BR-edresson-low.onnx",
    "tugao": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx",
    "cadu": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx",
    "libritts": "en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx",
    "vctk": "en/en_GB/vctk/medium/en_GB-vctk-medium.onnx",
    "mls_fr": "fr/fr_FR/mls/medium/fr_FR-mls-medium.onnx",
}
CHAMADOS = ["Ei Zé", "Hey Zé", "Ei, Zé!", "Hey, Zé."]
PARECIDAS = [
    "Pois é", "Pois é, né", "Não é", "José", "Café", "Zé", "Né", "Até", "Ei", "Hey", "É isso",
    "Olha só", "Ei, você", "Hey Jarvis", "Fé", "Pé", "O Zé Ramalho", "Esse é o José",
    "Reis é", "Seis é", "Bem, é", "Mas é", "Já é", "É sim", "Pois é, ué", "Tem que ver isso aí",
]  # fmt: skip
FRASES = [
    "Neste vídeo eu vou mostrar como configurar o seu computador para programar melhor.",
    "Bom dia a todos, hoje vamos falar sobre inteligência artificial e o trabalho.",
    "A previsão do tempo para amanhã é de chuva forte na região metropolitana.",
    "Primeiro abra o terminal, depois instale as dependências e rode os testes.",
    "Pois é, o café de hoje ficou forte demais, né? Mas é isso mesmo.",
    "O valor entre um e o outro muda quando a gente altera o código da função.",
    "Eu acabo aprendendo muito quando alguém está tentando tomar uma decisão difícil.",
    "Olha, se você clicar ali em cima, abre a configuração e dá para mudar tudo.",
]


def _baixar(nome: str) -> Path:
    """A voz do Piper (modelo e configuração), baixada uma vez e conferida pelo md5."""
    caminho = VOZES[nome]
    destino = VOZES_DIR / Path(caminho).name
    if destino.exists() and destino.with_suffix(".onnx.json").exists():
        return destino
    VOZES_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    indice = json.load(urllib.request.urlopen(f"{BASE}/voices.json", timeout=60))  # noqa: S310
    arquivos = next(v["files"] for v in indice.values() if caminho in v["files"])
    for arquivo in (caminho, caminho + ".json"):
        print(f"baixando {arquivo}", flush=True)
        endereco = f"{BASE}/{urllib.parse.quote(arquivo)}"
        dados = urllib.request.urlopen(endereco, timeout=600).read()  # noqa: S310
        if hashlib.md5(dados).hexdigest() != arquivos[arquivo]["md5_digest"]:  # noqa: S324
            raise RuntimeError(f"{arquivo}: arquivo diferente do publicado")
        (VOZES_DIR / Path(arquivo).name).write_bytes(dados)
    return destino


class Vozes:
    def __init__(self, nomes: list[str]) -> None:
        from piper import PiperVoice

        self.vozes = {n: PiperVoice.load(str(_baixar(n))) for n in nomes}
        self.pt = self.vozes.get("faber") or next(iter(self.vozes.values()))

    def falantes(self, nome: str) -> int:
        return int(self.vozes[nome].config.num_speakers)

    def fonemas(self, texto: str) -> list[str]:
        """A pronúncia em português, usada também pelas vozes de outros idiomas."""
        return [f for frase in self.pt.phonemize(texto) for f in frase]

    def dizer(self, nome: str, texto: str, rng: np.random.Generator, falante: int = 0) -> Audio:
        import scipy.signal as sinal  # type: ignore[import-untyped,import-not-found,unused-ignore]
        from piper import SynthesisConfig

        voz = self.vozes[nome]
        conhecidos = voz.config.phoneme_id_map
        fonemas = [f for f in self.fonemas(texto) if f in conhecidos]
        config = SynthesisConfig(
            speaker_id=falante if self.falantes(nome) > 1 else None,
            length_scale=float(rng.uniform(0.75, 1.35)),
            noise_scale=float(rng.uniform(0.4, 0.9)),
            noise_w_scale=float(rng.uniform(0.5, 1.0)),
        )
        bruto = voz.phoneme_ids_to_audio(voz.phonemes_to_ids(fonemas), config)
        audio = np.asarray(bruto[0] if isinstance(bruto, tuple) else bruto, np.float32)
        taxa = int(voz.config.sample_rate)
        x = sinal.resample_poly(audio, TAXA, taxa).astype(np.float32)
        x = x / (np.abs(x).max() + 1e-9)
        if trecho := _trecho_de_fala(x * 32767):
            x = x[trecho[0] : trecho[1]]
        saida: Audio = x * 32767 * float(rng.uniform(0.15, 0.8))
        return saida


def _eco(x: Audio, rng: np.random.Generator) -> Audio:
    """Uma sala: resposta ao impulso de ruído com decaimento exponencial (0,1 a 0,6 s)."""
    rt60 = rng.uniform(0.1, 0.6)
    n = int(TAXA * rt60)
    ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir[0] = 1.0
    ir /= np.abs(ir).sum() ** 0.5 * 4
    y = np.convolve(x, ir)[: len(x)]
    saida: Audio = (y * (np.abs(x).max() / (np.abs(y).max() + 1e-9))).astype(np.float32)
    return saida


def _filtro(x: Audio, rng: np.random.Generator) -> Audio:
    """Microfone barato ou fone: corta graves e agudos."""
    import scipy.signal as sinal  # type: ignore[import-untyped,import-not-found,unused-ignore]

    sos = sinal.butter(
        4, [rng.uniform(80, 300), rng.uniform(3200, 7000)], "bandpass", fs=TAXA, output="sos"
    )
    saida: Audio = sinal.sosfilt(sos, x).astype(np.float32)
    return saida


def _variar(x: Audio, rng: np.random.Generator, fundo: list[Audio]) -> Audio:
    if rng.random() < 0.5:
        x = _eco(x, rng)
    if rng.random() < 0.35:
        x = _filtro(x, rng)
    return x


def _com_fundo(clip: Audio, rng: np.random.Generator, fundo: list[Audio]) -> Audio:
    """Ruído branco e, às vezes, fala de fundo bem mais baixa que o chamado."""
    nivel = np.sqrt(np.mean(clip**2)) + 1e-9
    if rng.random() < 0.6:
        clip = clip + rng.standard_normal(len(clip)).astype(np.float32) * nivel * 10 ** (
            -rng.uniform(15, 40) / 20
        )
    if fundo and rng.random() < 0.35:
        a = fundo[int(rng.integers(len(fundo)))]
        if len(a) > CLIP:
            i = int(rng.integers(0, len(a) - CLIP))
            trecho = a[i : i + CLIP]
            clip = clip + trecho / (np.sqrt(np.mean(trecho**2)) + 1e-9) * nivel * 10 ** (
                -rng.uniform(12, 30) / 20
            )
    return clip.astype(np.float32)


def _amostras(
    vozes: Vozes,
    nome: str,
    textos: list[str],
    n: int,
    rng: np.random.Generator,
    falantes: list[int],
) -> list[Audio]:
    saida = []
    for _ in range(n):
        texto = textos[int(rng.integers(len(textos)))]
        falante = falantes[int(rng.integers(len(falantes)))] if falantes else 0
        saida.append(vozes.dizer(nome, texto, rng, falante))
    return saida


def treinar(destino: Path = DESTINO, escala: float = 1.0) -> dict[str, Any]:
    from sklearn.neural_network import MLPClassifier  # type: ignore[import-not-found,unused-ignore]

    rng = np.random.default_rng(13)
    vozes = Vozes(list(VOZES))
    inicio = time.monotonic()
    # Falantes separados para o teste: o treino não os vê.
    separar = {"libritts": 60, "vctk": 10, "mls_fr": 10}
    treino_f: dict[str, list[int]] = {}
    teste_f: dict[str, list[int]] = {}
    for nome in vozes.vozes:
        ids = list(rng.permutation(vozes.falantes(nome)))
        k = separar.get(nome, 0)
        teste_f[nome], treino_f[nome] = [int(i) for i in ids[:k]], [int(i) for i in ids[k:]]

    def quantos(n: int) -> int:
        return max(1, int(n * escala))

    # Positivos: sem o Cadu. Negativos: todas as vozes.
    positivas = {"faber": 260, "jeff": 260, "edresson": 200, "tugao": 160,
                 "libritts": 2400, "vctk": 500, "mls_fr": 400}  # fmt: skip
    chamados: list[Audio] = []
    for nome, n in positivas.items():
        chamados += _amostras(vozes, nome, CHAMADOS, quantos(n), rng, treino_f[nome])
    print(f"chamados sintetizados: {len(chamados)} ({time.monotonic() - inicio:.0f} s)", flush=True)
    parecidas: list[Audio] = []
    frases: list[Audio] = []
    for nome in vozes.vozes:
        peso = 3 if nome in ("libritts", "vctk", "mls_fr") else 1
        parecidas += _amostras(vozes, nome, PARECIDAS, quantos(220 * peso), rng, treino_f[nome])
        frases += _amostras(vozes, nome, FRASES, quantos(12 * peso), rng, treino_f[nome])
    cadu_chamando = _amostras(vozes, "cadu", CHAMADOS, quantos(200), rng, [])
    print(f"negativos sintetizados ({time.monotonic() - inicio:.0f} s)", flush=True)

    pos: list[Audio] = []
    neg: list[Audio] = []
    for x in chamados:
        y = _variar(x, rng, frases)
        pos.append(_com_fundo(_colocar(y, FIM + int(rng.integers(-4800, 1600))), rng, frases))
        for fracao in (0.4,):  # só o "Ei" não acorda
            neg.append(_com_fundo(_colocar(y[: int(len(y) * fracao)], FIM), rng, frases))
    for x in [*parecidas, *cadu_chamando]:
        y = _variar(x, rng, frases)
        neg.append(_com_fundo(_colocar(y, FIM + int(rng.integers(-3200, 1600))), rng, frases))
    for x in frases:
        neg.extend(_janelas(_variar(x, rng, frases), int(0.25 * TAXA)))
    for nivel in (0.0, 1e-5, 1e-4, 1e-3, 3e-3, 1e-2):
        neg.extend(
            (rng.standard_normal(CLIP) * nivel * 32767).astype(np.float32) for _ in range(60)
        )
    falsos = [_carregar(p) for p in sorted(FALSOS.glob("*.wav"))] if FALSOS.is_dir() else []
    for x in falsos:
        for _ in range(12):
            neg.append(
                _colocar(x[-CLIP:] * rng.uniform(0.6, 1.4), FIM + int(rng.integers(-1600, 1600)))
            )

    features = Features(MODELOS_ONNX / "melspectrogram.onnx", MODELOS_ONNX / "embedding_model.onnx")
    print(f"embeddings: {len(pos)} positivos, {len(neg)} negativos", flush=True)
    X = np.concatenate([_embeddings(pos, features), _embeddings(neg, features)])
    y = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    print(f"embeddings prontos ({time.monotonic() - inicio:.0f} s)", flush=True)
    planos = X.reshape(len(X), -1)
    media, desvio = planos.mean(0), planos.std(0) + 1e-6
    mlp = MLPClassifier(
        hidden_layer_sizes=(96,), alpha=1e-3, max_iter=400, early_stopping=True, random_state=13
    )
    mlp.fit((planos - media) / desvio, y)
    profundidade = len(mlp.coefs_)
    pesos = {f"W{i}": mlp.coefs_[i].astype(np.float32) for i in range(profundidade)} | {
        f"b{i}": mlp.intercepts_[i].astype(np.float32) for i in range(profundidade)
    }

    # Teste: falantes que o treino não viu, sons falsos reais e chamados reais (se houver).
    silencio = np.zeros(TAXA // 2, np.float32)
    teste_pos = []
    for nome in separar:
        teste_pos += _amostras(vozes, nome, CHAMADOS, 60, rng, teste_f[nome])
    teste_pos = [_com_fundo(_colocar(_variar(x, rng, frases), FIM), rng, frases) for x in teste_pos]
    teste_neg = []
    for nome in separar:
        teste_neg += _amostras(vozes, nome, PARECIDAS, 80, rng, teste_f[nome])
    fala_teste = []
    for nome in separar:
        fala_teste += _amostras(vozes, nome, FRASES, 10, rng, teste_f[nome])
    reais = [_carregar(p) for p in sorted(REAIS.glob("*.wav"))] if REAIS.is_dir() else []

    destino.parent.mkdir(parents=True, exist_ok=True)
    relatorio: dict[str, Any] = {
        "treinado_em": time.strftime("%Y-%m-%d %H:%M"),
        "positivos": len(pos),
        "negativos": len(neg),
        "teste": {"chamados": len(teste_pos), "parecidas": len(teste_neg), "reais": len(reais)},
    }
    melhor: tuple[float, float] | None = None
    for limiar in (0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99):
        np.savez(destino, depth=profundidade, mean=media, std=desvio, threshold=limiar, **pesos)
        detector = Detector(ModeloAtivacao(destino), features)
        acerto = np.mean(
            [_contar(detector, np.concatenate([silencio, x, silencio])) > 0 for x in teste_pos]
        )
        reais_ok = (
            np.mean([_contar(detector, np.concatenate([silencio, x, silencio])) > 0 for x in reais])
            if reais
            else None
        )
        f_parecidas = sum(
            _contar(detector, np.concatenate([silencio, x, silencio])) > 0 for x in teste_neg
        )
        f_fala = sum(_contar(detector, np.concatenate([silencio, x, silencio])) for x in fala_teste)
        f_reais = sum(_contar(detector, x) for x in falsos)
        falsos_total = int(f_parecidas + f_fala + f_reais)
        relatorio[f"limiar_{limiar}"] = {
            "acerto": round(float(acerto), 3),
            "reais": None if reais_ok is None else round(float(reais_ok), 2),
            "falsos_parecidas": int(f_parecidas),
            "falsos_fala": int(f_fala),
            "falsos_reais": int(f_reais),
        }
        print(limiar, relatorio[f"limiar_{limiar}"], flush=True)
        # Poucos falsos em centenas de parecidas, nenhum nos sons reais; depois, o maior acerto.
        poucos = f_reais == 0 and falsos_total <= max(2, len(teste_neg) // 100)
        if poucos and (melhor is None or acerto >= melhor[1]):
            melhor = (limiar, float(acerto))
    escolhido = melhor[0] if melhor else 0.99
    np.savez(destino, depth=profundidade, mean=media, std=desvio, threshold=escolhido, **pesos)
    relatorio["limiar_escolhido"] = escolhido
    relatorio["segundos"] = round(time.monotonic() - inicio)
    destino.with_suffix(".json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1))
    return relatorio


TESTE = lugares.DADOS / "ativacao" / "teste"
FRASES_TESTE = ["Pois é", "Não é", "José", "Café", "Pois é, né", "É isso", "Olha só", "Zé", "Ei",
                "Mas é"]  # fmt: skip


def gravar_teste(vezes: int = 10) -> Path:
    """Um minuto guiado pela voz do Zé: chamados e frases parecidas de uma pessoa real, só para
    medir o modelo (não entram no treino)."""
    from zervis.transporte.local import Captura
    from zervis.voz.treino_ativacao import _bip, _falar, _gravar, _salvar

    sessao = TESTE / time.strftime("%Y%m%d-%H%M%S")
    captura = Captura(tamanho_fila=2000)
    captura.abrir()
    try:
        _falar("Teste do chamado. Depois de cada bipe, diga a frase que eu pedir, do seu jeito.")
        for i in range(vezes):
            frase = ("Ei Zé", "Hey Zé")[i % 2]
            _falar(f"{frase}.")
            _bip()
            _salvar(sessao / "chamado" / f"{i:02d}.wav", _gravar(captura, 2.5))
            print(f"chamado {i + 1}/{vezes}", flush=True)
        _falar("Agora frases que não podem me acordar.")
        for i, frase in enumerate(FRASES_TESTE):
            _falar(f"{frase}.")
            _bip()
            _salvar(sessao / "parecida" / f"{i:02d}.wav", _gravar(captura, 2.0))
            print(f"parecida {i + 1}/{len(FRASES_TESTE)}", flush=True)
        _falar("Pronto, obrigado.")
    finally:
        captura.fechar()
    return sessao


if __name__ == "__main__":
    if sys.argv[1:2] == ["gravar-teste"]:
        print(gravar_teste())
        raise SystemExit
    escala = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    print(json.dumps(treinar(escala=escala), ensure_ascii=False, indent=1))
