"""Retrato de leitura da oficina para Brain / Work / Focus no Barehands.

Executado na thread da pasta, nunca no laço de áudio. A lista permitida evita
exportar prompts, conversas e comandos dos terminais junto dos estados públicos.
"""

from typing import Any

from jarvis.oficina.orca import Orca


def retrato(tarefas: dict[str, dict[str, str]]) -> dict[str, Any]:
    resposta = Orca().chamar("worktree", "ps", "--limit", "200", limite_s=3)
    projetos: list[dict[str, Any]] = []
    agentes: list[dict[str, Any]] = []
    for w in resposta.get("worktrees", []):
        if w.get("isArchived") or not w.get("path"):
            continue
        identidade = str(w.get("worktreeId") or w.get("id") or w["path"])
        nome = str(w.get("displayName") or w["path"].rsplit("/", 1)[-1])
        projetos.append(
            {"id": identidade, "rotulo": nome, "estado": w.get("workspaceStatus") or ""}
        )
        for a in w.get("agents", []):
            agentes.append(
                {
                    "id": f"{identidade}:{a.get('paneKey', len(agentes))}",
                    "rotulo": str(a.get("agentType") or "Agente"),
                    "estado": str(a.get("state") or "desconhecido"),
                    "projeto": identidade,
                    "projeto_nome": nome,
                }
            )
    return {
        "disponivel": True,
        "limitado": bool(resposta.get("truncated")),
        "projetos": projetos,
        "agentes": agentes,
        "tarefas": [
            {
                "id": k,
                "rotulo": v.get("tarefa", "Tarefa delegada"),
                "projeto_nome": v.get("projeto", ""),
                "agente": v.get("agente", ""),
            }
            for k, v in tarefas.items()
        ],
    }
