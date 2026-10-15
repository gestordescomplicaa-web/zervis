"""A recepcionista (ADR 0031, etapa 2): o agente atende ligações do WhatsApp em tempo real."""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import numpy as np
import pytest

from jarvis.atendimento import agente as ag
from jarvis.atendimento import ligacao as lg

QUADRO = b"\x01\x00" * 960


def test_voz_do_piper_vira_pcm_16k() -> None:
    um_segundo = np.zeros(22050, dtype=np.float32)
    pcm = lg.para_16k(um_segundo, 22050)
    assert len(pcm) == 16000 * 2
    assert lg.para_16k(np.array([2.0, -2.0], dtype=np.float32), 16000) == b"\xff\x7f\x01\x80"


def test_frases_saem_enquanto_o_modelo_escreve_e_a_marca_nunca_vai_para_a_voz() -> None:
    assert lg.frases_prontas("Olá! A limpeza custa") == (["Olá!"], "A limpeza custa")
    assert lg.frases_prontas("Vou chamar a equipe. [[PASSAR: quer") == (
        ["Vou chamar a equipe."],
        "[[PASSAR: quer",
    )
    assert lg.frases_prontas("Tchau![[DESLIGAR]]") == (["Tchau!"], "[[DESLIGAR]]")


def test_prompt_da_ligacao_tem_as_regras_de_voz() -> None:
    texto = lg.sistema(ag.Perfil(nome="Bia"))
    assert "Você é Bia" in texto and "LIGAÇÃO TELEFÔNICA" in texto and "[[DESLIGAR]]" in texto
    assert "20 palavras" in texto and "WhatsApp" not in texto  # a voz troca o estilo do texto
    assert lg.saudacao(ag.Perfil(nome="Bia", empresa="Clínica Sorriso")) == (
        "Olá! Aqui é Bia, da Clínica Sorriso. Como posso ajudar?"
    )


class Conexao:
    """O WebSocket do WaCalls: entrega o áudio do cliente e guarda o que o agente manda."""

    def __init__(self) -> None:
        self.enviados: list[bytes] = []
        self.fim = asyncio.Event()

    async def send(self, dados: bytes) -> None:
        self.enviados.append(dados)

    async def _audio(self) -> AsyncIterator[bytes]:
        yield b"\x00\x00" * 320
        await self.fim.wait()

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._audio()


class Ouvido:
    def __init__(self) -> None:
        self.fila: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.recebido = 0
        self.fechado = False

    async def enviar(self, pcm: bytes) -> None:
        self.recebido += len(pcm)

    async def eventos(self) -> AsyncIterator[tuple[str, str]]:
        while True:
            yield await self.fila.get()

    async def fechar(self) -> None:
        self.fechado = True


class Motor:
    com_estado = True

    def __init__(self, respostas: Callable[[str], list[str]]) -> None:
        self.respostas = respostas
        self.pedidos: list[str] = []
        self.sistema = ""
        self.fechado = False
        self.aquecido = False

    async def iniciar(self, sistema: str) -> None:
        self.sistema = sistema

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        if mensagens[-1]["content"].startswith("[Sistema:"):  # o aquecimento com a saudação
            self.aquecido = True
            yield "Olá!"
            return
        self.pedidos.append(mensagens[-1]["content"])
        for pedaco in self.respostas(mensagens[-1]["content"]):
            yield pedaco

    async def interromper(self) -> None:
        pass

    async def fechar(self) -> None:
        self.fechado = True


def _chamada(
    tmp_path: Path, respostas: Callable[[str], list[str]]
) -> tuple[lg.Chamada, Conexao, Ouvido, Motor, list[str], list[tuple[str, str]]]:
    conexao, ouvido, motor = Conexao(), Ouvido(), Motor(respostas)
    falas: list[str] = []
    passados: list[tuple[str, str]] = []

    def falar(texto: str) -> bytes:
        if texto not in lg.REACOES:  # as reações ("Uhum.") são sintetizadas uma vez por ligação
            falas.append(texto)
        return QUADRO

    chamada = lg.Chamada(
        conexao, ouvido, motor, ag.Perfil(nome="Bia", empresa="Clínica Sorriso"),
        "5511999990000", "", ag.Registros(tmp_path),
        lambda nome, motivo: passados.append((nome, motivo)), falar, quadro_s=0,
    )  # fmt: skip
    return chamada, conexao, ouvido, motor, falas, passados


