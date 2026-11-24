"""Os avisos do que trabalha sozinho (ADR 0130): a Prospecção e o Instagram na central de avisos.

Antes, os dois só escreviam uma linha na tela: a pausa da prospecção, a Apify sem crédito e a
pessoa que quer falar com você no direct não eram faladas, não esperavam na fila e não chegavam
ao celular. E a saudação automática do WhatsApp Business de uma loja contatada virava lead.
"""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from zervis.atendimento import whatsapp
from zervis.avisos import pendentes as pd
from zervis.avisos import prioridade as pr
from zervis.avisos.caixa import Caixa
from zervis.avisos.fila import PRIORIDADES
from zervis.nucleo.servicos import avisos as servico_avisos
from zervis.nucleo.servicos.atendimento import ServicoAtendimento
from zervis.nucleo.servicos.avisos import ServicoAvisos
from zervis.prospeccao import funil

QUARTA_10H = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Recife")).timestamp()
LOJA = "558198190151"


class _NaHora:
    """A thread do envio ao WhatsApp, rodando na hora: o teste vê o resultado sem esperar."""

    def __init__(self, target: Any, args: tuple[Any, ...] = (), **_: Any) -> None:
        self.target, self.args = target, args

    def start(self) -> None:
        self.target(*self.args)


def _nucleo(modo: str) -> Any:
    n: Any = SimpleNamespace(
        _meta={}, tela=[], falados=[], enviados=[], modo_fala=modo, _fonte=None
    )
    n._na_linha = lambda tipo, texto: n.tela.append(texto)
    n.eventos = SimpleNamespace(put=n.falados.append)
    n.central = SimpleNamespace(
        whatsapp_ativo=True,
        enviar=lambda texto, chave, telefone="": n.enviados.append((texto, telefone)),
    )
    return n


@pytest.fixture
def seu_whatsapp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(servico_avisos, "threading", SimpleNamespace(Thread=_NaHora))
    monkeypatch.setattr(whatsapp, "conversa", lambda arquivo=None: (True, ["5581999990000"]))


@pytest.mark.usefixtures("seu_whatsapp")
def test_urgente_fura_a_fila_e_vai_ao_seu_whatsapp_a_notificacao_so_espera_a_vez() -> None:
    n = _nucleo("avisos")
    avisos = ServicoAvisos(n)
    pausa = "Prospecção pausada: 2 pessoas pediram para não receber mensagens nesta semana."
    avisos.notificar(pausa, urgente=True, origem="prospeccao")
    assert n.tela == [pausa] and [a.texto for a in n.falados] == [pausa]
    assert n._meta[pausa] == {"prioridade": PRIORIDADES["urgente"], "origem": "prospeccao"}
    assert n.enviados == [(pausa, "5581999990000")]
    enviada = "Prospecção: mensagem enviada para Carlos (Sorrir)."
    avisos.notificar(enviada, origem="prospeccao")
    assert n._meta[enviada]["prioridade"] == PRIORIDADES["notificacao"]
    assert len(n.falados) == 2 and len(n.enviados) == 1  # o que não precisa de você não vai


@pytest.mark.usefixtures("seu_whatsapp")
def test_no_silencioso_fica_na_tela_e_o_urgente_ainda_chega_ao_celular() -> None:
    n = _nucleo("silencioso")
    texto = "@cliente quer falar com você no direct: pediu o preço."
    ServicoAvisos(n).notificar(texto, urgente=True, origem="instagram")
    assert n.tela == [texto] and n.falados == []
    assert n.enviados == [(texto, "5581999990000")]


def _atendimento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    relogio = SimpleNamespace(t=QUARTA_10H)
    agora = lambda: relogio.t  # noqa: E731
    config = tmp_path / "prospeccao.json"
    funil.salvar_config(funil.Config(ligada=True, cidade="Caruaru, PE"), config)
    f = funil.Funil(tmp_path / "prospeccao-dados.json", config, agora=agora)
    with f._empresas.transacao():
        dau = f._nova("Dau Autopeças", "maps", status="enviada", enviado=QUARTA_10H)
        dau["telefone_enviado"] = LOJA
        f._empresas.gravar([dau])
    monkeypatch.setattr(funil, "_PADRAO", f)
    falados: list[Any] = []
    n: Any = SimpleNamespace(
        leads=pd.Pendentes(tmp_path / "pendentes.json", agora),
        caixa=Caixa(tmp_path / "caixa.json", agora),
        prioridade=pr.Prioridade(tmp_path / "prioridade.json", agora),
        modo_fala="avisos",
        avisos_lidos={},
        mensagens=SimpleNamespace(ativo=True, receber=lambda *dados: None),
        eventos=SimpleNamespace(put=falados.append),
        _na_linha=lambda tipo, texto: None,
        _fonte=None,
        falados=falados,
        relogio=relogio,
        funil=f,
    )
    n.servico = ServicoAtendimento(n)
    # O envio da prospecção põe o número na lista de prioridade por 24 horas (ADR 0055).
    n.prioridade.esperar_resposta("Williams (Dau Autopeças)", f"{LOJA}@s.whatsapp.net", LOJA)
    return n


def _chega(n: Any, texto: str) -> None:
    n.servico._evento_da_central(
        {"tipo": "mensagem", "nome": "TELEVENDAS DAU", "texto": texto, "telefone": LOJA,
         "chat": f"{LOJA}@s.whatsapp.net", "midia": "", "quando": n.relogio.t}
    )  # fmt: skip


def test_a_saudacao_automatica_da_loja_nao_vira_lead_a_pessoa_sim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    n = _atendimento(tmp_path, monkeypatch)
    n.relogio.t += 30
    _chega(n, "*Bem-vindo(a) a DAU AUTOPEÇAS | CARUARU* Como podemos lhe atender?")
    assert n.falados == [] and n.leads.abertas() == []
    assert n.funil.todas()[0]["status"] == "enviada"
    n.relogio.t += 2 * 3600
    _chega(n, "Boa tarde! O Williams pediu para você mandar mais detalhes.")
    assert n.funil.todas()[0]["status"] == "respondeu"
    assert len(n.falados) == 1 and len(n.leads.abertas()) == 1
