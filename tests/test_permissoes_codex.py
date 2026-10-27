"""A aprovação das sessões do Codex (ADR 0039): o mesmo caminho do Claude, com o que o Codex 0.159
tem de diferente (prova de 27/10/2026): gancho só de comando, que a pessoa confia uma vez; a
pergunta dele só depois do gancho; o Esc avisa pelo `Interrupt`; MCP por `approval_mode`."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from zervis.cerebro import mcp_externo
from zervis.oficina.permissoes import PRAZO_CODEX_S, Permissoes
from zervis.oficina.sessoes import (
    GANCHO_CODEX,
    GANCHOS_DO_CODEX,
    Sessao,
    Sessoes,
    comando_terminal,
    conectores_codex,
)
from zervis.portal.servidor import Portal

EXTERNOS = mcp_externo.Externos(
    servidores={"n8n-loja": {"type": "stdio", "command": "n8n-mcp", "args": []}},
    livres=["mcp__n8n-loja__search_workflows"],
    bloqueadas=["mcp__n8n-loja__delete_agent"],
)
PUBLICAR: dict[str, Any] = {
    "tool_name": "mcp__n8n-loja__publish_workflow",
    "tool_input": {"workflowId": "QkER"},
    "turn_id": "turno-codex",
}


def valores(argumentos: list[str]) -> list[str]:
    return [a for a in argumentos if a != "-c"]


def test_no_terminal_o_codex_recebe_todas_as_ferramentas_com_o_modo_certo() -> None:
    perguntar = valores(conectores_codex(EXTERNOS, perguntar=True)[0])
    assert 'mcp_servers.n8n-loja.default_tools_approval_mode="prompt"' in perguntar
    assert 'mcp_servers.n8n-loja.tools.search_workflows.approval_mode="approve"' in perguntar
    assert 'mcp_servers.n8n-loja.disabled_tools=["delete_agent"]' in perguntar
    assert not any("enabled_tools" in a for a in perguntar)
    # Sem como perguntar (codex exec, sem terminal): só as livres, como antes.
    sem = valores(conectores_codex(EXTERNOS)[0])
    assert 'mcp_servers.n8n-loja.enabled_tools=["search_workflows"]' in sem
    assert not any("approval_mode" in a for a in sem)


def test_os_ganchos_do_codex_sao_sempre_os_mesmos(tmp_path: Path) -> None:
    rota = "http://127.0.0.1:8796/sessoes/permissao"
    um = comando_terminal(
        Sessao(id="a", nome="A", pasta="/x", motor="codex"), "", tmp_path / "a", None, EXTERNOS,
        None, rota,
    )  # fmt: skip
    outro = comando_terminal(
        Sessao(id="b", nome="B", pasta="/y", motor="codex"), "", tmp_path / "b", None, None, None,
        rota,
    )  # fmt: skip
    ganchos = [a for a in um if a.startswith("hooks.")]
    assert {g.split("=", 1)[0] for g in ganchos} == {"hooks.PermissionRequest", "hooks.Interrupt"}
    # O Codex pede para confiar em cada gancho novo: nada da sessão no comando (nem a chave,
    # nem o endereço, nem o arquivo de eventos), para confiar uma vez por conta.
    assert ganchos == [a for a in outro if a.startswith("hooks.")]
    assert not any(str(tmp_path) in g or "8796" in g for g in ganchos)
    assert f"timeout={int(PRAZO_CODEX_S) + 10}" in ganchos[0]
    # Sem o painel, nada de gancho.
    sem = comando_terminal(Sessao(id="c", nome="C", pasta="/z", motor="codex"), "", tmp_path / "c")
    assert not any(a.startswith("hooks.") for a in sem)


def test_o_gancho_do_codex_repassa_ao_ze_e_devolve_a_decisao() -> None:
    permissoes = Permissoes()
    chave = permissoes.chave("s1", PRAZO_CODEX_S)
    portal = Portal({}, {}, porta=0, permissoes=permissoes)
    portal.iniciar()
    try:
        ambiente = {
            "ZE_PERMISSAO": chave,
            "ZE_PERMISSAO_URL": f"{portal.endereco}sessoes/permissao",
            "ZE_PERMISSAO_PRAZO": "10",
            "PATH": os.environ.get("PATH", ""),
        }
        saida: dict[str, Any] = {}

        def gancho() -> None:
            feito = subprocess.run(  # noqa: S603 (o próprio Python e o código fixo do gancho)
                [sys.executable, "-c", GANCHO_CODEX],
                input=json.dumps(PUBLICAR),
                capture_output=True,
                text=True,
                env=ambiente,
                timeout=20,
            )
            saida["volta"] = feito.stdout

        t = threading.Thread(target=gancho)
        t.start()
        fim = time.monotonic() + 10
        while not permissoes.pendentes():
            assert time.monotonic() < fim
            time.sleep(0.02)
        pedido = permissoes.pendentes()[0]
        assert pedido["turno"] == "turno-codex"  # o Codex manda `turn_id`, não `prompt_id`
        permissoes.decidir("s1", pedido["id"], True, "voz")
        t.join(20)
        volta = json.loads(saida["volta"])
        assert volta["hookSpecificOutput"]["decision"] == {"behavior": "allow"}
    finally:
        portal.parar()
    # Sem o Zé (variáveis faltando ou painel fora): sai vazio, e a pergunta do Codex aparece.
    vazio = subprocess.run(  # noqa: S603
        [sys.executable, "-c", GANCHO_CODEX], input="{}", capture_output=True, text=True, env={}
    )
    assert vazio.stdout == "" and vazio.returncode == 0


def test_o_esc_do_codex_retira_o_pedido_e_o_prazo_e_menor(tmp_path: Path) -> None:
    raiz = tmp_path / "projetos"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,), rodar=lambda *a: None)
    s = sessoes.criar("Loja", str(raiz / "loja"), "codex")
    chave = sessoes.permissoes.chave(s.id, PRAZO_CODEX_S)
    assert sessoes.permissoes._prazos[s.id] == PRAZO_CODEX_S < sessoes.permissoes.prazo_s
    saida: dict[str, Any] = {}
    threading.Thread(
        target=lambda: saida.update(volta=sessoes.permissoes.pedir(chave, PUBLICAR)), daemon=True
    ).start()
    fim = time.monotonic() + 3
    while not sessoes.permissoes.pendentes():
        assert time.monotonic() < fim
        time.sleep(0.01)
    sessoes._evento(s.id, {"hook_event_name": "Interrupt", "turn_id": "outro-turno"})
    assert sessoes.permissoes.pendentes()  # o Esc de outro turno não leva este
    sessoes._evento(s.id, {"hook_event_name": "Interrupt", "turn_id": "turno-codex"})
    fim = time.monotonic() + 3
    while "volta" not in saida:
        assert time.monotonic() < fim
        time.sleep(0.01)
    assert saida["volta"] == {} and not sessoes.permissoes.pendentes()


def test_a_tela_de_confiar_nos_ganchos_vira_aviso_uma_vez(tmp_path: Path) -> None:
    raiz = tmp_path / "projetos"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,), rodar=lambda *a: None)
    s = sessoes.criar("Loja", str(raiz / "loja"), "codex")
    avisos: list[str] = []
    sessoes.ao_avisar = lambda sessao, mensagem: avisos.append(mensagem)
    sessoes._olhar_saida(s.id, b"\x1b[1m  Hooks need ")
    sessoes._olhar_saida(s.id, b"review\x1b[0m\r\n  2 hooks are new or changed.")  # partido
    sessoes._olhar_saida(s.id, b"Hooks need review")
    assert avisos == [GANCHOS_DO_CODEX]
