"""O "Precisa de você" (ADR 0133): o que espera quem usa, do mais grave ao menos, cada item com a
página que resolve; uma fonte que falha não derruba a lista."""

from types import SimpleNamespace as N
from typing import Any

import pytest

from zervis.nucleo import autoconhecimento, precisa


class Sessoes:
    def __init__(self, lista: list[Any], trabalhando: tuple[str, ...] = (), pedidos: Any = None):
        self._lista, self._trabalhando = lista, trabalhando
        self.permissoes = N(pendentes=lambda sid: (pedidos or {}).get(sid, []))

    def listar(self) -> list[Any]:
        return self._lista

    def trabalhando(self) -> tuple[str, ...]:
        return self._trabalhando


def _sessao(id_: str, **campos: Any) -> Any:
    base = {"id": id_, "nome": id_.title(), "origem": "painel", "interrompida": "",
            "limite": False, "estado": "parada", "atualizada": "2026-11-25T10:00:00-03:00",
            "resumo": ""}  # fmt: skip
    return N(**{**base, **campos})


def _fontes(**partes: Any) -> precisa.Fontes:
    base: dict[str, Any] = {
        "leads": N(abertas=lambda: []),
        "sessoes": Sessoes([]),
        "jobs": N(listar=lambda: []),
        "manutencao": N(mudancas=lambda: {"copia": False}),
        "pendencias": N(listar=lambda: []),
        "versoes": N(foto=lambda: {}),
        "aprovacoes": None,
    }
    return precisa.Fontes(**{**base, **partes})


@pytest.fixture(autouse=True)
def _sem_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Prospecção e o Marketing leem as pastas de dados: fora destes testes."""
    monkeypatch.setattr(precisa, "_prospeccao", lambda _: [])
    monkeypatch.setattr(precisa, "_marketing", lambda _: [])
    fontes = (precisa._aprovacoes, precisa._leads, precisa._sessoes, precisa._o_ze)
    monkeypatch.setattr(precisa, "FONTES", fontes)


def test_sem_nada_a_lista_vem_vazia_e_o_ze_diz_que_nada_espera() -> None:
    assert precisa.montar(_fontes()) == []
    assert "Nada" in precisa.texto([])


def test_lead_com_telefone_leva_ao_whatsapp_e_sem_telefone_a_pagina() -> None:
    leads = [
        N(id="a", nome="Ana", texto="Fazem   orçamento?", telefone="5581999990000", chegou=10.0),
        N(id="b", nome="Bia", texto="", telefone="", chegou=20.0),
    ]
    itens = precisa.montar(_fontes(leads=N(abertas=lambda: leads)))
    assert [i.titulo for i in itens] == ["Responder Ana", "Responder Bia"]  # a mais antiga antes
    assert itens[0].para_tela()["link"] == "https://wa.me/5581999990000"
    assert itens[0].detalhe == "“Fazem orçamento?”"
    assert itens[1].para_tela()["link"] == "#atendimento"


def test_aprovacao_do_whatsapp_se_resolve_ali_mesmo() -> None:
    pedidos = [{"id": "x1", "descricao": "Enviar o orçamento", "origem": "whatsapp",
                "quando": "2026-11-25T10:00:00-03:00"}]  # fmt: skip
    (item,) = precisa.montar(_fontes(aprovacoes=lambda: pedidos))
    assert item.aprovacao == "x1" and item.detalhe == "Enviar o orçamento"
    assert item.quando > 0


def test_sessoes_pedindo_ou_paradas_entram_e_as_que_trabalham_nao() -> None:
    sessoes = Sessoes(
        [
            _sessao("pede"),
            _sessao("parou", interrompida="caiu a conexão"),
            _sessao("quebrou", estado="erro"),
            _sessao("trabalha", interrompida="antiga"),
            _sessao("ze", origem="manutencao", limite=True),
        ],
        trabalhando=("trabalha",),
        pedidos={"pede": [{"id": "p1", "frase": "Posso rodar os testes?", "tipo": "permissao"}]},
    )
    itens = precisa.montar(_fontes(sessoes=sessoes))
    assert [i.id for i in itens] == ["sessao:quebrou", "sessao:parou", "permissao:p1"]
    assert itens[0].nivel == "critico" and itens[1].detalhe == "Interrompida"
    assert itens[2].titulo == "Aprovar na sessão Pede"


def test_o_proprio_ze_automacao_com_erro_primeiro_depois_melhorias_e_versao() -> None:
    jobs = [N(id="j1", nome="Backup", ativo=True, ultimo_status="erro", proxima="")]
    itens = precisa.montar(
        _fontes(
            jobs=N(listar=lambda: jobs),
            manutencao=N(mudancas=lambda: {"commits": ["a", "b"]}),
            pendencias=N(listar=lambda: [1]),
            versoes=N(foto=lambda: {"disponivel": True}),
        )
    )
    assert [i.secao for i in itens] == ["automacoes", "melhorias", "memoria", "atualizacoes"]
    assert itens[1].detalhe == "2 mudanças prontas" and itens[2].detalhe == "1 sugestão"


def test_uma_fonte_que_falha_nao_derruba_as_outras() -> None:
    def quebra() -> list[Any]:
        raise OSError("disco")

    leads = [N(id="a", nome="Ana", texto="oi", telefone="", chegou=1.0)]
    itens = precisa.montar(_fontes(sessoes=N(listar=quebra), leads=N(abertas=lambda: leads)))
    assert [i.titulo for i in itens] == ["Responder Ana"]


def test_o_ze_agora_mostra_quem_trabalha_e_as_proximas_automacoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs = [
        N(id="j2", nome="Relatório", ativo=True, proxima="2026-11-26T09:00:00-03:00"),
        N(id="j1", nome="Lembrete", ativo=True, proxima="2026-11-25T18:00:00-03:00"),
        N(id="j3", nome="Parado", ativo=False, proxima="2026-11-25T08:00:00-03:00"),
    ]
    sessoes = Sessoes([_sessao("site", resumo="Escrevendo os testes")], trabalhando=("site",))
    agora = precisa.agora(_fontes(sessoes=sessoes, jobs=N(listar=lambda: jobs)))
    titulos = [a["titulo"] for a in agora]
    assert (
        titulos[0] == "Sessão Site"
        and agora[0]["vivo"]
        and agora[0]["detalhe"] == "Escrevendo os testes"
    )
    assert titulos[-2:] == ["Lembrete", "Relatório"]


def test_o_retrato_do_ze_leva_o_que_espera_o_usuario() -> None:
    itens = [precisa.Item("lead:a", "atendimento", "WhatsApp", "Responder Ana", "“oi”")]
    texto = precisa.texto(itens)
    assert "Responder Ana" in texto and "Início" in texto
    retrato = autoconhecimento.texto(autoconhecimento.Retrato("Claude"), precisa=texto)
    assert "Responder Ana" in retrato
