"""O Live (ADR 0042): conversa em tempo real, como numa ligação, com o revezamento do LIGATIA.

Com a voz conectada ao vivo (o navegador ou o app do celular), o áudio não passa pelo recorte do
Zé (`escuta.py`): vai para uma sessão do LiveKit Agents que roda aqui dentro, sem sala e sem
worker. Ela ouve sem parar (Silero), transcreve em streaming (Deepgram nova-3, pt-BR), decide o
fim da fala também pelo texto (o detector multilíngue do LiveKit, local) e corta a própria fala
quando a pessoa fala por cima. Provado em 27/10/2026 (`docs/adr/0042`): fim de fala em 0,40 a
0,48 s, contra 1,05 s do recorte; corte da fala 0,5 s depois de a pessoa começar.

O Live troca só os ouvidos, a boca e o revezamento. O resto do Zé fica como está: cada fala da
pessoa vira o `FimDeFala` de sempre na máquina de estados, e o cérebro, os comandos, as
confirmações ("Aprovo?") e os avisos seguem pelo laço. O que o laço manda falar volta para cá:
dentro da vez da pessoa, vira a resposta dela; fora (um aviso), é falado pela sessão. A voz é o
motor do Zé (`nuvem.Motor`: Fish, ElevenLabs ou o Cadu).

O detector de fim de fala é da LiveKit Model License: grátis, mas só dentro do LiveKit Agents e não
aberto. Fica fora do repositório e é baixado na primeira subida (`garantir_modelo`), na pasta de
modelos do Zé.
"""

import asyncio
import contextlib
import logging
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from zervis import lugares

log = logging.getLogger(__name__)

PASTA_HF = lugares.DADOS / "modelos" / "hf"
TAXA_ENTRADA = 16000  # o WebSocket da voz: int16 a 16 kHz, quadros de 80 ms
TAXA_VOZ = 24000
FIM_MIN_S = 0.4  # os do LIGATIA: menor espera depois do fim provável da frase
# A escolha "Espera" da página Voz vira o teto: quanto o Zé aguarda numa frase pela metade.
FIM_MAX_S = {"rapida": 1.5, "normal": 2.0, "longa": 3.0}
INTERRUPCAO_MIN_S = 0.5  # fala por cima mais curta que isto (tosse, "hum") não corta
# No começo de cada conexão, a fala do Zé não é cortada por este tempo: o cancelamento de eco do
# aparelho ainda se ajusta e a própria voz voltaria pelo microfone. O LiveKit usa 3 s; o
# navegador e o celular já chegam com o cancelamento ligado.
AQUECIMENTO_ECO_S = 1.5
PRAZO_LIGAR_S = 15.0


def _hf() -> None:
    # Antes de importar o huggingface_hub: o cache dele fica na pasta de modelos do Zé.
    os.environ["HF_HUB_CACHE"] = str(PASTA_HF)


def modelo_pronto() -> bool:
    """O detector de fim de fala já está na pasta (sem rede)."""
    _hf()
    try:
        from huggingface_hub import hf_hub_download
        from livekit.plugins.turn_detector.models import HG_MODEL, MODEL_REVISIONS, ONNX_FILENAME

        revisao = MODEL_REVISIONS["multilingual"]
        for nome, pasta in ((ONNX_FILENAME, "onnx"), ("languages.json", None)):
            hf_hub_download(
                HG_MODEL, nome, subfolder=pasta, revision=revisao, local_files_only=True
            )
    except Exception:  # sem o pacote, sem o arquivo ou cache quebrado: o Live fica de fora
        return False
    return True


def garantir_modelo() -> bool:
    """Baixa o detector (cerca de 9 MB, revisão fixa do plugin) se faltar; True se baixou agora."""
    if modelo_pronto():
        return False
    _hf()
    from livekit.plugins.turn_detector.multilingual import _EUORunnerMultilingual

    _EUORunnerMultilingual._download_files()
    return True


def live_ativo(nucleo: object) -> "Live | None":
    """O Live do núcleo, se ele está com a conversa agora (a voz conectada ao vivo). Uma função, não
    um método: os testes chamam os métodos do núcleo com objetos que não têm o Live."""
    live: Live | None = getattr(nucleo, "live", None)
    return live if live is not None and live.ativo else None


