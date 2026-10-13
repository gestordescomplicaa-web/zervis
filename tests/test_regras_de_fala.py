"""Regras de fala (ADR 0027): o que vira voz, em quantas palavras e quantas vezes."""

from typing import Any

import pytest

from jarvis.avisos import modo
from jarvis.nucleo import estados as e
from jarvis.nucleo.laco import Nucleo

LONGO = (
    "A sessão de autodesenvolvimento terminou. Proposta um: agrupar os erros pela mensagem final. "
    "Proposta dois: registrar a queda do modo imersivo. Proposta três: reiniciar o túnel "
    "sozinho. Proposta quatro: reconectar a voz do navegador."
)


def test_aviso_curto_passa_como_esta() -> None:
    assert modo.manchete("A sessão Loja terminou.") == "A sessão Loja terminou."


def test_aviso_longo_vira_manchete_com_o_resto_na_tela() -> None:
    curto = modo.manchete(LONGO)
    assert curto.startswith("A sessão de autodesenvolvimento terminou.")
    assert curto.endswith("O resto está na tela.")
    assert len(curto.split()) <= modo.MANCHETE_PALAVRAS + 5


def test_frase_unica_comprida_e_cortada_nas_palavras() -> None:
    curto = modo.manchete(" ".join(["palavra"] * 80))
    assert "…" in curto and len(curto.split()) <= modo.MANCHETE_PALAVRAS + 5


class _Fila:
    def __init__(self) -> None:
        self.guardados: list[str] = []

    def guardar(self, texto: str) -> None:
        self.guardados.append(texto)


class _Nucleo:
    def __init__(self) -> None:
        self._comecados: dict[str, int] = {}
        self._cortados: set[str] = set()
        self._avisos_dados: dict[str, float] = {}
        self._na_tela: dict[str, None] = {}
        self.linha: list[tuple[str, str]] = []
        self.fila = _Fila()
        self._meta: dict[str, dict[str, Any]] = {}

    def _guardar(self, texto: str) -> None:
        self.fila.guardar(texto)

    def _na_linha(self, tipo: str, texto: str) -> None:
        self.linha.append((tipo, texto))


def _regra(n: Any, texto: str) -> str | None:
    aviso = Nucleo._regras_de_fala(n, e.Aviso(texto))
    return None if aviso is None else aviso.texto


def _reter(n: Any, texto: str) -> None:
    Nucleo._executar(n, e.ReterAviso(texto))


def test_o_mesmo_aviso_nao_se_repete_em_dois_minutos(monkeypatch: pytest.MonkeyPatch) -> None:
    agora = [1000.0]
    monkeypatch.setattr("jarvis.nucleo.laco.time.monotonic", lambda: agora[0])
    n = _Nucleo()
    texto = "A sessão Loja está esperando sua aprovação."
    assert _regra(n, texto)
    n._avisos_dados[texto] = agora[0]  # a fala começou (o Falar marca)
    agora[0] += 30
    assert _regra(n, texto) is None
    agora[0] += modo.REPETIR_S
    assert _regra(n, texto)


def test_aviso_que_esperou_o_ze_ficar_livre_nao_conta_como_repetido() -> None:
    """13/10/2026: o fim da sessão chegou com o Zé ocupado, esperou e foi descartado."""
    n = _Nucleo()
    texto = "A sessão Universo - Teste terminou."
    assert _regra(n, texto)  # chegou, mas o Zé estava ocupado
    _reter(n, texto)  # ficou guardado sem começar a falar
    assert _regra(n, texto) == texto  # a volta é dita


def test_aviso_longo_fica_inteiro_na_tela_uma_vez() -> None:
    n = _Nucleo()
    assert _regra(n, LONGO) == modo.manchete(LONGO)
    assert n.linha == [("aviso", LONGO)]
    n2 = _Nucleo()
    n2._na_tela[LONGO] = None  # quem avisou já pôs na tela
    _regra(n2, LONGO)
    assert n2.linha == []


def test_aviso_cortado_volta_uma_vez_e_depois_fica_so_na_tela() -> None:
    n = _Nucleo()
    texto = "A sessão Loja terminou."
    assert _regra(n, texto)
    n._comecados[texto] = 1  # começou a ser falado e foi cortado
    _reter(n, texto)
    assert n.fila.guardados == [texto]
    assert _regra(n, texto) == texto  # a volta do cortado não conta como repetição
    n._comecados[texto] = 2  # cortado de novo
    _reter(n, texto)
    assert n.fila.guardados == [texto]


def test_aviso_retido_sem_ter_comecado_espera_sem_contar_corte() -> None:
    n = _Nucleo()
    _reter(n, "Lembrete: reunião.")
    _reter(n, "Lembrete: reunião.")
    assert n.fila.guardados == ["Lembrete: reunião."] * 2 and not n._cortados
