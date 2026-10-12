"""A voz remota: o Zé como participante da sala LiveKit (plano da voz remota, etapa 1).

Só o transporte muda (ADR 0005): o microfone da pessoa chega em quadros de 80 ms a 16 kHz, os
mesmos da `Captura` local, e entra na mesma fila do laço; a voz do Piper sai por uma faixa da sala
em vez do alto-falante. Ativação, escuta, Deepgram, cérebro e modos de fala não mudam.

Usa só a sala e as faixas do SDK de tempo real (`livekit`, Apache-2.0), sem o framework de
agentes. O SDK é assíncrono: a sala roda num laço asyncio numa thread própria, e as outras
threads do Zé falam com ela por `run_coroutine_threadsafe`.
"""

import asyncio
import contextlib
import logging
import threading
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np
from livekit import rtc

log = logging.getLogger(__name__)

TAXA_ENTRADA = 16000
QUADRO_MS = 80
BYTES_QUADRO = TAXA_ENTRADA * QUADRO_MS // 1000 * 2
TAXA_SAIDA = 48000
PESSOA = "pessoa-"  # prefixo da identidade de quem fala com o Zé (o token do painel)
ESPERA_S = (1.0, 2.0, 5.0, 15.0, 30.0)


class SalaRemota:
    """Mantém o Zé na sala; avisa quando a pessoa entra ou sai e entrega o áudio dela."""

    def __init__(
        self,
        url: str,
        token: Callable[[], str],
        ao_quadro: Callable[[bytes], None],
        ao_conectar: Callable[[bool], None],
    ) -> None:
        self.url = url
        self.token = token
        self.ao_quadro = ao_quadro
        self.ao_conectar = ao_conectar
        self.loop = asyncio.new_event_loop()
        self.fonte: rtc.AudioSource | None = None
        self.pessoas: set[str] = set()
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    @property
    def conectada(self) -> bool:
        return bool(self.pessoas)

    def iniciar(self) -> None:
        self._fio = threading.Thread(target=self._rodar, name="voz-remota", daemon=True)
        self._fio.start()

    def parar(self) -> None:
        self._parar.set()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

    def _rodar(self) -> None:
        asyncio.set_event_loop(self.loop)
        with contextlib.suppress(RuntimeError):  # parar() interrompe o laço
            self.loop.run_until_complete(self._manter())

    async def _manter(self) -> None:
        quedas = 0
        while not self._parar.is_set():
            sala = rtc.Room(loop=self.loop)
            caiu = asyncio.Event()
            self._ligar_eventos(sala, caiu)
            try:
                await sala.connect(self.url, self.token())
                self.fonte = rtc.AudioSource(TAXA_SAIDA, 1, queue_size_ms=500)
                faixa = rtc.LocalAudioTrack.create_audio_track("voz-do-ze", self.fonte)
                opcoes = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
                await sala.local_participant.publish_track(faixa, opcoes)
                log.info("voz remota: o Zé entrou na sala")
                quedas = 0
                await caiu.wait()
            except Exception as erro:
                log.warning("voz remota: sem conexão com a sala (%s)", erro)
            finally:
                self.fonte = None
                self._sairam(set(self.pessoas))
                with contextlib.suppress(Exception):
                    await sala.disconnect()
            espera = ESPERA_S[min(quedas, len(ESPERA_S) - 1)]
            quedas += 1
            await asyncio.sleep(espera)

    def _ligar_eventos(self, sala: rtc.Room, caiu: asyncio.Event) -> None:
        @sala.on("track_subscribed")
        def _faixa(
            faixa: rtc.Track, _pub: rtc.RemoteTrackPublication, quem: rtc.RemoteParticipant
        ) -> None:
            if faixa.kind != rtc.TrackKind.KIND_AUDIO or not quem.identity.startswith(PESSOA):
                return
            self.loop.create_task(self._ouvir(faixa))
            if not self.pessoas:
                self.pessoas.add(quem.identity)
                log.info("voz remota: conectada")
                self.ao_conectar(True)
            self.pessoas.add(quem.identity)

        @sala.on("participant_disconnected")
        def _saiu(quem: rtc.RemoteParticipant) -> None:
            self._sairam({quem.identity})

        @sala.on("disconnected")
        def _caiu(*_: object) -> None:
            caiu.set()

    def _sairam(self, identidades: set[str]) -> None:
        if not self.pessoas & identidades:
            return
        self.pessoas -= identidades
        if not self.pessoas:
            log.info("voz remota: desconectada")
            self.ao_conectar(False)

    async def _ouvir(self, faixa: rtc.Track) -> None:
        fluxo = rtc.AudioStream(
            faixa, sample_rate=TAXA_ENTRADA, num_channels=1, frame_size_ms=QUADRO_MS
        )
        resto = b""
        try:
            async for evento in fluxo:
                resto += bytes(evento.frame.data)
                while len(resto) >= BYTES_QUADRO:
                    self.ao_quadro(resto[:BYTES_QUADRO])
                    resto = resto[BYTES_QUADRO:]
        finally:
            await fluxo.aclose()

    # --- saída: chamadas de outras threads ------------------------------------------------------

    def enviar(self, quadro: rtc.AudioFrame, espera_s: float = 5.0) -> None:
        """Entrega um pedaço da voz à faixa do Zé; bloqueia enquanto a fila da faixa está cheia,
        o que dá o ritmo do tempo real a quem escreve."""
        fonte = self.fonte
        if fonte is None or not self.loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(fonte.capture_frame(quadro), self.loop).result(espera_s)

    def esperar_tocar(self, espera_s: float = 60.0) -> None:
        fonte = self.fonte
        if fonte is None or not self.loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(fonte.wait_for_playout(), self.loop).result(espera_s)

    def limpar(self) -> None:
        """Corta o que ainda não tocou (interrupção)."""
        fonte = self.fonte
        if fonte is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(fonte.clear_queue)

    def tocador(self, taxa: int) -> "TocadorRemoto":
        return TocadorRemoto(self, taxa)

    def tocar_wav(self, arquivo: Path) -> None:
        """Um som curto (o bip) pela faixa do Zé, até o fim."""
        with wave.open(str(arquivo)) as w:
            taxa, canais, pcm = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
        amostras = np.frombuffer(pcm, "<i2").reshape(-1, canais).mean(axis=1) / 32768.0
        t = self.tocador(taxa)
        t.write(amostras.astype("<f4").tobytes())
        t.close()
        t.wait()


