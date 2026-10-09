"""O front recebe relações e estados, sem o conteúdo dos terminais."""

import json
from typing import Any

import pytest

from jarvis.rosto import rotina


class FakeOrcaRotina:
    def chamar(self, *args: str, limite_s: float) -> dict[str, Any]:
        assert args == ("worktree", "ps", "--limit", "200")
        assert limite_s == 3
        return {
            "worktrees": [
                {
                    "worktreeId": "projeto::principal",
                    "path": "/mesma/pasta",
                    "displayName": "Principal",
                    "workspaceStatus": "in-progress",
                    "agents": [
                        {
                            "paneKey": "terminal-a",
                            "agentType": "codex",
                            "state": "working",
                            "prompt": "conteúdo reservado",
                            "toolInput": "comando reservado",
                            "lastAssistantMessage": "mensagem reservada",
                        }
                    ],
                },
                {
                    "worktreeId": "projeto::outra-frente",
                    "path": "/mesma/pasta",
                    "displayName": "Outra frente",
                    "agents": [],
                },
                {"worktreeId": "arquivado", "path": "/arquivado", "isArchived": True},
            ]
        }


def test_frentes_com_mesma_pasta_conservam_identidade_e_relacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rotina, "Orca", FakeOrcaRotina)
    dados = rotina.retrato({})
    assert [p["id"] for p in dados["projetos"]] == ["projeto::principal", "projeto::outra-frente"]
    assert dados["agentes"][0]["projeto"] == "projeto::principal"


def test_retrato_nao_exporta_prompt_comando_ou_mensagem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rotina, "Orca", FakeOrcaRotina)
    dados = rotina.retrato({"tarefa-a": {"tarefa": "Revisar projeto", "agente": "codex"}})
    assert "reservado" not in json.dumps(dados)
    assert "reservada" not in json.dumps(dados)
    assert dados["tarefas"][0]["rotulo"] == "Revisar projeto"
