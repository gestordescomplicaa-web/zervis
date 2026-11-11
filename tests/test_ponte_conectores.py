"""A ponte dos conectores (plano de maturidade, Frente 2; ADR 0076): o segredo de um conector fica
com o Zé. O agente recebe só o endereço da ponte e a chave da própria sessão."""

import json
import stat
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro.mcp_externo import Externos
from zervis.oficina import ponte, sessoes
from zervis.oficina.permissoes import Permissoes
from zervis.oficina.ponte import Ponte
from zervis.oficina.sessoes import CONECTORES, Sessoes
from zervis.portal import servidor
from zervis.portal.servidor import Portal

FALSO = Path(__file__).parent / "dados" / "conector_falso.py"
SEGREDO = "segredo-do-conector"


def _externos() -> Externos:
    return Externos(
        servidores={
            "falso": {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(FALSO)],
                "env": {"FALSO_TOKEN": SEGREDO},
            },
            "aberto": {"type": "stdio", "command": "sem-segredo-mcp"},
        },
        livres=["mcp__falso__segredo_chegou"],
        bloqueadas=["mcp__falso__apagar_tudo"],
    )


def test_so_o_conector_com_segredo_passa_pela_ponte() -> None:
    p = Ponte(lambda _chave: None, lambda _sessao: (_externos(), Path()))
    assert p.para_agente(_externos(), "chave") == _externos()  # sem painel, como antes
    p.endereco = "http://127.0.0.1:8796/sessoes/conectores"
    agente = p.para_agente(_externos(), "chave-da-sessao")
    assert agente.servidores["falso"] == {
        "type": "http",
        "url": "http://127.0.0.1:8796/sessoes/conectores/falso",
        "headers": {"Authorization": "Bearer chave-da-sessao"},
    }
    assert agente.servidores["aberto"] == _externos().servidores["aberto"]
    assert agente.livres == _externos().livres and agente.bloqueadas == _externos().bloqueadas
    assert SEGREDO not in json.dumps(agente.servidores)
    assert servidor.CONECTORES == ponte.CAMINHO


@pytest.fixture
def no_painel(tmp_path: Path) -> Iterator[tuple[str, str, Permissoes]]:
    """O painel de verdade, numa porta livre, com a ponte de uma sessão cujo projeto é tmp_path."""
    permissoes = Permissoes()
    chave = permissoes.chave("a1b2c3d4")
    p = Ponte(permissoes.sessao_da_chave, lambda _s: (_externos(), tmp_path), permissoes.tem_chave)
    painel = Portal({}, {}, porta=0, permissoes=permissoes, conectores=p.atender)
    painel.iniciar()
    p.endereco = f"{painel.endereco}{ponte.CAMINHO}"
    try:
        yield f"{p.endereco}/falso", chave, permissoes
    finally:
        p.parar()
        painel.parar()


def _rpc(url: str, chave: str, metodo: str, params: dict[str, Any] | None = None) -> Any:
    corpo = {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}}
    pedido = urllib.request.Request(  # noqa: S310 (o painel local do teste)
        url,
        data=json.dumps(corpo).encode(),
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(pedido, timeout=60) as resposta:  # noqa: S310
        return json.loads(resposta.read())["result"]


def test_o_agente_usa_o_conector_sem_ver_o_segredo(
    no_painel: tuple[str, str, Permissoes], tmp_path: Path
) -> None:
    url, chave, _ = no_painel
    inicio = _rpc(
        url,
        chave,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"},
        },
    )
    assert "tools" in inicio["capabilities"]
    nomes = [f["name"] for f in _rpc(url, chave, "tools/list")["tools"]]
    assert nomes == ["segredo_chegou", "onde"]  # a bloqueada nem aparece
    chegou = _rpc(url, chave, "tools/call", {"name": "segredo_chegou", "arguments": {}})
    assert chegou["content"][0]["text"] == "sim"  # o segredo chegou ao conector, não ao agente
    onde = _rpc(url, chave, "tools/call", {"name": "onde", "arguments": {}})
    assert onde["content"][0]["text"] == str(tmp_path)  # roda na pasta do projeto
    recusada = _rpc(url, chave, "tools/call", {"name": "apagar_tudo", "arguments": {}})
    assert recusada["isError"] and "bloqueada" in recusada["content"][0]["text"]


def test_sem_a_chave_da_sessao_nada_feito(no_painel: tuple[str, str, Permissoes]) -> None:
    url, chave, permissoes = no_painel
    with pytest.raises(urllib.error.HTTPError) as erro:
        _rpc(url, "chave-inventada", "tools/list")
    assert erro.value.code == 401
    permissoes.esquecer("a1b2c3d4", chave)  # o terminal fechou: a chave deixa de valer
    with pytest.raises(urllib.error.HTTPError) as erro:
        _rpc(url, chave, "tools/list")
    assert erro.value.code == 401


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
@pytest.mark.parametrize("motor", ["claude", "codex"])
def test_o_terminal_da_sessao_nao_leva_o_segredo(
    motor: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De ponta a ponta: um agente de mentira grava o ambiente e a linha de comando que recebeu,
    e o arquivo de conectores do Claude fica na pasta da sessão."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    saida = tmp_path / "recebido.txt"
    falso = bin_ / motor
    falso.write_text(f'#!/bin/sh\n{{ env; echo "ARGS: $*"; }} > {saida}\nsleep 5\n')
    falso.chmod(falso.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_}:/usr/bin:/bin")
    monkeypatch.setattr(sessoes, "conectores_do_projeto", lambda _s: _externos())
    monkeypatch.setattr(sessoes, "confiar_pasta_claude", lambda _s: None)
    projeto = tmp_path / "casa" / "projetos" / "loja"
    projeto.mkdir(parents=True)
    ses = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), lambda s, r: None)
    ses.permissoes.endereco = "http://127.0.0.1:8796/sessoes/permissao"
    ses.ponte.endereco = "http://127.0.0.1:8796/sessoes/conectores"
    s = ses.criar("Loja", str(projeto), motor)
    terminal = ses.abrir_terminal(s.id)
    try:
        prazo = time.monotonic() + 10
        while not (saida.exists() and "ARGS:" in saida.read_text()) and time.monotonic() < prazo:
            time.sleep(0.05)
        recebido = saida.read_text()
    finally:
        terminal.encerrar()
    arquivo = ses._dir(s.id) / CONECTORES
    if motor == "claude":
        configurado = json.loads(arquivo.read_text())["mcpServers"]
        assert configurado["falso"]["url"] == "http://127.0.0.1:8796/sessoes/conectores/falso"
        recebido += arquivo.read_text()
    else:
        assert "sessoes/conectores/falso" in recebido
    assert SEGREDO not in recebido
    assert "ZE_PERMISSAO=" in recebido  # a chave da sessão, que abre só a ponte dela
