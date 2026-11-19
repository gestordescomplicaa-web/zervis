"""Os formatos editoriais dos vídeos (ADR 0113): o esqueleto que o diretor escolhe antes de
escrever, para que dois vídeos da mesma marca não tenham o mesmo roteiro.

Cada formato é um jeito comprovado de vídeo curto: como ele abre, como anda e como fecha. O
diretor escolhe um que os últimos vídeos não usaram (a memória do ADR 0111 leva o formato de cada
um) e o gancho segue uma das técnicas de abertura. Nada aqui é animação: é o roteiro.
"""

FORMATOS: dict[str, str] = {
    "erro": "O erro que todo mundo comete: o gancho aponta o erro do público (sem ofender); "
    "a consequência em uma cena forte; o jeito certo em 2 ou 3 batidas rápidas; o convite.",
    "lista": 'Três sinais (ou três coisas): o gancho promete a lista ("3 sinais de que..."); '
    "uma cena por item, curtas, com o número na tela; o terceiro é o mais forte; o convite.",
    "pov": 'POV: o gancho põe quem assiste numa cena que ele vive ("POV: você é dono de..."), '
    "de preferência com uma foto; a situação aperta em 2 cenas; a virada com a solução; o convite.",
    "mito": "Mito ou verdade: o gancho afirma uma crença comum do público; a resposta seca "
    '("mito") numa cena de impacto; a verdade com uma analogia visual; o convite.',
    "dia": 'Um dia com e sem: cada cena é um horário ("oito da manhã", "meio-dia", "onze da '
    'noite"), em cortes rápidos, mostrando o problema; depois a mesma rotina resolvida; o convite.',
    "comparacao": "Com e sem: a mesma situação dos dois jeitos, alternando em cortes (sem, com, "
    "sem, com), até a diferença ficar óbvia; o convite.",
    "pergunta": "A pergunta do cliente: o gancho é a pergunta que o público faz de verdade "
    '("dá pra...?"); a resposta direta logo na segunda cena; o como em 2 ou 3 batidas; o convite.',
    "segredo": "O que ninguém te conta: o gancho abre uma curiosidade e não responde; cada cena "
    "chega mais perto; a revelação perto do fim, com a cena mais forte; o convite.",
}

GANCHOS = (
    "a pergunta que dói (o problema do público, em uma frase)",
    "o número (só se vier do material, com a fonte)",
    "a provocação (o erro ou a crença do público)",
    "o POV (quem assiste dentro da cena)",
    "a curiosidade sem resposta (o que ninguém te conta)",
    "a afirmação contra o senso comum",
)


def secao() -> str:
    """O trecho do pedido ao diretor: os formatos e as técnicas de gancho."""
    formatos = "\n".join(f"- {nome}: {como}" for nome, como in FORMATOS.items())
    ganchos = "; ".join(GANCHOS)
    return (
        "## Formato e gancho\n"
        'Escolha um formato (o campo "formato" do JSON) e siga o esqueleto dele:\n'
        f"{formatos}\n"
        f"O gancho usa uma destas técnicas: {ganchos}. A primeira frase tem até 8 palavras e "
        "prende em um segundo e meio. Nunca abra com saudação, com o nome da marca nem com "
        '"você sabia". O vídeo pode abrir com texto (gancho), com uma foto cheia, com um '
        "ícone ou com um número; o que importa é parar o dedo de quem rola.\n"
    )