async def _ate(condicao: Callable[[], bool], prazo: float = 3.0) -> None:
    async def esperar() -> None:
        while not condicao():  # noqa: ASYNC110 (condição de outra tarefa, sem evento próprio)
            await asyncio.sleep(0.005)

    await asyncio.wait_for(esperar(), prazo)


def test_atende_responde_frase_a_frase_e_desliga_na_despedida(tmp_path: Path) -> None:
    def respostas(pedido: str) -> list[str]:
        if "tchau" in pedido:
            return ["Obrigada por ligar, até logo! [[DESLIG", "AR]]"]
        return ["A limpeza custa ", "cento e cinquenta reais. Quer ", "agendar?"]

    async def cena() -> None:
        chamada, conexao, ouvido, motor, falas, _ = _chamada(tmp_path, respostas)
        tarefa = asyncio.ensure_future(chamada.atender())
        await _ate(lambda: len(falas) == 1)
        assert falas[0] == "Olá! Aqui é Bia, da Clínica Sorriso. Como posso ajudar?"
        assert "LIGAÇÃO TELEFÔNICA" in motor.sistema
        await ouvido.fila.put(("final", "quanto custa"))
        await ouvido.fila.put(("fim_da_fala", "a limpeza?"))
        await _ate(lambda: len(falas) == 3)
        assert falas[1:] == ["A limpeza custa cento e cinquenta reais.", "Quer agendar?"]
        assert "quanto custa a limpeza?" in motor.pedidos[0] and "<<<" in motor.pedidos[0]
        await ouvido.fila.put(("fim_da_fala", "não, obrigado, tchau"))
        assert await asyncio.wait_for(tarefa, 3) == "normal"
        assert falas[-1] == "Obrigada por ligar, até logo!"
        assert conexao.enviados and all(len(q) == lg.QUADRO for q in conexao.enviados)
        assert ouvido.recebido > 0 and ouvido.fechado and motor.fechado
        conversa = ag.Registros(tmp_path).historico("5511999990000")
        assert [t["quem"] for t in conversa] == ["agente", "cliente", "agente", "cliente", "agente"]

    asyncio.run(cena())


def test_passa_para_voce_na_ligacao_e_encerra(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, _, ouvido, _, falas, passados = _chamada(
            tmp_path, lambda _: ["Alguém da equipe vai te retornar. [[PASSAR: quer fechar]]"]
        )
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "quero fechar o pacote hoje"))
        assert await asyncio.wait_for(tarefa, 3) == "passou"
        assert falas[-1] == "Alguém da equipe vai te retornar."
        assert passados == [("+5511999990000", "ligação, quer fechar")]
        assert ag.Registros(tmp_path).pausado("5511999990000")

    asyncio.run(cena())


