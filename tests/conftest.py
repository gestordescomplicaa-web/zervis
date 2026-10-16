"""Os testes nunca leem nem escrevem os dados de verdade (docs/plano-distribuicao.md).

Antes de qualquer módulo do Zé ser importado, as três raízes (config, dados, estado) apontam para
uma pasta temporária: sem perfil, sem chaves e sem memória da máquina de quem roda os testes.
"""

import os
import tempfile

import pytest

os.environ["JARVIS_RAIZ"] = tempfile.mkdtemp(prefix="ze-testes-")
os.environ.pop("JARVIS_PERFIL", None)
os.environ["JARVIS_FUSO"] = "America/Recife"  # as datas dos testes foram escritas nesse fuso
# A captura das sessões não pode alcançar a memória da pessoa que roda os testes.
os.environ["AI_MEMORY_DATA_DIR"] = os.path.join(os.environ["JARVIS_RAIZ"], "ai-memory")
os.environ["AI_MEMORY_SERVER_URL"] = "http://127.0.0.1:1"
os.environ.pop("AI_MEMORY_AUTH_TOKEN", None)
# Nem as contas dos agentes desta máquina: pastas de login vazias, sem ninguém logado.
for _variavel in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
    os.environ[_variavel] = os.path.join(os.environ["JARVIS_RAIZ"], "contas-vazias", _variavel)

# Os testes do modo imersivo abrem a página num Chromium de verdade (sem tela) e levam minutos:
# rodam à parte, em `make check-imersivo`.
collect_ignore = [] if os.environ.get("ZE_TESTES_IMERSIVO") else ["imersivo"]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Com `ZE_SEM_PULOS=1` (a CI), teste pulado é falha. Sem Chromium ou sem os modelos de som,
    a prova que o teste daria some sem aviso e o `make check` passaria assim mesmo (lição de
    16/10/2026: o painel no navegador pulado numa máquina sem Chromium)."""
    if not os.environ.get("ZE_SEM_PULOS") or exitstatus != pytest.ExitCode.OK:
        return
    relator = session.config.pluginmanager.get_plugin("terminalreporter")
    if relator is not None and relator.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    if os.environ.get("ZE_SEM_PULOS") and (pulados := terminalreporter.stats.get("skipped")):
        terminalreporter.write_line(
            f"ZE_SEM_PULOS: {len(pulados)} teste(s) pulado(s) contam como falha.", red=True
        )
