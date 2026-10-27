"""ZERVIS_* é o nome das variáveis; JARVIS_* (o de antes de 20/10/2026) ainda vale."""

import pytest

from zervis import ambiente, lugares


def test_o_nome_novo_vale_primeiro_e_o_antigo_ainda_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZERVIS_PAINEL_PORTA", raising=False)
    monkeypatch.setenv("JARVIS_PAINEL_PORTA", "8796")
    assert ambiente.ler("PAINEL_PORTA", "8795") == "8796"
    monkeypatch.setenv("ZERVIS_PAINEL_PORTA", "8797")
    assert ambiente.ler("PAINEL_PORTA", "8795") == "8797"
    monkeypatch.delenv("ZERVIS_PAINEL_PORTA")
    monkeypatch.delenv("JARVIS_PAINEL_PORTA")
    assert ambiente.ler("PAINEL_PORTA", "8795") == "8795"
    assert ambiente.nomes("PERFIL") == ("ZERVIS_PERFIL", "JARVIS_PERFIL")


def test_perfil_pelo_nome_antigo_ainda_separa_as_pastas(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ("ZERVIS_RAIZ", "ZERVIS_PERFIL", "JARVIS_RAIZ"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("JARVIS_PERFIL", "teste")
    assert all(r.name == "zervis-teste" for r in lugares.raizes())


def test_ponte_aceita_a_chave_pelo_nome_antigo(monkeypatch: pytest.MonkeyPatch) -> None:
    from zervis.cerebro import rapido

    monkeypatch.delenv("ZERVIS_PONTE_API_KEY", raising=False)
    monkeypatch.setenv("JARVIS_PONTE_API_KEY", "chave-antiga")
    assert rapido.ler_chave("ponte", "") == "chave-antiga"
    monkeypatch.setenv("ZERVIS_PONTE_API_KEY", "chave-nova")
    assert rapido.ler_chave("ponte", "") == "chave-nova"
