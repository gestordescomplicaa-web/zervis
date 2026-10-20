"""Contas sintéticas e PTY real: continuidade sem alterar modelo nem repetir contas."""

import asyncio
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import contas
from jarvis.oficina import fallback
from jarvis.oficina.sessoes import LimiteErro, Sessao, Sessoes, comando_terminal


def esperar(condicao: Any) -> None:
    fim = time.monotonic() + 8
    while not condicao():
        assert time.monotonic() < fim, "fallback demorou"
        time.sleep(0.02)


@pytest.fixture
def contas_teste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> contas.Contas:
    cs = contas.Contas(tmp_path / "contas.json", tmp_path / "contas")
    monkeypatch.setattr(contas, "Contas", lambda: cs)
    for nome, plano in (("Origem", "pro"), ("Gratuita", "free"), ("Plus", "plus"), ("Pro", "pro")):
        c = cs.adicionar("codex", nome)
        claims = {"https://api.openai.com/auth": {"chatgpt_plan_type": plano}}
        carga = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        c.login.write_text(json.dumps({"tokens": {"id_token": f"x.{carga}.x"}}))
        (c.onde / "models_cache.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "slug": "modelo-teste",
                            "visibility": "list",
                            "display_name": "Modelo",
                            "supported_reasoning_levels": [{"effort": "high"}],
                        }
                    ]
                }
            )
        )
    return cs


def test_ordem_por_plano_e_compatibilidade(contas_teste: contas.Contas) -> None:
    cs = contas_teste
    origem = next(c for c in cs.listar() if c.nome == "Origem")
    assert [
        c.nome for c in fallback.candidatas(cs, "codex", "modelo-teste", "high", {origem.id})
    ] == ["Pro", "Plus", "Gratuita"]
    assert not fallback.candidatas(cs, "codex", "modelo-teste", "ultra", set())
    assert not fallback.candidatas(cs, "codex", "outro-modelo", "high", set())
    assert not fallback.candidatas(cs, "codex", "", "", set())


@pytest.mark.parametrize("origem", ["painel", "manutencao"])
def test_cadeia_automatica_na_mesma_sessao_sem_repetir_contas(
    tmp_path: Path,
    contas_teste: contas.Contas,
    origem: str,
) -> None:
    cs = contas_teste
    inicial = next(c for c in cs.listar() if c.nome == "Origem")
    recebidos: list[tuple[str, str, str, str]] = []
    avisos: list[str] = []

    async def rodar(ss: Sessoes, s: Sessao, texto: str) -> str:
        recebidos.append((cs.achar(s.conta).nome, s.modelo, s.esforco, texto))
        await asyncio.sleep(0.02)
        raise LimiteErro("usage limit")

    ss = Sessoes(tmp_path / "sessoes", (tmp_path,), lambda s, r: avisos.append(r), rodar)
    s = ss.criar("Teste", str(tmp_path), "codex", origem=origem)
    ss._mudar(s.id, conta=inicial.id, modelo="modelo-teste", esforco="high")
    ss.enviar(s.id, "Faça apenas o restante.")
    esperar(lambda: any("Nenhuma conta" in a for a in avisos))
    assert [c[0] for c in recebidos] == ["Origem", "Pro", "Plus", "Gratuita"]
    assert all(c[1:3] == ("modelo-teste", "high") for c in recebidos)
    assert all(c[3].count("Faça apenas o restante.") <= 3 for c in recebidos)
    assert len(ss.listar()) == 1
    assert ss.ler(s.id).origem == origem
    assert ss.ler(s.id).limite
    assert len(ss._dados.listar("fallback-contas")) == 4


def eventos_nativos(pasta: Path, erro: bool = True) -> list[dict[str, Any]]:
    eventos = [
        {
            "type": "session_meta",
            "payload": {"id": "fio-teste", "cwd": str(pasta), "source": "cli"},
        },
        {"type": "turn_context", "payload": {"model": "modelo-teste", "effort": "high"}},
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "Pedido digitado no terminal."},
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "error" if erro else "agent_message",
                "codex_error_info": "usage_limit_exceeded" if erro else None,
                "message": "You've hit your usage limit",
            },
        },
    ]
    for evento in eventos:
        evento["timestamp"] = datetime.now().astimezone().isoformat()
    return eventos


