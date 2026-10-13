"""O OmniRoute de quem usa, configurado no painel: endereço, chave e a lista de modelos dele."""

import io
import json
import stat
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import omniroute
from jarvis.cerebro.omniroute import OmniErro


def test_endereco_https_em_qualquer_lugar_http_so_local() -> None:
    assert omniroute.validar_endereco("https://omni.exemplo.com/v1/") == "https://omni.exemplo.com"
    assert omniroute.validar_endereco("http://127.0.0.1:20128") == "http://127.0.0.1:20128"
    with pytest.raises(OmniErro, match="https"):
        omniroute.validar_endereco("http://192.168.0.10:20128")  # a chave iria aberta na rede
    with pytest.raises(OmniErro):
        omniroute.validar_endereco("ftp://omni")


def test_conexao_salva_com_a_chave_so_para_o_usuario(tmp_path: Path) -> None:
    chave = tmp_path / "omniroute.key"
    conexao = tmp_path / "omniroute.json"
    omniroute.gravar_conexao("https://omni.exemplo.com", "sk-teste", chave, conexao)
    assert omniroute.ler_endereco(conexao) == "https://omni.exemplo.com"
    assert omniroute.ler_chave(chave) == "sk-teste"
    assert stat.S_IMODE(chave.stat().st_mode) == 0o600
    omniroute.gravar_conexao("http://localhost:20128", None, chave, conexao)  # sem chave: mantém
    assert omniroute.ler_chave(chave) == "sk-teste"


class _Resposta(io.BytesIO):
    def __enter__(self) -> "_Resposta":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


def test_lista_de_modelos_e_mensagens_curtas() -> None:
    corpo = json.dumps({"data": [{"id": "cx/gpt-6-luna"}, {"id": "auto/subscription"}]}).encode()
    ok = omniroute.modelos("http://127.0.0.1:20128", "k", lambda pedido, timeout: _Resposta(corpo))
    assert ok == ["auto/subscription", "cx/gpt-6-luna"]

    def recusa(pedido: Any, timeout: float) -> Any:
        raise urllib.error.HTTPError(pedido.full_url, 401, "x", {}, None)  # type: ignore[arg-type]

    def fora(pedido: Any, timeout: float) -> Any:
        raise OSError("recusado")

    with pytest.raises(OmniErro, match="Chave inválida"):
        omniroute.modelos("http://127.0.0.1:20128", "k", recusa)
    with pytest.raises(OmniErro, match="Sem conexão"):
        omniroute.modelos("http://127.0.0.1:20128", "k", fora)
