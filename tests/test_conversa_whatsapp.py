"""O chat "Você" do WhatsApp (ADR 0102): sua mensagem para o próprio número é um pedido ao Zé,
respondido no mesmo chat por um cérebro próprio, sem confirmação de nada com efeito."""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.atendimento import central as c
from zervis.atendimento import whatsapp as w
from zervis.atendimento.whatsapp import Recebida
from zervis.cerebro import por_mensagem as pm
from zervis.cerebro.base import Espera, EventoCerebro, Fim, Texto
from zervis.nucleo.servicos import atendimento as sa

EU = "5511999990000@s.whatsapp.net"


def _msg(**campos: Any) -> dict[str, Any]:
    return {
        "event_id": "s:1",
        "direction": "outbound",
        "chat_jid": EU,
        "phone": "5511999990000",
        "type": "text",
        "content": "que horas são?",
        **campos,
    }


def test_so_a_sua_mensagem_numa_conversa_privada_vale_como_o_chat_voce() -> None:
    lote = {
        "mensagens": [
            _msg(is_self=True),
            _msg(event_id="s:2", is_self=True, direction="inbound"),  # não é sua
            _msg(event_id="s:3", is_self=True, chat_jid="120363000000000000@g.us"),  # grupo
            _msg(event_id="s:4"),  # sem a marca do WaCalls
            _msg(event_id="s:5", is_self="true"),  # só o booleano vale
        ]
    }
    assert [(r.id, r.proprio) for r in w.recebidas(lote)] == [
        ("s:1", True),
        ("s:2", False),
        ("s:3", False),
        ("s:4", False),
        ("s:5", False),
    ]


# --- a Central ------------------------------------------------------------------------------


class WhatsAppFalso:
    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone: str, texto: str, chave: str, chat: str = "") -> str:
        self.enviadas.append((chat, texto))
        return f"s:{len(self.enviadas)}"

    def parar(self) -> None:
        pass


class AtendenteFalso:
    def __init__(self, pasta: Path) -> None:
        from zervis.atendimento.agente import Registros

        self.registros = Registros(pasta)
        self.recebidas: list[Recebida] = []

    def receber(self, r: Recebida) -> None:
        self.recebidas.append(r)


def _central(tmp_path: Path) -> tuple[c.Central, WhatsAppFalso, AtendenteFalso]:
    wa, at = WhatsAppFalso(), AtendenteFalso(tmp_path)
    return c.Central(lambda: None, wa, at), wa, at  # type: ignore[arg-type, return-value]


def test_central_faz_do_chat_voce_um_pedido_e_descarta_o_eco_da_resposta(
    tmp_path: Path,
) -> None:
    central, wa, at = _central(tmp_path)
    central._recebida(Recebida("s:1", "Eu", "5511", "que horas são?", True, EU, proprio=True))
    eventos, _ = central.eventos.depois(0)
    assert [(e["tipo"], e["texto"], e["chat"]) for e in eventos] == [
        ("pedido", "que horas são?", EU)
    ]
    assert at.recebidas == []  # nem o agente de atendimento nem o arquivo ("respondida")

    corpo = {"chat": EU, "texto": "São  dez horas.", "chave": "k", "proprio": True}
    assert central.responder("POST", "/whatsapp/enviar", corpo)[0] == 200
    assert wa.enviadas == [(EU, "São  dez horas.")]
    # A resposta volta pelo WaCalls como mensagem sua: não vira pedido (senão, um laço).
    central._recebida(Recebida("s:2", "Eu", "5511", "São dez horas.", True, EU, proprio=True))
    assert central.eventos.depois(1)[0] == []
    # A mesma frase escrita de novo por você, depois do eco, é um pedido.
    central._recebida(Recebida("s:3", "Eu", "5511", "São dez horas.", True, EU, proprio=True))
    assert [e["tipo"] for e in central.eventos.depois(1)[0]] == ["pedido"]