@pytest.mark.parametrize("confirmado", [True, False])
def test_terminal_real_retoma_so_com_evidencia_e_atualiza_copia_nativa(
    tmp_path: Path,
    contas_teste: contas.Contas,
    monkeypatch: pytest.MonkeyPatch,
    confirmado: bool,
) -> None:
    cs = contas_teste
    inicial = next(c for c in cs.listar() if c.nome == "Origem")
    pro = next(c for c in cs.listar() if c.nome == "Pro")
    transcricao = inicial.onde / "sessions/rollout-fio-teste.jsonl"
    transcricao.parent.mkdir()
    antiga = pro.onde / "sessions/rollout-fio-teste.jsonl"
    antiga.parent.mkdir()
    antiga.write_text("cópia antiga\n")
    comandos: list[tuple[Sessao, str]] = []
    avisos: list[str] = []

    def comando(
        s: Sessao, pedido: str, eventos: Path, contexto: Path | None, *_conectores: object
    ) -> list[str]:
        comandos.append((s, pedido))
        if s.conta == inicial.id:
            linhas = "".join(json.dumps(e) + "\n" for e in eventos_nativos(tmp_path, confirmado))
            script = (
                "from pathlib import Path; import time; "
                f"Path({str(transcricao)!r}).write_text({linhas!r}); "
                'print("You\'ve hit your usage limit", flush=True); time.sleep(60)'
            )
        else:
            script = "import time; print('Continuando', flush=True); time.sleep(60)"
        return [sys.executable, "-c", script]

    monkeypatch.setattr("jarvis.oficina.sessoes.comando_terminal", comando)
    monkeypatch.setattr("jarvis.oficina.sessoes.confiar_pasta_codex", lambda s: None)
    ss = Sessoes(tmp_path / "sessoes", (tmp_path,), lambda s, r: avisos.append(r))
    s = ss.criar("Teste", str(tmp_path), "codex")
    ss._mudar(s.id, conta=inicial.id, modelo="modelo-antigo", esforco="low")
    primeiro = ss.abrir_terminal(s.id)
    try:
        if confirmado:
            esperar(lambda: avisos)
            assert len(comandos) == 2
            novo, pedido = comandos[-1]
            assert novo.conta == pro.id
            assert (novo.modelo, novo.esforco) == ("modelo-teste", "high")
            assert novo.sdk_sessao == "fio-teste"
            assert "Pedido digitado no terminal." in pedido and "Não repita ações" in pedido
            assert antiga.read_text() == transcricao.read_text()
            assert not primeiro.vivo and not primeiro.leitor.is_alive()
            assert ss.ler(s.id).estado == "trabalhando"
        else:
            esperar(lambda: transcricao.exists() and primeiro.fim > 0)
            time.sleep(0.6)
            assert len(comandos) == 1 and primeiro.vivo
            assert not avisos and not ss.ler(s.id).limite
    finally:
        ss.fallback.cancelar(s.id)
        for terminal in ss.terminais.values():
            terminal.encerrar()


def test_cancelamento_e_reserva_impedem_retomada(
    tmp_path: Path,
    contas_teste: contas.Contas,
) -> None:
    async def rodar(*args: Any) -> str:
        pytest.fail("não deve enviar")

    ss = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=rodar)
    s = ss.criar("Teste", str(tmp_path), "codex")
    inicial = next(c for c in contas_teste.listar() if c.nome == "Origem")
    ss._mudar(
        s.id,
        conta=inicial.id,
        modelo="modelo-teste",
        esforco="high",
        limite=True,
        ultimo_pedido="pedido",
        estado="erro",
    )
    ss.fallback.agendar(s.id, True)
    ss.fallback.cancelar(s.id)
    time.sleep(0.5)
    assert ss.ler(s.id).conta == inicial.id
    ss.reservada = lambda: "Atualização em andamento."
    ss.fallback.agendar(s.id, True)
    esperar(lambda: s.id not in ss.fallback.pendentes)
    assert ss.ler(s.id).conta == inicial.id and not ss.tarefas


def test_registro_nao_reusa_limite_de_turno_antigo(tmp_path: Path) -> None:
    arquivo = tmp_path / "registro.jsonl"
    eventos = eventos_nativos(tmp_path)
    eventos.append(
        {"type": "event_msg", "payload": {"type": "user_message", "message": "Novo pedido"}}
    )
    arquivo.write_text("".join(json.dumps(e) + "\n" for e in eventos))
    contexto = fallback.ler_registro(arquivo, "codex")
    assert contexto.pedido == "Novo pedido" and not contexto.limite


def test_claude_passa_esforco_explicito(tmp_path: Path) -> None:
    s = Sessao("teste", "Teste", str(tmp_path), modelo="claude-sonnet-5-5", esforco="high")
    cmd = comando_terminal(s, "continue", tmp_path / "eventos")
    assert cmd[cmd.index("--effort") + 1] == "high"


