"""A chave do painel sem crédito não para a nota do dia nem a revisão (22/10/2026)."""

import asyncio
from pathlib import Path

import pytest

from zervis import atividade
from zervis.cerebro import acesso

CHAVE = {"metodo": "chave", "origem": "painel", "valor": "x"}


@pytest.fixture
def com_chave(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> atividade.Atividade:
    monkeypatch.setattr(acesso, "_pela_assinatura", False)
    monkeypatch.setattr(acesso, "escolha", lambda pasta=None: CHAVE)
    monkeypatch.setattr(acesso, "assinatura_disponivel", lambda login=None: True)
    registro = atividade.Atividade(tmp_path / "atividade.jsonl")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    return registro


def test_chave_sem_credito_vai_pela_assinatura_e_avisa_uma_vez(
    com_chave: atividade.Atividade,
) -> None:
    ambientes: list[dict[str, str]] = []

    async def consultar(ambiente: dict[str, str]) -> str:
        ambientes.append(ambiente)
        if not ambiente:
            raise RuntimeError("Claude Code returned an error result: Credit balance is too low")
        return "nota"

    assert asyncio.run(acesso.com_reserva(consultar, "a nota do dia")) == "nota"
    assert asyncio.run(acesso.com_reserva(consultar, "a revisão")) == "nota"
    assert ambientes == [{}, {acesso.CHAVE: ""}, {acesso.CHAVE: ""}]  # a 2ª já vai direto
    (linha,) = com_chave.listar()
    assert linha["tipo"] == "falha" and "recusada" in linha["titulo"]


@pytest.mark.parametrize(
    ("erro", "assinatura"),
    [("Overloaded", True), ("Credit balance is too low", False)],
)
def test_outro_erro_ou_sem_assinatura_aparece_como_e(
    com_chave: atividade.Atividade, monkeypatch: pytest.MonkeyPatch, erro: str, assinatura: bool
) -> None:
    monkeypatch.setattr(acesso, "assinatura_disponivel", lambda login=None: assinatura)

    async def consultar(ambiente: dict[str, str]) -> str:
        raise RuntimeError(erro)

    with pytest.raises(RuntimeError, match=erro):
        asyncio.run(acesso.com_reserva(consultar, "a nota do dia"))
    assert com_chave.listar() == [] and acesso.ambiente_das_consultas() == {}


def test_pelo_login_nao_ha_reserva(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem usa a assinatura desde o começo não tem chave para recusar."""
    monkeypatch.setattr(acesso, "_pela_assinatura", False)
    login = {"metodo": "login", "origem": "agente", "valor": ""}
    monkeypatch.setattr(acesso, "escolha", lambda pasta=None: login)

    async def consultar(ambiente: dict[str, str]) -> str:
        raise RuntimeError("Credit balance is too low")

    with pytest.raises(RuntimeError):
        asyncio.run(acesso.com_reserva(consultar, "a revisão"))
