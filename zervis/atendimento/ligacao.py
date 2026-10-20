"""A recepcionista: o agente atende ligações do WhatsApp em tempo real (ADR 0031, etapa 2).

O caminho do Ligatia, sem a sala do LiveKit no meio (uma peça a menos, inclusive numa VPS): o
WaCalls entrega o áudio da chamada por WebSocket (PCM 16 kHz mono, Int16LE) e recebe a voz de
volta no mesmo canal.

- **Ouvir:** Deepgram nova-3 em streaming durante a ligação inteira. O turno do cliente fecha no
  `speech_final` do Deepgram, a não ser que a frase tenha ficado pela metade (a mesma regra da
  voz do Zé, `escuta.ficou_no_meio`); aí espera o fim da fala (`UtteranceEnd`).
- **Pensar:** o mesmo agente do texto (persona, conhecimento, quando passar), com as regras de
  ligação no prompt, pelo motor rápido do Zé. Um motor por ligação: com estado, ele já guarda a
  conversa e recebe só a fala nova.
- **Falar:** a voz do Cadu (Piper), frase a frase, enquanto o modelo ainda escreve. O WaCalls
  envia na hora o que recebe, então o ritmo é daqui: um quadro de 60 ms a cada 60 ms.
- **Interromper:** se o cliente começa a falar enquanto o agente fala, a voz para e a resposta em
  andamento é descartada.
- **Passar para você:** o agente diz que alguém vai retornar, encerra a ligação, para de atender
  aquele contato e o Zé avisa. `[[DESLIGAR]]` encerra depois da despedida.
"""

import asyncio
import contextlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import numpy as np

from zervis.atendimento import agente
from zervis.voz import deepgram
from zervis.voz.escuta import ficou_no_meio
from zervis.voz.fala import para_fala

log = logging.getLogger(__name__)

TAXA = 16000
QUADRO = 960 * 2  # 60 ms de PCM 16 kHz Int16LE: o quadro do codec do WhatsApp
QUADRO_S = 0.06
DURACAO_MAXIMA_S = 15 * 60
SILENCIO_MAXIMO_S = 45.0  # ninguém fala: o agente pergunta uma vez e depois encerra
PALAVRAS_PARA_INTERROMPER = 2
LIGACOES_JUNTAS = 2
ESPERA_ANTECIPAR_S = 0.25  # o texto parou de mudar por isto: a resposta começa em silêncio
REACAO_S = 0.8  # sem nenhuma palavra do modelo até aqui, uma reação curta evita o silêncio
REACOES = ("Uhum.", "Certo.", "Entendi.")
_SO_REACAO = frozenset({"uhum", "certo", "entendi", "claro", "ok", "ta", "beleza", "hum"})
_FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")
_DESLIGAR = re.compile(r"\[\[\s*DESLIGAR\s*\]\]", re.I)
PARAMETROS = {
    **deepgram.PARAMETROS,
    "endpointing": "400",
    "utterance_end_ms": "1200",
    "vad_events": "true",
}
REGRAS_DA_LIGACAO = (
    "Nesta ligação:\n"
    "- Para passar para uma pessoa: diga que alguém da equipe vai retornar a ligação em breve e "
    "termine com [[PASSAR: motivo]].\n"
    "- Concluir um assunto não encerra a ligação: pergunte se pode ajudar em mais alguma coisa. "
    "Só quando o cliente se despedir, despeça-se em uma frase e termine com [[DESLIGAR]]."
)


class Motor(agente.Motor, Protocol):
    async def interromper(self) -> None: ...


class Conexao(Protocol):
    """O WebSocket do WaCalls (PCM nos dois sentidos)."""

    async def send(self, dados: bytes) -> None: ...
    def __aiter__(self) -> AsyncIterator[Any]: ...


def sistema(p: agente.Perfil) -> str:
    return agente.sistema(p, "voz") + "\n\n" + REGRAS_DA_LIGACAO


def saudacao(p: agente.Perfil) -> str:
    empresa = f", da {p.empresa}" if p.empresa else ""
    return f"Olá! Aqui é {p.nome}{empresa}. Como posso ajudar?"


