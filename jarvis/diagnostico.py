"""O diagnóstico do Zé (ADR 0025, camada 2): o que deu errado, agrupado por causa.

Lê a atividade (falhas, negadas, não entendi, correções, pedidos) e o registro técnico do serviço
(erros e avisos), junta o que é igual e devolve um relatório curto em Markdown. É feito aqui, sem
modelo: a sessão "Zé · melhorias" recebe o relatório e propõe as correções (ADR 0026); nada muda
sem a pessoa aprovar.
"""

import re
import time
from collections import Counter
from collections.abc import Iterable
from typing import Any

from jarvis.atividade import TIPOS

ROTULOS = {
    "execucao": "Execuções",
    "negada": "Negadas",
    "falha": "Falhas",
    "nao_entendi": "Não entendeu",
    "correcao": "Correções",
    "pedido": "Pedidos atendidos",
}
# Prefixo do journal ("2026-10-13T11:24:19-03:00 omarchy python[123]: ") e o que muda a cada vez.
PREFIXO = re.compile(r"^\S+\s+\S+\s+[\w.-]+\[\d+\]:\s*")
VARIAVEL = re.compile(r"\b\d[\d:.,/-]*\b|0x[0-9a-f]+|https?://\S+|/[\w./-]{8,}")


def assinatura(linha: str) -> str:
    """A mesma mensagem com números, endereços e caminhos trocados por #: o que se repete."""
    return VARIAVEL.sub("#", PREFIXO.sub("", linha)).strip()[:160]


def _exemplos(itens: Iterable[dict[str, Any]], campo: str, maximo: int = 3) -> list[str]:
    vistos = list(dict.fromkeys(str(i.get(campo) or "") for i in itens))
    return [v for v in vistos if v][:maximo]


def montar(
    itens: list[dict[str, Any]],
    registro: list[str],
    dias: int = 7,
    agora: float | None = None,
) -> str:
    """O relatório dos últimos `dias` a partir da atividade e do registro técnico."""
    agora = agora if agora is not None else time.time()
    recentes = [i for i in itens if float(i.get("quando", 0)) >= agora - dias * 86400]
    por_tipo = {t: [i for i in recentes if i.get("tipo") == t] for t in TIPOS}
    data = time.strftime("%d/%m/%Y %H:%M", time.localtime(agora))
    linhas = [
        f"# Diagnóstico do Zé ({data}, últimos {dias} dias)",
        "",
        " · ".join(f"{ROTULOS[t]}: {len(por_tipo[t])}" for t in TIPOS),
    ]

    def secao(titulo: str, grupos: Counter[str], exemplos: dict[str, list[str]]) -> None:
        if not grupos:
            return
        linhas.extend(["", f"## {titulo}"])
        for chave, n in grupos.most_common(8):
            ex = exemplos.get(chave) or []
            sufixo = f" (ex.: {'; '.join(ex)})" if ex else ""
            linhas.append(f"- {chave}: {n} vez(es){sufixo}")

    falhas = por_tipo["falha"]
    secao(
        "Falhas",
        Counter(str(i.get("titulo")) for i in falhas),
        {
            t: _exemplos((i for i in falhas if i.get("titulo") == t), "erro")
            or _exemplos((i for i in falhas if i.get("titulo") == t), "motivo")
            for t in {str(i.get("titulo")) for i in falhas}
        },
    )
    nao = por_tipo["nao_entendi"]
    if nao:
        linhas.extend(
            [
                "",
                "## Não entendeu",
                f"- {len(nao)} vez(es) (ex.: {'; '.join(_exemplos(nao, 'titulo', 5))})",
            ]
        )
    corr = por_tipo["correcao"]
    if corr:
        linhas.extend(
            ["", "## Correções da pessoa", *(f'- "{t}"' for t in _exemplos(corr, "titulo", 5))]
        )
    negadas = por_tipo["negada"]
    secao(
        "Negadas",
        Counter(f"{i.get('titulo')} ({i.get('motivo', '')})" for i in negadas),
        {},
    )
    erros = Counter(
        assinatura(x) for x in registro if any(m in x for m in ("ERROR", "WARNING", "Traceback"))
    )
    secao("Registro técnico (erros e avisos que mais se repetem)", erros, {})
    if len(linhas) == 3:
        linhas.extend(["", "Nada a corrigir nos últimos dias."])
    return "\n".join(linhas) + "\n"


PEDIDO = (
    "Diagnóstico do uso real do Zé, para você melhorar o próprio Zé (ADR 0025 e 0026). Leia "
    "docs/essencia.md. Proponha até cinco melhorias numeradas, da mais útil para a menos, cada uma "
    "com: o problema que resolve, a causa provável, o tipo (aprender: sinônimo, memória ou skill; "
    "ajustar: configuração; corrigir código) e o risco. Não implemente ainda: espere a pessoa "
    "escolher nesta sessão. Ao implementar, trabalhe nesta cópia, com testes e commit; nada entra "
    "no Zé em uso sem a pessoa aprovar no painel. Os dados do uso estão todos neste relatório: "
    "não leia as pastas de dados do Zé (~/.config/zervis, ~/.local/share/zervis, "
    "~/.local/state/zervis), que guardam conversas e acessos da pessoa; trabalhe com o relatório "
    "e o código.\n\n"
)
