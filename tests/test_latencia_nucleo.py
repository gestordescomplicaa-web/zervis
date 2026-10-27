"""A instrumentação acompanha o fluxo real da máquina, com IO falso e estado isolado."""

import collections
import concurrent.futures
import queue
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from zervis.avisos.fila import Fila
from zervis.cerebro.eco import Eco
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo, Status
from zervis.voz.escuta import Segmentador
from zervis.voz.latencia import Latencias


class VozCronometrada:
    ultimo_erro: str | None = None

    def __init__(self) -> None:
        self.observadores: list[Callable[[float], None]] = []

    def falar(self, texto: str, ao_iniciar: Callable[[float], None] | None = None) -> int:
        if ao_iniciar:
            self.observadores.append(ao_iniciar)
        return len(self.observadores)

    def parar(self) -> None:
        pass


class EscutaCronometrada:
    """O Deepgram de mentira: recebe o áudio e devolve o pedido ao terminar."""

    def enviar(self, dados: bytes) -> None:
        pass

    def terminar(self) -> str:
        return "Qual é a hora?"

    def cancelar(self) -> None:
        pass


class NucleoCronometrado(Nucleo):
    def __init__(self, pasta: Path) -> None:
        self.latencias = Latencias(pasta / "latencias")
        self._turno_atual = None
        self._turno_cerebro = (0, None)
        self._digitado_em = self._fim_fala_em = None
        self._fala_perdida_s = 0.0
        self._antes_do_chamado = collections.deque(maxlen=38)
        self.maquina = e.Maquina(estado=e.Estado.ATIVO)
        self.eventos = queue.Queue()
        self.status = Status()
        self.marca = 0
        self._pedido_em = self._transcricao_inicio = time.monotonic()
        self._ultima_fala = 0
        self._fontes = (0, [])
        self.turnos = []
        self.avisos_falados = []
        self.sessoes = SimpleNamespace(em_foco=("", 0.0))  # type: ignore[assignment]
        self.cerebro, self.provedor = Eco(), "eco"
        self.voz = VozCronometrada()  # type: ignore[assignment]
        self.motor_voz = SimpleNamespace(aquecer=lambda: None, ultimo="piper")  # type: ignore[assignment]
        self.ponte = SimpleNamespace(  # type: ignore[assignment]
            perguntar=lambda t, m: None,
            interromper=lambda: None,
            responder_aprovacao=lambda a, f="": None,
        )
        self.teclado = SimpleNamespace(terminou=lambda: None, falou=lambda t: None)  # type: ignore[assignment]
        self.detector = SimpleNamespace(reiniciar=lambda: None)  # type: ignore[assignment]
        self.anel = SimpleNamespace(parar=lambda: None, expressao=lambda e, t: None)  # type: ignore[assignment]
        self.evidencias = SimpleNamespace(registrar=lambda *a: None)  # type: ignore[assignment]
        self.consumo = SimpleNamespace(somar=lambda *a: None)  # type: ignore[assignment]
        self.uso_ferramentas = SimpleNamespace(somar=lambda *a: None)  # type: ignore[assignment]
        self.fila = Fila(pasta / "avisos.json")
        self.segmentador = Segmentador(fim_silencio_s=0.16)
        self.vad = SimpleNamespace(prever=lambda a: float(np.any(a)), reiniciar=lambda: None)  # type: ignore[assignment]
        self.cfg = {"escuta": {"limiar_vad": 0.5, "registrar_texto": False}}  # type: ignore[assignment]
        self.meio_transcricao = "deepgram"
        self.transcricoes = concurrent.futures.ThreadPoolExecutor(1)
        self.transcrevendo = None
        self.deepgram = SimpleNamespace(  # type: ignore[assignment]
            disponivel=True, nova=EscutaCronometrada, contar=lambda escuta: None
        )
        self.escuta = None

    def _com_nucleo(self, texto: str) -> str:
        return texto

    def _com_avisos(self, texto: str) -> str:
        return texto

    def _registrar_turno(self, turno: dict[str, str]) -> None:
        pass

    def _fim_da_conversa(self) -> None:
        pass

    def _descartar_escuta(self) -> None:
        self.segmentador.limpar()

    def _tocar_bip(self) -> None:
        pass

    def _comando(self, nome: str) -> None:
        self.marca += 1
        self.eventos.put(e.Frase("Comando executado."))
        self.eventos.put(e.RespostaFim())

    def som(self) -> None:
        voz = self.voz
        assert isinstance(voz, VozCronometrada)
        voz.observadores[-1](time.monotonic())

    def concluir(self) -> None:
        self._frase_do_cerebro(self.marca, "Pronto.")
        self._fim_do_cerebro(self.marca, None)
        while not self.eventos.empty():
            self.tratar(self.eventos.get_nowait())
        self.som()
        self.tratar(e.FalaOcioso())


@pytest.fixture
def nucleo(tmp_path: Path) -> Iterator[NucleoCronometrado]:
    n = NucleoCronometrado(tmp_path)
    try:
        yield n
    finally:
        n.transcricoes.shutdown(wait=True)
        n._fechar_latencia("servico_parado")
        n.latencias.fechar()


