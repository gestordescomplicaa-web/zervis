"""Pedidos do imersivo: origem, autorização e conteúdo na fronteira HTTP real."""

import http.client
import json
import os
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from zervis.imersivo import servidor
from zervis.imersivo.http import NOME_ARQUIVO, gravar_token, ler_token
from zervis.rosto.quadro import Quadro


@dataclass
class ApiImersivo:
    porta: int
    estado: Path
    token: str

    def pedir(
        self,
        metodo: str,
        caminho: str,
        corpo: str = "",
        autorizado: bool = True,
        cabecalhos: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        headers = {"Content-Type": "application/json"}
        if autorizado:
            headers["X-Ze-Token"] = self.token
        headers.update(cabecalhos or {})
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=3)
        try:
            conexao.request(metodo, caminho, body=corpo, headers=headers)
            resposta = conexao.getresponse()
            return resposta.status, resposta.read()
        finally:
            conexao.close()


@pytest.fixture
def api_imersivo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiImersivo]:
    monkeypatch.setattr(servidor, "ESTADO", tmp_path)
    monkeypatch.setattr(servidor, "TOKEN", "token-sintetico-do-teste", raising=False)
    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
    fio = threading.Thread(target=http.serve_forever, daemon=True)
    fio.start()
    try:
        yield ApiImersivo(http.server_port, tmp_path, "token-sintetico-do-teste")
    finally:
        http.shutdown()
        http.server_close()
        fio.join(3)


@pytest.mark.parametrize("caminho", ["/teclado", "/foco", "/cmd", "/state"])
def test_escrita_sem_token_nao_tem_efeito(api_imersivo: ApiImersivo, caminho: str) -> None:
    status, _ = api_imersivo.pedir(
        "POST", caminho, json.dumps({"texto": "pedido", "a": "reset"}), autorizado=False
    )
    assert status == 403
    assert list(api_imersivo.estado.iterdir()) == []


@pytest.mark.parametrize(
    "cabecalhos",
    [
        {"Host": "site-externo.invalid"},
        {"Origin": "http://site-externo.invalid"},
        {"Origin": "null"},
        {"X-Ze-Token": "outro-token"},
    ],
)
def test_escrita_recusa_host_origem_ou_token_invalido(
    api_imersivo: ApiImersivo, cabecalhos: dict[str, str]
) -> None:
    status, _ = api_imersivo.pedir("POST", "/teclado", '{"texto":"pedido"}', cabecalhos=cabecalhos)
    assert status == 403
    assert not (api_imersivo.estado / "teclado.json").exists()


def test_pagina_entrega_token_e_pedido_local_funciona(api_imersivo: ApiImersivo) -> None:
    status, pagina = api_imersivo.pedir("GET", "/stage.html", autorizado=False)
    assert status == 200 and api_imersivo.token.encode() in pagina
    assert b"__ZE_TOKEN__" not in pagina
    status, _ = api_imersivo.pedir(
        "POST",
        "/teclado",
        '{"texto":"Abra o guia"}',
        cabecalhos={"Origin": f"http://127.0.0.1:{api_imersivo.porta}"},
    )
    assert status == 200
    assert json.loads((api_imersivo.estado / "teclado.json").read_text())["texto"] == "Abra o guia"


def test_leitura_privada_exige_token_e_pagina_recusa_host_externo(
    api_imersivo: ApiImersivo,
) -> None:
    assert api_imersivo.pedir("GET", "/jarvis/mapa", autorizado=False)[0] == 403
    assert api_imersivo.pedir("GET", "/jarvis/mapa")[0] == 200
    for metodo in ("GET", "HEAD"):
        assert (
            api_imersivo.pedir(metodo, "/stage.html", cabecalhos={"Host": "site-externo.invalid"})[
                0
            ]
            == 403
        )


@pytest.mark.parametrize("tamanho", ["-1", "invalido", "262144"])
def test_corpo_invalido_e_recusado(api_imersivo: ApiImersivo, tamanho: str) -> None:
    status, _ = api_imersivo.pedir("POST", "/teclado", cabecalhos={"Content-Length": tamanho})
    assert status in (400, 413)
    assert not (api_imersivo.estado / "teclado.json").exists()


def test_quadro_do_nucleo_entrega_card_autorizado(api_imersivo: ApiImersivo) -> None:
    quadro = Quadro(
        lambda: True,
        f"http://127.0.0.1:{api_imersivo.porta}/cmd",
        token=api_imersivo.token,
    )
    assert quadro.apresentar("Revisão", "Texto para revisar.")
    status, comandos = api_imersivo.pedir("POST", "/state", "{}")
    assert status == 200
    assert json.loads(comandos)[-1]["title"] == "Revisão"


def test_token_local_tem_permissao_restrita_e_comandos_continuam_funcionando(
    api_imersivo: ApiImersivo,
) -> None:
    gravar_token(api_imersivo.estado, api_imersivo.token)
    assert (api_imersivo.estado / NOME_ARQUIVO).stat().st_mode & 0o777 == 0o600
    assert ler_token(api_imersivo.estado) == api_imersivo.token
    ambiente = {
        **os.environ,
        "ZE_IMERSIVO_ESTADO": str(api_imersivo.estado),
        "ZE_IMERSIVO_PORTA": str(api_imersivo.porta),
    }
    binarios = Path(servidor.__file__).parent / "bin"
    comando = subprocess.run(  # noqa: S603 (script do projeto, dados sintéticos)
        ["/usr/bin/bash", str(binarios / "board.sh"), '{"a":"reset"}'],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert comando.returncode == 0 and comando.stdout.strip() == "204"
    status, comandos = api_imersivo.pedir("POST", "/state", '{"items":[]}')
    assert status == 200 and json.loads(comandos)[-1]["a"] == "reset"
    leitura = subprocess.run(  # noqa: S603 (script do projeto)
        ["/usr/bin/bash", str(binarios / "board-state.sh")],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert leitura.returncode == 0 and "EMPTY" in leitura.stdout


def test_autoconhecimento_so_para_a_pagina_e_vazio_sem_o_arquivo(api_imersivo: ApiImersivo) -> None:
    """ADR 0045: o retrato do Zé chega às apresentações só com o token, e sem arquivo vem vazio."""
    assert api_imersivo.pedir("GET", "/autoconhecimento", autorizado=False)[0] == 403
    assert api_imersivo.pedir("GET", "/autoconhecimento") == (200, b"{}")
    (api_imersivo.estado / "autoconhecimento.json").write_text('{"agora": {"modelo": "X"}}')
    status, corpo = api_imersivo.pedir("GET", "/autoconhecimento")
    assert status == 200 and json.loads(corpo) == {"agora": {"modelo": "X"}}