def test_eco_so_vale_para_a_resposta_marcada_e_dentro_do_prazo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    central, _, _ = _central(tmp_path)
    corpo = {"chat": EU, "texto": "Pronto.", "chave": "k"}
    central.responder("POST", "/whatsapp/enviar", corpo)  # sem "proprio": resposta a um lead
    central._recebida(Recebida("s:1", "Eu", "5511", "Pronto.", True, EU, proprio=True))
    assert [e["tipo"] for e in central.eventos.depois(0)[0]] == ["pedido"]

    monkeypatch.setattr(c, "ECO_S", -1.0)  # o eco chegou tarde demais
    central.responder("POST", "/whatsapp/enviar", {**corpo, "proprio": True})
    central._recebida(Recebida("s:2", "Eu", "5511", "Pronto.", True, EU, proprio=True))
    assert [e["tipo"] for e in central.eventos.depois(1)[0]] == ["pedido"]


# --- o cérebro do WhatsApp ------------------------------------------------------------------


class CerebroFalso:
    def __init__(self, aprovar_em: str = "") -> None:
        self.persona = ""
        self.pedidos: list[str] = []
        self.fechado = False
        self.aprovar_em = aprovar_em
        self.respostas_da_aprovacao: list[Any] = []
        self.uso = {"input_tokens": 10}

    async def start(self, persona: str, aprovar: Any = None) -> None:
        self.persona, self.aprovar = persona, aprovar

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.pedidos.append(texto)
        yield Espera("Só um momento. ")
        if texto == self.aprovar_em:
            self.respostas_da_aprovacao.append(await self.aprovar("Enviar a mensagem?"))
        await asyncio.sleep(0.05)  # o segundo pedido chega enquanto este responde
        yield Texto(f"Resposta a {texto}.\n")
        yield Texto("- item")
        yield Fim()

    async def interrupt(self) -> None:
        pass

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        self.fechado = True


def _esperar(condicao: Any, prazo: float = 5.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def test_um_pedido_por_vez_na_ordem_sem_a_frase_de_espera_e_sem_confirmacao() -> None:
    cerebro = CerebroFalso(aprovar_em="manda oi para a Ana")
    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(lambda: cerebro, lambda: "PERSONA", feitos.append)
    try:
        assert conversa.pedir("que horas são?", EU)
        assert conversa.pedir("manda oi para a Ana", EU)
        _esperar(lambda: len(feitos) == 2)
    finally:
        conversa.fechar()
    assert cerebro.pedidos == ["que horas são?", "manda oi para a Ana"]
    assert feitos[0] == pm.Feito(
        "que horas são?", "Resposta a que horas são?.\n- item", None, EU, {"input_tokens": 10}
    )
    assert cerebro.persona.startswith("PERSONA") and "WhatsApp" in cerebro.persona
    [negada] = cerebro.respostas_da_aprovacao
    assert not negada and negada.fala == pm.SEM_CONFIRMACAO
    assert cerebro.fechado


def test_cerebro_sobe_sob_demanda_e_fecha_quando_fica_parado() -> None:
    criados: list[CerebroFalso] = []

    def criar() -> CerebroFalso:
        criados.append(CerebroFalso())
        return criados[-1]

    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(criar, lambda: "", feitos.append, ocioso_s=0.2)
    try:
        assert criados == []
        conversa.pedir("oi")
        _esperar(lambda: len(criados) == 1 and criados[0].fechado)
        conversa.pedir("oi de novo")
        _esperar(lambda: len(feitos) == 2)
        assert len(criados) == 2  # a sessão nova começa sem o histórico da anterior
    finally:
        conversa.fechar()


def test_cerebro_que_nao_sobe_vira_resposta_de_falha() -> None:
    def criar() -> Any:
        raise RuntimeError("sem conta")

    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(criar, lambda: "", feitos.append)
    try:
        conversa.pedir("oi", EU)
        _esperar(lambda: len(feitos) == 1)
    finally:
        conversa.fechar()
    assert feitos == [pm.Feito("oi", "", "RuntimeError", EU)]


# --- o serviço no Zé ------------------------------------------------------------------------


class CentralFalsa:
    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str, bool]] = []

    def enviar(self, texto: str, chave: str, chat: str = "", proprio: bool = False) -> None:
        self.enviadas.append((chat, texto, proprio))


class ConversaFalsa:
    def __init__(self, aceita: bool = True) -> None:
        self.pedidos: list[tuple[str, str]] = []
        self.aceita = aceita

    def pedir(self, texto: str, destino: str = "") -> bool:
        self.pedidos.append((texto, destino))
        return self.aceita


