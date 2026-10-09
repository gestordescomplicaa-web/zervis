"""O painel do Zé: só local, com token, e a chave colada nunca volta para a tela."""

import http.client
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis import config
from jarvis.cerebro import rapido
from jarvis.portal.acoes import Acoes
from jarvis.portal.servidor import PedidoInvalido, Portal
from jarvis.voz import deepgram


def pedir(
    portal: Portal,
    metodo: str,
    caminho: str,
    corpo: dict[str, Any] | None = None,
    cracha: str | None = "certo",
    host: str | None = None,
) -> tuple[int, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
    cab = {"Host": host or f"127.0.0.1:{portal.porta}"}
    if cracha is not None:
        cab["X-Ze-Token"] = portal.token if cracha == "certo" else cracha
    dados = json.dumps(corpo).encode() if corpo is not None else None
    if dados is not None:
        cab["Content-Type"] = "application/json"
    conn.request(metodo, caminho, body=dados, headers=cab)
    resp = conn.getresponse()
    bruto = resp.read()
    conn.close()
    try:
        return resp.status, json.loads(bruto)
    except ValueError:
        return resp.status, bruto.decode()


@pytest.fixture
def portal() -> Any:
    def recusar(dados: dict[str, Any]) -> Any:
        raise PedidoInvalido("modelo vazio")

    p = Portal(
        {"estado": lambda: {"ze": "ativo"}},
        {"eco": lambda dados: {"recebi": dados}, "recusa": recusar},
        porta=0,
        envios={"anexo": lambda corpo, consulta: {"bytes": len(corpo), **consulta}},
    )
    p.iniciar()
    yield p
    p.parar()


def test_a_pagina_traz_o_token_e_a_api_exige_o_token(portal: Portal) -> None:
    status, pagina = pedir(portal, "GET", "/", cracha=None)
    assert status == 200 and portal.token in pagina and "__TOKEN__" not in pagina
    assert pedir(portal, "GET", "/painel.js", cracha=None)[0] == 200
    assert pedir(portal, "GET", "/api/estado") == (200, {"ze": "ativo"})
    assert pedir(portal, "GET", "/api/estado", cracha=None)[0] == 403
    assert pedir(portal, "GET", "/api/estado", cracha="outro")[0] == 403
    assert pedir(portal, "POST", "/api/eco", {"a": 1}) == (200, {"recebi": {"a": 1}})
    assert pedir(portal, "POST", "/api/eco", {"a": 1}, cracha=None)[0] == 403
    assert pedir(portal, "GET", "/api/nada")[0] == 404
    assert pedir(portal, "POST", "/api/recusa", {}) == (400, {"erro": "modelo vazio"})


def test_outro_host_e_recusado_mesmo_com_token(portal: Portal) -> None:
    """DNS rebinding: um site de fora apontando para 127.0.0.1 chega com outro Host."""
    assert pedir(portal, "GET", "/", host="malicioso.com")[0] == 403
    assert pedir(portal, "GET", "/api/estado", host="malicioso.com")[0] == 403


# --- a via rápida pelo painel ---------------------------------------------------------------


class NucleoFalso:
    def __init__(self) -> None:
        self.cfg = config.validar({}, "teste")
        self.cerebro = SimpleNamespace(modelo="claude-sonnet-5-5")
        self.provedor = "claude"
        self.aplicadas = 0
        self.deepgram: deepgram.Deepgram
        self.detector = SimpleNamespace(modelo=SimpleNamespace(treinada=False))

    def aplicar_via_rapida(self) -> str:
        self.aplicadas += 1
        return ""

    def persona_rapida(self) -> str:
        return "P"


@pytest.fixture
def acoes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Acoes, NucleoFalso]:
    monkeypatch.setattr(rapido, "CHAVES", tmp_path / "chaves")
    monkeypatch.setattr(rapido, "ESCOLHA", tmp_path / "via-rapida.json")
    for variavel in rapido.VARIAVEIS.values():
        monkeypatch.delenv(variavel, raising=False)
    n = NucleoFalso()
    n.deepgram = deepgram.Deepgram(tmp_path / "config" / "deepgram.key")
    return Acoes(n, tmp_path / "latencias", tmp_path / "teste"), n


def test_a_chave_vai_para_um_arquivo_so_do_usuario_e_nunca_volta(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path
) -> None:
    a, n = acoes
    resposta = a.guardar_chave({"motor": "openai", "chave": "sk-segredo-1234"})
    texto = json.dumps(resposta)
    assert "sk-segredo" not in texto
    assert resposta["chaves"]["openai"] == {
        "usa": True,
        "tem": True,
        "origem": "painel",
        "fim": "1234",
    }
    arquivo = tmp_path / "chaves" / "openai.key"
    assert arquivo.read_text() == "sk-segredo-1234\n"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert stat.S_IMODE(arquivo.parent.stat().st_mode) == 0o700
    assert n.aplicadas == 0  # o motor em uso é o plano: nada a trocar
    with pytest.raises(PedidoInvalido):
        a.guardar_chave({"motor": "openai", "chave": "com espaço"})
    with pytest.raises(PedidoInvalido):
        a.guardar_chave({"motor": "plano", "chave": "x"})
    a.apagar_chave({"motor": "openai"})
    assert not arquivo.exists()


