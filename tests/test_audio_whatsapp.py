"""O áudio na conversa com o Zé (ADR 0103): só o do seu número é baixado, o Deepgram transcreve e
o texto vira o pedido."""

import io
import json
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.atendimento import central as c
from zervis.atendimento import whatsapp as w
from zervis.atendimento.whatsapp import Recebida
from zervis.nucleo.servicos import atendimento as sa
from zervis.voz import deepgram

DONO = "5511999990000"
EU = "5511999990000@s.whatsapp.net"


class Resposta:
    def __init__(self, corpo: bytes, tipo: str = "application/json") -> None:
        self.corpo = corpo
        self.headers = {"Content-Type": tipo}

    def __enter__(self) -> "Resposta":
        return self

    def __exit__(self, *_: Any) -> None:
        pass

    def read(self) -> bytes:
        return self.corpo


def test_deepgram_transcreve_o_arquivo_em_portugues_com_os_termos_do_ze() -> None:
    pedidos: list[Any] = []

    def abrir(pedido: Any, timeout: float) -> Resposta:
        pedidos.append(pedido)
        dados = {"results": {"channels": [{"alternatives": [{"transcript": " liga o Zé "}]}]}}
        return Resposta(json.dumps(dados).encode())

    assert deepgram.transcrever("chave", b"ogg", "audio/ogg; codecs=opus", abrir) == "liga o Zé"
    [p] = pedidos
    assert p.full_url.startswith(deepgram.ARQUIVO + "?")
    assert "model=nova-3" in p.full_url and "language=pt-BR" in p.full_url
    assert "keyterm=Z%C3%A9" in p.full_url
    assert p.get_header("Authorization") == "Token chave"
    assert p.get_header("Content-type") == "audio/ogg; codecs=opus" and p.data == b"ogg"


def test_deepgram_sem_fala_e_com_recusa() -> None:
    def vazio(pedido: Any, timeout: float) -> Resposta:
        return Resposta(b'{"results": {"channels": []}}')

    assert deepgram.transcrever("chave", b"ogg", "", vazio) == ""

    def sem_credito(pedido: Any, timeout: float) -> Resposta:
        raise urllib.error.HTTPError(pedido.full_url, 402, "x", {}, io.BytesIO())  # type: ignore[arg-type]

    with pytest.raises(deepgram.EscutaErro, match="sem crédito"):
        deepgram.transcrever("chave", b"ogg", "", sem_credito)


def test_wacalls_entrega_o_audio_pelo_id_do_evento(tmp_path: Path) -> None:
    pedidos: list[Any] = []

    def abrir(pedido: Any, timeout: float) -> Resposta:
        pedidos.append(pedido)
        if pedido.full_url.endswith("404"):
            raise urllib.error.HTTPError(pedido.full_url, 404, "x", {}, io.BytesIO())  # type: ignore[arg-type]
        return Resposta(b"OggS", "audio/ogg; codecs=opus")

    wa = w.WhatsApp(lambda r: None, lambda: True, tmp_path, tmp_path, abrir)
    wa.porta, wa.token = 4321, "segredo"
    wa.sessoes = lambda: [{"id": "s", "paired": True, "state": "open"}]  # type: ignore[method-assign]
    assert wa.baixar_audio("s:1") == (b"OggS", "audio/ogg; codecs=opus")
    assert pedidos[0].full_url == "http://127.0.0.1:4321/api/sessions/s/audio?evento=s%3A1"
    assert pedidos[0].get_header("X-internal-token") == "segredo"
    with pytest.raises(w.WhatsAppErro, match="404"):
        wa.baixar_audio("s:404")
    wa.sessoes = lambda: []  # type: ignore[method-assign]
    with pytest.raises(w.WhatsAppErro, match="não conectado"):
        wa.baixar_audio("s:1")


# --- a Central ------------------------------------------------------------------------------


