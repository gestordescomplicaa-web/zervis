"""Oficina e monitor com um Orca de mentira: projetos, delegação, caixa do Run e avisos."""

import threading
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro.claude import descrever
from jarvis.oficina.monitor import Monitor, aviso
from jarvis.oficina.oficina import Mensagem, Oficina
from jarvis.oficina.orca import OrcaErro

WORKTREES = {
    "worktrees": [
        {"displayName": "JARVIS ORCA", "path": "/p/jarvis", "agents": []},
        {"displayName": "LAÍA-LOCAL", "path": "/p/laya", "agents": [{"agentType": "codex"}]},
        {"displayName": "master", "path": "/p/sites", "agents": []},
        {"displayName": "master", "path": "/p/pc", "agents": []},
        {"displayName": "velho", "path": "/p/velho", "isArchived": True},
    ]
}


class OrcaFalso:
    def __init__(self, inicio: dict[str, Any] | None = None) -> None:
        self.chamadas: list[tuple[str, ...]] = []
        self.inicio = inicio or {"state": "ready", "dispatchId": "ctx_1"}
        self.terminais: list[str] = []
        self.tela: list[str] = []
        self.sessoes: dict[str, list[dict[str, str]]] = {}

    def chamar(self, *args: str, limite_s: float = 30) -> dict[str, Any]:
        self.chamadas.append(args)
        if args[:2] == ("worktree", "ps"):
            return WORKTREES
        if args[:2] == ("terminal", "list"):
            if args[-1] in self.sessoes:
                return {"terminals": self.sessoes[args[-1]]}
            return {"terminals": [{"handle": h} for h in self.terminais]}
        if args[:2] == ("terminal", "read"):
            return {"terminal": {"tail": self.tela}}
        if args[:2] == ("terminal", "create"):
            self.terminais.append(f"term_{len(self.terminais) + 1}")
            return {"terminal": {"handle": self.terminais[-1]}}
        if args[1] == "run-create":
            return {"run": {"id": f"run_{len(self.terminais)}"}}
        if args[1] == "worker-start":
            return self.inicio
        if args[1] == "worker-read":
            return {"terminal": {"tail": self.tela}}
        return {}


def _oficina(tmp_path: Path, orca: OrcaFalso | None = None) -> Oficina:
    return Oficina(tmp_path / "oficina.json", orca or OrcaFalso())  # type: ignore[arg-type]


def test_acha_projeto_sem_acento_e_recusa_ambiguidade(tmp_path: Path) -> None:
    oficina = _oficina(tmp_path)
    assert oficina.achar_projeto("laia local").caminho == "/p/laya"
    assert oficina.achar_projeto("jarvis").caminho == "/p/jarvis"
    with pytest.raises(OrcaErro, match="mais de um"):
        oficina.achar_projeto("master")
    with pytest.raises(OrcaErro, match="não achei"):
        oficina.achar_projeto("velho")


def test_delegar_cria_o_run_uma_vez_e_guarda_a_tarefa(tmp_path: Path) -> None:
    orca = OrcaFalso()
    oficina = _oficina(tmp_path, orca)
    recibo = oficina.delegar("rode os testes", "LAÍA-LOCAL", "codex")
    assert recibo == {"dispatch": "ctx_1", "agente": "Codex", "projeto": "LAÍA-LOCAL"}
    inicio = next(c for c in orca.chamadas if "worker-start" in c)
    assert inicio[inicio.index("--worktree") + 1] == "path:/p/laya"
    assert inicio[inicio.index("--run") + 1] == "run_1"
    assert inicio[inicio.index("--from") + 1] == "term_1"  # o posto do JARVIS é o remetente
    assert "worker_done" in inicio[inicio.index("--spec") + 1]  # sempre pede o aviso de fim
    oficina.delegar("de novo", "jarvis", "claude")
    assert sum("run-create" in c for c in orca.chamadas) == 1
    reaberta = _oficina(tmp_path)  # o Run e as tarefas sobrevivem a um reinício
    assert reaberta.run == "run_1" and set(reaberta.tarefas) == {"ctx_1"}


def test_agente_que_nao_ficou_pronto_e_liberado_e_avisa(tmp_path: Path) -> None:
    orca = OrcaFalso({"state": "failed", "dispatchId": "ctx_9", "failedStage": "agent_readiness"})
    oficina = _oficina(tmp_path, orca)
    with pytest.raises(OrcaErro, match="não ficou pronto"):
        oficina.delegar("x", "jarvis", "claude")
    assert ("orchestration", "worker-release", "--dispatch", "ctx_9") in orca.chamadas
    with pytest.raises(OrcaErro, match="agente desconhecido"):
        oficina.delegar("x", "jarvis", "gemini")


