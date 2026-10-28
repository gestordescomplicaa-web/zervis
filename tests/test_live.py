"""O Live (ADR 0042): a sessão do LiveKit Agents de verdade, com a máquina de estados e um laço
mínimo que executa os efeitos como o `laco.py`. Sem rede e sem modelo: o detector de voz é por
volume, o transcritor devolve um roteiro e a voz é um tom; o que se testa é o revezamento (a vez,
a fala por cima, a fala enquanto o Zé pensa, os avisos e as confirmações).

O detector de fim de fala de verdade (o modelo do LiveKit) tem o seu teste, num processo à parte
(o cache do Hugging Face é lido na importação).
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, stt, vad
from livekit.agents.language import LanguageCode
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import AudioBuffer

from zervis.nucleo import estados as e
from zervis.voz.live import Live, Pecas, pedido_do_turno
from zervis.voz.saida import FluxoPronto

QUADRO_S = 0.08
QUADRO = 1280  # 80 ms a 16 kHz, como o WebSocket da voz


# --- as peças falsas ------------------------------------------------------------------------------


class VadPorVolume(vad.VAD):
    """Fala é som alto; 0,25 s de silêncio fecham o trecho (como o Silero do Live)."""

    def __init__(self) -> None:
        super().__init__(capabilities=vad.VADCapabilities(update_interval=QUADRO_S))

    def stream(self) -> vad.VADStream:
        return _FluxoVad(self)


class _FluxoVad(vad.VADStream):
    async def _main_task(self) -> None:
        falando, fala, silencio, n = False, 0.0, 0.0, 0
        quadros: list[Any] = []
        async for q in self._input_ch:
            if isinstance(q, self._FlushSentinel):
                continue
            n += q.samples_per_channel
            dur = q.samples_per_channel / q.sample_rate
            alto = float(np.abs(np.frombuffer(q.data, "<i2")).mean()) > 1000

            def evento(
                tipo: vad.VADEventType,
                n: int = n,
                fala: float = 0.0,
                silencio: float = 0.0,
                **extra: Any,
            ) -> vad.VADEvent:
                return vad.VADEvent(
                    type=tipo,
                    samples_index=n,
                    timestamp=time.time(),
                    speech_duration=fala,
                    silence_duration=silencio,
                    **extra,
                )

            if alto:
                silencio = 0.0
                fala += dur
                quadros.append(q)
                if not falando:
                    falando = True
                    self._event_ch.send_nowait(
                        evento(
                            vad.VADEventType.START_OF_SPEECH,
                            n,
                            fala,
                            silencio,
                            frames=[q],
                            speaking=True,
                        )
                    )
            elif falando:
                silencio += dur
                quadros.append(q)
                if silencio >= 0.25:
                    falando = False
                    self._event_ch.send_nowait(
                        evento(
                            vad.VADEventType.END_OF_SPEECH,
                            n,
                            fala,
                            silencio,
                            frames=quadros,
                            speaking=False,
                        )
                    )
                    quadros, fala = [], 0.0
            self._event_ch.send_nowait(
                evento(
                    vad.VADEventType.INFERENCE_DONE,
                    n,
                    fala,
                    silencio,
                    frames=[q],
                    speaking=falando,
                    probability=1.0 if alto else 0.0,
                    raw_accumulated_speech=fala if alto else 0.0,
                    raw_accumulated_silence=silencio if not alto else 0.0,
                )
            )


class TranscritorDeRoteiro(stt.STT):  # type: ignore[type-arg]
    """Cada trecho de fala vira o próximo texto do roteiro."""

    def __init__(self, roteiro: "queue.Queue[str]") -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        self.roteiro = roteiro

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        try:
            texto = self.roteiro.get_nowait()
        except queue.Empty:
            texto = ""
        dados = stt.SpeechData(language=LanguageCode("pt-BR"), text=texto)
        return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[dados])


class MotorDeTom:
    """A voz: 50 ms de tom por caractere, em float32 como o Piper."""

    def abrir_fluxo(self, texto: str) -> tuple[int, FluxoPronto]:
        n = int(24000 * 0.05 * len(texto))
        tom = (np.sin(np.arange(n) / 8) * 0.3).astype("<f4")
        return 24000, FluxoPronto(tom.tobytes())


# --- o aparelho (o protocolo do VozNavegador) e o laço mínimo -------------------------------------


class Aparelho:
    """O app ou o navegador: manda o microfone em quadros de 80 ms e toca o que chega."""

    ao_vivo = True

    def __init__(self) -> None:
        self.conexao = self
        self.aberta = True
        self.recebido: list[dict[str, Any]] = []
        self.tocando_ate = 0.0
        self.taxa = 24000
        self.trava = threading.Lock()
        self.falas: list[np.ndarray] = []
        self.live: Live | None = None
        self.parar_mic = threading.Event()

    def controle(self, **dados: Any) -> None:
        with self.trava:
            self.recebido.append(dados)
            if dados.get("tipo") == "voz":
                self.taxa = int(dados["taxa"])
            elif dados.get("tipo") == "parar":
                self.tocando_ate = time.monotonic()

    def binario(self, dados: bytes) -> None:
        with self.trava:
            agora = time.monotonic()
            self.tocando_ate = max(self.tocando_ate, agora) + len(dados) / 2 / self.taxa

    @property
    def tocando(self) -> bool:
        with self.trava:
            return time.monotonic() < self.tocando_ate

    def dizer(self, segundos: float) -> None:
        n = int(16000 * segundos)
        self.falas.append((np.random.default_rng(0).normal(0, 4000, n)).astype("<i2"))

    def microfone(self) -> None:
        inicio, n = time.monotonic(), 0
        atual, pos = np.zeros(0, "<i2"), 0
        while not self.parar_mic.is_set():
            if pos >= len(atual) and self.falas:
                atual, pos = self.falas.pop(0), 0
            if pos < len(atual):
                pedaco = atual[pos : pos + QUADRO]
                pedaco = np.pad(pedaco, (0, QUADRO - len(pedaco)))
                pos += QUADRO
            else:
                pedaco = np.zeros(QUADRO, "<i2")
            if self.live is not None:
                self.live.receber(pedaco.tobytes())
            n += 1
            time.sleep(max(0.0, inicio + n * QUADRO_S - time.monotonic()))


class Laco:
    """Os efeitos como o `laco.py` executa, com um cérebro falso de latência conhecida."""

    def __init__(self, roteiro: "queue.Queue[str]") -> None:
        self.eventos: queue.Queue[Any] = queue.Queue()
        self.maquina = e.Maquina(estado=e.Estado.ATIVO)
        self.numero = self.ultima = self.vistos = self.marca = 0
        self.pedidos: list[str] = []
        self.historia: list[str] = []  # eventos e efeitos, em ordem
        self.pensa_s = 0.3
        self.live = Live(
            chave=lambda: "chave-de-teste",
            motor_voz=MotorDeTom(),
            ao_pedido=lambda t, f, c: self.eventos.put(e.FalaAoVivo(t, f, c)),
            ao_interromper=lambda: self.eventos.put(e.Interrompido()),
            ao_ociosa=self._ociosa,
            pecas=Pecas(
                vad=VadPorVolume(),
                stt=lambda: TranscritorDeRoteiro(roteiro),
                aquecimento_eco_s=0.0,
            ),
        )
        self.parar = threading.Event()

    def _ociosa(self, numero: int) -> None:
        if numero >= self.ultima:
            self.eventos.put(e.FalaOcioso())

    def _cerebro(self, texto: str, marca: int) -> None:
        time.sleep(self.pensa_s)
        if "apaga" in texto:
            if marca == self.marca:
                self.eventos.put(e.PedidoAprovacao("Vou apagar o arquivo. Aprovo?"))
            return
        if "curta" in texto:  # como a via rápida passando a vez: o aviso, e o resto bem depois
            self.eventos.put(e.Frase("Deixa eu ver."))
            time.sleep(2.0)
        resposta = ["Uma resposta bem comprida, que leva alguns segundos."] * (
            3 if "longa" in texto else 1
        )
        for frase in resposta:
            if marca != self.marca:
                return
            self.eventos.put(e.Frase(frase))
        if marca == self.marca:
            self.eventos.put(e.RespostaFim())

    def _executar(self, ef: Any) -> None:
        self.historia.append(type(ef).__name__)
        match ef:
            case e.Falar(texto):
                self.numero += 1
                self.ultima = self.numero
                self.live.falar(texto, self.numero, None)
            case e.EnviarAoCerebro(texto):
                self.marca += 1
                self.pedidos.append(texto)
                threading.Thread(target=self._cerebro, args=(texto, self.marca)).start()
            case e.InterromperCerebro():
                self.marca += 1
            case e.CortarFala():
                self.live.parar()
            case e.ResponderAprovacao(aprovado, _):
                self.eventos.put(e.Frase("Apagado." if aprovado else "Não apaguei."))
                self.eventos.put(e.RespostaFim())

    def rodar(self) -> None:
        while not self.parar.is_set():
            try:
                ev = self.eventos.get(timeout=0.05)
            except queue.Empty:
                ev = e.Tempo()
            if isinstance(ev, e.FalaAoVivo):
                self.vistos += 1
            if not isinstance(ev, e.Tempo):
                self.historia.append(type(ev).__name__)
            for ef in self.maquina.tratar(ev, time.monotonic()):
                self._executar(ef)
            m = self.maquina
            acabou = m.cerebro_terminou or m.estado not in (e.Estado.PENSANDO, e.Estado.FALANDO)
            self.live.acompanhar(acabou, self.vistos)

    def esperar(self, condicao: Any, prazo: float = 10.0) -> bool:
        fim = time.monotonic() + prazo
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.02)
        return False


@pytest.fixture
def conversa() -> Iterator[tuple[Laco, Aparelho, "queue.Queue[str]"]]:
    roteiro: queue.Queue[str] = queue.Queue()
    laco = Laco(roteiro)
    aparelho = Aparelho()
    assert laco.live.preparar()
    threading.Thread(target=laco.rodar, daemon=True).start()
    assert laco.live.ligar(aparelho), laco.live.erro
    aparelho.live = laco.live
    laco.eventos.put(e.AoVivo(True))
    threading.Thread(target=aparelho.microfone, daemon=True).start()
    try:
        yield laco, aparelho, roteiro
    finally:
        aparelho.parar_mic.set()
        laco.live.desligar()
        laco.parar.set()


def _vez(laco: Laco, aparelho: Aparelho, roteiro: "queue.Queue[str]", texto: str) -> None:
    roteiro.put(texto)
    aparelho.dizer(0.8)


# --- os cenários ----------------------------------------------------------------------------------


def test_a_fala_vira_pedido_e_a_resposta_volta_pela_voz(conversa: Any) -> None:
    laco, aparelho, roteiro = conversa
    _vez(laco, aparelho, roteiro, "Que horas são?")
    assert laco.esperar(lambda: laco.pedidos == ["Que horas são?"])
    assert laco.esperar(lambda: aparelho.tocando)
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.OUVINDO and not aparelho.tocando)
    tipos = [m["tipo"] for m in aparelho.recebido]
    assert tipos[0] == "voz" and "fim" in tipos and "parar" not in tipos
    assert "Interrompido" not in laco.historia


def test_frase_curta_vai_a_voz_sem_esperar_o_resto(conversa: Any) -> None:
    """ "Deixa eu ver." sai na hora, mesmo com o resto da resposta 2 s depois."""
    laco, aparelho, roteiro = conversa
    laco.pensa_s = 0.0
    _vez(laco, aparelho, roteiro, "Uma pergunta curta.")
    assert laco.esperar(lambda: "Falar" in laco.historia)
    falou = time.monotonic()
    assert laco.esperar(lambda: aparelho.tocando, 1.5), "a frase curta esperou o resto"
    assert time.monotonic() - falou < 1.5


def test_falar_por_cima_corta_o_ze_e_interrompe_o_cerebro(conversa: Any) -> None:
    laco, aparelho, roteiro = conversa
    laco.pensa_s = 0.0
    _vez(laco, aparelho, roteiro, "Me dá uma resposta longa.")
    assert laco.esperar(lambda: aparelho.tocando)
    time.sleep(1.0)
    _vez(laco, aparelho, roteiro, "Espera, para.")
    assert laco.esperar(lambda: {"tipo": "parar"} in aparelho.recebido, 3.0)
    assert laco.esperar(lambda: "Interrompido" in laco.historia)
    assert laco.esperar(lambda: laco.pedidos[-1:] == ["Espera, para."])
    assert laco.historia.index("Interrompido") < laco.historia.index("CortarFala")


def test_o_que_a_pessoa_emenda_enquanto_o_ze_pensa_vai_junto(conversa: Any) -> None:
    laco, aparelho, roteiro = conversa
    laco.pensa_s = 1.5
    _vez(laco, aparelho, roteiro, "Qual é a capital da França?")
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.PENSANDO)
    _vez(laco, aparelho, roteiro, "E da Itália também.")
    assert laco.esperar(
        lambda: laco.pedidos[-1:] == ["Qual é a capital da França? E da Itália também."]
    ), laco.pedidos
    assert "InterromperCerebro" in laco.historia


def test_aviso_sai_pela_sessao_e_o_ze_volta_a_ouvir(conversa: Any) -> None:
    laco, aparelho, _ = conversa
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.OUVINDO)
    laco.eventos.put(e.Aviso("A sessão Loja terminou."))
    assert laco.esperar(lambda: aparelho.tocando)
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.OUVINDO and not aparelho.tocando)
    assert laco.pedidos == []


def test_confirmacao_pela_voz_no_live(conversa: Any) -> None:
    laco, aparelho, roteiro = conversa
    _vez(laco, aparelho, roteiro, "Ei, apaga o arquivo teste.")
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.CONFIRMANDO)
    assert laco.esperar(lambda: not laco.maquina.pergunta_falando)  # a pergunta terminou de tocar
    _vez(laco, aparelho, roteiro, "Sim, pode apagar.")
    assert laco.esperar(lambda: "ResponderAprovacao" in laco.historia)
    assert laco.esperar(lambda: laco.maquina.estado is e.Estado.OUVINDO and not aparelho.tocando)
    assert laco.pedidos == ["Ei, apaga o arquivo teste."]  # o "sim" respondeu, não foi ao cérebro


def test_o_ze_cortar_a_propria_fala_nao_vira_interrupcao(conversa: Any) -> None:
    laco, aparelho, roteiro = conversa
    laco.pensa_s = 0.0
    _vez(laco, aparelho, roteiro, "Me dá uma resposta longa.")
    assert laco.esperar(lambda: aparelho.tocando)
    laco.eventos.put(e.Digitado("outra coisa"))  # escrever corta a resposta (CortarFala)
    assert laco.esperar(lambda: {"tipo": "parar"} in aparelho.recebido, 3.0)
    time.sleep(0.5)
    assert "Interrompido" not in laco.historia


# --- peças puras ----------------------------------------------------------------------------------


def test_pedido_do_turno_junta_o_que_ficou_sem_resposta() -> None:
    assert pedido_do_turno(["Oi.", "Que horas são?"], "") == "Que horas são?"
    assert (
        pedido_do_turno(["E da Itália?"], "Capital da França?") == "Capital da França? E da Itália?"
    )
    assert pedido_do_turno([], "") == ""


def test_interrompido_na_maquina() -> None:
    m = e.Maquina(estado=e.Estado.FALANDO, ao_vivo=True, cerebro_terminou=False)
    m.aviso_falando = None
    efeitos = m.tratar(e.Interrompido(), 10.0)
    assert e.CortarFala() in efeitos and e.InterromperCerebro() in efeitos
    assert (m.estado, m.autorizado, m.cerebro_terminou) == (e.Estado.OUVINDO, True, True)

    m = e.Maquina(estado=e.Estado.FALANDO, ao_vivo=True)
    m.aviso_falando = "A sessão Loja terminou."
    assert m.tratar(e.Interrompido(), 10.0) == [
        e.CortarFala(),
        e.ReterAviso("A sessão Loja terminou."),  # o aviso cortado volta para a fila
    ]

    m = e.Maquina(estado=e.Estado.CONFIRMANDO, ao_vivo=True)
    m.pergunta_falando = True
    assert m.tratar(e.Interrompido(), 10.0) == []
    assert (m.estado, m.pergunta_falando) == (e.Estado.CONFIRMANDO, False)  # já é a resposta

    m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True)
    assert m.tratar(e.Interrompido(), 10.0) == [] and m.estado is e.Estado.OUVINDO


def test_ao_vivo_concordar_nao_vira_pedido_mas_responde_uma_pergunta() -> None:
    """ "Entendi." mandado ao cérebro virava ação (teste de 27/10/2026); depois de uma pergunta
    do Zé, o "beleza" é a resposta."""
    for fala in ("Entendi.", "Beleza!", "Tá bom.", "uhum, certo"):
        m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True, autorizado=True)
        assert m.tratar(e.FalaAoVivo(fala), 2.0) == [] and m.estado is e.Estado.OUVINDO, fala
        assert m.autorizado
    m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True, autorizado=True)
    m.ze_perguntou = lambda: True
    assert m.tratar(e.FalaAoVivo("Beleza."), 2.0) == [e.EnviarAoCerebro("Beleza.")]
    m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True, autorizado=True)
    assert m.tratar(e.FalaAoVivo("Entendi, e o n8n?"), 2.0) == [
        e.EnviarAoCerebro("Entendi, e o n8n?")
    ]


def test_fala_ao_vivo_vale_como_fim_de_fala() -> None:
    m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True, autorizado=True)
    assert m.tratar(e.FalaAoVivo("que horas são", 1.0, 1.4), 2.0) == [
        e.EnviarAoCerebro("que horas são")
    ]
    m = e.Maquina(estado=e.Estado.OUVINDO, ao_vivo=True, autorizado=True)
    assert m.tratar(e.FalaAoVivo("ok"), 2.0) == [] and m.estado is e.Estado.OUVINDO


# --- o detector de fim de fala de verdade ---------------------------------------------------------

MODELOS = Path.home() / ".local/share/zervis/modelos/hf"
DETECTOR = """
import asyncio, json, sys
from livekit.agents import llm
from livekit.agents.inference_runner import _InferenceRunner
from livekit.plugins.turn_detector import multilingual
from zervis.voz.live import _ExecutorLocal, _detector