# Do Ligatia (RECEBE_LIGACAO/assistente.py, `_normalizar_voz` e `_RE_META`), do mesmo autor:
# o que o modelo escreve abreviado vira o que se fala, e frase de raciocínio interno nunca vira voz.
_RE_HORA_MIN = re.compile(r"\b(\d{1,2})\s*h\s*(\d{2})\b")
_RE_HORA = re.compile(r"(?<=\d)\s*h\b")
_RE_MIN = re.compile(r"(?<=\d)\s*min\b")
_RE_SEG = re.compile(r"(?<=\d)\s*seg\b")
_RE_KG = re.compile(r"(?<=\d)\s*kg\b")
_RE_KM = re.compile(r"(?<=\d)\s*km\b")
_RE_REAIS = re.compile(r"R\$\s*([\d.]*\d)(?:,(\d{1,2}))?", re.IGNORECASE)
_RE_CIFRAO = re.compile(r"R\$\s*", re.IGNORECASE)
_RE_REAIS_DUP = re.compile(r"\breais\s+reais\b", re.IGNORECASE)
_RE_PCT = re.compile(r"(?<=\d)\s*%")
_RE_NUMERO = re.compile(r"\bn[º°]", re.IGNORECASE)
_RE_META = re.compile(
    r"(?:\b(?:devo|preciso)\s+(?:encerrar|finalizar|desligar)\s+(?:a\s+)?(?:chamada|liga\w+))"
    r"|(?:\bo\s+cliente\s+(?:j[áa]\s+)?(?:se\s+despediu|encerrou|pediu|quer|disse|falou))"
    r"|(?:\b(?:let me|i should|i will|i need to|we need to|i can help"
    r"|the user|the customer|ok so)\b)",
    re.IGNORECASE,
)


def _reais(m: "re.Match[str]") -> str:
    """R$ 1.500,00 -> '1500 reais'; R$ 50,50 -> '50 reais e 50 centavos'."""
    inteiro, centavos = m.group(1), m.group(2)
    if centavos is None and "." in inteiro:
        cabeca, _, cauda = inteiro.rpartition(".")
        if cabeca and len(cauda) == 2:
            inteiro, centavos = cabeca, cauda
    inteiro = inteiro.replace(".", "")
    try:
        n = int(inteiro)
    except ValueError:
        return f"{inteiro} reais"
    texto = f"{n} {'real' if n == 1 else 'reais'}"
    if centavos:
        c = int((centavos + "00")[:2])
        if c:
            texto += f" e {c} {'centavo' if c == 1 else 'centavos'}"
    return texto


def normalizar_voz(texto: str) -> str:
    """Abreviações que a voz leria errado: '8h30' -> '8 horas e 30', 'R$ 150' -> '150 reais'."""
    t = _RE_HORA_MIN.sub(r"\1 horas e \2", texto)
    t = _RE_HORA.sub(" horas", t)
    t = _RE_MIN.sub(" minutos", t)
    t = _RE_SEG.sub(" segundos", t)
    t = _RE_KG.sub(" quilos", t)
    t = _RE_KM.sub(" quilômetros", t)
    t = _RE_REAIS.sub(_reais, t)
    t = _RE_CIFRAO.sub("", t)
    t = _RE_REAIS_DUP.sub("reais", t)
    t = _RE_PCT.sub(" por cento", t)
    return _RE_NUMERO.sub("número", t)


def e_raciocinio(frase: str) -> bool:
    """Frase de bastidor do modelo ("devo encerrar a chamada", "o cliente já se despediu")."""
    return _RE_META.search(frase) is not None


async def aquecer_motor(motor: Any, instrucoes: str, saudacao_dita: str) -> None:
    """Pré-aquecimento (o `prewarm` do Ligatia): iniciar não basta; a primeira resposta de um
    motor leva o dobro das seguintes (medido: 3,6 s contra 1,7 s). Aquece com a própria saudação,
    então a conversa do motor fica verdadeira: é exatamente o que o cliente ouve primeiro."""
    await motor.iniciar(instrucoes)
    pedido = (
        "[Sistema: a ligação de um cliente acaba de ser atendida. Responda apenas com a "
        f"saudação, exatamente assim: {saudacao_dita}]"
    )
    async for _ in motor.gerar(instrucoes, [{"role": "user", "content": pedido}]):
        pass