def _msg(tipo: str, **dados: Any) -> Mensagem:
    return Mensagem("msg_1", tipo, "assunto", "corpo da mensagem", dados)


def test_textos_dos_avisos() -> None:
    tarefa = {"agente": "codex", "projeto": "LAÍA-LOCAL"}
    feito = _msg("worker_done", outcome="succeeded", summary="Todos os testes passaram.")
    assert aviso(feito, tarefa) == (
        "O Codex terminou no projeto LAÍA-LOCAL: deu certo. Todos os testes passaram."
    )
    falhou = _msg("worker_done", outcome="failed")
    assert "falhou. corpo da mensagem" in aviso(falhou, tarefa)
    assert aviso(_msg("question"), {}) == "O agente pergunta: corpo da mensagem"


def test_monitor_avisa_libera_o_terminal_e_guarda_perguntas(tmp_path: Path) -> None:
    orca = OrcaFalso()
    oficina = _oficina(tmp_path, orca)
    oficina.delegar("rode os testes", "jarvis", "codex")
    avisos: list[str] = []
    monitor = Monitor(oficina, avisos.append, threading.Event())
    pergunta = Mensagem("q1", "question", "", "Posso apagar o cache?", {"dispatchId": "ctx_1"})
    feito = Mensagem("d1", "worker_done", "", "", {"dispatchId": "ctx_1", "outcome": "failed"})
    monitor.tratar([pergunta, Mensagem("h", "heartbeat", "", "", {}), feito])
    assert avisos == [
        "O Codex no projeto JARVIS ORCA pergunta: Posso apagar o cache?",
        "O Codex terminou no projeto JARVIS ORCA: falhou.",
    ]
    assert monitor.perguntas["q1"].agente == "Codex"
    assert ("orchestration", "worker-release", "--dispatch", "ctx_1") in orca.chamadas
    assert oficina.tarefas == {}


def test_frases_de_aprovacao_da_oficina() -> None:
    delegar = descrever(
        "mcp__jarvis__oficina_delegar",
        {"agente": "codex", "projeto": "LAÍA-LOCAL", "tarefa": "Rode os testes."},
    )
    assert delegar == "Vou pedir para um Codex, no projeto LAÍA-LOCAL: Rode os testes."
    responder = descrever("mcp__jarvis__oficina_responder", {"resposta": "pode"})
    assert responder == "Vou responder ao agente: pode"


def test_posto_sumido_abre_outro_com_run_novo(tmp_path: Path) -> None:
    orca = OrcaFalso()
    oficina = _oficina(tmp_path, orca)
    assert oficina.garantir_run() == "run_1"
    assert oficina.garantir_run() == "run_1"  # posto vivo: nada muda
    orca.terminais.clear()  # Orca reiniciado: o terminal do JARVIS não existe mais
    assert oficina.garantir_run() == "run_1" and oficina.posto == "term_1"
    assert sum(c[:2] == ("terminal", "create") for c in orca.chamadas) == 2


def test_claude_parado_no_aviso_do_modo_livre_vira_instrucao(tmp_path: Path) -> None:
    orca = OrcaFalso({"state": "failed", "dispatchId": "ctx_9", "lastError": "timeout"})
    orca.tela = ["  WARNING: Claude Code running in Bypass Permissions mode", "  No, exit"]
    with pytest.raises(OrcaErro, match="aceite esse aviso uma vez no Orca"):
        _oficina(tmp_path, orca).delegar("x", "jarvis", "claude")


def test_pasta_do_nome_falado() -> None:
    from jarvis.oficina.oficina import pasta_de

    assert pasta_de("Loja Virtual") == "loja-virtual"
    assert pasta_de("Laía  Local!") == "laia-local"