ex = _ExecutorLocal(_InferenceRunner.registered_runners,
                    multilingual._EUORunnerMultilingual.INFERENCE_METHOD)
ex.aquecer()
d = _detector(ex, multilingual)

async def nota(texto):
    ctx = llm.ChatContext()
    ctx.add_message(role="user", content=texto)
    return await d.predict_end_of_turn(ctx)

async def main():
    print(json.dumps({t: await nota(t) for t in sys.argv[1:]}))

asyncio.run(main())
"""


@pytest.mark.skipif(
    not (MODELOS / "models--livekit--turn-detector").is_dir(), reason="sem o modelo"
)
def test_detector_de_fim_de_fala_entende_frase_pela_metade() -> None:
    """O modelo do LiveKit, com o executor local do Live: frase pela metade fica com nota baixa
    (o Zé espera), frase completa com nota alta (responde já)."""
    pela_metade, completa = "Quero que você", "Que horas são agora?"
    ambiente = {**os.environ, "HF_HUB_CACHE": str(MODELOS), "HF_HUB_OFFLINE": "1"}
    saida = subprocess.run(  # noqa: S603 (o próprio Python, script fixo)
        [sys.executable, "-W", "ignore", "-c", DETECTOR, pela_metade, completa],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
        check=True,
    )
    notas = json.loads(saida.stdout.strip().splitlines()[-1])
    assert notas[pela_metade] < 0.2 < notas[completa], notas


# --- a ligação com a voz conectada (o serviço remoto) -------------------------------------------


class LiveFalso:
    def __init__(self, disponivel: bool = True) -> None:
        self.disponivel = disponivel
        self.fonte: Any = None
        self.recebidos: list[bytes] = []
        self.chamadas: list[str] = []

    @property
    def ativo(self) -> bool:
        return self.fonte is not None

    def ligar(self, fonte: Any) -> bool:
        self.chamadas.append("ligar")
        self.fonte = fonte
        return True

    def desligar(self) -> None:
        self.chamadas.append("desligar")
        self.fonte = None

    def receber(self, quadro: bytes) -> None:
        self.recebidos.append(quadro)


def _remoto(live: LiveFalso, modo_fala: str = "avisos") -> Any:
    from types import SimpleNamespace

    from zervis.nucleo.servicos.remoto import ServicoRemoto

    recebidos: list[bytes] = []
    n = SimpleNamespace(
        _fonte=None,
        captura=SimpleNamespace(
            fechar=lambda: None,
            abrir=lambda: None,
            remota=lambda ligada: None,
            receber=recebidos.append,
        ),
        microfone_travado=False,
        modo_fala=modo_fala,
        maquina=e.Maquina(estado=e.Estado.ATIVO),
        voz=SimpleNamespace(muda=False, parar=lambda: None, destino=None),
        rostos=SimpleNamespace(marcar=lambda *a: None),
        eventos=queue.Queue(),
        live=live,
    )
    servico = ServicoRemoto(n)
    n._fonte_remota = servico._fonte_remota
    n._quadro_remoto = servico._quadro_remoto
    return servico, n, recebidos


def _voz(ao_vivo: bool) -> Any:
    from zervis.transporte.navegador import VozNavegador

    return VozNavegador(Aparelho(), ao_vivo=ao_vivo)  # type: ignore[arg-type]


def test_a_voz_ao_vivo_conectada_vai_para_o_live_e_sai_ao_desconectar() -> None:
    live = LiveFalso()
    servico, n, recebidos = _remoto(live)
    voz = _voz(ao_vivo=True)
    servico._fonte_remota(voz, True)
    assert live.fonte is voz and n.eventos.get_nowait() == e.AoVivo(True)
    servico._quadro_remoto(voz, b"quadro")
    assert live.recebidos == [b"quadro"] and recebidos == []  # o recorte não recebe nada
    servico._fonte_remota(voz, False)
    assert live.chamadas == ["ligar", "desligar"]


def test_o_motor_rapido_entra_e_sai_com_o_live() -> None:
    """A via rápida só no Live: ao conectar e ao sair, o núcleo troca o motor (em segundo plano)."""
    live = LiveFalso()
    servico, n, _ = _remoto(live)
    trocas: queue.Queue[bool] = queue.Queue()
    n.aplicar_via_rapida = lambda: trocas.put(live.ativo)
    voz = _voz(ao_vivo=True)
    servico._fonte_remota(voz, True)
    assert trocas.get(timeout=2) is True
    servico._fonte_remota(voz, False)
    assert trocas.get(timeout=2) is False


def test_sem_o_live_ou_no_modo_chamado_segue_o_recorte() -> None:
    for live, ao_vivo in ((LiveFalso(disponivel=False), True), (LiveFalso(), False)):
        servico, _, recebidos = _remoto(live)
        voz = _voz(ao_vivo=ao_vivo)
        servico._fonte_remota(voz, True)
        servico._quadro_remoto(voz, b"quadro")
        assert live.chamadas == [] and recebidos == [b"quadro"]


def test_no_live_so_o_bipe_de_conectar(tmp_path: Path) -> None:
    """Teste de 27/10/2026: no Live o Zé bipava a cada "sua vez" (depois de um aviso, de uma
    pergunta, do chamado sozinho). Numa conversa contínua, fica só o bipe de conectar."""
    from types import SimpleNamespace

    from tests.test_latencia_nucleo import NucleoCronometrado

    bipes: list[int] = []

    class Nucleo(NucleoCronometrado):
        def _tocar_bip(self) -> None:
            bipes.append(1)

    n = Nucleo(tmp_path)
    n._pedidos_ao_vivo = 0
    n.live = SimpleNamespace(  # type: ignore[assignment]
        ativo=True, parar=lambda: None, acompanhar=lambda *a: None, falar=lambda *a: None
    )
    n.tratar(e.AoVivo(True))
    assert bipes == [1]  # conectou: o bipe de "pronto"
    n.tratar(e.FalaAoVivo("Zé?"))  # o chamado sozinho
    n.maquina.estado = e.Estado.FALANDO  # um aviso do Mãos livres (hoje o Live) no fim
    n.maquina.aviso_falando, n.maquina.escutar_depois = "A sessão Loja terminou.", True
    n.tratar(e.FalaOcioso())  # o fim do aviso, que abria a escuta com bipe
    assert bipes == [1]
    n.live = None  # type: ignore[assignment]
    n.tratar(e.FalaAoVivo("Zé?"))  # fora do Live, o bipe de "estou ouvindo" continua
    assert bipes == [1, 1]
