"""Treino do chamado pessoal ("Ei Zé" / "Hey Zé"), com a voz do usuário (08/10/2026).

Opcional desde 13/10/2026: o padrão é o chamado universal (`treino_universal.py`), que funciona
para qualquer pessoa. Este é o ajuste fino de quem quer mais precisão com a própria voz; o modelo
sai em `<dados>/ativacao/ei_ze.npz` e vale quando `ativacao.modelo` aponta para ele.

Portado do `train_wake.py` do Zé antigo (VIBE-CODING, o "Hey Orca"), agora sobre os mesmos
embeddings em fluxo do `ativacao.py`: o treino vê exatamente o que o detector vê ao vivo.

    uv run python -m zervis.voz.treino_ativacao gravar      # guiado por voz, uns 4 minutos
    uv run --with scikit-learn python -m zervis.voz.treino_ativacao treinar

`gravar` fala cada instrução pelo Piper, toca o bipe e grava pelo mesmo microfone do Zé
(`omarchy_mic_fx`): 30 chamados alternando "Ei Zé" e "Hey Zé", palavras parecidas que não podem
acordar ("café", "José", "pois é"...) e 40 s de fala normal. `treinar` gera o MLP e escolhe o
limiar pelo áudio separado para teste: todos os chamados reconhecidos e nenhum disparo falso,
com a maior margem. Negativos também vêm do Cadu (a voz do próprio Zé) dizendo o chamado
e frases parecidas: só a voz do usuário acorda. O scikit-learn só é usado aqui, no treino.
"""

import json
import queue
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from zervis import lugares
from zervis.transporte.local import Captura, comando_reprodutor
from zervis.voz import piper
from zervis.voz.ativacao import QUADRO, Detector, Features, ModeloAtivacao

TAXA = 16000
CLIP = int(2.0 * TAXA)
FIM = int(1.8 * TAXA)  # o chamado termina 0,2 s antes do fim da janela
PASTA = lugares.DADOS / "ativacao"
MODELO = PASTA / "ei_ze.npz"
MODELOS_ONNX = lugares.DADOS / "modelos"
CHAMADOS = ["Ei Zé", "Hey Zé"]
PARECIDAS = [
    "Zé", "José", "Café", "Pois é", "Ei, você", "Né", "Até", "Ei", "Hey", "Jarvis",
    "Pois é, né", "É isso", "Não é", "Olha só",
]  # fmt: skip
# Sons que dispararam o chamado sem ninguém chamar (o Zé guarda os últimos em
# <estado>/chamados): conferidos e copiados para cá, entram no treino como negativos.
FALSOS = PASTA / "falsos"
DIFICEIS = [
    "Zé.", "Ei.", "Hey.", "José.", "Café.", "Pois é.", "Né?", "Até mais.", "É sim.", "Ei, você.",
    "Hey Jarvis.", "Hey Orca.", "Ei, Orca.", "O Zé Ramalho.", "Esse é o José.", "Fé.", "Pé.",
    # O Cadu dizendo o próprio chamado: a voz do Zé nunca pode acordá-lo.
    "Ei Zé.", "Hey Zé.", "Ei, Zé!", "Hey, Zé?", "Ei Zé, tudo bem?", "Ô Zé.",
    "Hey Zé, abre o projeto.",
]  # fmt: skip
GENERICAS = [
    "Neste vídeo eu vou mostrar como configurar o seu computador para programar melhor.",
    "Bom dia a todos, hoje vamos falar sobre inteligência artificial e o trabalho.",
    "A previsão do tempo para amanhã é de chuva forte na região metropolitana.",
    "Primeiro abra o terminal, depois instale as dependências e rode os testes.",
    "Ei, olha isso aqui, ficou muito bom o resultado final da impressão.",
    "Pois é, o café de hoje ficou forte demais, né?",
]

Audio = np.ndarray[Any, np.dtype[np.float32]]


# --- gravar ---------------------------------------------------------------------------------


def _tocar(taxa: int, dados: bytes) -> None:
    subprocess.run(comando_reprodutor(taxa), input=dados, check=False)  # noqa: S603


