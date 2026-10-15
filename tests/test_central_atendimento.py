"""A Central de Atendimento (ADR 0031): serviço próprio, API local com token e eventos."""

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from jarvis.atendimento import central as c
from jarvis.atendimento import cliente as cl
from jarvis.atendimento import whatsapp as wa_mod
from jarvis.atendimento.whatsapp import Recebida


def test_token_criado_uma_vez_so_para_o_dono(tmp_path: Path) -> None:
    arquivo = tmp_path / "atendimento.token"
    primeiro = c.garantir_token(arquivo)
    assert len(primeiro) == 64 and c.garantir_token(arquivo) == primeiro
    assert arquivo.stat().st_mode & 0o777 == 0o600


def test_eventos_numerados_com_espera_longa() -> None:
    ev = c.Eventos(tamanho=3)
    assert ev.depois(0) == ([], 0)
    threading.Timer(0.1, lambda: ev.publicar("passou", nome="Ana", motivo="quer fechar")).start()
    inicio = time.monotonic()
    lista, ultimo = ev.depois(0, espera=5)
    assert time.monotonic() - inicio < 2 and ultimo == 1 and lista[0]["nome"] == "Ana"
    for i in range(4):
        ev.publicar("mensagem", n=i)
    lista, ultimo = ev.depois(1)
    assert ultimo == 5 and [e["id"] for e in lista] == [3, 4, 5]  # a fila guarda só as últimas
    assert ev.depois(99)[1] == 5  # quem viu mais do que existe (Central nova) recomeça


class WhatsAppFalso:
    def __init__(self) -> None:
        self.conectou = False
        self.desconectou = False

    def para_tela(self) -> dict[str, Any]:
        return {"estado": "conectado" if self.conectou else "desconectado"}

    def conectar_em_segundo_plano(self) -> None:
        self.conectou = True

    def desconectar(self) -> None:
        self.desconectou = True

    def iniciar(self) -> None:
        pass

    def parar(self) -> None:
        pass


class AtendenteFalso:
    def __init__(self, pasta: Path) -> None:
        from jarvis.atendimento.agente import Registros

        self.registros = Registros(pasta)
        self.recebidas: list[Recebida] = []

    def receber(self, r: Recebida) -> None:
        self.recebidas.append(r)

    def parar(self) -> None:
        pass


def _central(tmp_path: Path, avisos: bool = True) -> tuple[c.Central, Any, Any]:
    wa, at = WhatsAppFalso(), AtendenteFalso(tmp_path)
    central = c.Central(lambda: None, wa, at, avisos_ligados=lambda: avisos)  # type: ignore[arg-type, return-value]
    return central, wa, at


def test_mensagem_recebida_vai_ao_agente_e_aos_avisos(tmp_path: Path) -> None:
    central, _, at = _central(tmp_path)
    central._recebida(Recebida("s:1", "Ana", "5511", "quanto custa?"))
    central._recebida(Recebida("s:2", "Eu", "5511", "oi", de_mim=True))
    assert [r.id for r in at.recebidas] == ["s:1", "s:2"]
    eventos, _ = central.eventos.depois(0)
    assert [(e["tipo"], e["nome"]) for e in eventos] == [("mensagem", "Ana")]
    sem_avisos, _, _ = _central(tmp_path / "outra-instalacao", avisos=False)
    sem_avisos._recebida(Recebida("s:3", "Ana", "5511", "oi"))
    assert sem_avisos.eventos.depois(0) == ([], 0)


def _pedir(porta: int, metodo: str, caminho: str, token: str, corpo: Any = None) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    pedido = urllib.request.Request(
        f"http://127.0.0.1:{porta}{caminho}",
        data=None if corpo is None else json.dumps(corpo).encode(),
        method=metodo,
        headers={"X-Atendimento-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=5) as r:  # noqa: S310 (local)
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as erro:
        return erro.code, None


def test_api_local_com_token(tmp_path: Path) -> None:
    central, wa, at = _central(tmp_path)
    porta = central.servir("segredo")
    try:
        assert _pedir(porta, "GET", "/saude", "errado")[0] == 401
        codigo, saude = _pedir(porta, "GET", "/saude", "segredo")
        assert codigo == 200 and saude["versao"] == c.versao()
        assert _pedir(porta, "POST", "/whatsapp/conectar", "segredo", {})[0] == 200 and wa.conectou
        assert _pedir(porta, "GET", "/whatsapp", "segredo") == (200, {"estado": "conectado"})
        at.registros.pausar("5511999990000", "Ana", "quer fechar")
        assert _pedir(porta, "GET", "/pausados", "segredo")[1]["pausados"][0]["nome"] == "Ana"
        assert (
            _pedir(porta, "POST", "/devolver", "segredo", {"telefone": "5511999990000"})[0] == 200
        )
        assert at.registros.pausados() == []
        assert _pedir(porta, "GET", "/nada", "segredo")[0] == 404
    finally:
        central.parar()


class LancadorFalso:
    """Faz o papel do systemd: "subir" cria uma Central no próprio processo."""

    def __init__(self, tmp_path: Path, estado: Path, token: Path, versao: str = "") -> None:
        self.tmp_path, self.estado, self.token, self.versao = tmp_path, estado, token, versao
        self.central: c.Central | None = None
        self.subidas = 0

    def ativo(self) -> bool:
        return self.central is not None

    def iniciar(self, comando: list[str], registro: Path) -> None:
        self.subidas += 1
        self.central, _, _ = _central(self.tmp_path)
        porta = self.central.servir(c.garantir_token(self.token))
        self.estado.write_text(json.dumps({"porta": porta}))

    def parar(self) -> None:
        if self.central is not None:
            self.central.parar()
            self.central = None


def test_cliente_sobe_a_central_recebe_eventos_e_reinicia_versao_velha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estado, token = tmp_path / "atendimento.json", tmp_path / "atendimento.token"
    lancador = LancadorFalso(tmp_path, estado, token)
    eventos: list[dict[str, Any]] = []
    ze = cl.Cliente(eventos.append, lancador, estado, token)  # type: ignore[arg-type]
    try:
        ze.garantir()
        ze.garantir()  # já de pé e na mesma versão: não sobe outra
        assert lancador.subidas == 1
        ze.conectar()
        assert ze.para_tela() == {"estado": "conectado"} and ze.whatsapp_ativo
        assert lancador.central is not None
        lancador.central._passou("Ana", "quer fechar")
        fim = time.monotonic() + 5
        while not eventos:
            assert time.monotonic() < fim
            time.sleep(0.02)
        assert eventos[0]["tipo"] == "passou" and eventos[0]["nome"] == "Ana"

        monkeypatch.setattr(c, "versao", lambda: "outra")  # o Zé foi atualizado
        ze.garantir()
        assert lancador.subidas == 2
    finally:
        ze.parar()
        lancador.parar()


def test_central_desligada_mostra_o_estado_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_mod, "escolhido", lambda: False)
    monkeypatch.setattr(wa_mod, "go", lambda: "/usr/bin/go")
    ze = cl.Cliente(lambda e: None, LancadorFalso(tmp_path, tmp_path / "e", tmp_path / "t"),  # type: ignore[arg-type]
                    tmp_path / "e", tmp_path / "t")  # fmt: skip
    assert ze.para_tela() == {"estado": "desligado", "falha": ""} and not ze.whatsapp_ativo
    assert ze.pausados() == []
    monkeypatch.setattr(wa_mod, "escolhido", lambda: True)
    assert ze.para_tela() == {"estado": "iniciando"}
