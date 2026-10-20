"""O WhatsApp do atendimento (ADR 0031, etapa 1): o WaCalls dentro do Zé."""

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from zervis.atendimento import whatsapp as w
from zervis.avisos import mensagens as m

CHAT = "5511999990000@s.whatsapp.net"


def _lote(*itens: Any) -> dict[str, Any]:
    return {"mensagens": list(itens)}


def _msg(**campos: Any) -> dict[str, Any]:
    base = {
        "event_id": "s:1",
        "direction": "inbound",
        "type": "text",
        "content": "quanto custa?",
        "phone": "5511999990000",
        "push_name": "Ana  Souza",
        "chat_jid": "5511999990000@s.whatsapp.net",
    }
    return {**base, **campos}


def test_so_texto_vira_mensagem_recebida_ou_enviada() -> None:
    lote = _lote(
        _msg(),
        _msg(event_id="s:2", direction="outbound"),
        _msg(event_id="s:3", type="media", content=""),
        _msg(event_id="s:4", content="   "),
        _msg(event_id="s:5", push_name="", content="oi"),
        "lixo",
    )
    assert w.recebidas(lote) == [
        w.Recebida("s:1", "Ana Souza", "5511999990000", "quanto custa?", chat=CHAT),
        w.Recebida("s:2", "Ana Souza", "5511999990000", "quanto custa?", True, CHAT),
        w.Recebida("s:5", "5511999990000", "5511999990000", "oi", chat=CHAT),
    ]
    assert w.recebidas({"mensagens": "x"}) == [] and w.recebidas(None) == []


def test_numero_do_jid() -> None:
    assert w.numero("5511999990000:12@s.whatsapp.net") == "5511999990000"
    assert w.numero("") == ""


def test_token_do_receptor_e_o_mesmo_do_wacalls() -> None:
    # msgsender.go: sha256("agente-voz/interno/v1:" + semente)
    fonte = (w.FONTE / "cmd" / "server" / "msgsender.go").read_text()
    assert f'"{w.ROTULO}"' in fonte
    assert w.token_interno("abc") == hashlib.sha256(b"agente-voz/interno/v1:abc").hexdigest()