def test_frase_pela_metade_espera_o_fim_da_fala(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, motor, _, _ = _chamada(tmp_path, lambda _: ["Claro!"])
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "eu queria saber se"))
        await asyncio.sleep(0.05)
        assert motor.pedidos == []
        await ouvido.fila.put(("final", "vocês atendem sábado"))
        await ouvido.fila.put(("pausa", ""))
        await _ate(lambda: bool(motor.pedidos))
        assert "eu queria saber se vocês atendem sábado" in motor.pedidos[0]
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_cliente_interrompe_e_a_voz_para(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, _, _, _ = _chamada(tmp_path, lambda _: ["Ok."])
        chamada.tocador.quadro_s = 0.05  # ritmo de verdade para dar tempo de interromper
        tarefa = asyncio.ensure_future(chamada.atender())
        await _ate(lambda: chamada.tocador.falando)
        chamada.tocador.tocar(QUADRO * 40)  # uma fala longa
        await ouvido.fila.put(("parcial", "espera um pouco"))
        await _ate(lambda: not chamada.tocador.falando)
        assert len(conexao.enviados) < 10
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_quando_a_central_atende_a_ligacao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from jarvis.atendimento import central as c

    perfil = ag.Perfil(ligado=True, modo="teste", numeros_teste=["5511999990000"], ligacoes=True)
    atendente = ag.Atendente(lambda: None, lambda *_: "", lambda *_: None, tmp_path,  # type: ignore[arg-type, return-value]
                             perfil=lambda: perfil)  # fmt: skip
    central = c.Central(
        lambda: None,  # type: ignore[arg-type, return-value]
        wa=object(),  # type: ignore[arg-type]
        atendente=atendente,
        avisos_ligados=lambda: False,
        chave_deepgram=lambda: "chave",
    )
    monkeypatch.setattr(lg, "voz_pronta", lambda: True)
    try:
        assert central.vai_atender("5511999990000", "c1") is None
        assert central.vai_atender("5521888880000", "c1") == "fora das regras"
        assert central.vai_atender("", "c1") == "fora das regras"  # número oculto, modo teste
        atendente.registros.pausar("5511999990000", "Ana", "com você")
        assert central.vai_atender("5511999990000", "c1") == "conversa com você"
        atendente.registros.devolver("5511999990000")
        central.ligacoes.update({"a", "b"})
        assert central.vai_atender("5511999990000", "c1") == "ocupado"
        central.ligacoes.clear()
        central.chave_deepgram = lambda: None
        assert central.vai_atender("5511999990000", "c1") == "sem escuta ou voz"
        perfil.ligacoes = False
        assert central.vai_atender("5511999990000", "c1") == "fora das regras"
    finally:
        atendente.parar()


def test_cliente_continua_antes_da_resposta_e_vira_um_turno_so(tmp_path: Path) -> None:
    async def cena() -> None:
        liberar = asyncio.Event()

        class Lento(Motor):
            async def gerar(
                self, sistema: str, mensagens: list[dict[str, str]]
            ) -> AsyncIterator[str]:
                if mensagens[-1]["content"].startswith("[Sistema:"):
                    yield "Olá!"
                    return
                self.pedidos.append(mensagens[-1]["content"])
                if len(self.pedidos) == 1:
                    await liberar.wait()  # a primeira resposta ainda não saiu
                yield "Custa cento e cinquenta reais."

        chamada, conexao, ouvido, _, falas, _ = _chamada(tmp_path, lambda _: [])
        motor = Lento(lambda _: [])
        chamada.motor = motor
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "Oi, boa tarde."))
        await _ate(lambda: len(motor.pedidos) == 1)
        await ouvido.fila.put(("fim_da_fala", "Quanto custa a limpeza?"))
        await _ate(lambda: len(falas) == 2)
        assert "Oi, boa tarde. Quanto custa a limpeza?" in motor.pedidos[1]
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)
        clientes = [t["texto"] for t in ag.Registros(tmp_path).historico("5511999990000")
                    if t["quem"] == "cliente"]  # fmt: skip
        assert clientes == ["Oi, boa tarde. Quanto custa a limpeza?"]

    asyncio.run(cena())


def test_fala_sem_abreviacao_e_sem_bastidor() -> None:
    assert lg.normalizar_voz("Abre às 8h30 e custa R$ 1.500,00, 10% à vista.") == (
        "Abre às 8 horas e 30 e custa 1500 reais, 10 por cento à vista."
    )
    assert lg.normalizar_voz("R$ 50,50 em 20 min") == "50 reais e 50 centavos em 20 minutos"
    assert lg.e_raciocinio("Devo encerrar a chamada agora.")
    assert lg.e_raciocinio("O cliente já se despediu.")
    assert not lg.e_raciocinio("Obrigada por ligar, até logo!")


def test_frase_de_bastidor_nunca_vira_voz(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, _, falas, _ = _chamada(
            tmp_path, lambda _: ["O cliente já se despediu. ", "Até logo!"]
        )
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "tchau"))
        await _ate(lambda: len(falas) == 2)
        assert falas[1] == "Até logo!"
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


