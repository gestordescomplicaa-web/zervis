"""A conversa pelo WhatsApp é a mesma da voz e do painel, e o que ela pede com efeito espera a
aprovação no painel, que exige login (ADR 0104)."""

import asyncio
import threading
import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis.cerebro import por_mensagem as pm
from zervis.cerebro.aprovacoes import Aprovacoes
from zervis.cerebro.base import EventoCerebro, Fim, Texto
from zervis.memoria import conversas as cv
from zervis.nucleo.servicos import atendimento as sa

EU = "5511999990000@s.whatsapp.net"


def _esperar(condicao: Any, prazo: float = 5.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def _em_fundo(coro: Any) -> list[Any]:
    """Roda a corrotina numa thread (como o cérebro do WhatsApp) e devolve o resultado nela."""
    saida: list[Any] = []
    threading.Thread(target=lambda: saida.append(asyncio.run(coro)), daemon=True).start()
    return saida


# --- a fila de aprovações -------------------------------------------------------------------


def test_aprovar_negar_e_o_prazo() -> None:
    aprovacoes = Aprovacoes(prazo_s=5)
    saida = _em_fundo(aprovacoes.esperar("Vou parar a sessão.", "whatsapp"))
    _esperar(lambda: len(aprovacoes.listar()) == 1)
    [pendente] = aprovacoes.listar()
    assert pendente["descricao"] == "Vou parar a sessão." and pendente["origem"] == "whatsapp"
    assert aprovacoes.decidir("outro", True) is None
    assert aprovacoes.decidir(pendente["id"], True) is not None
    _esperar(lambda: saida == [True])
    assert aprovacoes.listar() == []
    assert aprovacoes.decidir(pendente["id"], True) is None  # decidido uma vez só

    saida = _em_fundo(aprovacoes.esperar("Vou mandar para a sessão: oi", "whatsapp"))
    _esperar(lambda: len(aprovacoes.listar()) == 1)
    aprovacoes.decidir(aprovacoes.listar()[0]["id"], False)
    _esperar(lambda: saida == [False])

    curta = Aprovacoes(prazo_s=0.05)
    assert asyncio.run(curta.esperar("Vou parar a sessão.", "whatsapp")) is None
    assert curta.listar() == []


def test_desligar_nega_o_que_esperava() -> None:
    aprovacoes = Aprovacoes(prazo_s=5)
    saida = _em_fundo(aprovacoes.esperar("Vou parar a sessão.", "whatsapp"))
    _esperar(lambda: len(aprovacoes.listar()) == 1)
    aprovacoes.negar_todas()
    _esperar(lambda: saida == [False])


# --- o cérebro do WhatsApp ------------------------------------------------------------------


class CerebroFalso:
    def __init__(self) -> None:
        self.pedidos: list[str] = []
        self.respostas: list[Any] = []
        self.autoaprovar: Any = lambda nome, entrada: nome == "volume"

    async def start(self, persona: str, aprovar: Any = None) -> None:
        self.persona, self.aprovar = persona, aprovar

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.pedidos.append(texto)
        if texto.endswith("para a sessão"):
            self.respostas.append(await self.aprovar("Vou parar a sessão."))
        yield Texto("Feito.")
        yield Fim()

    async def interrupt(self) -> None:
        pass

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        pass


def test_pedido_leva_a_conversa_da_voz_e_a_aprovacao_vai_ao_painel() -> None:
    cerebro = CerebroFalso()
    feitos: list[pm.Feito] = []
    pedidas: list[tuple[str, str]] = []
    contextos: list[bool] = []

    async def aprovar(descricao: str, destino: str) -> bool:
        pedidas.append((descricao, destino))
        return True

    def contexto(novo: bool) -> str:
        contextos.append(novo)
        return "[10:00] Usuário: abre o projeto\nZé: Aberto." if novo else ""

    conversa = pm.ConversaPorMensagem(
        lambda: cerebro, lambda: "", feitos.append, aprovar=aprovar, contexto=contexto
    )
    try:
        conversa.pedir("o que eu pedi?", EU)
        conversa.pedir("para a sessão", EU)
        _esperar(lambda: len(feitos) == 2)
    finally:
        conversa.fechar()
    assert contextos == [True, False]
    assert cerebro.pedidos[0] == (
        "<conversa>\n[10:00] Usuário: abre o projeto\nZé: Aberto.\n</conversa>\n\no que eu pedi?"
    )
    assert cerebro.pedidos[1] == "para a sessão"  # nada novo na voz: o pedido puro
    assert [f.pedido for f in feitos] == ["o que eu pedi?", "para a sessão"]  # sem o contexto
    assert pedidas == [("Vou parar a sessão.", EU)]
    assert [bool(r) for r in cerebro.respostas] == [True]
    assert "painel" in cerebro.persona


def test_anotar_na_memoria_passa_direto_e_o_resto_segue_a_politica() -> None:
    cerebro = CerebroFalso()
    pm.liberar_anotacoes(cerebro)
    liberar = cerebro.autoaprovar
    assert liberar(pm.MEMORIA, {"acao": "adicionar", "alvo": "usuario", "texto": "x"})
    assert not liberar(pm.MEMORIA, {"acao": "remover", "antigo": "x"})
    assert not liberar(pm.MEMORIA, {"acao": "trocar", "antigo": "x", "texto": "y"})
    assert liberar("volume", {})  # a política de antes continua valendo
    assert not liberar("mcp__jarvis__sessao_parar", {})
    sem_politica = SimpleNamespace()
    pm.liberar_anotacoes(sem_politica)
    assert not hasattr(sem_politica, "autoaprovar")


# --- a conversa do dia com a origem ---------------------------------------------------------


def test_origem_gravada_e_os_turnos_depois_de_uma_hora(tmp_path: Path) -> None:
    conversas = cv.Conversas(tmp_path)
    agora = datetime.now(cv.FUSO)
    conversas.registrar("abre o projeto", "Aberto.", agora - timedelta(seconds=30))
    conversas.registrar(
        "e as vendas?", "Subiram.", agora - timedelta(seconds=20), origem="whatsapp"
    )
    [voz, whats] = conversas.do_dia(agora.date())
    assert voz.origem == "" and whats.origem == "whatsapp"
    assert [t.pessoa for t in conversas.depois(agora - timedelta(minutes=1), {"whatsapp"})] == [
        "e as vendas?"
    ]
    assert [t.pessoa for t in conversas.depois(agora - timedelta(seconds=25))] == ["e as vendas?"]
    texto = cv.em_texto(conversas.do_dia(agora.date()))
    assert "Usuário: abre o projeto\nZé: Aberto." in texto
    assert "pelo WhatsApp] Usuário: e as vendas?" in texto
    assert cv.em_texto(conversas.do_dia(agora.date()), limite=60).count("Usuário") == 1


# --- o serviço no Zé ------------------------------------------------------------------------


class CentralFalsa:
    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, texto: str, chave: str, chat: str = "") -> None:
        self.enviadas.append((chat, texto))

    def parar(self) -> None:
        pass


