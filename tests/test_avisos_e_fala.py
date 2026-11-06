"""Os avisos chegam por onde você está, e o bastidor do modelo não vira voz (06/11/2026)."""

from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos import modo as modo_fala
from zervis.voz.fala import bastidor_em_ingles, para_fala


def test_no_silencioso_o_app_conectado_recebe_os_avisos() -> None:
    # O Silencioso é do PC: o Zé conversava pelo app, prometia "eu te aviso" e o aviso ia só
    # para a tela.
    app = SimpleNamespace(do_app=True)
    navegador = SimpleNamespace(do_app=False)
    assert modo_fala.efetivo(SimpleNamespace(modo_fala="silencioso", _fonte=app)) == "normal"
    assert modo_fala.efetivo(SimpleNamespace(modo_fala="silencioso", _fonte=navegador)) == (
        "silencioso"
    )
    assert modo_fala.efetivo(SimpleNamespace(modo_fala="silencioso", _fonte=None)) == "silencioso"
    assert modo_fala.efetivo(SimpleNamespace(modo_fala="live", _fonte=app)) == "live"


def test_o_resultado_da_ligacao_e_falado_pelo_app_no_silencioso(tmp_path: Any) -> None:
    from zervis.avisos.ligacoes import Ligacoes
    from zervis.nucleo.servicos.atendimento import ServicoAtendimento

    linha: list[str] = []
    n: Any = SimpleNamespace(
        eventos=Queue(), modo_fala="silencioso", _fonte=SimpleNamespace(do_app=True),
        ligacoes=Ligacoes(tmp_path / "ligacoes.json"), _na_linha=lambda t, x: linha.append(x),
    )  # fmt: skip
    ServicoAtendimento(n)._ligacao_feita(
        {"nome": "Marta Quintela", "telefone": "5581999990040", "resultado": "entregue"}
    )
    assert "dei o seu recado" in n.eventos.get_nowait().texto
    n._fonte = None
    ServicoAtendimento(n)._ligacao_feita({"nome": "Marta", "resultado": "entregue"})
    assert n.eventos.empty() and len(linha) == 2  # sem o app, no Silencioso: só na tela


@pytest.mark.parametrize(
    ("frase", "bastidor"),
    [
        ("Session is now stopped; read it.", True),
        ("Ok, let me check.", True),
        ("A Kaká tem o Google AI Pro.", False),
        ("Pronto, rodei o script.", False),
        ("Done.", False),  # curta demais para ter certeza
        ("Google AI Pro.", False),
    ],
)
def test_bastidor_em_ingles(frase: str, bastidor: bool) -> None:
    assert bastidor_em_ingles(frase) is bastidor


def test_o_bastidor_sai_da_fala_e_o_resto_fica() -> None:
    texto = "Um instante. Session is now stopped; read it. Saiu sim! Está em setenta e dois."
    assert para_fala(texto) == "Um instante. Saiu sim! Está em setenta e dois."
