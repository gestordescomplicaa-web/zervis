"""A Conversa no painel: o fio de hoje, o pedido escrito e o que o Silencioso mostra na tela."""

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jarvis.memoria.conversas import Conversas
from jarvis.memoria.linha import LinhaDoTempo, agora
from jarvis.nucleo import estados as e
from jarvis.nucleo.laco import Nucleo
from jarvis.portal.acoes import Acoes


def test_fio_de_hoje_junta_conversa_e_avisos_em_ordem(tmp_path: Path) -> None:
    conversas = Conversas(tmp_path / "conversas")
    linha = LinhaDoTempo(tmp_path / "linha.jsonl")
    hoje = agora()
    conversas.registrar("que horas são?", "Três da tarde.", hoje - timedelta(minutes=5))
    linha.registrar("lembrete", "Hora de beber água.", hoje - timedelta(minutes=2))
    linha.registrar("lembrete", "Daqui a pouco.", hoje + timedelta(hours=1))  # ainda não tocou
    linha.registrar("foco", "Comecei o site.", hoje - timedelta(minutes=1))  # não é aviso
    a = Acoes.__new__(Acoes)
    a.n = SimpleNamespace(conversas=conversas, linha=linha)
    itens = a.conversa()["itens"]
    assert [(i["tipo"], i["texto"]) for i in itens] == [
        ("voce", "que horas são?"),
        ("ze", "Três da tarde."),
        ("aviso", "Hora de beber água."),
    ]


class _Maquina:
    estado = e.Estado.ATIVO


class _Eventos:
    def __init__(self) -> None:
        self.postos: list[Any] = []

    def put(self, evento: Any) -> None:
        self.postos.append(evento)


def test_pedido_escrito_vai_como_digitado() -> None:
    n = SimpleNamespace(maquina=_Maquina(), eventos=_Eventos())
    assert Nucleo.escrever(n, "  liga o   modo avisos ") == "Enviado."  # type: ignore[arg-type]
    assert n.eventos.postos == [e.Digitado("liga o modo avisos")]
    assert Nucleo.escrever(n, "   ") == "Mensagem vazia."  # type: ignore[arg-type]
    n.maquina.estado = e.Estado.INATIVO
    assert Nucleo.escrever(n, "oi Zé") == "O Zé está inativo."  # type: ignore[arg-type]


def test_silencioso_mostra_na_tela_o_que_nao_falou() -> None:
    n = SimpleNamespace(ultimo_na_tela=None)
    Nucleo._mostrar(n, "Lembrete: alongar.")  # type: ignore[arg-type]
    assert n.ultimo_na_tela is not None and n.ultimo_na_tela[1] == "Lembrete: alongar."