class TocadorRemoto:
    """O pedaço do `subprocess.Popen` que a saída de voz usa (`stdin`, `poll`, `wait`, `kill`),
    escrevendo na faixa do Zé em vez do `paplay`: float32 na taxa do Piper vira int16 a 48 kHz."""

    def __init__(self, sala: SalaRemota, taxa: int) -> None:
        self.sala = sala
        self.taxa = taxa
        self.reamostrar = rtc.AudioResampler(taxa, TAXA_SAIDA) if taxa != TAXA_SAIDA else None
        self.codigo: int | None = None
        self.stdin = self
        self._resto = b""

    def _mandar(self, quadros: list[rtc.AudioFrame]) -> None:
        for q in quadros:
            if self.codigo is not None:
                raise BrokenPipeError
            self.sala.enviar(q)

    def write(self, dados: bytes) -> int:
        if self.codigo is not None:
            raise BrokenPipeError
        junto = self._resto + dados
        corte = len(junto) // 4 * 4
        self._resto = junto[corte:]
        if not corte:
            return len(dados)
        amostras = np.frombuffer(junto[:corte], "<f4")
        pcm = (np.clip(amostras, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        quadro = rtc.AudioFrame(pcm, self.taxa, 1, len(amostras))
        self._mandar(self.reamostrar.push(quadro) if self.reamostrar else [quadro])
        return len(dados)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self.reamostrar is not None and self.codigo is None:
            self._mandar(self.reamostrar.flush())

    def poll(self) -> int | None:
        return self.codigo

    def wait(self) -> int:
        if self.codigo is None:
            self.sala.esperar_tocar()
            self.codigo = 0
        return self.codigo

    def kill(self) -> None:
        self.codigo = -9
        self.sala.limpar()
