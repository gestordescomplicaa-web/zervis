"""Chamar você durante a ligação e passar para o app de voz, sem derrubar (ADR 0066)."""

import asyncio
import json
import threading
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest
from test_ligacao import _ate, _chamada  # type: ignore[import-not-found]

from zervis.atendimento import agente as ag
from zervis.atendimento import ligacao as lg
from zervis.nucleo import estados as e
from zervis.nucleo.servicos.atendimento import ServicoAtendimento

CHAMA = ["Vou ver se ele pode atender agora. [[CHAMAR: o orçamento da reforma]]"]


def _com_chamar(tmp_path: Path) -> tuple[Any, ...]:
    chamada, conexao, ouvido, motor, falas, _ = _chamada(
        tmp_path, lambda pedido: ["Ele não pode agora, posso anotar o recado?"]
        if "[Nota do sistema:" in pedido else CHAMA,
    )  # fmt: skip
    chamados: list[tuple[str, str, str]] = []
    chamada.ao_chamar = lambda nome, tel, assunto: chamados.append((nome, tel, assunto))
    chamada.dono = "Fulano"
    return chamada, conexao, ouvido, motor, falas, chamados


def test_atender_vira_ponte_e_a_ligacao_continua(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, motor, falas, chamados = _com_chamar(tmp_path)
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "quero falar com o dono sobre o orçamento"))
        await _ate(lambda: bool(chamados))
        assert chamados == [("+5511999990000", "5511999990000", "o orçamento da reforma")]
        assert chamada.em_espera and falas[-1] == "Vou ver se ele pode atender agora."
        await ouvido.fila.put(("fim_da_fala", "tá bom, eu espero"))  # na espera: só anotado
        await asyncio.sleep(0.05)
        assert len(motor.pedidos) == 1
        assert chamada.decidir("atender") and not chamada.decidir("atender")
        await _ate(lambda: chamada.em_ponte)
        assert falas[-1] == "Pronto, vou te passar para Fulano."
        sua_voz = b"\x05\x00" * 960  # (a voz falsa do agente é outra)
        chamada.ouvir_dono(b"\x05\x00" * 1280 * 3)  # 240 ms da sua voz: 4 quadros de 60 ms
        await _ate(lambda: conexao.enviados.count(sua_voz) == 4)
        assert all(len(q) == lg.QUADRO for q in conexao.enviados)
        primeira = conexao.enviados.index(sua_voz)
        assert conexao.enviados[primeira - 3 : primeira] == [b"\0" * lg.QUADRO] * 3  # a folga
        assert motor.pedidos and len(motor.pedidos) == 1  # o agente saiu da conversa
        chamada.ponte_fim.set()  # você desligou
        assert await asyncio.wait_for(tarefa, 3) == "transferida"
        quem = [f["quem"] for f in chamada.conversa]
        assert quem.count("cliente") == 2 and "[A ligação foi passada para Fulano.]" in [
            f["texto"] for f in chamada.conversa
        ]

    asyncio.run(cena())