def pedido_do_turno(falas: list[str], pendente: str) -> str:
    """O texto que vai ao Zé: a última fala da pessoa, com o pedido anterior que ficou sem
    resposta falada (ela emendou enquanto o Zé pensava: "qual a capital da França?... e da
    Itália também")."""
    ultima = falas[-1].strip() if falas else ""
    return f"{pendente} {ultima}".strip() if pendente else ultima


@dataclass
class Pecas:
    """As peças de ouvir trocadas (os testes, sem modelo nem rede): o detector de voz, uma fábrica
    de transcritor e o modo de fim de fala (um detector, ou "vad")."""

    vad: Any
    stt: Callable[[], Any]
    deteccao: Any = "vad"
    aquecimento_eco_s: float = AQUECIMENTO_ECO_S


@dataclass
class _Turno:
    """A vez da pessoa: o pedido mandado ao Zé e as frases da resposta, conforme chegam."""

    texto: str
    fila: "asyncio.Queue[str | None]" = field(default_factory=asyncio.Queue)
    fechado: bool = False
    falou: bool = False  # alguma frase da resposta chegou a tocar
    numero: int = 0  # a última fala do laço que entrou nesta resposta


class Live:
    """A sessão de voz em tempo real, num laço asyncio numa thread própria. Tudo o que o laço do
    Zé chama aqui é seguro de qualquer thread e não bloqueia (menos `ligar`, que espera a sessão
    subir)."""

    def __init__(
        self,
        chave: Callable[[], str | None],
        motor_voz: Any,
        ao_pedido: Callable[[str, float, float], None],
        ao_interromper: Callable[[], None],
        ao_ociosa: Callable[[int], None],
        espera: Callable[[], str] = lambda: "normal",
        pecas: "Pecas | None" = None,
    ) -> None:
        self.chave = chave
        self.motor_voz = motor_voz
        self.ao_pedido = ao_pedido
        self.ao_interromper = ao_interromper
        self.ao_ociosa = ao_ociosa
        self.espera = espera
        self.pecas = pecas  # outras peças de ouvir (os testes); None: Silero, Deepgram, detector
        self.fonte: Any = None
        self.pessoa_falando = False
        self.erro: str | None = None
        self._laco: asyncio.AbstractEventLoop | None = None
        self._pronto = threading.Event()
        self._sessao: Any = None
        self._entrada: Any = None
        self._turno: _Turno | None = None
        self._pendente = ""
        self._cortado_pelo_ze = False
        self._fim_fala_em = 0.0
        self._ao_iniciar: dict[int, Callable[[float], None]] = {}
        self._modulos: dict[str, Any] = {}
        self._resposta_criada: Any = None  # a fala que a sessão abriu para a vez que fechou
        # Pedidos mandados ao laço; uma vez só fecha depois de o laço ter visto o pedido dela
        # (sem isto, uma batida do relógio do laço antes do pedido fechava a vez vazia).
        self.enviados = 0

    # --- disponibilidade e subida ---------------------------------------------------------------

    def preparar(self) -> bool:
        """Na thread principal (o detector exige registrar o modelo nela): importa o LiveKit
        Agents e sobe o laço do Live, que carrega os modelos em segundo plano. False se faltar o
        pacote ou o modelo. A chave do Deepgram é conferida a cada conexão: colada depois no
        painel, já vale."""
        if self.pecas is not None:
            self._modulos = {"pecas": self.pecas}
            threading.Thread(target=self._rodar, name="live", daemon=True).start()
            return True
        if not modelo_pronto():
            self.erro = "sem o detector de fim de fala (rode `python -m zervis.preparar`)"
            return False
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")  # só o que já foi baixado
            from livekit.plugins import deepgram, silero
            from livekit.plugins.turn_detector import multilingual
        except Exception as erro:
            self.erro = f"LiveKit Agents indisponível: {type(erro).__name__}"
            log.warning("Live: %s", self.erro)
            return False
        self._modulos = {"deepgram": deepgram, "silero": silero, "detector": multilingual}
        threading.Thread(target=self._rodar, name="live", daemon=True).start()
        return True

    @property
    def disponivel(self) -> bool:
        return bool(self._modulos) and bool(self.chave())

    @property
    def ativo(self) -> bool:
        return self._sessao is not None

    def _rodar(self) -> None:
        asyncio.run(self._principal())

    async def _principal(self) -> None:
        import aiohttp
        from livekit.agents.inference_runner import _InferenceRunner

        self._http = aiohttp.ClientSession()
        if self.pecas is not None:
            self._vad = self.pecas.vad
        else:
            silero = self._modulos["silero"]
            self._vad = silero.VAD.load(
                min_silence_duration=0.25, min_speech_duration=0.05, prefix_padding_duration=0.1
            )
            metodo = self._modulos["detector"]._EUORunnerMultilingual.INFERENCE_METHOD
            self._executor = _ExecutorLocal(_InferenceRunner.registered_runners, metodo)
            await asyncio.to_thread(self._executor.aquecer)
        self._laco = asyncio.get_running_loop()
        self._pronto.set()
        log.info("Live pronto")
        try:
            await asyncio.Event().wait()
        finally:
            await self._http.close()

    def _no_laco(self, funcao: Callable[..., Any], *args: Any) -> None:
        if self._laco is not None:
            self._laco.call_soon_threadsafe(funcao, *args)

    # --- conexão --------------------------------------------------------------------------------

    def ligar(self, fonte: Any) -> bool:
        """A voz ao vivo conectou: abre a sessão para ela (fecha a anterior, se houver)."""
        if not self._pronto.wait(PRAZO_LIGAR_S) or self._laco is None:
            self.erro = "o Live não terminou de carregar"
            return False
        futuro = asyncio.run_coroutine_threadsafe(self._abrir(fonte), self._laco)
        try:
            futuro.result(PRAZO_LIGAR_S)
        except Exception as erro:
            self.erro = f"a sessão não abriu: {type(erro).__name__}: {erro}"
            log.warning("Live: %s", self.erro)
            return False
        self.erro = None
        return True

    def desligar(self) -> None:
        """Fecha a sessão e espera (pouco): quem chama já pode contar com o Live desligado."""
        if self._laco is None or self._sessao is None:
            return
        futuro = asyncio.run_coroutine_threadsafe(self._fechar(), self._laco)
        with contextlib.suppress(Exception):
            futuro.result(5.0)

    async def _abrir(self, fonte: Any) -> None:
        await self._fechar()
        from livekit.agents import AgentSession

        self.fonte = fonte
        self._entrada = _nova_entrada()
        if self.pecas is not None:
            stt, deteccao = self.pecas.stt(), self.pecas.deteccao
        else:
            stt = self._modulos["deepgram"].STT(
                model="nova-3",
                language="pt-BR",
                interim_results=True,
                punctuate=True,
                smart_format=False,  # "um Codex" virava "1 Codex" (deepgram.py)
                keyterm=["Zé", "Zérvis"],
                api_key=self.chave() or "",
                http_session=self._http,
            )
            deteccao = _detector(self._executor, self._modulos["detector"])
        sessao: Any = AgentSession(
            vad=self._vad,
            stt=stt,
            llm=_cerebro_do_ze(),
            tts=_voz_do_ze(self.motor_voz),
            aec_warmup_duration=(
                self.pecas.aquecimento_eco_s if self.pecas is not None else AQUECIMENTO_ECO_S
            ),
            turn_handling={
                "turn_detection": deteccao,
                "endpointing": {
                    "min_delay": FIM_MIN_S,
                    "max_delay": FIM_MAX_S.get(self.espera(), 2.0),
                },
                "interruption": {
                    "min_duration": INTERRUPCAO_MIN_S,
                    # Retomar depois de um "hum" pede pausar a fala no aparelho, que o app e o
                    # navegador ainda não fazem (ADR 0042, próximos passos).
                    "resume_false_interruption": False,
                },
                # O pedido vai ao cérebro de verdade (ferramentas, sessões): gerar antes de a vez
                # fechar mandaria pedidos pela metade, com efeito.
                "preemptive_generation": {"enabled": False},
            },
        )
        sessao.on("user_state_changed", self._estado_da_pessoa)
        sessao.on("speech_created", self._fala_criada)
        sessao.input.audio = self._entrada
        sessao.output.audio = _nova_saida(self)
        await sessao.start(agent=_agente(self))
        self._sessao = sessao
        self._turno, self._pendente = None, ""
        log.info("Live: sessão aberta")

    async def _fechar(self) -> None:
        sessao, self._sessao = self._sessao, None
        self.fonte = None
        self.pessoa_falando = False
        if self._turno is not None:
            self._fechar_turno()
        if sessao is not None:
            try:
                await sessao.aclose()
            except Exception:
                log.debug("Live: fechar a sessão falhou", exc_info=True)
            log.info("Live: sessão fechada")

    # --- o que o laço do Zé chama ---------------------------------------------------------------

    def receber(self, quadro: bytes) -> None:
        """Um quadro do microfone da voz conectada (int16, 16 kHz)."""
        if self._entrada is not None and self._sessao is not None:
            self._entrada.receber(quadro)

    def falar(self, texto: str, numero: int, ao_iniciar: Callable[[float], None] | None) -> None:
        """Uma frase do Zé: a resposta da vez aberta, ou um aviso falado pela sessão."""
        if ao_iniciar is not None:
            self._ao_iniciar[numero] = ao_iniciar
        self._no_laco(self._falar, texto, numero)

    def acompanhar(self, resposta_acabou: bool, vistos: int) -> None:
        """O laço tratou um evento: se a resposta acabou (o cérebro terminou, a pergunta de
        confirmação saiu ou o pedido não deu em nada) e o laço já viu todos os pedidos (`vistos`),
        a vez fecha e a pessoa volta a falar."""
        if resposta_acabou:
            self._no_laco(self._fechar_se_visto, vistos)

    def _fechar_se_visto(self, vistos: int) -> None:
        if vistos >= self.enviados:
            self._fechar_turno()

    def parar(self) -> None:
        """O próprio Zé corta a fala (um pedido escrito, o Silencioso): não é a pessoa
        interrompendo, então não avisa de volta."""
        self._no_laco(self._parar)

    # --- dentro do laço do Live -----------------------------------------------------------------

    def _falar(self, texto: str, numero: int) -> None:
        if self._sessao is None:
            self.ao_ociosa(numero)
            return
        turno = self._turno
        if turno is not None and not turno.fechado:
            turno.numero = numero
            turno.fila.put_nowait(texto)
            return
        handle = self._sessao.say(texto, allow_interruptions=True)
        handle.numero_do_ze = numero

    def _fechar_turno(self) -> None:
        turno = self._turno
        if turno is not None and not turno.fechado:
            turno.fechado = True
            turno.fila.put_nowait(None)

    def _parar(self) -> None:
        if self._sessao is not None and self._sessao.current_speech is not None:
            self._cortado_pelo_ze = True
            self._sessao.interrupt(force=True)
        self._fechar_turno()

    def _estado_da_pessoa(self, ev: Any) -> None:
        falando = str(ev.new_state) == "speaking"
        if self.pessoa_falando and not falando:
            self._fim_fala_em = time.monotonic()
        self.pessoa_falando = falando

    def _fala_criada(self, ev: Any) -> None:
        if ev.source == "generate_reply":
            self._resposta_criada = ev.speech_handle  # o llm_node dela roda logo depois
        ev.speech_handle.add_done_callback(self._fala_acabou)

    def _fala_acabou(self, handle: Any) -> None:
        numero = getattr(handle, "numero_do_ze", None)
        turno = getattr(handle, "turno_do_ze", None)
        if turno is not None:
            numero = turno.numero
        if handle.interrupted:
            if turno is not None and not turno.falou:
                self._pendente = turno.texto  # a resposta não chegou a tocar: vai com a próxima
            if self._cortado_pelo_ze:
                self._cortado_pelo_ze = False
            else:
                self.ao_interromper()
            return
        if turno is not None:
            self._pendente = ""
        if numero:
            self.ao_ociosa(int(numero))

    async def _vez(self, falas: list[str]) -> AsyncIterator[str]:
        """A vez da pessoa fechou: o pedido vai ao Zé e a resposta volta frase a frase."""
        texto = pedido_do_turno(falas, self._pendente)
        turno = _Turno(texto)
        if self._turno is not None:
            self._fechar_turno()
        self._turno = turno
        self._pendente = ""
        if self._resposta_criada is not None:
            self._resposta_criada.turno_do_ze = turno
            self._resposta_criada = None
        if not texto:
            self._fechar_turno()
        else:
            self.enviados += 1
            self.ao_pedido(texto, self._fim_fala_em or time.monotonic(), time.monotonic())
        try:
            while (frase := await turno.fila.get()) is not None:
                yield frase + " "
        except asyncio.CancelledError:
            if not turno.falou:
                self._pendente = texto
            raise
        finally:
            turno.fechado = True

    def _tocou(self, primeira: bool) -> None:
        """A saída mandou áudio ao aparelho."""
        if self._turno is not None:
            self._turno.falou = True
        if primeira and self._ao_iniciar:
            agora = time.monotonic()
            for numero in sorted(self._ao_iniciar):
                fazer = self._ao_iniciar.pop(numero)
                try:
                    fazer(agora)
                except Exception:
                    log.debug("Live: observador do primeiro som falhou", exc_info=True)


