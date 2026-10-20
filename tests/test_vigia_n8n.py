"""O vigia do n8n (ADR 0038, F2): de pé, fora do ar e de volta, um aviso por mudança."""

import http.server
import json
import queue
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import atividade
from zervis.nucleo import estados as e
from zervis.nucleo.servicos.automacoes import ServicoAutomacoes
from zervis.sistema import vigia_n8n
from zervis.sistema.vigia_n8n import VigiaN8n


def _n8n(saude: int, pronto: int) -> http.server.HTTPServer:
    """Um n8n de mentira: `/healthz` e `/healthz/readiness` com os códigos pedidos."""

    class N8n(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            codigo = pronto if self.path == "/healthz/readiness" else saude
            corpo = json.dumps({"status": "ok" if codigo == 200 else "error"}).encode()
            self.send_response(codigo)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_args: object) -> None:
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), N8n)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


@pytest.fixture
def instancias() -> Iterator[dict[str, str]]:
    servidores = {"de-pe": _n8n(200, 200), "sem-banco": _n8n(200, 503), "quebrado": _n8n(500, 500)}
    morto = _n8n(200, 200)
    endereco_morto = f"http://127.0.0.1:{morto.server_port}"
    morto.shutdown()
    morto.server_close()
    try:
        yield {
            **{n: f"http://127.0.0.1:{s.server_port}" for n, s in servidores.items()},
            "morto": endereco_morto,
        }
    finally:
        for s in servidores.values():
            s.shutdown()


def test_conferir_separa_os_motivos(instancias: dict[str, str]) -> None:
    assert {nome: vigia_n8n.conferir(base) for nome, base in instancias.items()} == {
        "de-pe": "ok",
        "sem-banco": "banco fora",
        "quebrado": "erro do servidor",
        "morto": "sem resposta",
    }


def test_alvos_sao_os_conectores_ligados_do_mcp_do_n8n() -> None:
    lista = [
        {"nome": "n8n-joao", "tipo": "http", "ligado": True,
         "url": "https://joao.exemplo.com/mcp-server/http"},
        {"nome": "n8n-velho", "tipo": "http", "ligado": False,
         "url": "https://velho.exemplo.com/mcp-server/http"},
        {"nome": "notion", "tipo": "http", "ligado": True, "url": "https://mcp.notion.com/mcp"},
        {"nome": "github", "tipo": "stdio", "ligado": True, "url": ""},
    ]  # fmt: skip
    assert vigia_n8n.alvos(lista) == {"n8n-joao": "https://joao.exemplo.com"}


def test_avisa_uma_vez_depois_de_tres_falhas_e_avisa_a_volta(tmp_path: Path) -> None:
    respostas = iter(["sem resposta"] * 4 + ["ok", "ok"])
    vigia = VigiaN8n(
        tmp_path / "vigia.db", conferir=lambda _b: next(respostas), alvos=lambda: {"n8n-joao": "x"}
    )
    rodadas = [vigia.amostrar() for _ in range(6)]
    assert rodadas == [
        [],
        [],
        [("urgente", "n8n-joao fora do ar: sem resposta.")],
        [],  # continua fora: sem repetir
        [("notificacao", "n8n-joao voltou.")],
        [],
    ]


def test_oscilacao_curta_nao_vira_aviso(tmp_path: Path) -> None:
    respostas = iter(["sem resposta", "sem resposta", "ok", "sem resposta", "sem resposta"])
    vigia = VigiaN8n(
        tmp_path / "vigia.db", conferir=lambda _b: next(respostas), alvos=lambda: {"loja": "x"}
    )
    assert [vigia.amostrar() for _ in range(5)] == [[]] * 5


def test_reiniciar_o_ze_nao_repete_nem_perde_o_aviso(tmp_path: Path) -> None:
    arquivo = tmp_path / "vigia.db"
    alvos = lambda: {"loja": "x"}  # noqa: E731
    fora = VigiaN8n(arquivo, conferir=lambda _b: "banco fora", alvos=alvos)
    assert [fora.amostrar() for _ in range(3)][-1] == [
        ("urgente", "n8n loja fora do ar: banco fora.")
    ]
    assert VigiaN8n(arquivo, conferir=lambda _b: "banco fora", alvos=alvos).amostrar() == []
    assert VigiaN8n(arquivo, conferir=lambda _b: "banco fora", alvos=alvos).fora() == {
        "loja": "banco fora"
    }
    voltou = VigiaN8n(arquivo, conferir=lambda _b: "ok", alvos=alvos)
    assert voltou.amostrar() == [("notificacao", "n8n loja voltou.")]


def test_conector_removido_sai_do_estado(tmp_path: Path) -> None:
    arquivo, alvos = tmp_path / "vigia.db", {"loja": "x"}
    vigia = VigiaN8n(arquivo, conferir=lambda _b: "sem resposta", alvos=lambda: alvos)
    for _ in range(3):
        vigia.amostrar()
    alvos.clear()
    vigia.amostrar()
    assert vigia.fora() == {}


def test_o_servico_registra_mostra_e_fala_conforme_o_modo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registro = atividade.Atividade(tmp_path / "atividade.jsonl")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    linha: list[tuple[str, str]] = []
    contexto: Any = SimpleNamespace(
        vigia_n8n=SimpleNamespace(
            amostrar=lambda: [("urgente", "n8n-joao fora do ar: sem resposta.")]
        ),
        modo_fala="avisos",
        _meta={},
        eventos=queue.Queue(),
        _na_linha=lambda tipo, texto: linha.append((tipo, texto)),
        _n8n_conferindo=threading.Event(),
    )
    contexto._n8n_conferindo.set()
    ServicoAutomacoes(contexto)._vigiar_n8n()
    assert linha == [("aviso", "n8n-joao fora do ar: sem resposta.")]
    assert contexto.eventos.get_nowait() == e.Aviso("n8n-joao fora do ar: sem resposta.")
    assert registro.listar()[0]["titulo"] == "n8n-joao fora do ar: sem resposta."
    assert not contexto._n8n_conferindo.is_set()  # a próxima rodada pode começar
    contexto.modo_fala = "silencioso"
    ServicoAutomacoes(contexto)._vigiar_n8n()
    assert contexto.eventos.empty() and len(linha) == 2  # na tela, sem falar
