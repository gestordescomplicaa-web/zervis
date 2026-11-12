"""O formulário de perguntas (AskUserQuestion) e a aprovação do plano (ExitPlanMode) das sessões
do Claude, respondidos pela voz e pelo painel (ADR 0039). Visto em 09 e 10/11/2026: o Zé
aprovava com um "sim" sozinho, o Claude Code descartava e o formulário ficava no terminal."""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_permissoes_voz import contexto  # type: ignore[import-not-found]

from zervis.nucleo import estados as e
from zervis.nucleo.servicos.oficina import ServicoOficina
from zervis.oficina.agentes import OUTRAS_COM_PERMISSAO, RESUMO_DO_EVENTO
from zervis.oficina.permissoes import Pedido, Permissoes, assinatura, escolher

BANCO = {
    "question": "Qual banco de dados usar?",
    "header": "Banco",
    "options": [
        {"label": "Postgres", "description": "Servidor"},
        {"label": "SQLite", "description": "Arquivo"},
    ],
    "multiSelect": False,
}
TESTES = {
    "question": "Quais testes rodar?",
    "header": "Testes",
    "options": [
        {"label": "Unidade", "description": ""},
        {"label": "Ponta a ponta", "description": ""},
    ],
    "multiSelect": True,
}
FORMULARIO: dict[str, Any] = {
    "tool_name": "AskUserQuestion",
    "tool_input": {"questions": [BANCO, TESTES]},
    "prompt_id": "t1",
}
PLANO: dict[str, Any] = {
    "tool_name": "ExitPlanMode",
    "tool_input": {"plan": "# Plano\n1. Criar a tabela\n2. Testar", "planFilePath": "planos/p.md"},
    "prompt_id": "t1",
}


def esperar(cond: Any) -> None:
    fim = time.monotonic() + 3
    while not cond():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def gancho(p: Permissoes, entrada: dict[str, Any], sessao: str = "s1") -> dict[str, Any]:
    saida: dict[str, Any] = {}
    antes = len(p.pendentes())
    chave = p.chave(sessao)
    threading.Thread(
        target=lambda: saida.update(volta=p.pedir(chave, entrada)), daemon=True
    ).start()
    esperar(lambda: len(p.pendentes()) > antes)
    return saida


@pytest.mark.parametrize(
    ("fala", "esperado"),
    [
        ("Postgres", ("opcao", "Postgres")),
        ("usa o SQLite", ("opcao", "SQLite")),
        ("a segunda", ("opcao", "SQLite")),
        ("a primeira", ("opcao", "Postgres")),
        ("opção dois", ("opcao", "SQLite")),
        ("a última", ("opcao", "SQLite")),
        ("outra resposta: MySQL, por favor", ("livre", "MySQL, por favor")),
        ("cancela", ("terminal", "")),
        ("responde no terminal", ("terminal", "")),
        # Nada disto vira resposta: o Zé pergunta de novo.
        ("sei lá", ("nenhuma", "")),
        ("qualquer um", ("nenhuma", "")),
        ("uma tabela nova com os pedidos", ("nenhuma", "")),
        ("", ("nenhuma", "")),
    ],
)
def test_a_escolha_falada_so_vale_quando_e_clara(fala: str, esperado: tuple[str, str]) -> None:
    assert escolher(["Postgres", "SQLite"], False, fala) == esperado


def test_varias_opcoes_quando_a_pergunta_aceita() -> None:
    opcoes = ["Unidade", "Ponta a ponta"]
    assert escolher(opcoes, True, "unidade e ponta a ponta") == ("opcao", "Unidade, Ponta a ponta")
    assert escolher(opcoes, False, "unidade e ponta a ponta") == ("nenhuma", "")  # uma só


def test_o_formulario_volta_ao_claude_com_as_respostas() -> None:
    p = Permissoes()
    saida = gancho(p, FORMULARIO)
    pedido = p.pendentes("s1")[0]
    assert pedido["tipo"] == "pergunta" and pedido["falavel"]
    assert pedido["frase"] == "perguntar: Qual banco de dados usar? (e mais 1)"
    assert [q["opcoes"] for q in pedido["perguntas"]] == [
        ["Postgres", "SQLite"],
        ["Unidade", "Ponta a ponta"],
    ]
    with pytest.raises(ValueError):  # um "sim" sozinho não responde um formulário
        p.decidir("s1", pedido["id"], True, "voz")
    p.responder("s1", pedido["id"], "Qual banco de dados usar?", "SQLite", "voz")
    assert "volta" not in saida  # falta a segunda pergunta
    p.responder("s1", pedido["id"], "Quais testes rodar?", "Unidade, Ponta a ponta", "painel")
    esperar(lambda: "volta" in saida)
    decisao = saida["volta"]["hookSpecificOutput"]["decision"]
    assert decisao == {
        "behavior": "allow",
        "updatedInput": {
            "questions": [BANCO, TESTES],  # as perguntas de volta, como vieram
            "answers": {
                "Qual banco de dados usar?": "SQLite",
                "Quais testes rodar?": "Unidade, Ponta a ponta",
            },
        },
    }
    with pytest.raises(KeyError):
        p.responder("s1", pedido["id"], "Qual banco de dados usar?", "Postgres", "voz")