def _falar(texto: str) -> None:
    taxa, x = piper.PADRAO.sintetizar(texto)
    _tocar(taxa, x.astype("<f4").tobytes())


def _bip() -> None:
    t = np.arange(int(0.15 * 16000)) / 16000
    _tocar(16000, (0.25 * np.sin(2 * np.pi * 880 * t)).astype("<f4").tobytes())


def _gravar(captura: Captura, segundos: float) -> bytes:
    captura._esvaziar()
    partes = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            partes.append(captura.quadros.get(timeout=1))
        except queue.Empty:  # fila vazia: segue até o tempo
            continue
    return b"".join(partes)


def _salvar(caminho: Path, pcm: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as w:
        w.setparams((1, 2, TAXA, 0, "NONE", "not compressed"))
        w.writeframes(pcm)


def gravar(vezes: int = 30) -> Path:
    sessao = PASTA / time.strftime("%Y%m%d-%H%M%S")
    captura = Captura(tamanho_fila=2000)
    captura.abrir()
    try:
        _falar(
            "Vamos gravar o seu chamado. Depois de cada bipe, diga a frase que eu pedir, "
            "do seu jeito normal, como se estivesse me chamando."
        )
        for i in range(vezes):
            frase = CHAMADOS[i % len(CHAMADOS)]
            _falar(f"{frase}.")
            _bip()
            _salvar(sessao / "positivo" / f"{i:02d}.wav", _gravar(captura, 2.5))
            print(f"chamado {i + 1}/{vezes}: {frase}", flush=True)
        _falar("Agora palavras parecidas, que não podem me acordar.")
        for i, palavra in enumerate(PARECIDAS * 2):  # duas vezes cada: são as que confundem
            _falar(f"{palavra}.")
            _bip()
            _salvar(sessao / "negativo" / f"parecida-{i:02d}.wav", _gravar(captura, 2.0))
        _falar(
            "Por último, fale normalmente por quarenta segundos, sobre qualquer coisa, sem me "
            "chamar. Pode começar depois do bipe."
        )
        _bip()
        _salvar(sessao / "negativo" / "fala.wav", _gravar(captura, 40))
        _bip()
        _falar("Pronto, gravei tudo. Obrigado.")
    finally:
        captura.fechar()
    print(f"gravado em {sessao}", flush=True)
    return sessao


# --- treinar --------------------------------------------------------------------------------


def _carregar(caminho: Path) -> Audio:
    with wave.open(str(caminho)) as w:
        dados: Audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32)
    return dados