def para_16k(audio: np.ndarray, taxa: int) -> bytes:
    """Float32 na taxa do Piper -> Int16LE a 16 kHz (interpolação linear: voz, não música)."""
    if taxa != TAXA and len(audio):
        tempo = np.arange(0, len(audio) * TAXA // taxa) * (taxa / TAXA)
        audio = np.interp(tempo, np.arange(len(audio)), audio).astype(np.float32)
    return bytes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())


def falar_com_piper(texto: str) -> bytes:
    from zervis.voz import piper

    taxa, fluxo = piper.PADRAO.abrir_fluxo(texto)
    dados = b"".join(iter(fluxo.read1, b""))
    return para_16k(np.frombuffer(dados, "<f4"), taxa)


def frases_prontas(buffer: str) -> tuple[list[str], str]:
    """As frases completas do que o modelo já escreveu e o resto, que ainda pode crescer. A marca
    `[[...]]` nunca vai para a voz."""
    corte = buffer.find("[[")
    falavel = buffer if corte < 0 else buffer[:corte]
    partes = _FIM_DE_FRASE.split(falavel)
    if corte >= 0:
        return [p for p in partes if p.strip()], buffer[corte:]
    return [p for p in partes[:-1] if p.strip()], partes[-1]


class Tocador:
    """Manda a voz ao WaCalls no ritmo da fala; `calar` descarta o que ainda não tocou."""

    def __init__(self, enviar: Callable[[bytes], Any], quadro_s: float = QUADRO_S) -> None:
        self.enviar = enviar
        self.quadro_s = quadro_s
        self.fila: asyncio.Queue[bytes] = asyncio.Queue()
        self._tocando = False
        self._quieto = asyncio.Event()
        self._quieto.set()

    @property
    def falando(self) -> bool:
        return self._tocando or not self.fila.empty()

    def tocar(self, pcm: bytes) -> None:
        for i in range(0, len(pcm), QUADRO):
            self.fila.put_nowait(pcm[i : i + QUADRO].ljust(QUADRO, b"\0"))
        if pcm:
            self._quieto.clear()

    def calar(self) -> None:
        while not self.fila.empty():
            self.fila.get_nowait()
        if not self._tocando:
            self._quieto.set()

    async def terminar(self) -> None:
        await self._quieto.wait()

    async def rodar(self) -> None:
        proximo = time.monotonic()
        while True:
            quadro = await self.fila.get()
            self._tocando = True
            proximo = max(proximo, time.monotonic())
            await self.enviar(quadro)
            proximo += self.quadro_s
            await asyncio.sleep(max(0.0, proximo - time.monotonic()))
            if self.fila.empty():
                self._tocando = False
                self._quieto.set()


class Ouvido:
    """O Deepgram durante a ligação inteira: recebe o PCM e entrega (tipo, texto)."""

    def __init__(self, chave: str) -> None:
        self.chave = chave
        self._ws: Any = None

    async def abrir(self) -> None:
        from websockets.asyncio.client import connect

        url = f"{deepgram.ENDERECO}?{urlencode(PARAMETROS)}"
        self._ws = await connect(url, additional_headers={"Authorization": f"Token {self.chave}"})

    async def enviar(self, pcm: bytes) -> None:
        if self._ws is not None:
            await self._ws.send(pcm)

    async def eventos(self) -> AsyncIterator[tuple[str, str]]:
        """("parcial", texto), ("final", texto), ("fim_da_fala", texto) e ("pausa", "")."""
        async for bruta in self._ws:
            if isinstance(bruta, bytes):
                continue
            dados = json.loads(bruta)
            if dados.get("type") == "UtteranceEnd":
                yield "pausa", ""
                continue
            if dados.get("type") != "Results":
                continue
            alternativas = (dados.get("channel") or {}).get("alternatives") or [{}]
            texto = str(alternativas[0].get("transcript", "")).strip()
            if not dados.get("is_final"):
                if texto:
                    yield "parcial", texto
            elif dados.get("speech_final"):
                yield "fim_da_fala", texto
            elif texto:
                yield "final", texto

    async def fechar(self) -> None:
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()