def test_negar_um_formulario_o_deixa_no_terminal() -> None:
    decididos: list[Pedido] = []
    p = Permissoes(ao_decidir=decididos.append)
    saida = gancho(p, FORMULARIO)
    p.decidir("s1", p.pendentes("s1")[0]["id"], False, "painel")
    esperar(lambda: "volta" in saida)
    assert saida["volta"] == {}  # sem decisão: o formulário segue no terminal
    assert decididos[0].decisao == "devolvido"


def test_o_plano_aprovado_volta_com_o_plano() -> None:
    p = Permissoes()
    saida = gancho(p, PLANO)
    pedido = p.pendentes("s1")[0]
    assert pedido["tipo"] == "plano" and pedido["falavel"]
    assert pedido["detalhe"].startswith("# Plano")
    p.decidir("s1", pedido["id"], True, "voz")
    esperar(lambda: "volta" in saida)
    assert saida["volta"]["hookSpecificOutput"]["decision"] == {
        "behavior": "allow",
        "updatedInput": PLANO["tool_input"],
    }


def test_respondido_no_terminal_sai_pelo_nome_da_ferramenta() -> None:
    # O que roda leva as respostas junto: a assinatura do formulário e do plano é só o nome.
    com_respostas = {**FORMULARIO["tool_input"], "answers": {"Qual banco de dados usar?": "SQLite"}}
    assert assinatura("AskUserQuestion", com_respostas) == assinatura("AskUserQuestion", {})
    evento = {
        "hook_event_name": "PostToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": com_respostas,
    }
    feito = subprocess.run(  # noqa: S603 (o próprio Python e o código fixo do gancho)
        [sys.executable, "-c", RESUMO_DO_EVENTO], input=json.dumps(evento), capture_output=True,
        text=True, check=True,
    )  # fmt: skip
    assert json.loads(feito.stdout)["assinatura"] == assinatura("AskUserQuestion", {})
    assert "AskUserQuestion" in OUTRAS_COM_PERMISSAO and "ExitPlanMode" in OUTRAS_COM_PERMISSAO
    p = Permissoes()
    saida = gancho(p, FORMULARIO)
    p.retirar("s1", rodou=assinatura("AskUserQuestion", com_respostas))
    esperar(lambda: "volta" in saida)
    assert saida["volta"] == {}


def _pedir_pela_voz(n: Any, entrada: dict[str, Any]) -> tuple[Pedido, dict[str, Any]]:
    permissoes = n.sessoes.permissoes
    chegou: list[Pedido] = []

    def ao_pedir(p: Pedido) -> None:
        ServicoOficina(n)._permissao_pedida(p)
        chegou.append(p)  # depois: a pergunta já está na fila quando o teste olha

    permissoes.ao_pedir = ao_pedir
    permissoes.ao_decidir = ServicoOficina(n)._permissao_decidida
    saida = gancho(permissoes, entrada)
    esperar(lambda: bool(chegou))
    return chegou[0], saida


def _falou(n: Any, texto: str) -> None:
    """O laço falou a pergunta: a escuta abre (o que `efeitos` faz ao falar)."""
    from zervis.nucleo.efeitos import QUAL_DELAS

    n._permissao_falada = n._perguntas_permissao[texto]
    n._permissao_ate = time.monotonic() + 45
    n._permissao_escolha = texto.endswith(QUAL_DELAS)


