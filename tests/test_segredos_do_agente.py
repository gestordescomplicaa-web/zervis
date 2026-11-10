"""Os segredos do Zé não chegam ao agente (plano de maturidade, Frente 2; ADR 0075).

O ambiente do Zé vem do perfil de quem usa, que exporta tokens de outros serviços: em 10/11/2026
um token do n8n chegava a todas as sessões, protegidas ou não. O agente recebe o ambiente sem as
variáveis de segredo, menos as do próprio login e as que a sessão entrega de propósito.
"""

import os
import stat
import time
from pathlib import Path

import pytest

from zervis.oficina import isolamento
from zervis.oficina.agentes import ambiente_do_agente, ambiente_para_sdk, sem_segredos
from zervis.oficina.sessoes import Sessao, Sessoes

DO_ZE = {
    "PATH": "/usr/bin",
    "HOME": "/home/x",
    "PWD": "/home/x",
    "LANG": "pt_BR.UTF-8",
    "XAUTHORITY": "/run/user/1000/xauth",
    "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent",
    "N8N_MCP_TOKEN": "n8n-segredo",
    "GITHUB_TOKEN": "ghp-segredo",
    "DEEPGRAM_API_KEY": "dg-segredo",
    "OPENROUTER_API_KEY": "or-segredo",
    "AWS_SECRET_ACCESS_KEY": "aws-segredo",
    "DB_PASSWORD": "senha",
    "ANTHROPIC_API_KEY": "sk-ant-login",
    "OPENAI_API_KEY": "sk-login",
}


def test_saem_os_segredos_e_fica_o_resto() -> None:
    limpo = sem_segredos(DO_ZE, "claude")
    assert not any("segredo" in v or v == "senha" for v in limpo.values())
    for fica in ("PATH", "HOME", "PWD", "LANG", "XAUTHORITY", "SSH_AUTH_SOCK"):
        assert limpo[fica] == DO_ZE[fica]


def test_cada_agente_leva_so_o_proprio_login() -> None:
    claude, codex = sem_segredos(DO_ZE, "claude"), sem_segredos(DO_ZE, "codex")
    assert claude["ANTHROPIC_API_KEY"] == "sk-ant-login" and "OPENAI_API_KEY" not in claude
    assert codex["OPENAI_API_KEY"] == "sk-login" and "ANTHROPIC_API_KEY" not in codex


def test_o_claude_pela_bedrock_leva_as_credenciais_da_nuvem() -> None:
    bedrock = sem_segredos({**DO_ZE, "CLAUDE_CODE_USE_BEDROCK": "1"}, "claude")
    assert bedrock["AWS_SECRET_ACCESS_KEY"] == "aws-segredo"  # noqa: S105 (de mentira)
    assert "GITHUB_TOKEN" not in bedrock
    assert "AWS_SECRET_ACCESS_KEY" not in sem_segredos(
        {**DO_ZE, "CLAUDE_CODE_USE_BEDROCK": "1"}, "codex"
    )


def test_o_que_a_sessao_entrega_de_proposito_passa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_MCP_TOKEN", "n8n-segredo")
    s = Sessao("a1b2c3d4", "Loja", "/tmp/loja", "codex")  # noqa: S108
    ambiente = ambiente_do_agente(s, {"ERP_TOKEN": "do-conector", "ZE_PERMISSAO": "chave"})
    assert "N8N_MCP_TOKEN" not in ambiente
    assert ambiente["ERP_TOKEN"] == "do-conector"  # noqa: S105 (de mentira)
    assert ambiente["ZE_PERMISSAO"] == "chave"
    assert ambiente["PATH"] == os.environ["PATH"]


def test_pelo_sdk_os_segredos_vao_vazios(monkeypatch: pytest.MonkeyPatch) -> None:
    """O SDK do Claude junta o ambiente do Zé por baixo: apagar é mandar vazio."""
    monkeypatch.setenv("N8N_MCP_TOKEN", "n8n-segredo")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-login")
    ambiente = ambiente_para_sdk(Sessao("a1b2c3d4", "Loja", "/tmp/loja", "claude"))  # noqa: S108
    assert ambiente["N8N_MCP_TOKEN"] == ""
    assert "ANTHROPIC_API_KEY" not in ambiente  # o login fica como está
    assert "PATH" not in ambiente


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_o_terminal_da_sessao_abre_sem_os_segredos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De ponta a ponta: um agente de mentira grava o ambiente que recebeu."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    saida = tmp_path / "ambiente.txt"
    falso = bin_ / "codex"
    falso.write_text(f"#!/bin/sh\nenv > {saida}\nsleep 5\n")
    falso.chmod(falso.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_}:/usr/bin:/bin")
    monkeypatch.setenv("N8N_MCP_TOKEN", "n8n-segredo")
    projeto = tmp_path / "casa" / "projetos" / "loja"
    projeto.mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), lambda s, r: None)
    s = sessoes.criar("Loja", str(projeto), "codex")
    terminal = sessoes.abrir_terminal(s.id)
    try:
        prazo = time.monotonic() + 10
        while not (saida.exists() and saida.read_text().strip()) and time.monotonic() < prazo:
            time.sleep(0.05)
        recebido = saida.read_text()
    finally:
        terminal.encerrar()
    assert "PATH=" in recebido
    assert "n8n-segredo" not in recebido


def test_na_protegida_o_run_user_vira_uma_pasta_vazia(tmp_path: Path) -> None:
    runtime = tmp_path / "run-user"
    runtime.mkdir()
    comando = isolamento.envolver(["true"], [], casa=tmp_path, runtime=runtime)
    assert ["--tmpfs", str(runtime)] == comando[comando.index(str(runtime)) - 1 :][:2]
    sem_pasta = isolamento.envolver(["true"], [], casa=tmp_path, runtime=tmp_path / "x")
    assert sem_pasta.count("--tmpfs") == 2  # o /tmp e a casa; a pasta que não existe, nada


@pytest.mark.skipif(
    not isolamento.disponivel() or not os.environ.get("XDG_RUNTIME_DIR"),
    reason="sem bubblewrap ou sem /run/user",
)
def test_o_d_bus_e_o_ssh_agent_da_maquina_ficam_fora(tmp_path: Path) -> None:
    """O D-Bus (chaveiro; `systemd-run --user` roda lá fora), o ssh-agent e o gpg-agent."""
    import subprocess

    runtime = os.environ["XDG_RUNTIME_DIR"]
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    comando = isolamento.envolver(["ls", "-A", runtime], [projeto], pasta=projeto)
    feito = subprocess.run(comando, capture_output=True, text=True, timeout=30)  # noqa: S603
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == ""
