"""A central de avisos (ADR 0029): o Zé narra as sessões, por prioridade, e a pessoa conduz."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jarvis.avisos import central
from jarvis.avisos.fila import Fila
from jarvis.nucleo import estados as e
from jarvis.nucleo.laco import Nucleo


def test_urgente_passa_na_frente_e_a_oferta_resume(tmp_path: Path) -> None:
    fila = Fila(tmp_path / "avisos.json")
    fila.guardar("A sessão Loja terminou.", titulo="a sessão Loja terminou", sessao="s1")
    fila.guardar(
        "A sessão Site está esperando sua aprovação.",
        prioridade=0,
        titulo="a sessão Site pede aprovação",
        sessao="s2",
    )
    texto, _ = fila.oferecer() or ("", None)
    assert texto == (
        "Duas novidades: a sessão Site pede aprovação e a sessão Loja terminou. Começo pela Site?"
    )
    assert [a.sessao for a in fila.validos()] == ["s2", "s1"]


def test_o_ze_narra_nunca_le_a_sessao_como_se_fosse_ele() -> None:
    assert central.narrar("Universo", "Ela cumprimentou você.", "Oi, Kiko!") == (
        "A sessão Universo terminou. Ela cumprimentou você."
    )
    assert central.narrar("Universo", None, "Oi, Kiko! Como você está?") == (
        "A sessão Universo terminou. Ela respondeu: Oi, Kiko!"
    )
    assert central.limpar_resumo('"Ela corrigiu o login e os testes passaram"') == (
        "Ela corrigiu o login e os testes passaram."
    )
    assert central.limpar_resumo("Oi, Kiko!") is None  # não é narração
    assert central.limpar_resumo("Ela " + "muito " * 40) is None  # longa demais


def test_responder_a_oferta_so_vale_logo_depois_dela() -> None:
    assert e.resposta_a_oferta("Começa") == "avisos_proximo"
    assert e.resposta_a_oferta("Zé, próximo") == "avisos_proximo"
    assert e.resposta_a_oferta("depois") == "avisos_depois"
    assert e.resposta_a_oferta("que horas são") is None
    m = e.Maquina()
    assert not isinstance(m._pedido("sim"), e.Comando)  # sem oferta, "sim" vai ao cérebro
    m.oferta = lambda: True
    assert m._pedido("sim") == e.Comando("avisos_proximo")
    assert e.comando("quais são os avisos") == "avisos_proximo"
    assert e.comando("o que ela disse") == "aviso_detalhe"


class _Nucleo:
    def __init__(self, fila: Fila) -> None:
        self.fila = fila
        self._oferta_ate = 0.0
        self._ultimo_de_sessao: dict[str, Any] | None = None
        self.focadas: list[str] = []
        self.sessoes = SimpleNamespace(focar=self.focadas.append)


def test_proximo_diz_um_por_vez_e_poe_a_sessao_em_foco(tmp_path: Path) -> None:
    fila = Fila(tmp_path / "avisos.json")
    fila.guardar("A sessão Loja terminou.", sessao="s1", detalhe="Corrigi o login.")
    fila.guardar("A sessão Blog terminou.", sessao="s2")
    n = _Nucleo(fila)
    assert Nucleo._proximo_aviso(n) == "A sessão Loja terminou. Mais um."  # type: ignore[arg-type]
    assert n.focadas == ["s1"] and n._oferta_ate > 0
    assert Nucleo._detalhe_do_aviso(n) == "Corrigi o login."  # type: ignore[arg-type]
    assert Nucleo._proximo_aviso(n) == "A sessão Blog terminou."  # type: ignore[arg-type]
    assert Nucleo._proximo_aviso(n) == "Nenhum aviso esperando."  # type: ignore[arg-type]
