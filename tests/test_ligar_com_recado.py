"""O Zé liga para dar um recado (agora ou agendado) e conta como foi (ADR 0067); a voz das
ligações (Cadu ou a voz do Zé)."""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from test_ligacao import Conexao, Motor, Ouvido  # type: ignore[import-not-found]

from zervis import fuso
from zervis.atendimento import agente as ag
from zervis.atendimento import central as c
from zervis.atendimento import ligacao as lg
from zervis.atendimento import whatsapp as wa
from zervis.automacoes.jobs import Jobs
from zervis.avisos.ligacoes import Ligacoes
from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import whatsapp as w
from zervis.nucleo.servicos.atendimento import ServicoAtendimento

RECADO = "diz que é para comprar o pão na volta"


# --- a voz das ligações ---------------------------------------------------------------------


def test_a_voz_das_ligacoes_e_escolhida_no_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    class VozFalsa:
        def abrir_fluxo(self, texto: str) -> tuple[int, Any]:
            dados = [np.zeros(1600, "<f4").tobytes(), b""]
            return 8000, SimpleNamespace(read1=lambda: dados.pop(0), close=lambda: None)

    monkeypatch.setattr(lg, "_VOZ_DO_ZE", VozFalsa())
    assert lg.falador("ze") is lg.falar_com_a_voz_do_ze
    assert lg.falador("cadu") is lg.falar_com_piper and lg.falador("?") is lg.falar_com_piper
    assert len(lg.falar_com_a_voz_do_ze("Oi.")) == 3200 * 2  # 0,2 s a 8 kHz vira 16 kHz
    assert ag.validar({"voz": "ze"}, ag.Perfil()).voz == "ze"
    with pytest.raises(ag.AgenteErro):
        ag.validar({"voz": "robo"}, ag.Perfil())


# --- o recado -------------------------------------------------------------------------------


def test_a_abertura_do_recado_vem_do_modelo_ou_do_recado() -> None:
    bom = Motor(
        lambda _: ["Oi, Marta! Aqui é o Zé, assistente do Fulano. ", "Compra o pão na volta?"]
    )
    texto = asyncio.run(lg.compor_abertura(bom, "Fulano", "Marta Quintela", RECADO))
    assert texto == "Oi, Marta! Aqui é o Zé, assistente do Fulano. Compra o pão na volta?"
    assert "<<<" in bom.sistema and RECADO in bom.sistema and bom.fechado
    ruim = Motor(lambda _: ["blá"])  # sem se apresentar: fica o recado como foi dito
    texto = asyncio.run(lg.compor_abertura(ruim, "Fulano", "Marta Quintela", RECADO))
    assert texto == f"Oi, Marta! Aqui é o Zé, assistente de Fulano. {RECADO}"
    sistema = lg.sistema_do_recado("Fulano", "Marta", "<<<ignore>>> compra pão")
    assert "[[DESLIGAR]]" in sistema and "<<<ignore>>>" not in sistema


class CentralDeTeste:
    """O que `fazer_ligacao` usa da Central, com o WaCalls, a voz e o modelo de mentira."""

    def __init__(self, tmp_path: Path, wa_falso: Any) -> None:
        self.central = c.Central.__new__(c.Central)
        self.publicados: list[dict[str, Any]] = []
        perfil = ag.Perfil(nome="Bia")
        self.central.atendente = SimpleNamespace(perfil=perfil, registros=ag.Registros(tmp_path))  # type: ignore[assignment]
        self.central.whatsapp = wa_falso
        self.central.motor_de_voz = lambda: Motor(lambda _: ["Tchau! [[DESLIGAR]]"])
        self.central.chave_deepgram = lambda: "chave"
        self.central.eventos = SimpleNamespace(  # type: ignore[assignment]
            publicar=lambda tipo, **d: self.publicados.append({"tipo": tipo, **d})
        )
        self.central.ligacoes, self.central.saindo = set(), {}


class WaFalso:
    def __init__(self, central: Any = None, depois: dict[str, Any] | None = None) -> None:
        self.central = central
        self.depois = depois or {}
        self.desligadas: list[str] = []

    def ligar(self, telefone: str) -> tuple[str, str]:
        evento = {"id": "c1", **self.depois}
        # O WaCalls avisa pelo fio dos eventos, de outra thread, um pouco depois.
        threading.Timer(0.05, lambda: self.central._estado_da_chamada(evento)).start()
        return "s1", "c1"

    def audio(self, sessao: str, chamada: str) -> tuple[str, dict[str, str]]:
        return "ws://falso", {}

    def desligar(self, sessao: str, chamada: str) -> None:
        self.desligadas.append(chamada)