class Chamada:
    """Uma ligação atendida, do "Olá" ao fim."""

    def __init__(
        self,
        conexao: Conexao,
        ouvido: Any,
        motor: Any,
        perfil: agente.Perfil,
        telefone: str,
        nome: str,
        registros: agente.Registros,
        ao_passar: Callable[[str, str], None],
        falar: Callable[[str], bytes] = falar_com_piper,
        quadro_s: float = QUADRO_S,
        iniciado: bool = False,
        saudacao_pronta: bytes | None = None,
    ) -> None:
        self.conexao = conexao
        self.ouvido = ouvido
        self.motor = motor
        self.perfil = perfil
        self.telefone = telefone
        self.nome = nome or (f"+{telefone}" if telefone else "Um contato")
        self.registros = registros
        self.ao_passar = ao_passar
        self.falar = falar
        self.tocador = Tocador(conexao.send, quadro_s)
        self.instrucoes = sistema(perfil)
        self.iniciado = iniciado  # o motor veio pronto da reserva (pré-aquecido)
        self.saudacao_pronta = saudacao_pronta  # a saudação já sintetizada
        self.encerrar = asyncio.Event()
        self.ouvindo: list[str] = []  # o turno do cliente, até fechar
        self.parcial = ""  # o trecho ainda provisório do Deepgram
        self.parcial_em = 0.0
        self.resposta: asyncio.Task[None] | None = None
        self.antecipada: tuple[str, asyncio.Event, asyncio.Task[None]] | None = None
        self.antecipacoes = [0, 0]  # [aproveitadas, descartadas]
        self.ultima_fala = time.monotonic()
        self.cutucou = False
        self.desfecho = "normal"
        self._preparo: asyncio.Future[None] | None = None
        self._interrompendo: asyncio.Future[None] | None = None
        self.sem_resposta: str | None = None  # a fala em resposta, enquanto nada foi dito
        self.reacoes: list[bytes] = []  # "Uhum.", "Certo.", "Entendi." já sintetizados
        self._reagiu = False
        self._vez_da_reacao = 0

    def _anotar(self, quem: str, texto: str) -> None:
        if self.telefone and texto:
            self.registros.anotar(self.telefone, quem, texto)

    async def _sintetizar(self, texto: str) -> bytes:
        if e_raciocinio(texto):
            log.warning("ligação: frase de bastidor barrada antes da voz")
            return b""
        texto = normalizar_voz(para_fala(texto)).strip()
        return await asyncio.to_thread(self.falar, texto) if texto else b""

    async def dizer(self, texto: str) -> None:
        self.tocador.tocar(await self._sintetizar(texto))

    @property
    def antecipa(self) -> bool:
        """Geração antecipada (como o `preemptive_generation` do Ligatia): só com motor sem
        estado, em que uma resposta descartada não deixa rastro na conversa."""
        return not getattr(self.motor, "com_estado", False)

    async def atender(self) -> str:
        """Roda a ligação até o fim; devolve o desfecho (normal, passou, limite, silencio)."""
        tarefas = [
            asyncio.ensure_future(self.tocador.rodar()),
            asyncio.ensure_future(self._receber_audio()),
            asyncio.ensure_future(self._ouvir()),
            asyncio.ensure_future(self._vigiar_antecipacao()),
        ]
        inicio = time.monotonic()
        try:
            if not self.iniciado:  # o motor aquece enquanto a saudação toca
                self._preparo = asyncio.ensure_future(
                    aquecer_motor(self.motor, self.instrucoes, saudacao(self.perfil))
                )
            if self.saudacao_pronta:
                self.tocador.tocar(self.saudacao_pronta)
            else:
                await self.dizer(saudacao(self.perfil))
            self._anotar("agente", saudacao(self.perfil))
            await self._preparar_reacoes()
            while not self.encerrar.is_set():
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self.encerrar.wait(), 1.0)
                if any(t.done() for t in tarefas[1:3]):
                    break  # a chamada ou o Deepgram caiu
                if time.monotonic() - inicio > DURACAO_MAXIMA_S:
                    self.desfecho = "limite"
                    await self._despedir("Nosso tempo de ligação acabou. Obrigado por ligar!")
                elif self._calado() > SILENCIO_MAXIMO_S:
                    if self.cutucou:
                        self.desfecho = "silencio"
                        await self._despedir("Como não te ouço, vou encerrar. Até logo!")
                    else:
                        self.cutucou = True
                        self.ultima_fala = time.monotonic()
                        await self.dizer("Você ainda está aí?")
            return self.desfecho
        finally:
            self._descartar_antecipada()
            for t in (self.resposta, self._preparo):
                if t is not None:
                    t.cancel()
            for t in tarefas:
                t.cancel()
            await asyncio.gather(*tarefas, return_exceptions=True)
            with contextlib.suppress(Exception):
                await self.ouvido.fechar()
            with contextlib.suppress(Exception):
                await self.motor.fechar()
            log.info("ligação: antecipações aproveitadas %d, descartadas %d", *self.antecipacoes)

    def _calado(self) -> float:
        if self.tocador.falando or (self.resposta is not None and not self.resposta.done()):
            self.ultima_fala = time.monotonic()
        return time.monotonic() - self.ultima_fala

    async def _despedir(self, frase: str) -> None:
        await self.dizer(frase)
        await self.tocador.terminar()
        self.encerrar.set()

    async def _receber_audio(self) -> None:
        async for mensagem in self.conexao:
            if isinstance(mensagem, bytes) and mensagem:
                await self.ouvido.enviar(mensagem)

    # --- o turno do cliente ---------------------------------------------------------------------

    def _previsto(self) -> str:
        return " ".join(t for t in (*self.ouvindo, self.parcial) if t).strip()

    async def _ouvir(self) -> None:
        async for tipo, texto in self.ouvido.eventos():
            if tipo == "parcial":
                self.ultima_fala = time.monotonic()
                if texto != self.parcial:
                    self.parcial, self.parcial_em = texto, time.monotonic()
                    self._conferir_antecipada()
                if self._interrompe(texto):
                    self._calar()
                continue
            self.parcial = ""
            if texto:
                self.ouvindo.append(texto)
                self.ultima_fala = time.monotonic()
                self.parcial_em = time.monotonic()
                self._conferir_antecipada()
                if self._interrompe(texto):
                    self._calar()
            fecha = tipo == "pausa" or (tipo == "fim_da_fala" and not ficou_no_meio(texto))
            if fecha and self.ouvindo:
                fala = " ".join(self.ouvindo)
                self.ouvindo = []
                self.cutucou = False
                if self.sem_resposta is not None:
                    # o cliente continuou antes de o agente dizer algo: uma resposta só, para tudo
                    fala = f"{self.sem_resposta} {fala}"
                    self._calar()
                self._fechar_turno(fala)

    def _fechar_turno(self, fala: str) -> None:
        if self.antecipada is not None and _mesmas_palavras(self.antecipada[0], fala):
            _, liberar, tarefa = self.antecipada
            self.antecipada = None
            self.antecipacoes[0] += 1
            self.resposta = tarefa
            self.sem_resposta = fala
            liberar.set()  # a resposta já estava sendo pensada: só falta tocar
            return
        self._descartar_antecipada()
        self.resposta = asyncio.ensure_future(self._responder(fala))

    async def _vigiar_antecipacao(self) -> None:
        """Quando o texto para de mudar por um instante, a resposta começa em silêncio."""
        while True:
            await asyncio.sleep(0.05)
            if not self.antecipa or self.antecipada is not None or self.sem_resposta is not None:
                continue
            if self.resposta is not None and not self.resposta.done():
                continue
            previsto = self._previsto()
            if not previsto or ficou_no_meio(previsto):
                continue
            if time.monotonic() - self.parcial_em >= ESPERA_ANTECIPAR_S:
                liberar = asyncio.Event()
                tarefa = asyncio.ensure_future(self._responder(previsto, liberar))
                self.antecipada = (previsto, liberar, tarefa)

    def _conferir_antecipada(self) -> None:
        if self.antecipada is not None and not _mesmas_palavras(
            self.antecipada[0], self._previsto()
        ):
            self._descartar_antecipada()  # o cliente continuou falando

    def _descartar_antecipada(self) -> None:
        if self.antecipada is not None:
            self.antecipada[2].cancel()
            self.antecipada = None
            self.antecipacoes[1] += 1

    def _interrompe(self, texto: str) -> bool:
        respondendo = self.resposta is not None and not self.resposta.done()
        return (self.tocador.falando or respondendo) and len(
            texto.split()
        ) >= PALAVRAS_PARA_INTERROMPER

    def _calar(self) -> None:
        self.tocador.calar()
        if self.resposta is not None and not self.resposta.done():
            self.resposta.cancel()
            interromper = getattr(self.motor, "interromper", None)
            if interromper is not None:
                self._interrompendo = asyncio.ensure_future(interromper())

    # --- a resposta -------------------------------------------------------------------------

    async def _preparar_reacoes(self) -> None:
        if not self.reacoes:
            self.reacoes = [await self._sintetizar(r) for r in REACOES]

    async def _reagir(self) -> None:
        """Se o modelo demora, uma reação curta ('Uhum.') antes da resposta, como numa ligação."""
        await asyncio.sleep(REACAO_S)
        if self.sem_resposta is not None and not self.tocador.falando and self.reacoes:
            self._reagiu = True
            self.tocador.tocar(self.reacoes[self._vez_da_reacao % len(self.reacoes)])
            self._vez_da_reacao += 1

    async def _dizer_resposta(self, frase: str, liberar: asyncio.Event | None) -> None:
        from zervis.cerebro.rapido import palavras

        if self._reagiu and set(palavras(frase)) <= _SO_REACAO:
            self._reagiu = False  # a reação já foi dita: o "Entendi!" do modelo seria repetido
            return
        self._reagiu = False
        pcm = await self._sintetizar(frase)  # a voz fica pronta antes da hora de tocar
        if liberar is not None:
            await liberar.wait()
        if self.sem_resposta is not None:  # a primeira frase: a fala do cliente vale como turno
            self._anotar("cliente", self.sem_resposta)
            self.sem_resposta = None
        self.tocador.tocar(pcm)

    async def _responder(self, fala: str, liberar: asyncio.Event | None = None) -> None:
        reacao = asyncio.ensure_future(self._reagir()) if liberar is None else None
        try:
            await self._responder_de_fato(fala, liberar)
        finally:
            if reacao is not None:
                reacao.cancel()

    async def _responder_de_fato(self, fala: str, liberar: asyncio.Event | None) -> None:
        if self._preparo is not None:
            await self._preparo
        historico = self.registros.historico(self.telefone) if self.telefone else []
        if liberar is None:
            self.sem_resposta = fala
        if getattr(self.motor, "com_estado", False):
            conteudo = f"O cliente disse:\n<<<\n{fala.replace('<<<', ' ').replace('>>>', ' ')}\n>>>"
        else:
            conteudo = agente.pedido(historico, fala)
        tudo, resto = "", ""
        async for pedaco in self.motor.gerar(
            self.instrucoes, [{"role": "user", "content": conteudo}]
        ):
            tudo += pedaco
            resto += pedaco
            frases, resto = frases_prontas(resto)
            for frase in frases:
                await self._dizer_resposta(frase, liberar)
        frases, _ = frases_prontas(resto + " ")
        for frase in frases:
            await self._dizer_resposta(frase, liberar)
        if liberar is not None:
            await liberar.wait()
        if self.sem_resposta is not None:
            self._anotar("cliente", fala)
            self.sem_resposta = None
        texto, motivo = agente.separar(_DESLIGAR.sub("", tudo))
        self._anotar("agente", texto)
        if motivo is not None:
            self.desfecho = "passou"
            if self.telefone:
                self.registros.pausar(self.telefone, self.nome, f"Ligação: {motivo}")
            self.ao_passar(self.nome, f"ligação, {motivo}")
            await self.tocador.terminar()
            self.encerrar.set()
        elif _DESLIGAR.search(tudo):
            await self.tocador.terminar()
            self.encerrar.set()


def _mesmas_palavras(a: str, b: str) -> bool:
    from zervis.cerebro.rapido import palavras

    return palavras(a) == palavras(b)


def voz_pronta(modelos: Path | None = None) -> bool:
    from zervis.voz import piper

    return piper.PADRAO.modelo.is_file() if modelos is None else (modelos / piper.VOZ).is_file()
