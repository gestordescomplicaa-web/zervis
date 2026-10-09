"""Ponte do cérebro: frases na ordem, fim avisado, interrupção sem aviso tardio."""

import asyncio
import threading
import time
from collections.abc import AsyncIterator

from jarvis.cerebro.base import EventoCerebro, Fim, Frases, Ponte, Texto
from jarvis.cerebro.eco import Eco


def test_frases_juntam_pedacos_e_fecham_o_resto() -> None:
    f = Frases()
    assert f.somar("Olá, A") == []
    assert f.somar("na. Tudo cer") == ["Olá, Ana."]
    assert f.somar("to? Sim! Fim") == ["Tudo certo?", "Sim!"]
    assert f.fechar() == ["Fim"]
    assert f.fechar() == []


class Fragmentado(Eco):
    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        yield Texto("  ")
        yield Texto("Olá")
        yield Texto(", Ana. ")
        yield Texto("Tudo bem?")
        yield Fim()


def test_primeiro_texto_chega_antes_da_frase_e_uma_vez_por_turno() -> None:
    eventos: list[tuple[str, int]] = []
    marcas: list[float] = []

    def primeiro(marca: int, em: float) -> None:
        eventos.append(("texto", marca))
        marcas.append(em)

    p = Ponte(
        Fragmentado(),
        "",
        lambda m, f: eventos.append(("frase", m)),
        lambda m, e: None,
        ao_primeiro_texto=primeiro,
    )
    inicio = time.monotonic()
    try:
        p.perguntar("oi", 1).result(timeout=3)
        p.perguntar("oi", 2).result(timeout=3)
        assert eventos == [
            ("texto", 1),
            ("frase", 1),
            ("frase", 1),
            ("texto", 2),
            ("frase", 2),
            ("frase", 2),
        ]
        assert len(marcas) == 2 and all(inicio <= m <= time.monotonic() for m in marcas)
    finally:
        p.fechar()


def test_falha_no_observador_nao_interrompe_a_resposta() -> None:
    frases: list[str] = []

    def quebrado(marca: int, em: float) -> None:
        raise RuntimeError("observador indisponível")

    p = Ponte(
        Eco(), "", lambda m, f: frases.append(f), lambda m, e: None, ao_primeiro_texto=quebrado
    )
    try:
        p.perguntar("teste", 1).result(timeout=3)
        assert frases
    finally:
        p.fechar()


def _ponte(cerebro: object) -> tuple[Ponte, list[str], threading.Event, list[str | None]]:
    frases: list[str] = []
    fins: list[str | None] = []
    terminou = threading.Event()

    def ao_falar(marca: int, frase: str) -> None:
        assert marca == 7
        frases.append(frase)

    def ao_terminar(marca: int, erro: str | None) -> None:
        fins.append(erro)
        terminou.set()

    return Ponte(cerebro, "persona", ao_falar, ao_terminar), frases, terminou, fins  # type: ignore[arg-type]


def test_eco_repete_o_pedido_em_uma_frase() -> None:
    ponte, frases, terminou, fins = _ponte(Eco(atraso_s=0))
    ponte.perguntar("teste", 7)
    assert terminou.wait(3)
    assert frases == ["Você disse: teste."]
    assert fins == [None]
    ponte.fechar()


class Lento(Eco):
    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        yield Texto("Primeira frase. ")
        await asyncio.sleep(10)
        yield Texto("Nunca chega.")
        yield Fim()


def test_interromper_corta_sem_avisar_fim() -> None:
    ponte, frases, terminou, fins = _ponte(Lento())
    ponte.perguntar("x", 7)
    for _ in range(100):
        if frases:
            break
        threading.Event().wait(0.01)
    ponte.interromper()
    assert not terminou.wait(0.3)
    assert frases == ["Primeira frase."]
    assert fins == []
    ponte.fechar()


class Quebrado(Eco):
    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        raise ConnectionError("sem rede")
        yield Fim()  # pragma: no cover


def test_falha_do_cerebro_vira_fim_com_erro() -> None:
    ponte, _, terminou, fins = _ponte(Quebrado())
    ponte.perguntar("x", 7)
    assert terminou.wait(3)
    assert fins == ["ConnectionError"]
    ponte.fechar()


class PedeAprovacao(Eco):
    async def start(self, persona: str, aprovar: object = None) -> None:
        self.aprovar = aprovar

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        aprovado = await self.aprovar("Vou pesquisar na internet: clima.")  # type: ignore[operator]
        yield Texto("Aprovado. " if aprovado else "Negado. ")
        yield Fim()


def _ponte_com_aprovacao(responder: bool | None) -> tuple[list[str], list[str]]:
    frases: list[str] = []
    pedidos: list[str] = []
    terminou = threading.Event()
    ponte: Ponte

    def ao_pedir(marca: int, descricao: str) -> None:
        assert marca == 7
        pedidos.append(descricao)
        if responder is not None:
            ponte.responder_aprovacao(responder)

    ponte = Ponte(
        PedeAprovacao(),
        "persona",
        lambda m, f: frases.append(f),
        lambda m, e: terminou.set(),
        ao_pedir,
    )
    ponte.perguntar("pesquisa o clima", 7)
    if responder is None:
        threading.Event().wait(0.2)
        ponte.interromper()  # fechar a janela no meio da pergunta
    else:
        assert terminou.wait(3)
    ponte.fechar()
    return frases, pedidos


def test_aprovacao_falada_sim_e_nao_chegam_ao_cerebro() -> None:
    assert _ponte_com_aprovacao(True) == (["Aprovado."], ["Vou pesquisar na internet: clima."])
    assert _ponte_com_aprovacao(False)[0] == ["Negado."]


def test_interromper_durante_a_pergunta_nega() -> None:
    frases, pedidos = _ponte_com_aprovacao(None)
    assert pedidos == ["Vou pesquisar na internet: clima."]
    assert frases == []  # interrompido: nada mais é falado


class Rotulado(Eco):
    def __init__(self, rotulo: str) -> None:
        super().__init__(atraso_s=0)
        self.rotulo, self.iniciado, self.fechado = rotulo, False, False

    async def start(self, persona: str, aprovar: object = None) -> None:
        self.iniciado = persona == "persona" and aprovar is not None

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        yield Texto(f"Sou o {self.rotulo}.")
        yield Fim()

    async def close(self) -> None:
        self.fechado = True


def test_trocar_inicia_o_novo_fecha_o_antigo_e_responde_pelo_novo() -> None:
    antigo, novo = Rotulado("antigo"), Rotulado("novo")
    ponte, frases, terminou, _ = _ponte(antigo)
    ponte.trocar(novo)
    ponte.perguntar("quem é?", 7)  # pedido logo depois da troca espera o cérebro novo
    assert terminou.wait(3)
    assert frases == ["Sou o novo."]
    assert novo.iniciado and antigo.fechado
    ponte.fechar()