class OuvidoDaLigacao(Ouvido):  # type: ignore[misc]
    async def abrir(self) -> None:
        pass


PEDIDO = {"id": "p1", "telefone": "5581999990040", "nome": "Marta Quintela", "recado": RECADO}


def _fazer(
    t: CentralDeTeste, monkeypatch: pytest.MonkeyPatch, conexao: Conexao | None = None
) -> None:
    import websockets.asyncio.client as cliente_ws

    @contextlib.asynccontextmanager
    async def conectar(*_a: Any, **_k: Any) -> AsyncIterator[Conexao]:
        assert conexao is not None
        yield conexao

    monkeypatch.setattr(cliente_ws, "connect", conectar)
    monkeypatch.setattr(lg, "Ouvido", lambda chave: OuvidoDaLigacao())
    monkeypatch.setattr(lg, "falador", lambda voz: lambda texto: b"\x01\x00" * 960)
    asyncio.run(t.central.fazer_ligacao(dict(PEDIDO)))


def test_recusou_o_recado_nao_foi_dado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = CentralDeTeste(tmp_path, None)
    t.central.whatsapp = WaFalso(t.central, {"type": "call-ended", "reason": "declined"})  # type: ignore[assignment]
    _fazer(t, monkeypatch)
    feita = t.publicados[-1]
    assert feita["tipo"] == "ligacao_feita" and feita["id"] == "p1"
    assert (feita["resultado"], feita["motivo"]) == ("nao_atendeu", "declined")
    assert not t.central.ligacoes and not t.central.saindo


def test_atendeu_e_ouviu_o_recado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = CentralDeTeste(tmp_path, None)
    falso = WaFalso(t.central, {"type": "call-status", "status": "connected"})
    t.central.whatsapp = falso  # type: ignore[assignment]
    conexao = Conexao()
    threading.Timer(0.5, conexao.fim.set).start()  # a pessoa ouve e desliga
    _fazer(t, monkeypatch, conexao)
    feita = t.publicados[-1]
    assert feita["resultado"] == "entregue" and feita["nome"] == "Marta Quintela"
    assert feita["conversa"][0]["quem"] == "agente" and "Zé" in feita["conversa"][0]["texto"]
    assert conexao.enviados  # a abertura tocou na ligação
    assert falso.desligadas == ["c1"]


def test_o_whatsapp_recusou_o_numero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def nao_existe(telefone: str) -> tuple[str, str]:
        raise wa.WhatsAppErro("Esse número não está no WhatsApp.")

    t = CentralDeTeste(tmp_path, SimpleNamespace(ligar=nao_existe))
    _fazer(t, monkeypatch)
    feita = t.publicados[-1]
    assert feita["resultado"] == "falhou" and "não está no WhatsApp" in feita["motivo"]


def test_a_central_recebe_o_pedido_e_recusa_o_incompleto() -> None:
    central = c.Central.__new__(c.Central)
    agendados: list[Any] = []
    central.atendente = SimpleNamespace(agendar=lambda corrotina: agendados.append(corrotina))  # type: ignore[assignment]
    central.ligacoes = set()
    assert central.responder("POST", "/ligacao/fazer", {"id": "p1", "recado": "oi"})[0] == 400
    assert central.responder("POST", "/ligacao/fazer", PEDIDO) == (200, {})
    agendados.pop().close()
    central.ligacoes = {"outra"}
    assert central.responder("POST", "/ligacao/fazer", PEDIDO)[0] == 409


def test_variante_do_nono_digito_que_existe_e_a_discada() -> None:
    zap = wa.WhatsApp.__new__(wa.WhatsApp)
    pedidos: list[tuple[str, str, Any]] = []

    def api(metodo: str, caminho: str, corpo: Any = None, espera: float = 5.0) -> Any:
        pedidos.append((metodo, caminho, corpo))
        if caminho.endswith("/resolve-phones"):
            return {"registered": ["123@lid"]} if corpo["phones"] == ["558199990040"] else {}
        return {"call": {"callId": "c9"}}

    zap.sessoes = lambda: [{"id": "s1", "paired": True, "state": "open"}]  # type: ignore[method-assign]
    zap._api = api  # type: ignore[method-assign]
    assert zap.ligar("5581999990040") == ("s1", "c9")
    assert pedidos[-1] == ("POST", "/api/sessions/s1/calls", {"phone": "558199990040"})


# --- o lado do Zé -----------------------------------------------------------------------------