def test_turno_por_voz_tem_os_cinco_marcos_e_nao_fecha_enquanto_transcreve(
    nucleo: NucleoCronometrado,
) -> None:
    n = nucleo
    n.tratar(e.Ativacao())
    quadro = np.ones(1280, "<i2").tobytes()
    silencio = bytes(2560)
    for q in [quadro, quadro, silencio, silencio]:
        n._quadro(q)
    turno = n._turno_atual
    assert turno is not None
    n.tratar(e.Tempo())
    assert n._turno_atual == turno  # o timer da escuta não é fim da resposta
    n.tratar(n.eventos.get(timeout=3))
    assert n.maquina.estado.value == e.Estado.PENSANDO.value
    n._primeiro_texto_do_cerebro(n.marca, time.monotonic())
    n.concluir()
    assert n.maquina.estado is e.Estado.OUVINDO and n._turno_atual is None
    r = n.latencias.ultimo
    assert r is not None and r["resultado"] == "concluido"
    assert r["origem"] == "voz" and r["transcricao_por"] == "deepgram"
    assert set(r["etapas_ms"]) == {
        "fim_de_turno",
        "transcricao",
        "despacho",
        "cerebro",
        "formacao_frase",
        "entrega_fala",
        "voz",
        "total",
    }


def test_digitado_interrompe_e_callbacks_antigos_nao_marcam_novo_turno(
    nucleo: NucleoCronometrado,
) -> None:
    n = nucleo
    n.tratar(e.Digitado("me diga a hora"))
    marca = n.marca
    n.tratar(e.Frase("Primeira resposta."))
    voz = n.voz
    assert isinstance(voz, VozCronometrada)
    antigo_som = voz.observadores[-1]
    n.tratar(e.Digitado("me diga a data"))
    assert n.latencias.ultimo is not None
    assert n.latencias.ultimo["resultado"] == "interrompido"
    turno = n._turno_atual
    assert turno is not None
    antigo_som(time.monotonic())
    n._primeiro_texto_do_cerebro(marca, time.monotonic())
    assert "primeiro_token" not in n.latencias.turnos[turno].marcos
    assert "primeiro_som" not in n.latencias.turnos[turno].marcos
    n.concluir()
    r = n.latencias.ultimo
    assert r["origem"] == "teclado" and "fim_fala" not in r["marcos_ms"]
    assert "transcricao" not in r["etapas_ms"]


def test_confirmacao_mantem_turno_original_e_identifica_primeiro_som(
    nucleo: NucleoCronometrado,
) -> None:
    n = nucleo
    n.tratar(e.Digitado("pesquise o tempo"))
    turno = n._turno_atual
    n._pedido_de_aprovacao(n.marca, "Posso pesquisar?")
    n.tratar(n.eventos.get_nowait())
    n.som()
    n.tratar(e.FalaOcioso())
    n.tratar(e.Digitado("não"))
    assert n._turno_atual == turno
    n.concluir()
    r = n.latencias.ultimo
    assert r is not None and r["aprovacao"] is True
    assert r["primeiro_som_tipo"] == "confirmacao"
    assert r["voz_por"] == "piper"  # quem falou a primeira frase (ADR 0041)


def test_comando_local_nao_inventa_latencia_do_cerebro(nucleo: NucleoCronometrado) -> None:
    n = nucleo
    n.tratar(e.Digitado("abre o guia"))
    while not n.eventos.empty():
        n.tratar(n.eventos.get_nowait())
    n.som()
    n.tratar(e.FalaOcioso())
    r = n.latencias.ultimo
    assert r is not None and r["rota"] == "comando"
    assert r["provedor"] == "" and "cerebro" not in r["etapas_ms"]


def test_fala_durante_o_pensamento_no_ao_vivo_e_contada_e_registrada(
    nucleo: NucleoCronometrado, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ao vivo, o que se diz enquanto o Zé pensa não é ouvido. Com o Codex isso leva segundos e
    parecia "surdez": agora o registro e a Atividade dizem quanto foi perdido."""
    registros: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "zervis.nucleo.laco.atividade.PADRAO.registrar",
        lambda tipo, titulo, **extra: registros.append((tipo, titulo)),
    )
    n = nucleo
    n.detector = SimpleNamespace(processar=lambda a: False, reiniciar=lambda: None)  # type: ignore[assignment]
    n.maquina.ao_vivo = True
    n.maquina.estado = e.Estado.PENSANDO
    voz = (np.sin(np.linspace(0, 400, 1280)) * 8000).astype("<i2").tobytes()
    baixo = (np.sin(np.linspace(0, 400, 1280)) * 20).astype("<i2").tobytes()
    for _ in range(10):  # 0,8 s de voz e 0,8 s de ruído de fundo
        n._quadro(voz)
        n._quadro(baixo)
    assert 0.7 < n._fala_perdida_s < 0.9  # o ruído de fundo não conta
    n._relatar_fala_perdida()
    assert registros == [("falha", "Fala não ouvida enquanto o Zé pensava")]
    assert n._fala_perdida_s == 0.0
    n._quadro(voz)  # uma tosse curta não vira aviso
    n._relatar_fala_perdida()
    assert len(registros) == 1
    n.maquina.ao_vivo = False  # fora do ao vivo o chamado funciona como sempre: nada a contar
    for _ in range(10):
        n._quadro(voz)
    assert n._fala_perdida_s == 0.0
