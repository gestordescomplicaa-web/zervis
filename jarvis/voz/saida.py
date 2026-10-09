"""Saída de voz com streaming e interrupção: Cadu pelo Piper, dentro do processo (ADR 0013).

O motor entrega float32 cru frase a frase (`jarvis/voz/piper.py`); a fila, a interrupção e o anel
só conhecem esse formato de fluxo, então outro motor pode entrar sem mexer aqui. Lições já pagas:
- a primeira frase sai sozinha para a voz começar enquanto o resto ainda é sintetizado;
- só começa a tocar com folga suficiente para a geração não ficar para trás (engasgo).
Uma fala por vez; `parar()` corta a atual e descarta a fila em menos de um quadro.
"""

import contextlib
import io
import logging
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from jarvis.transporte.local import comando_reprodutor

log = logging.getLogger(__name__)
CARACTERES_POR_SEGUNDO_FALADO = 1 / 0.065  # ~65 ms de fala por caractere
Amostras = NDArray[np.float32]


def pedacos(texto: str, limite: int = 650, limite_primeiro: int = 180) -> list[str]:
    """Pedaços alinhados a frases; a primeira (até 180 caracteres) vai sozinha."""
    saida: list[str] = []
    atual = ""
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    if len(frases) > 1 and len(frases[0]) <= limite_primeiro:
        saida.append(frases.pop(0))
    for frase in frases:
        while len(frase) > limite:
            corte = frase.rfind(" ", 0, limite) if " " in frase[:limite] else limite
            saida.append(frase[:corte])
            frase = frase[corte:].strip()
        if atual and len(atual) + 1 + len(frase) > limite:
            saida.append(atual)
            atual = frase
        else:
            atual = (atual + " " + frase).strip()
    if atual:
        saida.append(atual)
    return saida


class Fluxo(Protocol):
    def read1(self, n: int = -1, /) -> bytes: ...
    def close(self) -> None: ...


class FluxoPronto(io.BytesIO):
    """O áudio inteiro de uma frase já sintetizada, lido como se fosse um fluxo."""


class Onda(Protocol):
    """O anel do Barehands acompanha a voz enquanto ela toca."""

    def comecar(self, amostras: Callable[[], Amostras], taxa: int) -> None: ...
    def parar(self) -> None: ...


class Crescente:
    """PCM recebido até agora; quem toca lê enquanto mais chega."""

    def __init__(self) -> None:
        self.partes: list[Amostras] = []
        self.cache: Amostras = np.zeros(0, np.float32)
        self.trava = threading.Lock()

    def somar(self, dados: bytes) -> None:
        with self.trava:
            self.partes.append(np.frombuffer(dados, "<f4"))

    def amostras(self) -> Amostras:
        with self.trava:
            if self.partes:
                self.cache = np.concatenate([self.cache, *self.partes])
                self.partes = []
            return self.cache


@dataclass
class Pedaco:
    texto: str
    pcm: Crescente = field(default_factory=Crescente)
    pronto: threading.Event = field(default_factory=threading.Event)
    taxa: int | None = None
    erro: Exception | None = None