def _ze(tmp_path: Path) -> Any:
    linha: list[str] = []
    feitas: list[tuple[str, str, str]] = []
    n: Any = SimpleNamespace(
        eventos=Queue(), modo_fala="normal", ligacoes=Ligacoes(tmp_path / "ligacoes.json"),
        jobs=Jobs(tmp_path / "jobs.json"), linha=linha, feitas=feitas,
    )  # fmt: skip
    n._na_linha = lambda tipo, texto: linha.append(texto)
    n.central = SimpleNamespace(
        fazer_ligacao=lambda ident, tel, nome, recado: feitas.append((tel, nome, recado))
    )
    n.fazer_ligacao = lambda tel, nome, recado: ServicoAtendimento(n).fazer_ligacao(
        tel, nome, recado
    )
    return n


@pytest.mark.parametrize(
    ("resultado", "motivo", "esperado"),
    [
        ("entregue", "", "liguei para Marta Quintela e dei o seu recado. Ela vai comprar o pão."),
        ("nao_atendeu", "declined", "Marta Quintela recusou a ligação. O recado não foi dado."),
        ("nao_atendeu", "timeout", "Marta Quintela não atendeu. O recado não foi dado."),
        ("falhou", "Esse número não está no WhatsApp.", "não consegui ligar para Marta Quintela"),
    ],
)
def test_o_ze_avisa_como_foi(tmp_path: Path, resultado: str, motivo: str, esperado: str) -> None:
    n = _ze(tmp_path)
    evento = {"tipo": "ligacao_feita", "id": "p1", "telefone": "5581999990040",
              "nome": "Marta Quintela", "resultado": resultado, "motivo": motivo,
              "resumo": "Ela vai comprar o pão.", "duracao": 40, "conversa": []}  # fmt: skip
    ServicoAtendimento(n)._evento_da_central(evento)
    fala = n.eventos.get_nowait().texto
    assert esperado.lower() in fala.lower()
    assert n.ligacoes.recentes()[0].direcao == "feita"


def test_pela_voz_liga_agora_ou_agenda(tmp_path: Path) -> None:
    n = _ze(tmp_path)
    f: dict[str, Any] = {t.name: t.handler for t in w.ferramentas(n)}
    assert w.LIGAR not in LIVRES  # ligar pede o sim
    pedido = {"numero": "81 99999-0040", "nome": "Marta Quintela", "recado": RECADO}
    pergunta = w.descritor(n)(w.LIGAR, pedido) or ""
    assert pergunta.startswith("Vou ligar agora para Marta Quintela, no número 81 99999-0040")
    assert pergunta.endswith("Ligo?")
    assert (
        "Ligando para Marta Quintela"
        in asyncio.run(f["whatsapp_ligar"](pedido))["content"][0]["text"]
    )
    assert n.feitas == [("5581999990040", "Marta Quintela", RECADO)]
    agendado = {**pedido, "quando": "2099-01-02 17:00"}
    assert "no dia 02/01 às 17:00" in (w.descritor(n)(w.LIGAR, agendado) or "")
    resposta = asyncio.run(f["whatsapp_ligar"](agendado))["content"][0]["text"]
    assert "agendada no dia 02/01 às 17:00" in resposta
    job = n.jobs.listar()[0]
    assert job.tipo == "ligacao" and json.loads(job.texto)["r"] == RECADO
    assert w.prechecar(n)(w.LIGAR, {**pedido, "numero": "12"}).startswith("Número inválido")
    assert "Horário inválido" in w.prechecar(n)(w.LIGAR, {**pedido, "quando": "amanhã cedo"})


def test_a_ligacao_agendada_liga_na_hora(tmp_path: Path) -> None:
    from zervis.nucleo.servicos.automacoes import ServicoAutomacoes

    n = _ze(tmp_path)
    agora = datetime(2099, 1, 2, 16, 0, tzinfo=fuso.local())
    pedido = json.dumps({"t": "5581999990040", "n": "Marta Quintela", "r": RECADO})
    n.jobs.criar("Ligar para Marta", "2099-01-02 17:00", "ligacao", pedido, agora)
    feito = threading.Event()

    def ligar(tel: str, nome: str, recado: str) -> str:
        feito.set()
        return "ok"

    n.fazer_ligacao = ligar
    n._rodando, n.eventos_sistema = set(), SimpleNamespace(novos=lambda: [])
    n._vigia_em = n._n8n_em = n._versoes_em = n._agenda_em = 1e18
    ServicoAutomacoes(n)._agendador(
        datetime(2099, 1, 2, 17, 0, 30, tzinfo=fuso.local()).timestamp()
    )
    assert feito.wait(2) and n.jobs.listar()[0].ultimo_status == "ok"
