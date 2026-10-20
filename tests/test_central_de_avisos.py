"""A central de avisos (ADR 0029): o Zé narra as sessões, por prioridade, e a pessoa conduz."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis.avisos import central
from zervis.avisos.fila import Fila
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo


def test_urgente_passa_na_frente_e_as_sessoes_saem_separadas(tmp_path: Path) -> None:
    fila = Fila(tmp_path / "avisos.json")
    fila.guardar("A sessão Loja terminou.", titulo="a sessão Loja terminou", sessao="s1")
    fila.guardar(
        "A sessão Site está esperando sua aprovação.",
        prioridade=0,
        titulo="a sessão Site pede aprovação",
        sessao="s2",
    )
    texto, aviso = fila.oferecer() or ("", None)
    assert texto == "A sessão Site está esperando sua aprovação."
    assert aviso is not None and aviso.sessao == "s2"
    assert [a.sessao for a in fila.validos()] == ["s1"]


def test_o_ze_narra_nunca_le_a_sessao_como_se_fosse_ele() -> None:
    assert central.narrar("Universo", "Ela cumprimentou você.", "Oi, Kiko!") == (
        "Resultado da sessão Universo. Ela cumprimentou você."
    )
    assert central.narrar("Universo", None, "Oi, Kiko! Como você está?") == (
        "Resultado da sessão Universo. Ela informou: Oi, Kiko!"
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


def test_repete_a_ultima_fala_inteira_sem_o_cerebro() -> None:
    assert e.comando("Repete, por favor") == "repetir"
    assert e.comando("Não entendi") == "repetir"
    n = SimpleNamespace(
        marca=3,
        maquina=SimpleNamespace(aviso_falando=None, estado=e.Estado.FALANDO),
        teclado=SimpleNamespace(falou=lambda t: None),
        voz=SimpleNamespace(falar=lambda t, ao_iniciar=None: None),
        _turno_atual=None,
    )
    for frase in ("A Loja terminou.", "Os testes passaram."):  # duas frases da mesma resposta
        Nucleo._executar(n, e.Falar(frase))  # type: ignore[arg-type]
    assert Nucleo._comando_especial(n, "repetir", "") == "A Loja terminou. Os testes passaram."  # type: ignore[arg-type]
    n.marca = 4  # outro pedido: começa de novo
    Nucleo._executar(n, e.Falar("São três horas."))  # type: ignore[arg-type]
    assert Nucleo._comando_especial(n, "repetir", "") == "São três horas."  # type: ignore[arg-type]