class Voz:
    def __init__(
        self,
        onda: Onda | None = None,
        abrir_fluxo: Callable[[str], tuple[int, Fluxo]] | None = None,
        folga_s: float = 1.0,
        reprodutor: Callable[[int], list[str]] = comando_reprodutor,
    ) -> None:
        self.comando_reprodutor = reprodutor
        self.onda = onda
        if abrir_fluxo is None:
            from jarvis.voz import piper

            abrir_fluxo = piper.PADRAO.abrir_fluxo
        self.abrir_fluxo = abrir_fluxo
        self.folga_s = folga_s
        self.trabalhos: queue.Queue[tuple[int, str, float, int, Callable[[float], None] | None]] = (
            queue.Queue()
        )
        self.numero = 0  # cada fala pedida ganha um número; o aviso de ociosa diz até qual foi
        self.epoca = 0
        self.reprodutor: subprocess.Popen[bytes] | None = None
        self.resposta: Fluxo | None = None
        self.sintetizando = False
        self.ultimo_erro: str | None = None
        self.primeira_fala_s: float | None = None  # do pedido de fala ao primeiro som
        self.engasgos = 0  # vezes em que a reprodução alcançou a geração
        self.faladas = 0
        self.ao_ficar_ociosa: Callable[[int], None] | None = None
        threading.Thread(target=self._rodar, name="voz", daemon=True).start()

    def falar(self, texto: str, ao_iniciar: Callable[[float], None] | None = None) -> int:
        self.numero += 1
        self.trabalhos.put((self.epoca, texto, time.monotonic(), self.numero, ao_iniciar))
        return self.numero

    @property
    def tocando(self) -> bool:
        return self.reprodutor is not None and self.reprodutor.poll() is None

    @property
    def ocupada(self) -> bool:
        return self.sintetizando or self.tocando or not self.trabalhos.empty()

    def parar(self) -> None:
        self.epoca += 1
        while True:
            try:
                self.trabalhos.get_nowait()
            except queue.Empty:
                break
        reprodutor, resposta = self.reprodutor, self.resposta
        if reprodutor and reprodutor.poll() is None:
            reprodutor.kill()
        if resposta:
            # Fechar o fluxo faz o motor parar de gerar as frases que faltam.
            with contextlib.suppress(Exception):
                resposta.close()

    def _rodar(self) -> None:
        while True:
            epoca, texto, pedido_em, numero, ao_iniciar = self.trabalhos.get()
            try:
                self._falar(pedacos(texto), epoca, pedido_em, ao_iniciar)
                self.ultimo_erro = None
                if epoca == self.epoca:
                    self.faladas += 1
            except Exception as erro:
                self.ultimo_erro = str(erro)[:180]
                log.warning("falha na voz: %s", self.ultimo_erro)
            if self.trabalhos.empty() and self.ao_ficar_ociosa:
                self.ao_ficar_ociosa(numero)

    def _produzir(self, textos: list[str], epoca: int, saida: queue.Queue[Pedaco | None]) -> None:
        """Gera os pedaços em sequência: o próximo chega enquanto o atual toca."""
        try:
            for texto in textos:
                if epoca != self.epoca:
                    break
                pedaco = Pedaco(texto)
                saida.put(pedaco)
                try:
                    self.sintetizando = True
                    pedaco.taxa, self.resposta = self.abrir_fluxo(texto)
                    resto = b""
                    while epoca == self.epoca:
                        dados = self.resposta.read1(16384)
                        if not dados:
                            break
                        dados = resto + dados
                        util = len(dados) // 4 * 4
                        resto = dados[util:]
                        pedaco.pcm.somar(dados[:util])
                except Exception as erro:
                    pedaco.erro = erro
                finally:
                    self.sintetizando = False
                    pedaco.pronto.set()
                    if self.resposta:
                        self.resposta.close()
                        self.resposta = None
        finally:
            saida.put(None)

    def _esperar_folga(self, pedaco: Pedaco, epoca: int) -> None:
        # Só começa quando o resto vai chegar a tempo. A velocidade da síntese varia com a CPU
        # (0,9x parado, até 1,4x medido sob carga): mede neste fluxo e exige uma vantagem de
        # D·(1 - velocidade) + margem, D ≈ 65 ms de fala por caractere.
        esperado = len(pedaco.texto) / CARACTERES_POR_SEGUNDO_FALADO
        inicio = time.monotonic()
        while epoca == self.epoca and not pedaco.pronto.is_set():
            if pedaco.taxa:
                tem = len(pedaco.pcm.amostras()) / pedaco.taxa
                passou = time.monotonic() - inicio
                if tem >= self.folga_s and passou > 0.3:
                    velocidade = tem / passou
                    if tem >= esperado * (1 - min(velocidade, 1)) + 0.5:
                        return
            time.sleep(0.02)

    def _falar(
        self,
        textos: list[str],
        epoca: int,
        pedido_em: float,
        ao_iniciar: Callable[[float], None] | None = None,
    ) -> None:
        saida: queue.Queue[Pedaco | None] = queue.Queue()
        threading.Thread(target=self._produzir, args=(textos, epoca, saida), daemon=True).start()
        primeiro = True
        while (pedaco := saida.get()) is not None:
            self._esperar_folga(pedaco, epoca)
            if pedaco.erro:
                raise pedaco.erro
            if epoca != self.epoca or not len(pedaco.pcm.amostras()) or not pedaco.taxa:
                continue
            if primeiro:
                self.primeira_fala_s = round(time.monotonic() - pedido_em, 2)
                primeiro = False
            self._tocar(pedaco, pedaco.taxa, epoca, ao_iniciar)
            ao_iniciar = None  # um aviso por trabalho, mesmo se tiver várias frases

    def _tocar(
        self,
        pedaco: Pedaco,
        taxa: int,
        epoca: int,
        ao_iniciar: Callable[[float], None] | None = None,
    ) -> None:
        reprodutor = self.reprodutor = subprocess.Popen(  # noqa: S603 (comando fixo)
            self.comando_reprodutor(taxa),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert reprodutor.stdin is not None  # noqa: S101 (criado com PIPE)
        if self.onda:
            self.onda.comecar(pedaco.pcm.amostras, taxa)
        escritas = 0
        inicio = time.monotonic()
        faltou = False
        try:
            while epoca == self.epoca:
                amostras = pedaco.pcm.amostras()
                if len(amostras) > escritas:
                    dados = amostras[escritas:].astype("<f4").tobytes()
                    if escritas == 0 and ao_iniciar:
                        # O WAV inteiro pode exceder o pipe e bloquear até quase o fim da fala.
                        # Cronometre a primeira amostra entregue, antes de escrever o restante.
                        reprodutor.stdin.write(dados[:4])
                        reprodutor.stdin.flush()
                        try:
                            ao_iniciar(time.monotonic())
                        except Exception as falha:
                            log.warning("observador da voz falhou: %s", type(falha).__name__)
                        dados = dados[4:]
                    reprodutor.stdin.write(dados)
                    escritas = len(amostras)
                    faltou = False
                elif pedaco.pronto.is_set():
                    break
                else:
                    # 0,3 s: o buffer do próprio paplay antes de a reprodução secar de fato
                    if not faltou and time.monotonic() - inicio - 0.3 > escritas / taxa:
                        self.engasgos += 1
                        faltou = True
                    time.sleep(0.02)
            reprodutor.stdin.close()
            codigo = reprodutor.wait()
            if codigo not in (0, -9) and epoca == self.epoca:
                raise RuntimeError(f"O reprodutor de áudio falhou ({codigo}).")
        except BrokenPipeError:
            pass  # reprodutor morto por parar()
        finally:
            if self.onda:
                self.onda.parar()