def _servico(tmp_path: Path) -> tuple[sa.ServicoAtendimento, Any]:
    n = SimpleNamespace(central=CentralFalsa(), conversas=cv.Conversas(tmp_path))
    return sa.ServicoAtendimento(n), n


def test_acao_pedida_pelo_whatsapp_avisa_no_chat_e_espera_o_painel(tmp_path: Path) -> None:
    servico, n = _servico(tmp_path)
    saida = _em_fundo(servico._aprovar_no_painel("Vou parar a sessão.", EU))
    _esperar(lambda: len(servico.aprovacoes_pendentes()) == 1)
    assert n.central.enviadas == [(EU, sa.AGUARDANDO.format(descricao="Vou parar a sessão."))]
    [pendente] = servico.aprovacoes_pendentes()
    assert servico.decidir_aprovacao(pendente["id"], True) == "Aprovado."
    _esperar(lambda: saida == [True])
    assert servico.decidir_aprovacao(pendente["id"], True) == "Aprovação expirada."

    saida = _em_fundo(servico._aprovar_no_painel("Vou parar a sessão.", EU))
    _esperar(lambda: len(servico.aprovacoes_pendentes()) == 1)
    servico.parar_atendimento()  # o Zé desligando nega o que esperava
    _esperar(lambda: saida == [False])


def test_a_voz_e_o_whatsapp_veem_o_que_foi_dito_no_outro(tmp_path: Path) -> None:
    servico, n = _servico(tmp_path)
    antes = datetime.now(cv.FUSO) - timedelta(seconds=5)
    servico._visto_pelo_whatsapp = antes
    n.conversas.registrar("abre o projeto", "Aberto.", antes + timedelta(seconds=1))
    n.conversas.registrar(
        "e as vendas?", "Subiram.", antes + timedelta(seconds=2), origem="whatsapp"
    )

    assert "abre o projeto" in servico._contexto_da_voz(novo=False)
    assert "e as vendas?" not in servico._contexto_da_voz(novo=False)  # o dele mesmo, não
    assert servico._contexto_da_voz(novo=False) == ""  # já visto
    novo = servico._contexto_da_voz(novo=True)  # recém-subido: o dia, de onde vier
    assert "abre o projeto" in novo and "e as vendas?" in novo

    pedido = servico.com_o_whatsapp("e agora?")
    assert pedido.startswith("(Pelo WhatsApp, desde o pedido anterior:")
    assert "e as vendas?" in pedido and "abre o projeto" not in pedido
    assert pedido.endswith("\ne agora?")
    assert servico.com_o_whatsapp("e agora?") == "e agora?"  # já visto
