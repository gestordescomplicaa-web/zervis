"""O modo imersivo dentro do Zé: sobe junto, lê o estado da pasta do Zé e volta se cair."""

import json
import socket
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from jarvis.imersivo import Imersivo, porta_ocupada
from jarvis.rosto import manifesto


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def pegar(porta: int, caminho: str) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{porta}{caminho}", timeout=3) as r:
        corpo = r.read()
    return json.loads(corpo) if caminho != "/stage.html" else corpo.decode()


def esperar(condicao: Any, prazo: float = 15.0) -> None:
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return
        time.sleep(0.1)
    pytest.fail("não aconteceu a tempo")


@pytest.fixture
def imersivo(tmp_path: Path) -> Any:
    i = Imersivo(tmp_path / "imersivo" / "state", porta_livre())
    i.iniciar()
    esperar(lambda: porta_ocupada(i.porta))
    yield i
    i.parar()


def test_sobe_com_a_pagina_e_le_o_estado_da_pasta_do_ze(imersivo: Imersivo) -> None:
    assert "<title>" in pegar(imersivo.porta, "/stage.html")
    assert pegar(imersivo.porta, "/orb")["state"] == "idle"
    (imersivo.pasta_estado / "state").write_text("speaking")
    onda = {"samples": [0.5] * 64, "ts": time.time()}
    (imersivo.pasta_estado / "wave.json").write_text(json.dumps(onda))
    orbe = pegar(imersivo.porta, "/orb")
    assert orbe["state"] == "speaking" and orbe["wave"] == [0.5] * 64


def test_sem_manifesto_os_orbes_do_padrao_iguais_aos_do_ze(imersivo: Imersivo) -> None:
    titulos = [o["title"] for o in pegar(imersivo.porta, "/config")["orbs"]]
    assert titulos == [o.titulo for o in manifesto.ler(imersivo.pasta_estado.parent / "nada")]
    assert titulos == ["Mapa", "Guia", "Acervo"]


def test_se_o_servidor_cair_o_ze_sobe_de_novo(imersivo: Imersivo) -> None:
    assert imersivo.processo is not None
    antigo = imersivo.processo.pid
    imersivo.processo.kill()
    esperar(lambda: imersivo.processo is not None and imersivo.processo.pid != antigo)
    esperar(lambda: porta_ocupada(imersivo.porta))


def test_pedido_invalido_e_recusado_mesmo_com_python_otimizado(imersivo: Imersivo) -> None:
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{imersivo.porta}/foco",
        data=json.dumps({"acao": "apagar-tudo", "id": "x"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(pedido, timeout=3)  # noqa: S310 (http local)
    assert erro.value.code == 400
    assert not (imersivo.pasta_estado / "foco-acoes.jsonl").exists()
