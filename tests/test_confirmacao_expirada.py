"""14/10/2026: pelo celular, a pergunta de confirmação demorou a tocar; o cérebro desistiu aos
60 s, o "sim" chegou depois e o Zé ficou pensando para sempre, sem ouvir."""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.cerebro import base
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo


def test_cerebro_desistiu_a_maquina_sai_da_confirmacao() -> None:
    m = e.Maquina()
    m.estado = e.Estado.CONFIRMANDO
    m.pergunta_falando = True
    assert m.tratar(e.AprovacaoExpirou(), 0.0) == [e.CortarFala()]
    assert m.estado is e.Estado.PENSANDO
    assert m.tratar(e.Frase("Tudo bem, não mandei."), 0.0) == [e.Falar("Tudo bem, não mandei.")]


def test_resposta_depois_de_expirar_nao_trava() -> None:
    postos: list[Any] = []
    n = SimpleNamespace(
        ponte=SimpleNamespace(aprovacao_pendente=False, responder_aprovacao=lambda *a: None),
        eventos=SimpleNamespace(put=postos.append),
        pergunta="",
    )
    Nucleo._executar(n, e.ResponderAprovacao(True))  # type: ignore[arg-type]
    assert isinstance(postos[0], e.Frase) and "expirado" in postos[0].texto
    assert postos[1] == e.RespostaFim()


def test_rede_de_seguranca_do_cerebro_avisa_a_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "PRAZO_APROVACAO_S", 0.01)
    expirou: list[bool] = []
    ponte = base.Ponte.__new__(base.Ponte)
    ponte.ao_pedir_aprovacao = lambda marca, descricao: None
    ponte.ao_expirar_aprovacao = lambda: expirou.append(True)
    ponte.marca = 1
    ponte.aprovacao = None

    async def rodar() -> base.Resposta:
        ponte.laco = asyncio.get_running_loop()
        return await ponte._aprovar("Vou mandar para a sessão.")

    assert asyncio.run(rodar()).aprovado is False and expirou == [True]
    assert not ponte.aprovacao_pendente