def test_mudar_o_motor_grava_por_cima_da_config_e_aplica_na_hora(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path
) -> None:
    a, n = acoes
    assert a.cerebro()["via"]["motor"] == "plano"
    resposta = a.mudar_cerebro({"motor": "openai", "modelo": "gpt-5.4-mini", "ligada": True})
    assert resposta["via"]["motor"] == "openai" and n.aplicadas == 1
    assert json.loads((tmp_path / "via-rapida.json").read_text())["modelo"] == "gpt-5.4-mini"
    for errado in (
        {"motor": "groq"},
        {"modelo": ""},
        {"endereco": "http://site-de-fora.com/v1"},
        {"arquivo_chave": "/etc/passwd"},
        {"ligada": "sim"},
    ):
        with pytest.raises(PedidoInvalido):
            a.mudar_cerebro(errado)
    # A ponte sem endereço não vale: fica a config.
    a.mudar_cerebro({"motor": "ponte"})
    assert rapido.efetiva(n.cfg["via_rapida"])["motor"] == "plano"


def test_testar_sem_chave_avisa_sem_chamar_ninguem(acoes: tuple[Acoes, NucleoFalso]) -> None:
    a, _ = acoes
    assert a.testar({"motor": "anthropic", "modelo": "claude-haiku-4-5"}) == {
        "ok": False,
        "erro": "falta a chave deste motor",
    }


def test_a_chave_do_deepgram_liga_a_escuta_na_hora_e_nunca_volta(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, n = acoes
    conferidas: list[str] = []

    def conferir(chave: str) -> tuple[bool, str]:
        conferidas.append(chave)
        return chave.endswith("9876"), "O Deepgram recusou a chave."

    monkeypatch.setattr(deepgram, "conferir", conferir)
    assert a.escuta()["deepgram"] == {"tem": False, "fim": ""}
    assert a.escuta()["ativacao"] is False
    resposta = a.guardar_chave_escuta({"chave": "dg-segredo-9876"})
    assert "dg-segredo" not in json.dumps(resposta)
    assert resposta["deepgram"] == {"tem": True, "fim": "9876"} and resposta["valida"]
    assert n.deepgram.disponivel  # sem reiniciar
    arquivo = tmp_path / "config" / "deepgram.key"
    assert arquivo.read_text() == "dg-segredo-9876\n"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert not a.guardar_chave_escuta({"chave": "errada-0000"})["valida"]
    assert a.testar_chave_escuta({}) == {"ok": False, "mensagem": "O Deepgram recusou a chave."}
    assert conferidas[-1] == "errada-0000"  # sem chave colada, confere a guardada
    with pytest.raises(PedidoInvalido):
        a.guardar_chave_escuta({"chave": "com espaço"})
    a.apagar_chave_escuta({})
    assert not arquivo.exists() and not n.deepgram.disponivel


def test_conferir_a_chave_do_deepgram_distingue_recusa_de_rede() -> None:
    import urllib.error

    def recusa(pedido: Any, timeout: float) -> Any:
        raise urllib.error.HTTPError(pedido.full_url, 401, "Unauthorized", {}, None)  # type: ignore[arg-type]

    def sem_rede(pedido: Any, timeout: float) -> Any:
        raise OSError("sem rede")

    assert deepgram.conferir("x", recusa) == (False, "O Deepgram recusou a chave.")
    assert deepgram.conferir("x", sem_rede)[0] is False


def test_os_arquivos_da_pagina_sao_leves() -> None:
    web = Path(__file__).resolve().parents[1] / "jarvis/portal/web"
    total = sum(f.stat().st_size for f in web.iterdir())
    assert total < 100_000, total  # docs/plano-painel.md: abaixo de 100 KB
    assert "http" not in (web / "index.html").read_text().replace("http://www.w3.org", "")
    assert os.access(web / "painel.js", os.R_OK)


def test_envio_de_arquivo_cru_com_token(portal: Portal) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
    cab = {"Host": f"127.0.0.1:{portal.porta}", "X-Ze-Token": portal.token}
    conn.request("POST", "/api/anexo?id=ab12cd34&nome=foto.png", body=b"\x89PNG" * 10, headers=cab)
    resp = conn.getresponse()
    assert resp.status == 200
    assert json.loads(resp.read()) == {"bytes": 40, "id": "ab12cd34", "nome": "foto.png"}
    conn.request("POST", "/api/anexo?id=x", body=b"x", headers={"Host": cab["Host"]})
    assert conn.getresponse().status == 403