def test_hook_atrasado_nao_apaga_limite_nem_anuncia_conclusao(tmp_path: Path) -> None:
    avisos: list[str] = []
    ss = Sessoes(
        tmp_path / "sessoes", (tmp_path,), lambda s, r: avisos.append(r), rodar=lambda *args: None
    )
    s = ss.criar("Teste", str(tmp_path))
    ss._mudar(s.id, limite=True, estado="erro")
    ss.fallback.pendentes[s.id] = object()
    ss._evento(s.id, {"hook_event_name": "UserPromptSubmit", "prompt": "pedido atual"})
    ss._evento(s.id, {"hook_event_name": "Stop", "last_assistant_message": "limit reached"})
    assert ss.ler(s.id).limite and ss.ler(s.id).estado == "erro"
    assert not avisos


def test_percentual_cheio_nao_comprova_bloqueio(tmp_path: Path) -> None:
    arquivo = tmp_path / "registro.jsonl"
    eventos = eventos_nativos(tmp_path, False)
    eventos.append(
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {
                    "primary": {"used_percent": 100},
                    "credits": {"has_credits": True},
                },
            },
        }
    )
    arquivo.write_text("".join(json.dumps(e) + "\n" for e in eventos))
    assert not fallback.ler_registro(arquivo, "codex").limite


def test_claude_nao_confunde_esforco_salvo_com_o_da_conversa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conta = contas.Conta("claude:teste", "claude", "Teste", str(tmp_path / "conta"))
    arquivo = conta.onde / "projects/projeto/fio.jsonl"
    arquivo.parent.mkdir(parents=True)
    eventos = [
        {"type": "user", "message": {"content": "pedido"}},
        {"type": "assistant", "error": "rate_limit", "message": {"model": "claude-sonnet-5-5"}},
    ]
    arquivo.write_text("".join(json.dumps(e) + "\n" for e in eventos))
    (conta.onde / "settings.json").write_text('{"effortLevel":"low"}')
    ss = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *args: None)
    s = Sessao("teste", "Teste", str(tmp_path), sdk_sessao="fio")
    monkeypatch.delenv("CLAUDE_CODE_EFFORT_LEVEL", raising=False)
    assert ss.fallback._registro(s, conta).esforco == ""
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "high")
    contexto = ss.fallback._registro(s, conta)
    assert contexto.esforco == "high" and contexto.limite


def test_redesenhar_limite_antigo_na_conta_atual_nao_altera_estado(
    tmp_path: Path,
    contas_teste: contas.Contas,
) -> None:
    atual = next(c for c in contas_teste.listar() if c.nome == "Origem")
    avisos: list[str] = []
    ss = Sessoes(
        tmp_path / "sessoes", (tmp_path,), lambda s, r: avisos.append(r), rodar=lambda *args: None
    )
    s = ss.criar("Teste", str(tmp_path), "codex")
    ss._mudar(
        s.id,
        conta=atual.id,
        sdk_sessao="fio-teste",
        estado="trabalhando",
        ultimo_pedido="Pedido atual",
    )
    ss.fallback.inicios[s.id] = time.time() - 1
    eventos = eventos_nativos(tmp_path)
    eventos[-1]["timestamp"] = datetime.fromtimestamp(time.time() - 3600).astimezone().isoformat()
    # Uma atualização de saldo depois do erro antigo não torna esse erro recente.
    eventos.append(
        {
            "type": "event_msg",
            "timestamp": datetime.now().astimezone().isoformat(),
            "payload": {"type": "token_count", "rate_limits": {"primary": {"used_percent": 20}}},
        }
    )
    arquivo = atual.onde / "sessions/rollout-fio-teste.jsonl"
    arquivo.parent.mkdir()
    arquivo.write_text("".join(json.dumps(e) + "\n" for e in eventos))
    ss._olhar_saida(s.id, b"You've hit your usage limit")
    esperar(lambda: s.id not in ss.fallback.pendentes)
    final = ss.ler(s.id)
    assert final.conta == atual.id and final.estado == "trabalhando" and not final.limite
    assert final.ultimo_pedido == "Pedido atual" and not avisos


def test_limite_fica_vinculado_a_conta_e_marcacao_antiga_e_descartada(tmp_path: Path) -> None:
    ss = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *args: None)
    s = ss.criar("Teste", str(tmp_path), "codex")
    ss._mudar(s.id, limite=True, estado="erro", resumo="a conta Padrão do Codex bateu o limite")
    assert ss.ler(s.id).limite_conta == s.conta
    assert not ss._mudar(s.id, conta="codex:outra").limite
    dados = ss._dados.ler("sessoes", s.id)
    assert dados is not None
    dados.update(limite=True, limite_conta="codex:padrao")
    ss._dados.guardar("sessoes", dados, s.id)
    assert not ss.ler(s.id).limite
    dados.pop("limite_conta")  # estado salvo antes da correção
    ss._dados.guardar("sessoes", dados, s.id)
    assert not ss.ler(s.id).limite and not ss.ler(s.id).resumo
