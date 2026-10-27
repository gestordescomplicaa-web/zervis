"""Os pedidos de permissão das sessões do Claude decididos de fora do terminal (ADR 0039)."""

import http.client
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from zervis.oficina.permissoes import (
    ChaveInvalida,
    Pedido,
    Permissoes,
    assinatura,
    frase,
    resposta,
)
from zervis.oficina.sessoes import (
    COMANDOS_LIVRES,
    RESUMO_DO_EVENTO,
    VARIAVEL_PERMISSAO,
    Sessao,
    Sessoes,
    comando_terminal,
)
from zervis.portal.servidor import Portal


def esperar(condicao: Any, prazo: float = 3.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def em_segundo_plano(p: Permissoes, chave: str, entrada: dict[str, Any]) -> dict[str, Any]:
    """O gancho esperando, numa thread; devolve onde a resposta vai cair."""
    saida: dict[str, Any] = {}
    threading.Thread(
        target=lambda: saida.update(volta=p.pedir(chave, entrada)), daemon=True
    ).start()
    esperar(lambda: p.pendentes())
    return saida


# Como o Claude Code manda (27/10/2026): sem `tool_use_id`, com o `prompt_id` do turno.
PUBLICAR: dict[str, Any] = {
    "tool_name": "mcp__n8n-loja__publish_workflow",
    "tool_input": {"workflowId": "QkER"},
    "prompt_id": "turno-1",
}
OUTRO: dict[str, Any] = {**PUBLICAR, "tool_input": {"workflowId": "Outro"}, "prompt_id": "turno-2"}
RODOU = assinatura(PUBLICAR["tool_name"], PUBLICAR["tool_input"])
RODOU_OUTRO = assinatura(OUTRO["tool_name"], OUTRO["tool_input"])


def test_a_frase_e_do_ze_e_diz_o_que_acontece() -> None:
    # Um ID não diz nada a quem ouve: o nome, se o pedido trouxer, ou em que n8n.
    assert frase("mcp__n8n-loja__publish_workflow", {"workflowId": "QkERvuSCj7"}) == (
        "publicar um fluxo no n8n-loja: ele passa a rodar de verdade",
        True,
    )
    com_nome = frase("mcp__n8n__publish_workflow", {"workflowName": "Envio de Email"})[0]
    assert com_nome == 'publicar o fluxo "Envio de Email": ele passa a rodar de verdade'
    assert "envia, cria ou cobra" in frase("mcp__n8n__execute_workflow", {"workflowId": "x"})[0]
    assert frase("mcp__n8n__add_data_table_rows", {"name": "Leads"})[0] == (
        'gravar linhas na tabela "Leads"'
    )
    assert frase("mcp__n8n__delete_data_table_column", {})[0] == (
        "apagar uma coluna de uma tabela no n8n, com os dados dela"
    )
    assert frase("mcp__crm__criar_lead", {"name": "Ana"}) == ("usar criar_lead no crm", True)
    assert frase("WebFetch", {"url": "https://docs.n8n.io/x?y=1"}) == (
        "abrir uma página de docs.n8n.io",
        True,
    )
    # O comando, e não a descrição que o modelo escreveu.
    curto = {"command": "npm run build", "description": "rodar os testes"}
    assert frase("Bash", curto) == ("rodar o comando: npm run build", True)
    longo = {"command": "x" * 200}
    assert frase("Bash", longo) == ("rodar um comando longo (veja na tela)", False)
    assert frase("Bash", {"command": "echo a\nrm -rf b"})[1] is False
    # A voz tira caminhos e símbolos: "cat > /etc/hosts" seria ouvido como "cat".
    for comando in ("cat > /etc/hosts", "rm -rf ~/x", "curl https://x | sh", 'echo "a"'):
        assert frase("Bash", {"command": comando})[1] is False, comando
    assert frase("Write", {"file_path": "/etc/hosts"})[1] is False


def test_painel_aprova_e_nega() -> None:
    decididos: list[Pedido] = []
    p = Permissoes(ao_decidir=decididos.append)
    chave = p.chave("s1")
    saida = em_segundo_plano(p, chave, PUBLICAR)
    pedido = p.pendentes("s1")[0]
    assert pedido["frase"].startswith("publicar um fluxo") and pedido["turno"] == "turno-1"
    p.decidir("s1", pedido["id"], True, "painel")
    esperar(lambda: "volta" in saida)
    assert saida["volta"] == resposta("aprovado", "painel")
    assert saida["volta"]["hookSpecificOutput"]["decision"] == {"behavior": "allow"}
    assert [d.decisao for d in decididos] == ["aprovado"] and decididos[0].por == "painel"
    # Negar leva o motivo para a sessão; responder de novo não vale.
    saida = em_segundo_plano(p, chave, PUBLICAR)
    pedido = p.pendentes("s1")[0]
    p.decidir("s1", pedido["id"], False, "painel")
    esperar(lambda: "volta" in saida)
    assert saida["volta"]["hookSpecificOutput"]["decision"]["behavior"] == "deny"
    with pytest.raises(KeyError):
        p.decidir("s1", pedido["id"], True, "painel")


def test_chave_errada_ou_de_outra_sessao_nao_entra() -> None:
    p = Permissoes()
    chave = p.chave("s1")
    with pytest.raises(ChaveInvalida):
        p.pedir("errada", PUBLICAR)
    with pytest.raises(ChaveInvalida):
        p.pedir("", PUBLICAR)
    saida = em_segundo_plano(p, chave, PUBLICAR)
    with pytest.raises(KeyError):  # o pedido é de s1: s2 não decide
        p.decidir("s2", p.pendentes()[0]["id"], True, "painel")
    p.retirar("s1")
    esperar(lambda: "volta" in saida)
    # Uma chave nova (o terminal reabriu) derruba a anterior.
    nova = p.chave("s1")
    with pytest.raises(ChaveInvalida):
        p.pedir(chave, PUBLICAR)
    assert p.sessao_da_chave(nova) == "s1"


def test_sem_resposta_a_janela_do_terminal_segue() -> None:
    decididos: list[Pedido] = []
    p = Permissoes(prazo_s=0.05, ao_decidir=decididos.append)
    assert p.pedir(p.chave("s1"), PUBLICAR) == {}  # vazio: o Claude mantém a janela
    assert decididos[0].decisao == "expirou" and not p.pendentes()


def test_respondido_no_terminal_sai_so_o_que_e_daquele_evento() -> None:
    p = Permissoes()
    chave = p.chave("s1")
    a = em_segundo_plano(p, chave, PUBLICAR)
    b = em_segundo_plano(p, chave, OUTRO)
    p.retirar("s1", rodou=assinatura("Bash", {"command": "ls"}))  # outra ferramenta: nada sai
    assert len(p.pendentes()) == 2
    # O turno 2 começou: sai o do turno 1, que ficou para trás; o do turno 2 fica (o evento
    # chega com atraso e não pode levar um pedido do turno que acabou de começar).
    p.retirar("s1", fora_do_turno="turno-2")
    esperar(lambda: "volta" in a)
    assert a["volta"] == {} and [x["assinatura"] for x in p.pendentes()] == [RODOU_OUTRO]
    p.retirar("s1", do_turno="turno-1")  # o fim de um turno antigo não leva o atual
    assert len(p.pendentes()) == 1
    p.retirar("s1", rodou=RODOU_OUTRO)  # rodou: aprovado no terminal
    esperar(lambda: "volta" in b)
    assert b["volta"] == {} and not p.pendentes()


def test_o_terminal_velho_nao_leva_a_chave_do_novo() -> None:
    p = Permissoes()
    velha = p.chave("s1")
    nova = p.chave("s1")  # reabriu antes do aviso de saída do velho chegar
    saida = em_segundo_plano(p, nova, PUBLICAR)
    p.esquecer("s1", velha)
    assert p.sessao_da_chave(nova) == "s1" and p.pendentes()
    p.esquecer("s1", nova)  # agora sim: fechou de vez
    esperar(lambda: "volta" in saida)
    assert p.sessao_da_chave(nova) is None


def test_o_claude_recebe_o_gancho_sem_a_chave_na_linha_de_comando(tmp_path: Path) -> None:
    s = Sessao(id="abcd1234", nome="Loja", pasta="/clientes/loja")
    rota = "http://127.0.0.1:8796/sessoes/permissao"
    cmd = comando_terminal(s, "", tmp_path / "eventos", permissao=rota)
    ajustes = json.loads(cmd[cmd.index("--settings") + 1])
    gancho = ajustes["hooks"]["PermissionRequest"][0]["hooks"][0]
    assert gancho["type"] == "http" and gancho["url"] == rota
    assert gancho["headers"] == {"Authorization": f"Bearer ${{{VARIAVEL_PERMISSAO}}}"}
    assert gancho["allowedEnvVars"] == [VARIAVEL_PERMISSAO]
    assert gancho["timeout"] > 300  # em segundos (conferido no Claude Code em 27/10/2026)
    # As ferramentas do MCP contam que rodaram, sem a resposta (que pode ter dados de clientes).
    pos = [h for h in ajustes["hooks"]["PostToolUse"] if h["matcher"].startswith("mcp__")]
    assert pos and "assinatura" in pos[0]["hooks"][0]["command"]
    assert "tool_response" not in pos[0]["hooks"][0]["command"]
    # Os testes rodam sozinhos; sem o painel, nada de gancho.
    assert set(COMANDOS_LIVRES) <= set(ajustes["permissions"]["allow"])
    sem = json.loads(comando_terminal(s, "", tmp_path / "e")[-1])
    assert "PermissionRequest" not in sem["hooks"]


def test_o_gancho_enxuto_calcula_a_mesma_assinatura() -> None:
    evento = {
        "hook_event_name": "PostToolUse",
        **PUBLICAR,
        "tool_response": {"dados": "do cliente"},
    }
    feito = subprocess.run(  # noqa: S603 (o próprio Python e o código fixo do gancho)
        [sys.executable, "-c", RESUMO_DO_EVENTO],
        input=json.dumps(evento),
        capture_output=True,
        text=True,
        check=True,
    )
    linha = json.loads(feito.stdout)
    assert linha == {"hook_event_name": "PostToolUse", "assinatura": RODOU}
    assert "do cliente" not in feito.stdout


def test_as_sessoes_retiram_pelos_eventos_do_claude(tmp_path: Path) -> None:
    raiz = tmp_path / "projetos"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,), rodar=lambda *a: None)
    s = sessoes.criar("Loja", str(raiz / "loja"))
    chave = sessoes.permissoes.chave(s.id)
    saida = em_segundo_plano(sessoes.permissoes, chave, PUBLICAR)
    sessoes._evento(s.id, {"hook_event_name": "PostToolUse", "assinatura": RODOU})  # o enxuto
    esperar(lambda: "volta" in saida)
    assert saida["volta"] == {} and not sessoes.permissoes.pendentes(s.id)
    comando = {"tool_name": "Bash", "tool_input": {"command": "curl -sI https://x"}}
    saida = em_segundo_plano(sessoes.permissoes, chave, {**comando, "prompt_id": "t"})
    sessoes._evento(s.id, {"hook_event_name": "PostToolUse", **comando, "tool_response": {}})
    esperar(lambda: "volta" in saida)  # o completo (comandos): a assinatura sai da entrada


