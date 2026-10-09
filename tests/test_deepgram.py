"""Escuta pelo Deepgram com um WebSocket de mentira: parciais, Finalize, falhas e privacidade."""

import json
import queue
import time
from pathlib import Path
from typing import Any

import pytest

from jarvis.voz.deepgram import Deepgram, EscutaDeepgram, EscutaErro, ler_chave


def _resultado(texto: str, final: bool, do_finalize: bool = False) -> str:
    return json.dumps(
        {
            "type": "Results",
            "is_final": final,
            "from_finalize": do_finalize,
            "channel": {"alternatives": [{"transcript": texto}]},
        }
    )


class WsFalso:
    """Responde parciais enquanto recebe áudio e o final quando chega o Finalize."""

    def __init__(self, responde_finalize: bool = True) -> None:
        self.enviados: list[Any] = []
        self.respostas: queue.Queue[str | None] = queue.Queue()
        self.responde_finalize = responde_finalize
        self.url = ""

    def send(self, dado: Any) -> None:
        self.enviados.append(dado)
        if isinstance(dado, bytes) and len(self.enviados) == 1:
            self.respostas.put(_resultado("pede para", final=False))
            self.respostas.put(_resultado("Pede para um Codex", final=True))
        elif (
            isinstance(dado, str)
            and json.loads(dado)["type"] == "Finalize"
            and self.responde_finalize
        ):
            self.respostas.put(_resultado("rodar os testes.", final=True, do_finalize=True))
        elif isinstance(dado, str) and json.loads(dado)["type"] == "CloseStream":
            self.respostas.put(None)

    def close(self) -> None:
        self.respostas.put(None)

    def __iter__(self) -> "WsFalso":
        return self

    def __next__(self) -> str:
        item = self.respostas.get(timeout=5)
        if item is None:
            raise StopIteration
        return item


def _escuta(ws: WsFalso) -> EscutaDeepgram:
    def conectar(url: str, chave: str) -> WsFalso:
        assert chave == "k"
        ws.url = url
        return ws

    return EscutaDeepgram("k", conectar=conectar)


def test_texto_dos_finais_depois_do_finalize() -> None:
    ws = WsFalso()
    escuta = _escuta(ws)
    escuta.enviar(b"\x00" * 2560)
    escuta.enviar(b"\x00" * 2560)
    assert escuta.terminar(2) == "Pede para um Codex rodar os testes."
    assert "language=pt-BR" in ws.url and "model=nova-3" in ws.url
    assert escuta.segundos == pytest.approx(0.16)

    def tipos() -> list[str]:
        return [json.loads(d)["type"] for d in ws.enviados if isinstance(d, str)]

    for _ in range(100):  # o CloseStream sai pela thread da conexão logo depois
        if len(tipos()) == 2:
            break
        time.sleep(0.01)
    assert tipos() == ["Finalize", "CloseStream"]


def test_sem_resposta_ao_finalize_vira_erro_para_cair_no_whisper() -> None:
    escuta = _escuta(WsFalso(responde_finalize=False))
    escuta.enviar(b"\x00" * 2560)
    with pytest.raises(EscutaErro):
        escuta.terminar(0.3)


def test_falha_de_conexao_vira_erro() -> None:
    def conectar(url: str, chave: str) -> WsFalso:
        raise OSError("rede")

    escuta = EscutaDeepgram("k", conectar=conectar)
    with pytest.raises(EscutaErro, match="conexão"):
        escuta.terminar(1)


def test_sem_chave_fica_indisponivel(tmp_path: Path) -> None:
    assert not Deepgram(tmp_path / "nao-existe.key").disponivel
    arquivo = tmp_path / "deepgram.key"
    arquivo.write_text("  abc \n")
    assert ler_chave(arquivo) == "abc"
    assert Deepgram(arquivo).disponivel
