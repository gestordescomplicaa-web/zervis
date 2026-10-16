"""As ferramentas do cérebro sobre as sessões de código do Zé (sem o Orca, ADR 0015)."""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from jarvis.cerebro import contas
from jarvis.cerebro.ferramentas import LIVRES, SERVIDOR
from jarvis.cerebro.ferramentas import sessoes as g
from jarvis.oficina.sessoes import Sessao, Sessoes


def chamar(ferramentas: dict[str, Any], nome: str, args: dict[str, Any]) -> Any:
    r = asyncio.run(ferramentas[nome](args))
    texto = r["content"][0]["text"]
    return (texto, True) if r.get("is_error") else (json.loads(texto), False)


def test_delegar_acompanhar_e_ler_uma_sessao(tmp_path: Path) -> None:
    projeto = tmp_path / "casa" / "loja"
    projeto.mkdir(parents=True)

    async def rodar(sessoes: Sessoes, s: Sessao, texto: str) -> str:
        sessoes.anotar(s.id, "agente", f"Feito: {texto}")
        return "Feito."

    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), rodar=rodar)
    f = {t.name: t.handler for t in g.ferramentas(sessoes)}
    criada, erro = chamar(
        f, "sessao_criar", {"nome": "Loja", "pasta": str(projeto), "tarefa": "testes"}
    )
    assert not erro and criada["criada"] and criada["pasta"] == str(projeto)
    fim = time.monotonic() + 5
    while sessoes.ler(criada["id"]).estado == "trabalhando" and time.monotonic() < fim:
        time.sleep(0.02)
    (item,) = chamar(f, "sessoes_listar", {})[0]
    assert (
        item["nome"] == "Loja" and item["estado"] == "parada" and item["ultimo_recado"] == "Feito."
    )
    lido, _ = chamar(f, "sessao_ler", {"sessao": criada["id"]})
    assert [m["quem"] for m in lido["mensagens"]][-2:] == ["usuario", "agente"]
    assert lido["mensagens"][-1]["texto"] == "Feito: testes"
    # Fora das pastas permitidas não vira sessão; sem pasta nem projeto novo, avisa.
    assert chamar(f, "sessao_criar", {"nome": "x", "pasta": "/etc"})[1]
    texto, erro = chamar(f, "sessao_criar", {"nome": "x"})
    assert erro and "projetos novos" in texto  # sem raiz de projetos, não inventa pasta


def test_cada_sessao_nova_ganha_a_propria_pasta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Na VPS: "crie uma sessão chamada teste", sem pasta, numa máquina sem identidade no git."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig-vazio"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr(g, "motor_conectado", lambda: "codex")
    projetos = tmp_path / "casa" / "projetos"
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), projetos_novos=projetos)
    f = {t.name: t.handler for t in g.ferramentas(sessoes)}
    teste, erro = chamar(f, "sessao_criar", {"nome": "teste"})
    assert not erro and teste["pasta"] == str(projetos / "teste") and teste["motor"] == "codex"
    log = subprocess.run(  # noqa: S603 (git fixo, argumentos em lista)
        ["git", "-C", teste["pasta"], "log", "--format=%an"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    assert log.stdout.strip() == "Zérvis"  # o primeiro commit saiu, mesmo sem nome no git
    outra, _ = chamar(f, "sessao_criar", {"nome": "outra"})
    assert outra["pasta"] == str(projetos / "outra")  # independentes
    # O nome de um projeto que já existe é a pasta dele.
    junto, _ = chamar(f, "sessao_criar", {"nome": "revisão", "pasta": "teste"})
    assert junto["pasta"] == str(projetos / "teste")


def test_motor_padrao_e_o_agente_com_conta_conectada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pastas = {"claude": tmp_path / "claude", "codex": tmp_path / "codex"}

    class Contas:
        def em_uso(self, motor: str) -> contas.Conta:
            return contas.Conta(f"{motor}:t", motor, "T", pasta=str(pastas[motor]))

    monkeypatch.setattr(contas, "Contas", Contas)
    assert g.motor_conectado() == "claude"  # nenhuma: o primeiro
    pastas["codex"].mkdir()
    (pastas["codex"] / "auth.json").write_text("{}")
    assert g.motor_conectado() == "codex"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert g.motor_conectado() == "claude"


def test_ler_e_listar_sao_livres_e_o_resto_pede_aprovacao() -> None:
    livres = {n.removeprefix(f"mcp__{SERVIDOR}__") for n in LIVRES}
    assert {"sessoes_listar", "sessao_ler"} <= livres
    assert not {"sessao_criar", "sessao_enviar", "sessao_parar"} & livres
    assert g.ferramentas(None) == []


def test_a_sessao_pelo_nome_ou_a_em_foco(tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    for nome in ("loja", "site", "site-novo"):
        (casa / nome).mkdir(parents=True)

    async def rodar(sessoes: Sessoes, s: Sessao, texto: str) -> str:
        return "ok"

    sessoes = Sessoes(tmp_path / "sessoes", (casa,), rodar=rodar)
    loja = sessoes.criar("Loja Virtual", str(casa / "loja"))
    sessoes.criar("Site", str(casa / "site"))
    sessoes.criar("Site novo", str(casa / "site-novo"))
    f = {t.name: t.handler for t in g.ferramentas(sessoes)}
    assert sessoes.achar("loja virtual").id == loja.id
    assert sessoes.achar("LOJA").id == loja.id  # um pedaço único basta
    assert sessoes.achar("site").nome == "Site"  # o nome exato vence o pedaço
    texto, erro = chamar(f, "sessao_ler", {"sessao": "novo site"})
    assert erro and "não há sessão" in texto
    sessoes.focar(loja.id)  # o último aviso foi dela
    lido, erro = chamar(f, "sessao_ler", {})
    assert not erro and lido["nome"] == "Loja Virtual"
    sessoes.em_foco = (loja.id, time.time() - 3600)  # foco velho não vale
    texto, erro = chamar(f, "sessao_ler", {})
    assert erro and "qual sessão" in texto