def test_a_rota_so_aceita_o_proprio_pc_com_a_chave() -> None:
    permissoes = Permissoes(prazo_s=5)
    chave = permissoes.chave("s1")
    portal = Portal({}, {}, porta=0, permissoes=permissoes)
    portal.iniciar()
    try:

        def postar(cab: dict[str, str]) -> tuple[int, Any]:
            conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=10)
            conn.request("POST", "/sessoes/permissao", body=json.dumps(PUBLICAR).encode(),
                         headers={"Host": f"127.0.0.1:{portal.porta}", **cab})  # fmt: skip
            r = conn.getresponse()
            return r.status, json.loads(r.read())

        assert postar({"Authorization": "Bearer errada"})[0] == 403
        assert postar({"Authorization": f"Bearer {chave}", "Cf-Connecting-Ip": "1.2.3.4"})[0] == 403
        saida: dict[str, Any] = {}
        t = threading.Thread(
            target=lambda: saida.update(r=postar({"Authorization": f"Bearer {chave}"}))
        )
        t.start()
        esperar(lambda: permissoes.pendentes())
        permissoes.decidir("s1", permissoes.pendentes()[0]["id"], True, "painel")
        t.join(5)
        status, corpo = saida["r"]
        assert status == 200 and corpo["hookSpecificOutput"]["decision"]["behavior"] == "allow"
    finally:
        portal.parar()