def test_agora_nao_o_agente_anota_o_recado(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, motor, falas, chamados = _com_chamar(tmp_path)
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "posso falar com o dono?"))
        await _ate(lambda: bool(chamados))
        chamada.decidir("recusar")
        await _ate(lambda: falas[-1] == "Ele não pode agora, posso anotar o recado?")
        assert "[Nota do sistema: Fulano não pode atender agora" in motor.pedidos[-1]
        assert not chamada.em_espera and not chamada.em_ponte
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_sem_resposta_lembra_que_espera_e_depois_o_recado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lg, "ESPERA_DONO_S", 0.3)
    monkeypatch.setattr(lg, "LEMBRAR_ESPERA_S", 0.1)

    async def cena() -> None:
        chamada, conexao, ouvido, _, falas, _ = _com_chamar(tmp_path)
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "posso falar com o dono?"))
        await _ate(lambda: "Ele não pode agora, posso anotar o recado?" in falas)
        assert "Só mais um instante, por favor." in falas
        assert not chamada.decidir("atender")  # tarde demais
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_sem_o_ze_para_perguntar_vai_direto_ao_recado(tmp_path: Path) -> None:
    async def cena() -> None:
        chamada, conexao, ouvido, _, falas, _ = _com_chamar(tmp_path)
        chamada.ao_chamar = None
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "posso falar com o dono?"))
        await _ate(lambda: "Ele não pode agora, posso anotar o recado?" in falas)
        conexao.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_a_ponte_da_central_leva_e_traz_o_audio(tmp_path: Path) -> None:
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    from zervis.atendimento import central as c

    atendente = ag.Atendente(lambda: None, lambda *_: "", lambda *_: None, tmp_path)  # type: ignore[arg-type, return-value]
    central = c.Central(lambda: None, wa=object(), atendente=atendente)  # type: ignore[arg-type, return-value]
    central.token = "segredo"  # noqa: S105 (token do teste)
    ouvidos: list[bytes] = []

    class Atendida:
        em_espera, em_ponte = True, False

        def __init__(self) -> None:
            self.ponte_pronta, self.ponte_fim = asyncio.Event(), asyncio.Event()
            self.para_ponte: asyncio.Queue[bytes] = asyncio.Queue()

        def decidir(self, decisao: str) -> bool:
            self.em_espera, self.em_ponte = False, decisao == "atender"
            self.ponte_pronta.set()
            return True

        def ouvir_dono(self, pcm: bytes) -> None:
            ouvidos.append(pcm)

    atendida = Atendida()
    central.atendidas["c1"] = atendida  # type: ignore[assignment]
    try:
        assert (
            central.responder("POST", "/ligacao/decidir", {"chamada": "zz", "atender": True})[0]
            == 409
        )
        codigo, dados = central.responder(
            "POST", "/ligacao/decidir", {"chamada": "c1", "atender": True}
        )
        assert codigo == 200 and dados["porta"] > 0
        url = f"ws://127.0.0.1:{dados['porta']}/ponte/c1"
        with (
            connect(url, additional_headers={"X-Atendimento-Token": "errado"}) as ruim,
            pytest.raises(ConnectionClosed),
        ):
            ruim.recv(timeout=2)
        with connect(url, additional_headers={"X-Atendimento-Token": "segredo"}) as ws:
            ws.send(b"\x02\x00" * 1280)
            atendente.agendar(atendida.para_ponte.put(b"\x03\x00" * 960))
            assert ws.recv(timeout=3) == b"\x03\x00" * 960
            for _ in range(50):
                if ouvidos:
                    break
                threading.Event().wait(0.02)
            assert ouvidos == [b"\x02\x00" * 1280]
            central.encerrar("c1")
            ws.send(b"\x00\x00" * 1280)  # o próximo quadro já encontra a ponte fechada
            with pytest.raises(ConnectionClosed):
                for _ in range(10):
                    ws.recv(timeout=2)
        assert atendida.ponte_fim.is_set()
    finally:
        atendente.parar()


# --- o lado do Zé ---------------------------------------------------------------------------


class ConexaoDoApp:
    """O WebSocket do app: guarda o áudio e as mensagens de controle que chegam a ele."""

    aberta = True

    def __init__(self) -> None:
        self.recebidos: list[bytes] = []
        self.controles: list[dict[str, Any]] = []

    def binario(self, pcm: bytes) -> None:
        self.recebidos.append(pcm)

    def texto(self, dados: str) -> None:
        self.controles.append(json.loads(dados))


class App:
    """A VozNavegador do app: o controle passa pela conexão, como na de verdade."""

    do_app, conectada, sem_eco = True, True, False

    def __init__(self) -> None:
        self.conexao: Any = ConexaoDoApp()
        self.real = self.conexao

    @property
    def controles(self) -> list[dict[str, Any]]:
        return self.real.controles

    @property
    def recebidos(self) -> list[bytes]:
        return self.real.recebidos

    def controle(self, **dados: Any) -> None:
        self.conexao.texto(json.dumps(dados))


class CentralFalsa:
    def __init__(self) -> None:
        self.decisoes: list[tuple[str, bool]] = []
        self.encerradas: list[str] = []
        self.token = "t"  # noqa: S105 (token do teste)

    def decidir_ligacao(self, chamada: str, atender: bool) -> str:
        self.decisoes.append((chamada, atender))
        return f"ws://127.0.0.1:1/ponte/{chamada}" if atender else ""

    def encerrar_ligacao(self, chamada: str) -> None:
        self.encerradas.append(chamada)


