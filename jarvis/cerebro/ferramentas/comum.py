"""O que todas as ferramentas do servidor `jarvis` usam: respostas e erros no formato MCP."""

import json
import logging
from typing import Any

from jarvis.habilidades.skills import Skills
from jarvis.memoria.curta import Mudanca

log = logging.getLogger("jarvis.cerebro.ferramentas")


def _texto(dados: Any) -> dict[str, Any]:
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    return {"content": [{"type": "text", "text": texto}]}


def _erro(erro: Exception) -> dict[str, Any]:
    log.warning("ferramenta da oficina falhou: %s", erro)
    return {"content": [{"type": "text", "text": f"Falhou: {erro}"}], "is_error": True}


def _mudanca(args: dict[str, Any]) -> Mudanca:
    return Mudanca(
        str(args.get("acao", "")),
        str(args.get("alvo", "")),
        str(args.get("texto", "")),
        str(args.get("antigo", "")),
    )


def _skill_nova(skills: Skills, entrada: dict[str, Any]) -> str:
    return skills.novo_conteudo(
        str(entrada.get("nome", "")),
        conteudo=str(entrada.get("conteudo", "")),
        antigo=str(entrada.get("trecho_antigo", "")),
        novo=str(entrada.get("trecho_novo", "")),
    )