class MotorSemEstado(Motor):
    com_estado = False


def test_resposta_antecipada_aproveitada_quando_o_cliente_termina_igual(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, _, falas, _ = _chamada(tmp_path, lambda _: [])
        motor = MotorSemEstado(lambda _: ["Custa cento e cinquenta reais."])
        chamada.motor = motor
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("parcial", "quanto custa a limpeza"))
        await _ate(lambda: chamada.antecipada is not None)  # o texto parou de mudar
        await _ate(lambda: len(motor.pedidos) == 1)
        await _ate(lambda: len(falas) == 2)  # a voz já foi sintetizada...
        await asyncio.sleep(0.05)
        assert len(conexao.enviados) == 1  # ...mas só a saudação tocou
        await ouvido.fila.put(("fim_da_fala", "Quanto custa a limpeza?"))
        await _ate(lambda: len(conexao.enviados) == 2)
        assert falas[1] == "Custa cento e cinquenta reais." and len(motor.pedidos) == 1
        assert chamada.antecipacoes == [1, 0]
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_resposta_antecipada_descartada_quando_o_cliente_continua(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, _, falas, _ = _chamada(tmp_path, lambda _: [])
        motor = MotorSemEstado(lambda p: ["Sim, sábado também."] if "sábado" in p else ["Custa X."])
        chamada.motor = motor
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("parcial", "quanto custa a limpeza"))
        await _ate(lambda: chamada.antecipada is not None)
        await ouvido.fila.put(("parcial", "quanto custa a limpeza e vocês abrem sábado"))
        await _ate(lambda: chamada.antecipada is None or "sábado" in chamada.antecipada[0])
        await ouvido.fila.put(("fim_da_fala", "Quanto custa a limpeza e vocês abrem sábado?"))
        await _ate(lambda: "Sim, sábado também." in falas)
        await _ate(lambda: len(ag.Registros(tmp_path).historico("5511999990000")) == 3)
        conversa = [
            (t["quem"], t["texto"]) for t in ag.Registros(tmp_path).historico("5511999990000")
        ]
        assert conversa[1:] == [  # o que o cliente ouviu: nada da resposta descartada
            ("cliente", "Quanto custa a limpeza e vocês abrem sábado?"),
            ("agente", "Sim, sábado também."),
        ]
        assert chamada.antecipacoes[1] >= 1
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_motor_pre_aquecido_e_saudacao_pronta(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, _, motor, falas, _ = _chamada(tmp_path, lambda _: [])
        chamada.iniciado = True
        chamada.saudacao_pronta = QUADRO * 2
        tarefa = asyncio.ensure_future(chamada.atender())
        await _ate(lambda: len(conexao.enviados) >= 2)
        assert not motor.aquecido and falas == []  # nem aqueceu de novo, nem sintetizou
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_modelo_lento_ganha_uma_reacao_curta_sem_repetir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lg, "REACAO_S", 0.05)

    async def cena() -> None:
        sinteses: list[str] = []
        chamada, conexao, ouvido, _, _, _ = _chamada(tmp_path, lambda _: [])

        class Lento(Motor):
            async def gerar(
                self, sistema: str, mensagens: list[dict[str, str]]
            ) -> AsyncIterator[str]:
                if mensagens[-1]["content"].startswith("[Sistema:"):
                    yield "Olá!"
                    return
                await asyncio.sleep(0.3)
                yield "Entendi! Custa cento e cinquenta reais."

        chamada.motor = Lento(lambda _: [])

        def falar(texto: str) -> bytes:
            sinteses.append(texto)
            return QUADRO

        chamada.falar = falar
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "Quanto custa a limpeza?"))
        await _ate(lambda: "Custa cento e cinquenta reais." in sinteses)
        assert chamada._vez_da_reacao == 1  # tocou um "Uhum." enquanto esperava
        assert "Entendi!" not in sinteses  # e o "Entendi!" do modelo não repetiu
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())
