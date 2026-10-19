"""O Zé integra um sistema pela conversa (ADR 0037): cadastrar, testar e listar conectores, sem
segredo passando pelo cérebro, e o painel avisando que há conector novo para aplicar."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import conectores, mcp_externo
from jarvis.cerebro.claude import descrever
from jarvis.cerebro.ferramentas import LIVRES, SERVIDOR
from jarvis.cerebro.ferramentas import conectores as g
from jarvis.portal.acoes.conectores import AcoesConectores
from jarvis.portal.acoes.pagina import Servicos
from tests.test_conectores import SERVIDOR as SERVIDOR_FALSO


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(mcp_externo, "CAMINHO", tmp_path / "mcp.toml")
    monkeypatch.setattr(mcp_externo, "PAINEL", tmp_path / "mcp-painel.json")
    monkeypatch.setattr(mcp_externo, "SEGREDOS", tmp_path / "chaves" / "mcp")
    return tmp_path


def chamar(nome: str, args: dict[str, Any]) -> tuple[Any, bool]:
    f: dict[str, Any] = {t.name: t.handler for t in g.ferramentas()}
    r = asyncio.run(f[nome](args))
    texto = r["content"][0]["text"]
    if r.get("is_error"):
        return texto, True
    try:
        return json.loads(texto), False
    except ValueError:
        return texto, False


def test_cadastrar_sem_o_segredo_pede_o_valor_no_painel(config: Path) -> None:
    r, erro = chamar(
        "conector_cadastrar",
        {"nome": "hubspot", "tipo": "stdio", "comando": "npx", "ambiente": ["HUBSPOT_TOKEN"]},
    )
    assert not erro and r["faltam_segredos"] == ["HUBSPOT_TOKEN"]
    assert "Conectores" in r["proximo_passo"] and "teste" not in r
    lista, _ = chamar("conectores_listar", {})
    assert lista[0]["nome"] == "hubspot" and lista[0]["faltam_segredos"] == ["HUBSPOT_TOKEN"]


def test_cadastrar_com_tudo_ja_testa_e_lista_as_ferramentas(config: Path) -> None:
    script = config / "servidor.py"
    script.write_text(SERVIDOR_FALSO)
    r, erro = chamar(
        "conector_cadastrar",
        {
            "nome": "falso",
            "tipo": "stdio",
            "comando": sys.executable,
            "argumentos": [str(script)],
            "livres": ["listar_repos"],
            "bloqueadas": ["criar_issue"],
        },
    )
    assert not erro and r["teste"]["ok"]
    assert [f["nome"] for f in r["teste"]["ferramentas"]] == ["criar_issue", "listar_repos"]
    carregado = mcp_externo.carregar(mcp_externo.CAMINHO, env={}, painel=mcp_externo.PAINEL)
    assert carregado.livres == ["mcp__falso__listar_repos"]
    assert carregado.bloqueadas == ["mcp__falso__criar_issue"]
    testado, _ = chamar("conector_testar", {"nome": "falso"})
    assert testado["ok"]


@pytest.mark.parametrize(
    "dados",
    [
        {"tipo": "stdio", "comando": "npx", "argumentos": ["srv", "--api-key", "abc123456"]},
        {"tipo": "stdio", "comando": "npx", "argumentos": ["--token=ghp_" + "a" * 30]},
        {"tipo": "http", "url": "https://crm.exemplo.com/mcp?api_key=abcdef123"},
    ],
)
def test_segredo_no_comando_ou_no_endereco_e_recusado(config: Path, dados: dict[str, Any]) -> None:
    r, erro = chamar("conector_cadastrar", {"nome": "crm", **dados})
    assert erro and "segredo" in r
    assert not mcp_externo.PAINEL.exists()


def test_o_que_nao_e_segredo_passa(config: Path) -> None:
    for argumentos in (
        ["--key-file", "~/chaves/crm.pem"],
        ["--api-key", "$CRM_CHAVE"],
        ["--read-only"],
    ):
        dados = {"comando": "npx", "argumentos": argumentos}
        conectores.salvar("crm", dados, mcp_externo.PAINEL, mcp_externo.CAMINHO)


def test_listar_e_testar_livres_cadastrar_pede_aprovacao() -> None:
    nomes = {f"mcp__{SERVIDOR}__{n}" for n in ("conectores_listar", "conector_testar")}
    assert nomes <= set(LIVRES)
    assert f"mcp__{SERVIDOR}__conector_cadastrar" not in LIVRES
    frase = descrever(
        "mcp__jarvis__conector_cadastrar",
        {"nome": "crm", "tipo": "http", "url": "https://mcp.crm.com/v1"},
    )
    assert frase == "Vou cadastrar o conector crm, ligado a mcp.crm.com."
    local = descrever(
        "mcp__jarvis__conector_cadastrar",
        {"nome": "gh", "tipo": "stdio", "comando": "npx", "argumentos": ["-y", "srv"]},
    )
    assert local == "Vou cadastrar o conector gh, rodando npx -y srv."


class PainelFalso:
    conectores_pendentes = False

    @staticmethod
    def _chamar(funcao: Any) -> Any:
        return funcao()


def test_conector_cadastrado_pela_conversa_aparece_como_pendente(config: Path) -> None:
    valendo = mcp_externo.carregar(mcp_externo.CAMINHO, env={}, painel=mcp_externo.PAINEL)
    pagina = AcoesConectores(PainelFalso(), Servicos({"externos": lambda: valendo}))  # type: ignore[arg-type]
    assert pagina.conectores()["pendente"] is False
    dados = {"tipo": "http", "url": "https://mcp.crm.com/v1"}
    conectores.salvar("crm", dados, mcp_externo.PAINEL, mcp_externo.CAMINHO)
    assert pagina.conectores()["pendente"] is True