# --- as peças da sessão ---------------------------------------------------------------------------


class _ExecutorLocal:
    """O executor de inferência do worker do LiveKit, aqui mesmo: o modelo carrega uma vez e cada
    consulta (milissegundos) roda numa thread."""

    def __init__(self, registrados: dict[str, Any], metodo: str) -> None:
        self.registrados = registrados
        self.metodo = metodo  # o detector multilíngue (o pacote registra também o inglês)
        self.rodando: dict[str, Any] = {}
        self.trava = threading.Lock()

    def _rodar(self, metodo: str, dados: bytes) -> bytes | None:
        self._rodar_inicializar(metodo)
        with self.trava:
            resposta: bytes | None = self.rodando[metodo].run(dados)
            return resposta

    def aquecer(self) -> None:
        """Carrega o modelo antes da primeira conversa (alguns segundos, uma vez)."""
        self._rodar_inicializar(self.metodo)

    def _rodar_inicializar(self, metodo: str) -> None:
        with self.trava:
            if metodo not in self.rodando:
                r = self.registrados[metodo]()
                r.initialize()
                self.rodando[metodo] = r

    async def do_inference(self, method: str, data: bytes) -> bytes | None:
        return await asyncio.to_thread(self._rodar, method, data)


def _detector(executor: _ExecutorLocal, multilingual: Any) -> Any:
    """O detector multilíngue com o executor local (o do plugin pede o contexto de um worker)."""
    from livekit.plugins.turn_detector.base import EOUModelBase

    class DetectorLocal(multilingual.MultilingualModel):  # type: ignore[misc]
        def __init__(self) -> None:
            EOUModelBase.__init__(self, model_type="multilingual", inference_executor=executor)

    return DetectorLocal()


