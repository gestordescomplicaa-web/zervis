"""O transcritor do Live que só mantém a conexão aberta enquanto há fala (ADR 0099).

Todo quadro do microfone passa pelo detector de voz local (o Silero, sem custo). A conexão com o
transcritor de fora (o Deepgram, que cobra pelo áudio) abre quando ele percebe voz e fecha
depois de `dormir_s` sem fala. O áudio de pouco antes da voz (`ANTES_DA_FALA_S`) fica guardado e
vai primeiro, para a primeira palavra não se perder enquanto a conexão abre.

Os eventos do transcritor de fora passam como estão: para a sessão do LiveKit, é o mesmo
transcritor, só que às vezes calado.
"""

import asyncio
import contextlib
import logging
import time
from collections import deque
from typing import Any

log = logging.getLogger(__name__)

ANTES_DA_FALA_S = 1.0


def que_dorme(interno: Any, vad: Any, dormir_s: float) -> Any:
    """Envolve `interno` (um `stt.STT` do LiveKit): a mesma interface, a conexão só com fala."""
    from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, stt
    from livekit.agents.vad import VADEventType

    if not interno.capabilities.streaming:  # um transcritor por trecho (os testes)
        interno = stt.StreamAdapter(stt=interno, vad=vad)

    class TranscritorQueDorme(stt.STT):  # type: ignore[type-arg]
        def __init__(self) -> None:
            super().__init__(capabilities=interno.capabilities)
            self.aberturas = 0  # quantas vezes a conexão abriu
            self.aberto = False

        @property
        def model(self) -> str:
            return str(interno.model)

        @property
        def provider(self) -> str:
            return str(interno.provider)

        def _update_session_keyterms(self, keyterms: list[str]) -> None:
            interno._update_session_keyterms(keyterms)

        def _push_conversation_item(self, ev: Any) -> None:
            interno._push_conversation_item(ev)

        async def _recognize_impl(self, buffer: Any, **opcoes: Any) -> Any:
            return await interno.recognize(buffer, **opcoes)

        def stream(self, **opcoes: Any) -> Any:
            return FluxoQueDorme(self, opcoes)

    class FluxoQueDorme(stt.RecognizeStream):
        def __init__(self, dono: TranscritorQueDorme, opcoes: dict[str, Any]) -> None:
            conexao = opcoes.get("conn_options", DEFAULT_API_CONNECT_OPTIONS)
            super().__init__(stt=dono, conn_options=conexao)
            self.dono, self.opcoes = dono, opcoes
            self.interno: Any = None
            self.repasse: asyncio.Future[None] | None = None
            self.antes: deque[Any] = deque()
            self.falando = False
            self.ultima_fala = time.monotonic()

        async def _metrics_monitor_task(self, eventos: Any) -> None:
            async for _ in eventos:  # as métricas são as do interno
                pass

        def _guardar(self, quadro: Any) -> None:
            self.antes.append(quadro)
            while sum(q.duration for q in self.antes) > ANTES_DA_FALA_S:
                self.antes.popleft()

        def _acordar(self) -> None:
            if self.interno is not None:
                return
            self.interno = interno.stream(**self.opcoes)
            self.repasse = asyncio.ensure_future(self._repassar(self.interno))
            while self.antes:
                self.interno.push_frame(self.antes.popleft())
            self.dono.aberturas += 1
            self.dono.aberto = True
            log.info("Live: Deepgram ouvindo")

        async def _fechar_interno(self) -> None:
            fluxo, repasse = self.interno, self.repasse
            self.interno = self.repasse = None
            self.dono.aberto = False
            if repasse is not None:
                repasse.cancel()
            if fluxo is not None:
                with contextlib.suppress(Exception):
                    await fluxo.aclose()

        async def _repassar(self, fluxo: Any) -> None:
            async for evento in fluxo:
                self._event_ch.send_nowait(evento)

        async def _ouvir(self, fluxo_vad: Any) -> None:
            async for ev in fluxo_vad:
                if ev.type == VADEventType.START_OF_SPEECH:
                    self.falando = True
                    self._acordar()
                elif ev.type == VADEventType.END_OF_SPEECH:
                    self.falando = False
                    self.ultima_fala = time.monotonic()

        async def _run(self) -> None:
            fluxo_vad = vad.stream()
            ouvinte = asyncio.ensure_future(self._ouvir(fluxo_vad))
            try:
                async for item in self._input_ch:
                    if isinstance(item, self._FlushSentinel):
                        if self.interno is not None:
                            self.interno.flush()
                        continue
                    fluxo_vad.push_frame(item)
                    if self.interno is None:
                        self._guardar(item)
                        continue
                    self.interno.push_frame(item)
                    if self.falando:
                        self.ultima_fala = time.monotonic()
                    elif time.monotonic() - self.ultima_fala > dormir_s:
                        await self._fechar_interno()
                        log.info("Live: Deepgram dormindo (%.0f s sem fala)", dormir_s)
            finally:
                ouvinte.cancel()
                with contextlib.suppress(Exception):
                    await fluxo_vad.aclose()
                await self._fechar_interno()

    return TranscritorQueDorme()
