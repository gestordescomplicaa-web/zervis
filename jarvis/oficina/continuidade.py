"""Passagem baseada nos registros da sessão, sem inferir conclusão nem novos pedidos."""

from typing import Any

PASSAGEM = "[Passagem do Zé]"
PEDIDO_AGORA = "\n\nPedido agora:\n"


def pedido_sem_contexto(texto: str) -> str:
    if texto.startswith(PASSAGEM):
        texto = texto.rpartition(PEDIDO_AGORA)[2]
    return texto.strip()


def trecho(texto: str, limite: int) -> str:
    """Um corte explícito conserva também as ressalvas que costumam ficar no fim."""
    if len(texto) <= limite:
        return texto
    marca = "\n[trecho omitido; consulte o histórico da sessão]\n"
    metade = (limite - len(marca)) // 2
    return texto[:metade] + marca + texto[-metade:]


def trabalho(
    mensagens: list[dict[str, Any]], ultimo_pedido: str, interrompida: str
) -> tuple[str, str]:
    """Importações de outras sessões são consulta; não substituem a tarefa da central."""
    locais = [m for m in mensagens if not m.get("origem_sessao")]
    indice = next((i for i in range(len(locais) - 1, -1, -1) if locais[i]["quem"] == "usuario"), -1)
    pedido = pedido_sem_contexto(
        interrompida or ultimo_pedido or (locais[indice]["texto"] if indice >= 0 else "")
    )
    # Um pedido enviado pelo painel pode ainda não ter chegado ao hook. A resposta anterior
    # não é resultado desse pedido. Não se usa o resumo de 300 caracteres como prova de entrega.
    mesmo = indice >= 0 and locais[indice]["texto"] == pedido
    resposta = (
        next((m["texto"] for m in reversed(locais[indice + 1 :]) if m["quem"] == "agente"), "")
        if mesmo
        else ""
    )
    return pedido, resposta


def recentes(mensagens: list[dict[str, Any]], desde: int) -> str:
    rotulos = {"usuario": "usuário", "agente": "agente", "ferramenta": "ação"}
    linhas: list[str] = []
    total = 0
    aviso = "[Há eventos anteriores omitidos; consulte o histórico da sessão]\n"
    cortado = False
    for m in reversed(mensagens[desde:]):
        if m["quem"] not in rotulos:
            continue
        origem = f" (origem {m['origem_sessao']})" if m.get("origem_sessao") else ""
        linha = f"- {rotulos[m['quem']]}{origem}: {trecho(m['texto'], 1000)}"
        if total + len(linha) + 1 > 6000 - len(aviso):
            cortado = True
            break
        linhas.insert(0, linha)
        total += len(linha) + 1
    return (aviso if cortado else "") + ("\n".join(linhas) or "- nada")
