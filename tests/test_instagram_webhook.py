"""Os avisos da Meta na hora (ADR 0122): a rota pública só aceita o desafio com o nosso token e o
aviso assinado com a chave do app; o aviso só acorda os ciclos que já existem."""

import hashlib
import hmac
import http.client
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from zervis.portal.servidor import Portal
from zervis.redes import instagram_webhook as iw
from zervis.redes.instagram import InstagramErro

SEGREDO = "0123456789abcdef0123456789abcdef"


def _assinado(corpo: bytes, segredo: str = SEGREDO) -> str:
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def _comentario(de: str = "999", conta: str = "111") -> bytes:
    return json.dumps({"object": "instagram", "entry": [{"id": conta, "changes": [
        {"field": "comments", "value": {"id": "c1", "text": "quero", "from": {"id": de}}}]}]}
    ).encode()  # fmt: skip


@pytest.fixture
def webhook(tmp_path: Path) -> iw.Webhook:
    assinaturas: list[int] = []
    w = iw.Webhook(tmp_path / "avisos.json", agora=lambda: 1000.0,
                   assinar=lambda: assinaturas.append(1))  # fmt: skip
    w.acordados = []  # type: ignore[attr-defined]
    w.acordar = lambda: w.acordados.append(1)  # type: ignore[attr-defined]
    w.assinaturas = assinaturas  # type: ignore[attr-defined]
    return w


def test_o_desafio_so_com_o_nosso_token(webhook: iw.Webhook) -> None:
    token = webhook.verificacao()
    assert len(token) >= 24 and webhook.verificacao() == token  # gerado uma vez, guardado
    ok = f"hub.mode=subscribe&hub.verify_token={token}&hub.challenge=42"
    assert webhook.desafio(ok) == "42"
    assert webhook.desafio("hub.mode=subscribe&hub.verify_token=outro&hub.challenge=42") is None
    assert webhook.desafio(f"hub.verify_token={token}&hub.challenge=42") is None


def test_so_o_aviso_assinado_acorda(webhook: iw.Webhook) -> None:
    corpo = _comentario()
    assert not webhook.receber(corpo, _assinado(corpo))  # sem a chave salva: recusado
    with pytest.raises(InstagramErro):
        webhook.guardar("curta")
    webhook.guardar(SEGREDO)
    assert webhook.assinaturas == [1]  # type: ignore[attr-defined]
    assert not webhook.confirmado()
    assert not webhook.receber(corpo, _assinado(corpo, "f" * 32))
    assert not webhook.receber(corpo + b" ", _assinado(corpo))  # o corpo mudou no caminho
    assert webhook.acordados == []  # type: ignore[attr-defined]
    assert webhook.estado()["recusados"] == 2  # salvar a chave zerou o de antes
    assert webhook.receber(corpo, _assinado(corpo))
    assert webhook.acordados == [1]  # type: ignore[attr-defined]
    assert webhook.confirmado() and webhook.estado()["ultimo"] == 1000.0
    assert "segredo" not in webhook.estado() and SEGREDO not in json.dumps(webhook.estado())
    assert oct(webhook.arquivo.stat().st_mode & 0o777) == "0o600"
    webhook.guardar("a" * 32)  # chave nova: espera de novo o primeiro aviso assinado
    assert not webhook.confirmado()
    webhook.esquecer()
    assert not webhook.estado()["configurado"]


def test_os_avisos_da_propria_conta_nao_acordam(webhook: iw.Webhook) -> None:
    webhook.guardar(SEGREDO)
    for corpo in (
        _comentario(de="111"),  # a resposta pública que o próprio Zé deu
        json.dumps(
            {"entry": [{"id": "111", "messaging": [{"message": {"text": "oi", "is_echo": True}}]}]}
        ).encode(),
        b"nao e json",
    ):
        assert webhook.receber(corpo, _assinado(corpo))
    assert webhook.acordados == []  # type: ignore[attr-defined]
    mensagem = json.dumps({"entry": [{"id": "111", "messaging": [{"message": {"text": "oi"}}]}]})
    assert webhook.receber(mensagem.encode(), _assinado(mensagem.encode()))
    assert webhook.acordados == [1]  # type: ignore[attr-defined]


def test_avisos_durante_uma_volta_viram_uma_volta_a_mais() -> None:
    entrou, solta, voltas = threading.Event(), threading.Event(), []

    def fazer() -> None:
        voltas.append(1)
        entrou.set()
        solta.wait(5)

    d = iw.Despertador(fazer, "teste-avisos")
    d.acordar()
    assert entrou.wait(5)
    for _ in range(5):  # cinco avisos enquanto a primeira volta anda
        d.acordar()
    entrou.clear()
    solta.set()
    assert entrou.wait(5)
    assert d._thread is not None
    d._thread.join(0.3)
    assert len(voltas) == 2


def _pedir(portal: Portal, metodo: str, caminho: str, corpo: bytes = b"",
           cab: dict[str, str] | None = None) -> tuple[int, str]:  # fmt: skip
    conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
    conn.request(metodo, caminho, body=corpo or None,
                 headers={"Host": f"127.0.0.1:{portal.porta}", **(cab or {})})  # fmt: skip
    resp = conn.getresponse()
    texto = resp.read().decode()
    conn.close()
    return resp.status, texto


def test_a_rota_publica_sem_entrar_no_painel(
    webhook: iw.Webhook, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(iw, "PADRAO", webhook)
    portal = Portal({}, {}, porta=0)
    portal.iniciar()
    try:
        token = webhook.verificacao()
        caminho = f"{iw.CAMINHO}?hub.mode=subscribe&hub.verify_token={token}&hub.challenge=abc"
        assert _pedir(portal, "GET", caminho) == (200, "abc")  # sem token do painel
        assert _pedir(portal, "GET", f"{iw.CAMINHO}?hub.mode=subscribe")[0] == 403
        corpo = _comentario()
        cab: dict[str, Any] = {"X-Hub-Signature-256": _assinado(corpo)}
        assert _pedir(portal, "POST", iw.CAMINHO, corpo, cab)[0] == 403  # sem a chave salva
        webhook.guardar(SEGREDO)
        assert _pedir(portal, "POST", iw.CAMINHO, corpo, {"X-Hub-Signature-256": "x"})[0] == 403
        assert _pedir(portal, "POST", iw.CAMINHO, corpo, cab)[0] == 200
        assert webhook.acordados == [1]  # type: ignore[attr-defined]
        assert _pedir(portal, "GET", "/publico/nada/x.jpg")[0] == 404  # os links seguem iguais
    finally:
        portal.parar()