class WsFalso:
    def __init__(self) -> None:
        self.enviados: list[bytes] = []
        self.entrada: Queue[bytes | None] = Queue()

    def __iter__(self) -> Any:
        while (m := self.entrada.get()) is not None:
            yield m

    def send(self, dados: bytes) -> None:
        self.enviados.append(dados)

    def close(self) -> None:
        self.entrada.put(None)


def _ze(fonte: Any) -> Any:
    linha: list[str] = []
    n: Any = SimpleNamespace(
        _fonte=fonte, central=CentralFalsa(), eventos=Queue(), avisos_lidos={}, linha=linha,
        maquina=e.Maquina(), ligacao_pendente=None, ponte_ligacao=None, modo_fala="normal",
    )  # fmt: skip
    n._na_linha = lambda tipo, texto: linha.append(texto)
    return n


CHAMANDO = {"tipo": "chamando", "chamada": "c1", "nome": "Ana Lima", "telefone": "5581999990030",
            "assunto": "o orçamento da reforma"}  # fmt: skip


def test_o_ze_pergunta_pelo_app_e_atender_liga_a_ponte(monkeypatch: pytest.MonkeyPatch) -> None:
    from zervis.transporte import ponte as p

    app, ws = App(), WsFalso()
    n = _ze(app)
    servico = ServicoAtendimento(n)
    servico._evento_da_central(CHAMANDO)
    aviso = n.eventos.get_nowait()
    fala = aviso.texto
    assert aviso.escutar  # a resposta vem sem "Ei Zé"
    assert "Ana Lima está na linha e quer falar com você sobre o orçamento da reforma." in fala
    assert fala.endswith("Pode atender?")
    chamando = {"tipo": "ligacao", "estado": "chamando", "id": "c1", "nome": "Ana Lima"}
    assert app.controles[-1] == {**chamando, "assunto": "o orçamento da reforma"}
    assert "whatsapp_ligacao" in next(iter(n.avisos_lidos.values()))
    original = p.Ponte.iniciar

    def iniciar(ponte: p.Ponte) -> None:
        ponte._conectar = lambda *a, **k: ws
        original(ponte)

    monkeypatch.setattr(p.Ponte, "iniciar", iniciar)
    assert servico.decidir_ligacao(True) == "Passando Ana Lima para você."
    assert n.central.decisoes == [("c1", True)] and n.maquina.em_ligacao
    assert {
        "tipo": "ligacao",
        "estado": "em_curso",
        "id": "c1",
        "nome": "Ana Lima",
    } in app.controles
    assert n.maquina.tratar(e.Aviso("Lembrete: beber água."), 0) == [
        e.ReterAviso("Lembrete: beber água.")
    ]
    assert app.sem_eco  # a sua voz vai crua: o celular já tira o eco
    folga = app.recebidos[0]
    assert folga == b"\0\0" * 3200  # 200 ms de silêncio contra os soluços da rede
    assert {"tipo": "voz", "taxa": 16000} in app.controles
    n.ponte_ligacao.enviar(b"mic")
    ws.entrada.put(b"pessoa")
    for _ in range(50):
        if len(app.recebidos) > 1:
            break
        threading.Event().wait(0.02)
    assert ws.enviados == [b"mic"] and app.recebidos == [folga, b"pessoa"]
    # O caso de 06/11/2026: o Zé respondeu ao "sim" pelo Live com a ponte aberta. A fala dele
    # trocava a taxa do app e silenciava o microfone; agora não chega ao app.
    controles = len(app.controles)
    app.controle(tipo="voz", taxa=24000)
    app.conexao.binario(b"fala do Ze")
    app.controle(tipo="fim")
    assert len(app.controles) == controles and app.recebidos == [folga, b"pessoa"]
    app.controle(tipo="whatsapp", leads=[])  # o que não é áudio passa
    assert app.controles[-1] == {"tipo": "whatsapp", "leads": []}
    assert servico.encerrar_ligacao() == "Ligação encerrada." and n.central.encerradas == ["c1"]
    for _ in range(50):
        if n.ponte_ligacao is None:
            break
        threading.Event().wait(0.02)
    assert n.ponte_ligacao is None and not n.maquina.em_ligacao
    assert app.conexao is app.real and not app.sem_eco  # o Zé volta a falar com o app
    assert app.controles[-1]["estado"] == "fim" and {"tipo": "fim"} in app.controles