def _servico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ligada: bool = True
) -> tuple[sa.ServicoAtendimento, Any]:
    monkeypatch.setattr(sa, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    if ligada:
        w.escolher(True, sa.CONVERSA)
    registradas: list[tuple[str, str]] = []
    n = SimpleNamespace(
        central=CentralFalsa(),
        conversa_whatsapp=ConversaFalsa(),
        conversas=SimpleNamespace(registrar=lambda p, r: registradas.append((p, r))),
        consumo=SimpleNamespace(somar=lambda uso, provedor: None),
        provedor="claude",
        registradas=registradas,
    )
    return sa.ServicoAtendimento(n), n


def _pedido(**campos: Any) -> dict[str, Any]:
    return {"tipo": "pedido", "chat": EU, "texto": "que horas são?", "hora": time.time(), **campos}


def test_pedido_so_com_a_conversa_ligada_no_painel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch, ligada=False)
    servico._evento_da_central(_pedido())
    assert n.conversa_whatsapp.pedidos == [] and n.central.enviadas == []
    assert servico.ligar_conversa_whatsapp(True) == "Conversa pelo WhatsApp ligada."
    assert servico.conversa_pelo_whatsapp()
    servico._evento_da_central(_pedido())
    assert n.conversa_whatsapp.pedidos == [("que horas são?", EU)]


def test_pedido_atrasado_grupo_e_midia_nao_vao_ao_cerebro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    servico._evento_da_central(_pedido(hora=time.time() - sa.PEDIDO_VALIDO_S - 5))
    servico._evento_da_central(_pedido(chat="120363000000000000@g.us"))
    servico._evento_da_central(_pedido(texto="", midia="audio", evento="s:9"))
    assert n.conversa_whatsapp.pedidos == []
    assert n.central.enviadas == [(EU, sa.SO_TEXTO, True)]


def test_fila_cheia_avisa_no_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    n.conversa_whatsapp.aceita = False
    servico._evento_da_central(_pedido())
    assert n.central.enviadas == [(EU, sa.FILA_CHEIA, True)]


def test_resposta_vai_ao_chat_em_partes_e_entra_na_conversa_do_dia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    longa = ("Uma frase de resposta. " * 100).strip()
    servico.resposta_do_whatsapp(pm.Feito("resuma", longa, None, EU))
    partes = [t for _, t, _ in n.central.enviadas]
    assert len(partes) == 2 and all(len(p) <= sa.PARTE_MAXIMA for p in partes)
    assert " ".join(partes) == longa
    assert all(chat == EU and proprio for chat, _, proprio in n.central.enviadas)
    assert n.registradas == [("resuma", longa)]

    servico.resposta_do_whatsapp(pm.Feito("oi", "", "TimeoutError", EU))
    assert n.central.enviadas[-1] == (EU, sa.SEM_RESPOSTA, True)
    assert len(n.registradas) == 1  # a falha não entra na conversa do dia


def test_partes_quebram_no_paragrafo() -> None:
    texto = "a" * 10 + "\n\n" + "b" * 10
    assert sa._partes(texto, limite=15) == ["a" * 10, "b" * 10]
    assert sa._partes("x" * 30, limite=15) == ["x" * 15, "x" * 15]
    assert sa._partes("  ") == []


def test_conversa_do_nucleo_existe_e_fecha_sem_ter_subido() -> None:
    conversa = pm.ConversaPorMensagem(lambda: CerebroFalso(), lambda: "", lambda f: None)
    conversa.fechar()  # nunca subiu: nada a fechar, e não trava


def test_ao_desligar_o_ze_para_de_ouvir_a_central_e_fecha_o_chat_voce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    fechou: list[str] = []
    n.central.parar = lambda: fechou.append("central")
    n.conversa_whatsapp.fechar = lambda: fechou.append("conversa")
    servico.parar_atendimento()
    assert fechou == ["central", "conversa"]
    del n.conversa_whatsapp  # nunca houve pedido: nada a fechar
    servico.parar_atendimento()
    assert fechou == ["central", "conversa", "central"]