def _trecho_de_fala(x: Audio, quadro: int = 320) -> tuple[int, int] | None:
    e = np.sqrt(np.mean(x[: len(x) // quadro * quadro].reshape(-1, quadro) ** 2, axis=1))
    piso = np.percentile(e, 20)
    ligado = np.where(e > piso + 0.15 * (e.max() - piso))[0]
    return (int(ligado[0] * quadro), int((ligado[-1] + 1) * quadro)) if len(ligado) else None


def _colocar(x: Audio, fim: int, fundo: Audio | None = None) -> Audio:
    saida = np.zeros(CLIP, np.float32) if fundo is None else fundo.copy()
    inicio = fim - len(x)
    a = max(0, -inicio)
    saida[max(0, inicio) : fim] += x[a:]
    return saida


def _janelas(x: Audio, passo: int) -> list[Audio]:
    return [x[i : i + CLIP] for i in range(0, len(x) - CLIP + 1, passo)]


def _sintetizar(texto: str) -> Audio:
    taxa, x = piper.PADRAO.sintetizar(texto)
    reamostrado: Audio = (
        np.interp(np.arange(0, len(x), taxa / TAXA), np.arange(len(x)), x).astype(np.float32)
        * 32767
        * 0.6
    )
    return reamostrado


def _negativos_do_cadu(rng: np.random.Generator) -> list[Audio]:
    cache = PASTA / "negativos-cadu.npz"
    textos = np.array(DIFICEIS + GENERICAS)
    if cache.exists():
        guardado = np.load(cache)
        if np.array_equal(guardado["textos"], textos):
            return list(guardado["clips"])
    clips: list[Audio] = []
    for texto in GENERICAS:
        x = _sintetizar(texto)
        silencio = np.zeros(TAXA, np.float32)
        clips.extend(_janelas(np.concatenate([silencio, x, silencio]), int(0.15 * TAXA)))
    for texto in DIFICEIS:
        x = _sintetizar(texto)
        trecho = _trecho_de_fala(x)
        x = x[trecho[0] : trecho[1]] if trecho else x
        clips.append(_colocar(x[-CLIP:], FIM))
        clips.extend(_colocar(x[-CLIP:], FIM + int(rng.integers(-3000, 3000))) for _ in range(3))
    np.savez(cache, clips=np.array(clips, np.float32), textos=textos)
    return clips


def _embeddings(clips: list[Audio], features: Features) -> np.ndarray[Any, np.dtype[np.float32]]:
    """Os 16 últimos embeddings de cada janela, em fluxo, como o detector calcula ao vivo."""
    saida = []
    for clip in clips:
        features.reiniciar()
        audio = np.clip(clip, -32768, 32767).astype(np.int16)
        for i in range(0, len(audio) - QUADRO + 1, QUADRO):
            features(audio[i : i + QUADRO])
        saida.append(features.ultimas()[0])
    return np.array(saida, np.float32)


def _contar(detector: Detector, audio: Audio) -> int:
    detector.reiniciar()
    n = 0
    for i in range(0, len(audio) - QUADRO + 1, QUADRO):  # até o último quadro (era pulado)
        n += detector.processar(np.clip(audio[i : i + QUADRO], -32768, 32767).astype(np.int16))
    return n


def treinar(destino: Path = MODELO) -> dict[str, Any]:
    from sklearn.neural_network import MLPClassifier  # type: ignore[import-not-found,unused-ignore]

    rng = np.random.default_rng(7)
    sessoes = sorted(p for p in PASTA.iterdir() if p.is_dir())
    chamados = [_carregar(p) for s in sessoes for p in sorted((s / "positivo").glob("*.wav"))]
    chamados_com_trecho = [(x, t) for x in chamados if (t := _trecho_de_fala(x))]
    fala = [_carregar(p) for s in sessoes for p in sorted((s / "negativo").glob("fala*.wav"))]
    parecidas = [
        _carregar(p) for s in sessoes for p in sorted((s / "negativo").glob("parecida-*.wav"))
    ]
    ordem = rng.permutation(len(chamados_com_trecho))
    separados = [chamados_com_trecho[i] for i in ordem[: max(3, len(ordem) // 5)]]
    treino = [chamados_com_trecho[i] for i in ordem[len(separados) :]]
    corte = [int(len(a) * 0.75) for a in fala]
    fundo_treino = [a[:c] for a, c in zip(fala, corte, strict=True)]
    fundo_teste = [a[c:] for a, c in zip(fala, corte, strict=True)]

    def fundo() -> Audio:
        a = fundo_treino[int(rng.integers(len(fundo_treino)))]
        i = int(rng.integers(0, len(a) - CLIP))
        trecho: Audio = a[i : i + CLIP] * rng.uniform(0.05, 0.4)
        return trecho

    pos: list[Audio] = []
    neg: list[Audio] = []
    for x, (a, b) in treino:
        frase = x[a:b]
        for _ in range(32):
            ganho = rng.uniform(0.5, 1.6)
            com_fundo = fundo() if rng.random() < 0.7 else None
            # "Ei Zé" dura meio segundo: o detector pede 3 quadros seguidos (0,24 s), então o
            # chamado aparece em posições de até 0,3 s antes do fim da janela.
            pos.append(_colocar(frase * ganho, FIM + int(rng.integers(-4800, 1600)), com_fundo))
        for fracao in (0.35, 0.5):  # só o começo ("Ei") não pode acordar
            neg.append(_colocar(frase[: int(len(frase) * fracao)], FIM))
    for x in parecidas:
        trecho = _trecho_de_fala(x)
        if trecho:
            for _ in range(6):
                neg.append(
                    _colocar(
                        x[trecho[0] : trecho[1]] * rng.uniform(0.6, 1.4),
                        FIM + int(rng.integers(-1600, 1600)),
                    )
                )
    for a in fundo_treino:
        neg.extend(_janelas(a, int(0.1 * TAXA)))
    # Silêncio e ruído baixo nunca acordam (13/10/2026: disparou em silêncio a -91 dBFS).
    for nivel in (0.0, 1e-5, 1e-4, 1e-3, 3e-3):
        for _ in range(40):
            neg.append((rng.standard_normal(CLIP) * nivel).astype(np.float32))
    sons_falsos = [_carregar(p) for p in sorted(FALSOS.glob("*.wav"))] if FALSOS.is_dir() else []
    for x in sons_falsos:
        for _ in range(8):
            neg.append(
                _colocar(x[-CLIP:] * rng.uniform(0.6, 1.4), FIM + int(rng.integers(-1600, 1600)))
            )
    neg.extend(_negativos_do_cadu(rng))
    neg.extend(fundo() for _ in range(len(neg) // 4))

    features = Features(MODELOS_ONNX / "melspectrogram.onnx", MODELOS_ONNX / "embedding_model.onnx")
    print(f"embeddings: {len(pos)} positivos, {len(neg)} negativos", flush=True)
    X = np.concatenate([_embeddings(pos, features), _embeddings(neg, features)])
    y = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    planos = X.reshape(len(X), -1)
    media, desvio = planos.mean(0), planos.std(0) + 1e-6
    mlp = MLPClassifier(
        hidden_layer_sizes=(64,), alpha=1e-3, max_iter=400, early_stopping=True, random_state=7
    )
    mlp.fit((planos - media) / desvio, y, sample_weight=np.where(y == 1, len(neg) / len(pos), 1.0))
    profundidade = len(mlp.coefs_)
    pesos = {f"W{i}": mlp.coefs_[i].astype(np.float32) for i in range(profundidade)} | {
        f"b{i}": mlp.intercepts_[i].astype(np.float32) for i in range(profundidade)
    }
    relatorio: dict[str, Any] = {
        "treinado_em": time.strftime("%Y-%m-%d %H:%M"),
        "chamados_treino": len(treino),
        "chamados_teste": len(separados),
        "positivos": len(pos),
        "negativos": len(neg),
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    melhor: tuple[float, float] | None = None
    silencio = np.zeros(TAXA, np.float32)
    for limiar in (0.3, 0.4, 0.5, 0.7, 0.9, 0.95, 0.98):
        np.savez(destino, depth=profundidade, mean=media, std=desvio, threshold=limiar, **pesos)
        detector = Detector(ModeloAtivacao(destino), features)
        acerto = sum(
            _contar(detector, np.concatenate([silencio, x, silencio])) > 0 for x, _ in separados
        ) / len(separados)
        falsos = (
            sum(_contar(detector, a) for a in fundo_teste)
            + sum(_contar(detector, np.concatenate([silencio, x, silencio])) for x in parecidas)
            + sum(_contar(detector, np.concatenate([silencio, x, silencio])) for x in sons_falsos)
        )
        relatorio[f"limiar_{limiar}"] = {"acerto": round(acerto, 2), "falsos": falsos}
        if falsos == 0 and acerto > 0 and (melhor is None or acerto >= melhor[1]):
            melhor = (limiar, acerto)  # empate: o limiar mais alto, mais margem
    escolhido = melhor[0] if melhor else 0.99
    np.savez(destino, depth=profundidade, mean=media, std=desvio, threshold=escolhido, **pesos)
    destino.chmod(0o600)
    relatorio["limiar_escolhido"] = escolhido
    (destino.parent / "relatorio.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2)
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2), flush=True)
    return relatorio


if __name__ == "__main__":
    if (sys.argv[1] if len(sys.argv) > 1 else "gravar") == "treinar":
        treinar()
    else:
        gravar()