def test_sem_o_app_conectado_o_agente_anota_o_recado() -> None:
    n = _ze(None)
    ServicoAtendimento(n)._evento_da_central(CHAMANDO)
    assert n.central.decisoes == [("c1", False)] and n.eventos.empty()
    assert n.linha == ["Ana Lima ligou e queria falar com você: o orçamento da reforma."]


def test_agora_nao_pelo_app_ou_pela_voz() -> None:
    app = App()
    n = _ze(app)
    servico = ServicoAtendimento(n)
    servico._evento_da_central(CHAMANDO)
    assert "anota o recado de Ana Lima" in servico.decidir_ligacao(False)
    assert n.central.decisoes == [("c1", False)] and not n.maquina.em_ligacao
    assert servico.decidir_ligacao(True) == "Nenhuma ligação esperando por você."


def test_a_voz_do_app_vai_para_a_ponte_e_nao_para_o_ei_ze() -> None:
    from zervis.nucleo.servicos.remoto import ServicoRemoto

    app = App()
    enviados: list[bytes] = []
    capturados: list[bytes] = []
    n: Any = SimpleNamespace(
        _fonte=app, microfone_travado=False, live=None,
        captura=SimpleNamespace(receber=capturados.append),
        ponte_ligacao=SimpleNamespace(ativa=True, voz=app, enviar=enviados.append),
    )  # fmt: skip
    ServicoRemoto(n)._quadro_remoto(app, b"q")
    assert enviados == [b"q"] and capturados == []
    n.ponte_ligacao.ativa = False
    ServicoRemoto(n)._quadro_remoto(app, b"r")
    assert capturados == [b"r"]


def test_pela_voz_atende_recusa_e_encerra() -> None:
    from zervis.cerebro.ferramentas import LIVRES
    from zervis.cerebro.ferramentas import whatsapp as w

    feitos: list[str] = []

    def decidir(atender: bool) -> str:
        feitos.append(f"decidir {atender}")
        return "ok"

    def encerrar() -> str:
        feitos.append("encerrar")
        return "fim"

    n: Any = SimpleNamespace(decidir_ligacao=decidir, encerrar_ligacao=encerrar)
    f: dict[str, Any] = {t.name: t.handler for t in w.ferramentas(n)}
    for acao in ("atender", "recusar", "encerrar"):
        asyncio.run(f["whatsapp_ligacao"]({"acao": acao}))
    assert feitos == ["decidir True", "decidir False", "encerrar"]
    assert asyncio.run(f["whatsapp_ligacao"]({"acao": "x"}))["is_error"]
    assert "mcp__jarvis__whatsapp_ligacao" in LIVRES


def test_o_prompt_ensina_a_chamar_pelo_nome_do_dono() -> None:
    assert "falar com Fulano" in lg.sistema(ag.Perfil(nome="Bia"), "Fulano")
    assert "[[CHAMAR:" in lg.sistema(ag.Perfil(nome="Bia"))


def test_alguem_na_camera_pede_para_falar_com_voce() -> None:
    """ADR 0088: a mesma pergunta pelo app, sem "na linha" e sem nome (ninguém se identificou)."""
    app = App()
    n = _ze(app)
    ServicoAtendimento(n)._evento_da_central(
        {
            "tipo": "chamando",
            "chamada": "camera",
            "nome": "",
            "telefone": "",
            "assunto": "o Carlos, entrega de um pacote",
            "origem": "camera",
        }
    )
    fala = n.eventos.get_nowait().texto
    assert "Alguém na câmera da entrada quer falar com você sobre o Carlos" in fala
    assert "na linha" not in fala
    assert app.controles[-1]["id"] == "camera"
    assert n.ligacao_pendente["id"] == "camera"