def test_pela_voz_uma_pergunta_por_vez_e_a_sessao_segue(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    n._permissao_escolha = False
    _, saida = _pedir_pela_voz(n, FORMULARIO)
    primeira = n.eventos.get_nowait()
    assert primeira == e.Aviso(
        "A sessão Loja tem 2 perguntas. A primeira: Qual banco de dados usar? "
        "As opções são Postgres ou SQLite. Qual delas?",
        escutar=True,
        sequencial=True,
    )
    _falou(n, primeira.texto)
    servico = ServicoOficina(n)
    # Uma fala que não é opção: pergunta de novo, sem responder nada.
    assert servico._responder_escolha("sei lá") == "Não achei essa opção."
    de_novo = n.eventos.get_nowait()
    assert de_novo.texto == primeira.texto and de_novo.pedido
    _falou(n, de_novo.texto)
    assert servico._responder_escolha("a segunda") == "Anotado."
    segunda = n.eventos.get_nowait()
    assert segunda.texto == (
        "Pergunta 2 de 2 da sessão Loja: Quais testes rodar? As opções são Unidade ou "
        "Ponta a ponta. Pode escolher mais de uma. Qual delas?"
    )
    _falou(n, segunda.texto)
    assert servico._responder_escolha("unidade e ponta a ponta") == (
        "Respondido: Unidade, Ponta a ponta. A sessão Loja segue."
    )
    esperar(lambda: "volta" in saida)
    respostas = saida["volta"]["hookSpecificOutput"]["decision"]["updatedInput"]["answers"]
    assert respostas == {
        "Qual banco de dados usar?": "SQLite",
        "Quais testes rodar?": "Unidade, Ponta a ponta",
    }
    assert not n._perguntas_permissao and n._permissao_ate == 0.0


def test_pela_voz_aprova_nao_responde_um_formulario(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    n._permissao_escolha = False
    _pedir_pela_voz(n, FORMULARIO)
    assert ServicoOficina(n)._responder_permissao(True) == (
        "A sessão fez uma pergunta. Diga a opção, ou responda no painel."
    )
    assert ServicoOficina(n)._responder_permissao(False) == (
        "Certo. A pergunta da sessão Loja fica no terminal."
    )


def test_pela_voz_o_plano_se_aprova_com_sim(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    n._permissao_escolha = False
    _, saida = _pedir_pela_voz(n, PLANO)
    aviso = n.eventos.get_nowait()
    assert aviso.texto == (
        "A sessão Loja terminou o plano e quer começar. O plano está na tela. Aprovo?"
    )
    _falou(n, aviso.texto)
    assert not n._permissao_escolha  # é sim ou não, não uma opção
    assert ServicoOficina(n)._responder_permissao(True) == "Aprovado. A sessão Loja segue."
    esperar(lambda: "volta" in saida)
    assert saida["volta"]["hookSpecificOutput"]["decision"]["updatedInput"] == PLANO["tool_input"]


def test_a_maquina_manda_a_fala_inteira_como_escolha() -> None:
    m = e.Maquina()
    m.escolha = lambda: True
    assert m._pedido("a segunda") == e.Comando("permissao_escolha:a segunda")
    assert m._pedido("outra resposta: usa o MySQL") == e.Comando(
        "permissao_escolha:outra resposta: usa o MySQL"
    )
    assert m._pedido("o que é SQLite?") != e.Comando("permissao_escolha:o que é SQLite?")
    m.escolha = lambda: False
    assert m._pedido("a segunda") != e.Comando("permissao_escolha:a segunda")


def test_a_pergunta_da_sessao_nunca_vira_manchete(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from zervis.nucleo.servicos.avisos import ServicoAvisos

    longa = (
        "A sessão Loja pergunta: "
        + "qual destas opções compridas você prefere " * 6
        + "Qual delas?"
    )
    n: Any = SimpleNamespace(
        _perguntas_permissao={longa: ("s1", "p1")}, avisos_lidos={}, _avisos_dados={},
        _comecados={}, _cortados=set(), _na_tela=set(), _meta={}, _na_linha=lambda *a: None,
        abertura=None,
    )  # fmt: skip
    aviso = e.Aviso(longa, escutar=True)
    assert ServicoAvisos(n)._regras_de_fala(aviso) is aviso


def test_pelo_painel_cada_pergunta_tem_os_botoes_e_a_resposta_volta(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from zervis.oficina.sessoes import Sessoes
    from zervis.portal.acoes import Acoes
    from zervis.portal.servidor import PedidoInvalido

    raiz = tmp_path / "projetos"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,), rodar=lambda *a: None)
    s = sessoes.criar("Loja", str(raiz / "loja"))
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path, tmp_path)
    saida = gancho(sessoes.permissoes, FORMULARIO, s.id)
    pedido = acoes._sessao(s)["permissoes"][0]
    assert pedido["tipo"] == "pergunta" and pedido["respostas"] == {}
    assert pedido["perguntas"][0]["opcoes"] == ["Postgres", "SQLite"]
    with pytest.raises(PedidoInvalido, match="opções"):  # "Aprovar" não responde um formulário
        acoes.permissao_da_sessao({"id": s.id, "pedido": pedido["id"], "aprovar": True})
    feito = acoes.permissao_da_sessao(
        {
            "id": s.id,
            "pedido": pedido["id"],
            "pergunta": "Qual banco de dados usar?",
            "valor": "Postgres",
        }
    )
    assert feito["aviso"] == "Anotado."
    assert feito["permissoes"][0]["respostas"] == {"Qual banco de dados usar?": "Postgres"}
    feito = acoes.permissao_da_sessao(
        {"id": s.id, "pedido": pedido["id"], "pergunta": "Quais testes rodar?", "valor": "Unidade"}
    )
    assert feito["aviso"] == "Respondido." and feito["permissoes"] == []
    esperar(lambda: "volta" in saida)
    assert saida["volta"]["hookSpecificOutput"]["decision"]["updatedInput"]["answers"] == {
        "Qual banco de dados usar?": "Postgres",
        "Quais testes rodar?": "Unidade",
    }
