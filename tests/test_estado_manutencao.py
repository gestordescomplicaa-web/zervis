"""Manutenção como estado do Zé (ADR 0028): aplicar só nele e sem interromper outras sessões."""

from pathlib import Path
from typing import Any

import pytest

from jarvis.nucleo.laco import Nucleo
from jarvis.oficina.sessoes import Sessao, SessaoErro, Sessoes
from jarvis.portal.senha import SO_NO_PC


class _Manutencao:
    def __init__(self, ligado: bool) -> None:
        self.ligado = ligado


class _Sessoes:
    def __init__(self, trabalhando: dict[str, str]) -> None:
        self.ativas = trabalhando  # id -> origem

    def trabalhando(self) -> list[str]:
        return list(self.ativas)

    def ler(self, id_: str) -> Sessao:
        return Sessao(id_, id_, "~/p", "claude", origem=self.ativas[id_])


class _Nucleo:
    _outras_trabalhando = Nucleo._outras_trabalhando

    def __init__(self, ligado: bool, trabalhando: dict[str, str]) -> None:
        self.manutencao = _Manutencao(ligado)
        self.sessoes = _Sessoes(trabalhando)
        self._aplicar_depois: bool | None = None
        self.aplicados: list[bool] = []


def test_aplicar_so_no_estado_de_manutencao() -> None:
    n = _Nucleo(False, {})
    assert Nucleo.aplicar_melhorias(n, False) == "Entre no modo manutenção para aplicar."  # type: ignore[arg-type]


def test_com_outra_sessao_trabalhando_espera_e_aplica_quando_livre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    n = _Nucleo(True, {"loja": "", "ze": "manutencao"})
    aviso = Nucleo.aplicar_melhorias(n, True)  # type: ignore[arg-type]
    assert aviso == "Uma sessão está trabalhando. Aplico quando ela terminar."
    assert n._aplicar_depois is True
    aplicados: list[bool] = []
    monkeypatch.setattr(
        _Nucleo,
        "aplicar_melhorias",
        lambda self, revisado=False: aplicados.append(revisado),
        raising=False,
    )
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert aplicados == []  # a loja ainda trabalha
    del n.sessoes.ativas["loja"]  # a sessão do próprio Zé não conta
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert aplicados == [True] and n._aplicar_depois is None


def test_sair_da_manutencao_cancela_a_espera() -> None:
    n = _Nucleo(True, {"loja": ""})
    Nucleo.aplicar_melhorias(n, False)  # type: ignore[arg-type]
    n.manutencao.ligado = False
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert n._aplicar_depois is None


def test_sessao_reservada_recusa_trabalho_novo_menos_a_do_ze(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path, (tmp_path,), rodar=lambda *_: "ok")
    loja = sessoes.criar("Loja", str(tmp_path))
    sessoes.reservada = lambda: "Atualização do Zé em andamento. Tente em instantes."
    with pytest.raises(SessaoErro, match="Atualização do Zé"):
        sessoes.enviar(loja.id, "rode os testes")


def test_entrar_e_sair_da_manutencao_so_pelo_pc() -> None:
    assert "ze/manutencao" in SO_NO_PC


class _Voz:
    """O núcleo só com o que o pedido falado de reiniciar usa."""

    def __init__(self, fonte: object = None, digitado: float | None = None) -> None:
        self._fonte = fonte
        self._digitado_em = digitado
        self.aplicados: list[bool] = []
        self.ditos: list[str] = []
        self.manutencao = self
        self.eventos = self

    def mudancas(self) -> dict[str, Any]:
        return {"commits": ["abc muda"]}

    def aplicar_melhorias(self, revisado: bool = False) -> str:
        self.aplicados.append(revisado)
        return "aplicando"

    def _no_proprio_pc(self) -> bool:
        return Nucleo._no_proprio_pc(self)  # type: ignore[arg-type]

    def put(self, evento: Any) -> None:
        if hasattr(evento, "texto"):
            self.ditos.append(evento.texto)


@pytest.mark.parametrize(
    ("voz", "aplicados", "dito"),
    [
        (_Voz(), [False], "aplicando"),  # "eu revisei" pela voz não vale como revisão
        (_Voz(fonte=object()), [], "Aplique no computador."),  # celular
        (_Voz(digitado=1.0), [], "Aplique no computador."),  # digitado no painel
    ],
)
def test_pela_voz_so_no_pc_e_nunca_a_zona_protegida(
    voz: _Voz, aplicados: list[bool], dito: str
) -> None:
    Nucleo._responder_depois(voz, "reiniciar", "revisado")  # type: ignore[arg-type]
    assert voz.aplicados == aplicados and voz.ditos == [dito]