def test_criar_projeto_com_git_e_registro_no_orca(tmp_path: Path) -> None:
    orca = OrcaFalso()
    oficina = Oficina(tmp_path / "o.json", orca, raiz=tmp_path / "projetos")  # type: ignore[arg-type]
    recibo = oficina.criar_projeto("Loja Virtual")
    pasta = tmp_path / "projetos" / "loja-virtual"
    assert recibo == {"nome": "Loja Virtual", "pasta": str(pasta)}
    assert (pasta / ".git").is_dir() and (pasta / "README.md").read_text() == "# Loja Virtual\n"
    assert ("repo", "add", "--path", str(pasta)) in orca.chamadas
    nomear = next(c for c in orca.chamadas if c[:2] == ("worktree", "set"))
    assert nomear[-1] == "Loja Virtual"
    with pytest.raises(OrcaErro, match="já existe"):
        oficina.criar_projeto("loja virtual")
    with pytest.raises(OrcaErro, match="inválido"):
        oficina.criar_projeto("../../etc")


def test_frente_nova_sem_parentesco_e_status_do_quadro(tmp_path: Path) -> None:
    orca = OrcaFalso()
    oficina = _oficina(tmp_path, orca)
    oficina.nova_frente("laia local", "Tela de Login")
    criar = next(c for c in orca.chamadas if c[:2] == ("worktree", "create"))
    assert criar[criar.index("--name") + 1] == "tela-de-login"
    assert "--no-parent" in criar  # o posto do JARVIS não é pai da frente nova
    assert oficina.marcar("jarvis", "concluído") == {
        "projeto": "JARVIS ORCA",
        "status": "concluído",
    }
    assert orca.chamadas[-1][-1] == "completed"
    with pytest.raises(OrcaErro, match="status desconhecido"):
        oficina.marcar("jarvis", "apagado")


def test_codex_parado_na_revisao_de_hooks_vira_instrucao(tmp_path: Path) -> None:
    orca = OrcaFalso({"state": "failed", "dispatchId": "ctx_9", "lastError": "blocked"})
    orca.tela = ["  Hooks need review", "  2. Trust all and continue"]
    with pytest.raises(OrcaErro, match="confiar em todos"):
        _oficina(tmp_path, orca).delegar("x", "jarvis", "codex")


def test_mandar_texto_na_sessao_aberta_com_enter_separado(tmp_path: Path) -> None:
    orca = OrcaFalso()
    orca.sessoes["path:/p/laya"] = [
        {"handle": "t_shell", "title": "bash"},
        {"handle": "t_claude", "title": "OPA retomada", "agentIdentity": "claude"},
    ]
    recibo = _oficina(tmp_path, orca).mandar_texto("laia local", "oi\ntudo bem?")
    assert recibo == {"projeto": "LAÍA-LOCAL", "sessao": "OPA retomada", "agente": "claude"}
    envios = [c for c in orca.chamadas if c[:2] == ("terminal", "send")]
    assert [e[-1] for e in envios] == ["oi tudo bem?", "\r"]
    assert all(e[e.index("--terminal") + 1] == "t_claude" for e in envios)


def test_mandar_texto_recusa_tela_de_aprovacao_ou_sem_sessao(tmp_path: Path) -> None:
    orca = OrcaFalso()
    orca.sessoes["path:/p/laya"] = [{"handle": "t1", "title": "x", "agentIdentity": "codex"}]
    orca.tela = ["Would you like to run the following command?"]
    with pytest.raises(OrcaErro, match="esperando uma resposta"):
        _oficina(tmp_path, orca).mandar_texto("laia local", "oi")
    assert not any(c[:2] == ("terminal", "send") for c in orca.chamadas)
    with pytest.raises(OrcaErro, match="não há sessão"):
        _oficina(tmp_path, OrcaFalso()).mandar_texto("jarvis", "oi")


def test_mandar_texto_escolhe_pelo_agente_mesmo_com_o_nome_do_outro_no_titulo(
    tmp_path: Path,
) -> None:
    # Teste real de 07/10/2026: a sessão do Codex se chamava "Continue projeto do Claude".
    orca = OrcaFalso()
    orca.sessoes["path:/p/laya"] = [
        {"handle": "t_claude", "title": "Recuperar última sessão", "agentIdentity": "claude"},
        {"handle": "t_codex", "title": "Continue projeto do Claude", "agentIdentity": "codex"},
    ]
    oficina = _oficina(tmp_path, orca)
    with pytest.raises(OrcaErro, match="mais de uma sessão"):
        oficina.mandar_texto("laia local", "oi", sessao="claude")
    assert oficina.mandar_texto("laia local", "oi", agente="claude")["agente"] == "claude"
    envios = [c for c in orca.chamadas if c[:2] == ("terminal", "send")]
    assert all(e[e.index("--terminal") + 1] == "t_claude" for e in envios)
