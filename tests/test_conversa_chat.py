"""A Conversa como um chat (27/10/2026): a troca em curso vai à tela antes de ir ao histórico."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from tests.test_latencia_nucleo import NucleoCronometrado
from zervis.automacoes.agenda import FUSO
from zervis.nucleo import estados as e
from zervis.portal.acoes import Acoes


def test_a_troca_em_curso_aparece_ate_ser_gravada(tmp_path: Path) -> None:
    n = NucleoCronometrado(tmp_path)
    n.turnos = [{"pessoa": "Oi Zé", "jarvis": ""}]
    n._pedido_quando = datetime(2026, 10, 27, 21, 0, tzinfo=FUSO)
    assert n.conversa_em_andamento() is None  # parado: nada em curso
    n.maquina.estado = e.Estado.PENSANDO
    assert n.conversa_em_andamento() == {
        "quando": "2026-10-27T21:00:00-03:00",
        "pessoa": "Oi Zé",
        "ze": "",
    }
    n.turnos[-1]["jarvis"] = "Oi! Tudo"
    n.maquina.estado = e.Estado.FALANDO
    assert n.conversa_em_andamento()["ze"] == "Oi! Tudo"  # type: ignore[index]
    n._turno_gravado = n.turnos[-1]  # type: ignore[attr-defined]  # foi para o histórico
    assert n.conversa_em_andamento() is None


def test_o_fio_traz_a_troca_em_curso_no_fim_marcada(tmp_path: Path) -> None:
    agora = datetime.now(FUSO).replace(microsecond=0)
    gravada = SimpleNamespace(em=agora.replace(hour=0, minute=1), pessoa="Bom dia", ze="Bom dia!")
    nucleo = SimpleNamespace(
        conversas=SimpleNamespace(do_dia=lambda dia: [gravada]),
        linha=SimpleNamespace(entre=lambda *a: []),
        conversa_em_andamento=lambda: {
            "quando": agora.isoformat(timespec="seconds"),
            "pessoa": "E o n8n?",
            "ze": "O n8n é",
        },
    )
    itens = Acoes(nucleo, tmp_path, tmp_path).conversa()["itens"]
    assert [(i["tipo"], i["texto"], i.get("pendente")) for i in itens] == [
        ("voce", "Bom dia", None),
        ("ze", "Bom dia!", None),
        ("voce", "E o n8n?", "1"),
        ("ze", "O n8n é", "1"),
    ]
    nucleo.conversa_em_andamento = lambda: None
    assert len(Acoes(nucleo, tmp_path, tmp_path).conversa()["itens"]) == 2