def _pedir(porta: int, caminho: str, token: str, corpo: Any = None) -> tuple[int, Any]:
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{porta}{caminho}",
        data=dados,
        method="POST" if dados else "GET",
        headers={"X-Internal-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=5) as r:  # noqa: S310 (local)
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as erro:
        return erro.code, None


def test_receptor_exige_token_responde_a_captura_e_deduplica() -> None:
    capturar = [False]
    entregues: list[list[w.Recebida]] = []
    receptor = w.Receptor("certo", lambda: capturar[0], entregues.append)
    porta = receptor.iniciar()
    try:
        captura = "/api/interno/whatsapp/captura/fb2aada0c33a73dec601d8ccc0c3a392"
        assert _pedir(porta, captura, "errado")[0] == 401
        assert _pedir(porta, captura, "certo") == (200, {"capturar": False})
        capturar[0] = True
        assert _pedir(porta, captura, "certo") == (200, {"capturar": True})
        assert _pedir(porta, "/api/interno/whatsapp/captura/../x", "certo")[0] == 404

        caminho = "/api/interno/whatsapp/mensagens"
        assert _pedir(porta, caminho, "errado", _lote(_msg()))[0] == 401
        assert _pedir(porta, caminho, "certo", _lote(_msg())) == (200, {"recebidas": 1})
        # a fila do WaCalls reenvia o que não confirmou: a repetição não vira aviso de novo
        assert _pedir(porta, caminho, "certo", _lote(_msg(), _msg(event_id="s:9"))) == (
            200,
            {"recebidas": 1},
        )
    finally:
        receptor.parar()
    assert [[r.id for r in lote] for lote in entregues] == [["s:1"], ["s:9"]]


def _fonte(tmp_path: Path) -> Path:
    fonte = tmp_path / "wacalls"
    (fonte / "cmd" / "server").mkdir(parents=True)
    (fonte / "go.mod").write_text("module wacalls\n")
    (fonte / "cmd" / "server" / "main.go").write_text("package main\n")
    return fonte


def test_compila_uma_vez_por_versao_do_codigo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonte = _fonte(tmp_path)
    pasta = tmp_path / "dados"
    chamadas: list[list[str]] = []

    def executar(comando: list[str], **opcoes: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append(comando)
        assert opcoes["cwd"] == fonte and opcoes["env"]["CGO_ENABLED"] == "0"
        Path(comando[comando.index("-o") + 1]).write_text("binário")
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(w, "go", lambda: "/usr/bin/go")
    primeiro = w.compilar(pasta, fonte, executar)
    assert primeiro.name == f"wacalls-{w.impressao(fonte)}" and primeiro.read_text() == "binário"
    assert w.compilar(pasta, fonte, executar) == primeiro and len(chamadas) == 1

    (fonte / "cmd" / "server" / "main.go").write_text("package main // mudou\n")
    segundo = w.compilar(pasta, fonte, executar)
    assert segundo != primeiro and not primeiro.exists() and len(chamadas) == 2


def test_falha_na_compilacao_ou_sem_go(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fonte = _fonte(tmp_path)
    monkeypatch.setattr(w, "go", lambda: None)
    with pytest.raises(w.WhatsAppErro, match="Go não encontrado"):
        w.compilar(tmp_path / "dados", fonte)
    monkeypatch.setattr(w, "go", lambda: "/usr/bin/go")

    def falhar(comando: list[str], **opcoes: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(comando, 1, "", "erro de compilação")

    with pytest.raises(w.WhatsAppErro, match="Não foi possível preparar"):
        w.compilar(tmp_path / "dados", fonte, falhar)
    assert list((tmp_path / "dados" / "bin").iterdir()) == []


class FilhoFalso:
    def __init__(self, nome: str, comando: list[str], ambiente: dict[str, str], **_: Any) -> None:
        self.comando = comando
        self.ambiente = ambiente
        self.parado = False

    def iniciar(self) -> None:
        pass

    def parar(self) -> None:
        self.parado = True


class WaCallsFalso:
    """Responde como a API do WaCalls; guarda o que foi pedido."""

    def __init__(self) -> None:
        self.sessoes: list[dict[str, Any]] = []
        self.pedidos: list[tuple[str, str]] = []
        self.token = ""

    def __call__(self, pedido: urllib.request.Request, timeout: float) -> Any:
        assert pedido.full_url.startswith("http://127.0.0.1:")
        assert pedido.get_header("X-internal-token") == self.token
        caminho = "/" + pedido.full_url.split("/", 3)[3]
        metodo = pedido.get_method()
        self.pedidos.append((metodo, caminho))
        resposta: Any = {}
        if (metodo, caminho) == ("GET", "/api/sessions"):
            resposta = {"sessions": self.sessoes}
        elif (metodo, caminho) == ("POST", "/api/sessions"):
            self.sessoes = [{"id": "ab12", "state": "qr", "paired": False, "qr": "2@codigo"}]
            resposta = {"id": "ab12"}

        class Resposta:
            def __enter__(self) -> "Resposta":
                return self

            def __exit__(self, *_: Any) -> None:
                pass

            def read(self) -> bytes:
                return json.dumps(resposta).encode()

        return Resposta()


def _pronto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[w.WhatsApp, WaCallsFalso]:
    fonte = _fonte(tmp_path)
    pasta = tmp_path / "dados"
    (pasta / "bin").mkdir(parents=True)
    (pasta / "bin" / f"wacalls-{w.impressao(fonte)}").write_text("binário")
    monkeypatch.setattr(w, "Filho", FilhoFalso)
    monkeypatch.setattr(w, "ESCOLHA", tmp_path / "config" / "whatsapp.json")
    monkeypatch.setattr(w, "escolher", lambda ativo: (tmp_path / "escolha").write_text(str(ativo)))
    falso = WaCallsFalso()
    wa = w.WhatsApp(lambda r: None, lambda: True, pasta, fonte, falso)
    return wa, falso


def test_conectar_sobe_so_no_endereco_local_e_pede_o_qr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wa, falso = _pronto(tmp_path, monkeypatch)
    assert wa.para_tela()["estado"] == "desligado"
    wa.iniciar()
    falso.token = wa.token
    filho = wa.filho
    assert isinstance(filho, FilhoFalso)
    endereco = filho.comando[filho.comando.index("-addr") + 1]
    assert endereco.startswith("127.0.0.1:")
    assert len(filho.ambiente["WACALLS_INTERNAL_TOKEN"]) == 64
    assert filho.ambiente["DASHBOARD_URL"].startswith("http://127.0.0.1:")
    assert filho.ambiente["WA_DEVICE_NAME"] == "Zérvis"
    assert wa.para_tela() == {"estado": "desconectado"}

    wa.conectar()
    assert ("POST", "/api/sessions") in falso.pedidos
    assert (tmp_path / "escolha").read_text() == "True"
    assert wa.para_tela() == {"estado": "aguardando", "qr": "2@codigo"}

    falso.sessoes = [{"id": "ab12", "state": "open", "paired": True, "jid": "5511988887777:3@s"}]
    assert wa.para_tela() == {"estado": "conectado", "numero": "5511988887777"}
    wa.conectar()  # já pareado: nada a pedir
    assert falso.pedidos.count(("POST", "/api/sessions")) == 1

    wa.desconectar()
    assert ("DELETE", "/api/sessions/ab12") in falso.pedidos
    assert (tmp_path / "escolha").read_text() == "False"
    assert filho.parado and not wa.ativo
    wa.parar()


def test_desconectado_pede_novo_qr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wa, falso = _pronto(tmp_path, monkeypatch)
    wa.iniciar()
    falso.token = wa.token
    falso.sessoes = [{"id": "cd34", "state": "logged_out", "paired": False}]
    wa.conectar()
    assert falso.pedidos[-1] == ("POST", "/api/sessions/cd34/pair")
    wa.parar()


def test_sem_go_e_sem_binario_fica_indisponivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(w, "go", lambda: None)
    wa = w.WhatsApp(lambda r: None, lambda: True, tmp_path / "dados", _fonte(tmp_path))
    assert wa.para_tela() == {"estado": "indisponivel", "falha": ""}


class MotorFalso:
    com_estado = False

    def __init__(self) -> None:
        self.pedidos: list[str] = []

    async def iniciar(self, sistema: str) -> None:
        pass

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        self.pedidos.append(mensagens[0]["content"])
        yield "SIM" if "preço" in mensagens[0]["content"] else "NAO"

    async def reiniciar(self) -> None:
        pass

    async def fechar(self) -> None:
        pass


def test_mensagem_do_whatsapp_conectado_vira_aviso_sem_o_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(m, "disponivel", lambda: False)
    avisos: list[str] = []
    motor = MotorFalso()
    vigia = m.Mensagens(avisos.append, lambda: motor)
    vigia.receber("Ana", "oi")  # desligado: ignorada
    vigia.iniciar()
    try:
        fim = time.monotonic() + 5
        while vigia._fila is None:
            assert time.monotonic() < fim
            time.sleep(0.01)
        vigia.receber("Bruno", "bom dia")
        vigia.receber("Ana", "qual o preço do plano?")
        while not avisos:
            assert time.monotonic() < fim
            time.sleep(0.02)
    finally:
        vigia.parar()
    assert avisos == ["Lead quente no WhatsApp: Ana."]
    assert len(motor.pedidos) == 2 and all("<<<" in p for p in motor.pedidos)


def test_painel_mostra_o_qr_como_imagem_e_exige_confirmacao_para_desconectar(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    from zervis.portal.acoes import Acoes
    from zervis.portal.servidor import PedidoInvalido

    desconexoes: list[bool] = []

    def desconectar() -> str:
        desconexoes.append(True)
        return "WhatsApp desconectado."

    nucleo = SimpleNamespace(
        central=SimpleNamespace(
            para_tela=lambda: {"estado": "aguardando", "qr": "2@codigo"}, pausados=lambda: []
        ),
        mensagens=SimpleNamespace(ativo=False),
        deepgram=SimpleNamespace(disponivel=True),
        projeto_agente=tmp_path / "agente",
        desconectar_whatsapp=desconectar,
    )
    acoes = Acoes(nucleo, tmp_path, tmp_path)
    tela = acoes.atendimento()
    assert tela["whatsapp"]["estado"] == "aguardando"
    assert tela["whatsapp"]["qr"].startswith("<svg") and "2@codigo" not in tela["whatsapp"]["qr"]
    assert tela["avisos"] == {"ligado": False}
    with pytest.raises(PedidoInvalido):
        acoes.desconectar_whatsapp({})
    assert not desconexoes
    assert acoes.desconectar_whatsapp({"confirmado": True})["aviso"] == "WhatsApp desconectado."


def test_so_conversa_privada_entra_nunca_grupo_status_ou_canal() -> None:
    assert w.privado("5511999990000@s.whatsapp.net") and w.privado("123456789012@lid")
    for chat in (
        "120363000000000000@g.us",  # grupo
        "status@broadcast",
        "120363000000000000@newsletter",  # canal
        "5511999990000@g.us",
        "",
        "5511@s.whatsapp.net.evil",
    ):
        assert not w.privado(chat), chat
    lote = _lote(
        _msg(event_id="g:1", chat_jid="120363000000000000@g.us"),
        _msg(event_id="b:1", chat_jid="status@broadcast"),
        _msg(event_id="p:1"),
    )
    assert [r.id for r in w.recebidas(lote)] == ["p:1"]


def test_envio_so_para_um_numero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wa, falso = _pronto(tmp_path, monkeypatch)
    wa.iniciar()
    falso.token = wa.token
    for destino in ("120363000000000000@g.us", "120363000000000000-123", "status"):
        with pytest.raises(w.WhatsAppErro, match="Destino inválido"):
            wa.enviar(destino, "oi", "atendimento:12345678")
    assert not any("/messages" in caminho for _, caminho in falso.pedidos)
    wa.parar()