def _cerebro_do_ze() -> Any:
    from livekit.agents import llm

    class CerebroDoZe(llm.LLM):  # type: ignore[type-arg]
        """Só para a sessão ter um LLM: quem responde é o `llm_node` do agente (o laço do Zé)."""

        def chat(self, **kwargs: Any) -> Any:
            raise NotImplementedError("o Zé responde pelo llm_node do agente")

    return CerebroDoZe()


def _agente(live: Live) -> Any:
    from livekit.agents import Agent

    class AgenteDoZe(Agent):
        async def llm_node(self, chat_ctx: Any, tools: Any, model_settings: Any) -> Any:
            falas = [
                m.text_content or ""
                for m in chat_ctx.items
                if getattr(m, "role", None) == "user" and (m.text_content or "").strip()
            ]
            async for frase in live._vez(falas):
                yield frase

    return AgenteDoZe(instructions="O Zé responde pelo próprio cérebro.")


def _voz_do_ze(motor: Any) -> Any:
    """A voz do Zé (`nuvem.Motor`: Fish, ElevenLabs ou o Cadu) como TTS do LiveKit."""
    from livekit import rtc
    from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, tts

    class Frase(tts.ChunkedStream):
        async def _run(self, emissor: Any) -> None:
            laco = asyncio.get_running_loop()
            emissor.initialize(
                request_id=uuid.uuid4().hex,
                sample_rate=TAXA_VOZ,
                num_channels=1,
                mime_type="audio/pcm",
            )
            taxa, fluxo = await laco.run_in_executor(None, motor.abrir_fluxo, self.input_text)
            reamostrar = rtc.AudioResampler(taxa, TAXA_VOZ) if taxa != TAXA_VOZ else None
            try:
                while dados := await laco.run_in_executor(None, fluxo.read1, 16384):
                    pcm = (np.clip(np.frombuffer(dados, "<f4"), -1, 1) * 32767).astype("<i2")
                    if reamostrar is None:
                        emissor.push(pcm.tobytes())
                        continue
                    quadro = rtc.AudioFrame(pcm.tobytes(), taxa, 1, len(pcm))
                    for q in reamostrar.push(quadro):
                        emissor.push(bytes(q.data))
                if reamostrar is not None:
                    for q in reamostrar.flush():
                        emissor.push(bytes(q.data))
                emissor.flush()
            finally:
                fluxo.close()  # cortada no meio: o motor para de gerar e fecha a conexão

    class VozDoZe(tts.TTS):  # type: ignore[type-arg]
        def __init__(self) -> None:
            super().__init__(
                capabilities=tts.TTSCapabilities(streaming=False),
                sample_rate=TAXA_VOZ,
                num_channels=1,
            )

        def synthesize(
            self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
        ) -> Any:
            return Frase(tts=self, input_text=text, conn_options=conn_options)

    return VozDoZe()