class WhatsAppFalso:
    def __init__(self, falha: bool = False) -> None:
        self.baixados: list[str] = []
        self.falha = falha

    def baixar_audio(self, evento: str) -> tuple[bytes, str]:
        self.baixados.append(evento)
        if self.falha:
            raise w.WhatsAppErro("Sem conexão com o WhatsApp.")
        return b"OggS", "audio/ogg"


def _central(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    chave: str | None = "chave",
    falha: bool = False,
) -> tuple[c.Central, WhatsAppFalso]:
    from zervis.atendimento.agente import Registros

    monkeypatch.setattr(w, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    w.configurar_conversa(True, [DONO])
    wa = WhatsAppFalso(falha)
    atendente = SimpleNamespace(registros=Registros(tmp_path), receber=lambda r: None)
    central = c.Central(lambda: None, wa, atendente, chave_deepgram=lambda: chave)  # type: ignore[arg-type, return-value]
    return central, wa


def _audio(ident: str = "s:1", telefone: str = DONO) -> Recebida:
    return Recebida(ident, "Gabriel", telefone, "", chat=EU, midia="audio")


def _esperar_pedido(central: c.Central) -> dict[str, Any]:
    [evento], _ = central.eventos.depois(0, espera=5)
    return evento


def test_audio_do_seu_numero_vira_pedido_com_o_texto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    central, wa = _central(tmp_path, monkeypatch)
    monkeypatch.setattr(deepgram, "transcrever", lambda chave, dados, tipo: "que horas são")
    central._recebida(_audio())
    evento = _esperar_pedido(central)
    assert (evento["tipo"], evento["texto"], evento["midia"], evento["audio"]) == (
        "pedido",
        "que horas são",
        "",
        True,
    )
    assert wa.baixados == ["s:1"]


def test_audio_de_outro_numero_nunca_e_baixado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    central, wa = _central(tmp_path, monkeypatch)
    central._recebida(_audio(telefone="5511988887777"))
    time.sleep(0.1)
    assert wa.baixados == []
    assert [e["tipo"] for e in central.eventos.depois(0)[0]] == ["mensagem"]


@pytest.mark.parametrize(
    ("chave", "falha", "texto", "motivo"),
    [(None, False, "x", "sem_chave"), ("chave", True, "x", "transcricao"),
     ("chave", False, "", "transcricao")],
)  # fmt: skip
def test_audio_sem_chave_sem_download_ou_sem_fala_leva_o_motivo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    chave: str | None,
    falha: bool,
    texto: str,
    motivo: str,
) -> None:
    central, _ = _central(tmp_path, monkeypatch, chave, falha)
    monkeypatch.setattr(deepgram, "transcrever", lambda chave, dados, tipo: texto)
    central._recebida(_audio())
    evento = _esperar_pedido(central)
    assert (evento["midia"], evento["falha"]) == ("audio", motivo)


# --- o serviço no Zé ------------------------------------------------------------------------


def test_o_ze_avisa_por_que_o_audio_nao_foi_entendido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(w, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    w.configurar_conversa(True, [DONO])
    enviadas: list[tuple[str, str]] = []
    pedidos: list[tuple[str, str]] = []

    def pedir(texto: str, destino: str = "") -> bool:
        pedidos.append((texto, destino))
        return True

    n = SimpleNamespace(
        central=SimpleNamespace(enviar=lambda t, k, chat="": enviadas.append((chat, t))),
        conversa_whatsapp=SimpleNamespace(pedir=pedir),
    )
    servico = sa.ServicoAtendimento(n)
    base = {"tipo": "pedido", "chat": EU, "hora": time.time()}
    servico._evento_da_central({**base, "texto": "", "midia": "audio", "falha": "sem_chave"})
    servico._evento_da_central({**base, "texto": "", "midia": "audio", "falha": "transcricao"})
    servico._evento_da_central({**base, "texto": "que horas são", "midia": "", "audio": True})
    assert enviadas == [(EU, sa.AUDIO_SEM_CHAVE), (EU, sa.AUDIO_FALHOU)]
    assert pedidos == [("que horas são", EU)]