def _nova_entrada() -> Any:
    """Os quadros do microfone entrando no laço do Live (um `io.AudioInput`)."""
    from livekit import rtc
    from livekit.agents.voice import io

    class Entrada(io.AudioInput):
        def __init__(self) -> None:
            super().__init__(label="voz do Zé")
            self.fila: asyncio.Queue[Any] = asyncio.Queue()
            self.laco = asyncio.get_running_loop()

        def receber(self, pcm: bytes) -> None:  # de qualquer thread
            quadro = rtc.AudioFrame(pcm, TAXA_ENTRADA, 1, len(pcm) // 2)
            self.laco.call_soon_threadsafe(self.fila.put_nowait, quadro)

        async def __anext__(self) -> Any:
            return await self.fila.get()

    return Entrada()


def _nova_saida(live: Live) -> Any:
    """A fala indo ao aparelho no protocolo da voz ("voz" com a taxa, PCM int16, "fim";
    "parar" quando a pessoa corta). O fim da reprodução é estimado pelo relógio: o aparelho toca
    em tempo real o que chega."""
    from livekit.agents.voice import io

    class Saida(io.AudioOutput):
        def __init__(self) -> None:
            super().__init__(
                label="voz do Zé",
                next_in_chain=None,
                sample_rate=None,
                capabilities=io.AudioOutputCapabilities(pause=False),
            )
            self.duracao = 0.0
            self.inicio = 0.0
            self.taxa = 0
            self.cortada = asyncio.Event()
            self.tocando: asyncio.Future[None] | None = None

        def _mandar(self, **controle: Any) -> None:
            fonte = live.fonte
            if fonte is not None:
                fonte.controle(**controle)

        async def capture_frame(self, frame: Any) -> None:
            await super().capture_frame(frame)
            primeira = not self.duracao
            if primeira:
                self.inicio = time.monotonic()
                self.cortada.clear()
                self.on_playback_started(created_at=time.time())
            if primeira or frame.sample_rate != self.taxa:
                self.taxa = frame.sample_rate
                self._mandar(tipo="voz", taxa=self.taxa)
            self.duracao += frame.duration
            fonte = live.fonte
            if fonte is not None:
                try:
                    fonte.conexao.binario(bytes(frame.data))
                except Exception:
                    log.debug("Live: a voz não chegou ao aparelho", exc_info=True)
            live._tocou(primeira)

        def flush(self) -> None:
            super().flush()
            if self.duracao:
                self._mandar(tipo="fim")
                self.tocando = asyncio.ensure_future(self._esperar_tocar())

        def clear_buffer(self) -> None:
            if self.duracao:
                self._mandar(tipo="parar")
                self.cortada.set()

        async def _esperar_tocar(self) -> None:
            falta = self.inicio + self.duracao - time.monotonic()
            try:
                await asyncio.wait_for(self.cortada.wait(), max(0.0, falta))
                cortada = True
            except TimeoutError:
                cortada = False
            passou = time.monotonic() - self.inicio
            tocado = min(self.duracao, passou) if cortada else self.duracao
            self.duracao = 0.0
            self.on_playback_finished(playback_position=tocado, interrupted=cortada)

    return Saida()
