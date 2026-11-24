"""Os formatos editoriais dos vídeos (ADR 0113): o esqueleto que o diretor escolhe antes de
escrever, para que dois vídeos da mesma marca não tenham o mesmo roteiro.

Cada formato é um jeito comprovado de vídeo curto: como ele abre, como anda e como fecha. O
diretor escolhe um que os últimos vídeos não usaram (a memória do ADR 0111 leva o formato de cada
um) e o gancho segue uma das técnicas de abertura. Nada aqui é animação: é o roteiro.
"""

FORMATOS: dict[str, str] = {
    "caso": "A história de uma empresa, em quatro tempos claros. (1) O problema: um personagem "
    'com nome, negócio e cidade ("pensa na Márcia, que tem uma clínica de estética em Goiânia"), '
    "o problema acontecendo no dia a dia dela e quanto custa, na conta feita na tela com números "
    'de exemplo. (2) A solução, de quem fala: "na clínica da Márcia, a gente faria três coisas", '
    'e as três, concretas, num fluxo animado ("conexao" ou "hub", com os logos das '
    "ferramentas). (3) O resultado: como fica o dia dela depois. (4) A ponte: o mesmo problema "
    "em outros negócios, de passagem "
    '("loja, oficina, escritório: quem cobra cliente na mão perde igual"). Depois, o convite. '
    "É exemplo: a solução é o que a gente faria, nunca um cliente atendido; com um caso real do "
    'material, "a gente fez".',
    "cena": "No meio da ação: abre numa cena que o público vive (o dono fechando o caixa na "
    "planilha às onze da noite, o boleto vencido que ninguém cobrou), sem explicar nada; a "
    "tensão sobe em 2 cortes; a virada mostra a automação resolvendo, em uso; o convite. É um "
    "exemplo, nunca um caso real.",
    "contra": "Contra o senso comum: abre com uma afirmação que o público discorda de cara "
    '("contratar mais gente não resolve o seu financeiro"); a prova numa imagem forte; o porquê '
    "numa analogia; o convite.",
    "resultado": "O resultado primeiro: abre já no fim (o relatório do mês pronto na segunda de "
    "manhã, a nota emitida sozinha, a agenda cheia) e só depois mostra como chegou lá, em "
    "cortes rápidos do fluxo acontecendo, com os logos das ferramentas; o convite.",
    "erro": "O erro que todo mundo comete: o gancho aponta o erro do público (sem ofender); a "
    "consequência numa cena forte; o jeito certo numa imagem só, mostrado em uso; o convite.",
    "pov": 'POV: o gancho põe quem assiste numa cena que ele vive ("POV: você é dono de..."), '
    "de preferência com uma foto; a situação aperta em 2 cenas; a virada com a solução; o convite.",
    "mito": "Mito ou verdade: o gancho afirma uma crença comum do público; a resposta seca "
    '("mito") numa cena de impacto; a verdade com uma analogia visual; o convite.',
    "dia": 'Um dia com e sem: cada cena é um horário ("oito da manhã", "meio-dia", "onze da '
    'noite"), em cortes rápidos, mostrando o problema; depois a mesma rotina resolvida; o convite.',
    "comparacao": "Com e sem: a mesma situação dos dois jeitos, alternando em cortes (sem, com, "
    "sem, com), até a diferença ficar óbvia; o convite.",
    "segredo": "O que ninguém te conta: o gancho abre uma curiosidade e não responde; cada cena "
    "chega mais perto; a revelação perto do fim, com a cena mais forte; o convite.",
}

GANCHOS = (
    "a cena no meio da ação (o problema acontecendo agora, com hora e lugar)",
    "a perda invisível (o que a pessoa perde sem perceber)",
    "a afirmação contra o senso comum",
    'a provocação direta ao público ("se você é dono de loja, para de...")',
    "o resultado antes da explicação",
    "o POV (quem assiste dentro da cena)",
    "a curiosidade sem resposta",
)

# fraco → forte: o que o diretor vê para calibrar (sem número inventado)
EXEMPLOS = (
    ("Quanto custa uma hora perdida na sua empresa?",
     "Seu financeiro passa a segunda inteira conferindo extrato."),
    ("Por que seu concorrente vende mais que você?",
     "Seu concorrente responde na hora. Você, amanhã de manhã."),
    ("Você sabia que dá pra automatizar a cobrança?",
     "Tem boleto vencido há vinte dias que ninguém cobrou."),
)  # fmt: skip

# Os processos de uma empresa que a automação e a IA resolvem: o tema do vídeo pode ser qualquer
# um (a marca atende todos os setores), e o diretor varia entre eles.
PROCESSOS: dict[str, str] = {
    "atendimento": "atendimento e vendas (responder, qualificar, follow-up, orçamento)",
    "financeiro": "financeiro (cobrança, conciliação do extrato, contas a pagar, fluxo de caixa)",
    "fiscal": "fiscal e documentos (nota fiscal, contratos, propostas)",
    "operacao": "operação e estoque (pedido, reposição, ordem de serviço, agenda da equipe)",
    "pessoas": "pessoas (admissão, ponto, escala, treinamento)",
    "gestao": "gestão (relatórios e indicadores prontos, reuniões, tarefas da equipe)",
    "posvenda": "pós-venda (pesquisa, recompra, indicação, avaliação no Google)",
}


VALOR = (
    "## O que o vídeo entrega (o valor)\n"
    "Quem assiste é dono de negócio, gestor, e foge de vídeo com cara de anúncio. O vídeo tem de "
    "agregar: ensinar uma coisa que serve mesmo para quem nunca vai contratar (um jeito de "
    "enxergar o problema, uma conta que ele faz no negócio dele, o que dá para automatizar e por "
    "quê). Mostre o mecanismo (o que a automação faz, em que momento, com qual ferramenta) e os "
    "motivos da vantagem naquele negócio (tempo, dinheiro, cliente que não se perde, erro que "
    "some). **A solução é de quem fala:** depois do problema, diga o que a gente faz para "
    "resolver, em 2 ou 3 ações concretas (o que entra, onde, com qual ferramenta) e o resultado; "
    "quem assiste tem de sair sabendo como o problema se resolve e que quem fala sabe resolver. "
    "**A ponte:** a marca atende qualquer ramo, então a história é um exemplo do problema, não "
    "do nicho; antes do convite, uma cena mostra o mesmo problema em outros negócios. Nada de "
    'promessa vaga ("aumente suas vendas") nem de tom de vendedor ou de guru: é '
    "um dono de negócio que entende do assunto conversando com outro, no jeito brasileiro "
    "(direto, próximo, com exemplo do dia a dia daqui: WhatsApp, Pix, boleto, nota fiscal, "
    "o sistema da loja, a pessoa que faz tudo sozinha), sem jargão.\n"
    "**A automação usa o que a empresa já tem:** conversa com o sistema dela (o ERP, o CRM, o "
    "sistema da clínica, o e-commerce, o banco, o emissor de nota) pela integração, lendo e "
    "gravando lá, e usa IA onde há texto, voz, documento ou decisão (ler um PDF, entender um "
    "áudio, separar pedidos, responder). Planilha é um caso entre muitos, não o padrão: prefira "
    'o sistema da empresa, num nó próprio do fluxo ("server" ou "database", rótulo "Seu '
    'sistema").\n'
    "O tema pode ser qualquer processo da empresa, não só atendimento: "
    + "; ".join(f"{k}: {v}" for k, v in PROCESSOS.items())
    + '. Fique no processo do tema (o campo "processo" do JSON, a chave dele) e diga o assunto '
    'em 3 a 6 palavras (o campo "assunto": "proposta comercial atrasada"); os exemplos acima '
    "são só calibragem.\n"
    "**O fluxo é animado:** sempre que o vídeo explica como um processo anda (o que acontece "
    'depois do quê), mostre com "conexao" (as etapas ligadas, os dados correndo de uma para a '
    'outra) ou "hub", com o logo de cada ferramenta no nó ("logo: whatsapp", "logo: mercado '
    'pago"); foto é para o problema e o dia a dia, nunca para o fluxo.\n'
)


def secao() -> str:
    """O trecho do pedido ao diretor: os formatos, o gancho e o valor."""
    lista = "\n".join(f"- {nome}: {como}" for nome, como in FORMATOS.items())
    exemplos = "\n".join(f'- fraco: "{a}" → forte: "{b}"' for a, b in EXEMPLOS)
    return (
        "## Formato e gancho\n"
        'Escolha um formato (o campo "formato" do JSON) e siga o esqueleto dele:\n'
        f"{lista}\n"
        "**O gancho decide o vídeo: o primeiro segundo e meio para o dedo ou perde a pessoa.** "
        'Escreva 5 ganchos diferentes no campo "ganchos", cada um com uma técnica, e abra o vídeo '
        "com o mais forte (o que dá mais vontade de ver o resto). Um gancho forte é específico "
        "(um negócio, uma hora, uma cena, uma perda concreta), cria tensão ou contradição, abre "
        "uma pergunta que só o fim responde. **O primeiro quadro é imagem e frase juntas:** o "
        '"gancho" com "foto" (a cena do problema em foto, a frase de impacto por cima, grande). '
        "Muita gente assiste sem som: a frase na tela tem de prender sozinha. Até 8 palavras. "
        f"Técnicas: {'; '.join(GANCHOS)}.\n"
        'Nunca abra com pergunta genérica ("Por que...?", "Quanto custa...?", "Você '
        'sabia...?"), saudação, nome da marca, "neste vídeo" ou "fica até o fim". Se o último '
        "vídeo abriu com pergunta, este abre com uma afirmação ou uma cena.\n"
        f"Para calibrar:\n{exemplos}\n" + VALOR
    )


# As linhas editoriais (ADR 0116): para quem o vídeo fala e o que ele precisa ter.
LINHAS: dict[str, str] = {
    "empresarios": "Para donos de empresa. Fale do negócio de quem assiste, não da tecnologia: a "
    "dor concreta (tempo, dinheiro, cliente perdido), o que ela custa, a solução com automação e "
    "IA mostrada em uso, um exemplo do dia a dia dele e a entrega. Nada de jargão (API, LLM, "
    "prompt, token): o resultado. As ferramentas aparecem como logo, de passagem.",
    "ferramenta": "Sobre uma ferramenta. O gancho promete o que ela faz por quem assiste; mostre "
    'o logo dela ("logo: <ferramenta>") e o site ("site: <endereço>"); de 3 a 5 usos práticos, '
    "um por cena (item com o logo ou o print); para quem serve; preço ou plano grátis só se "
    "estiver no material. A entrega é a conversa: como essa ferramenta se aplicaria no negócio "
    "de quem comenta (nunca o link nem um tutorial técnico).",
}


def secao_entrega(linha: str = "", entrega: str = "", palavra: str = "") -> str:
    """A linha do vídeo e o convite do fim (ADR 0120): o comentário vira conversa no direct.

    Qualquer comentário já ganha a resposta e a abertura no direct (ADR 0118), então o vídeo não
    precisa de palavra-chave nem de brinde: pede um comentário sobre o negócio de quem assiste
    (o que já dá contexto para o diagnóstico) e promete a conversa. Brinde técnico (prompt,
    código, passo a passo) atrai público técnico; o público é o empresário."""
    linha_txt = LINHAS.get(linha) or (
        "Escolha a linha pelo tema: " + " | ".join(f"{k}: {v}" for k, v in LINHAS.items())
    )
    entrega_txt = (
        f"O que quem comentar recebe: {entrega}. Use exatamente isso, sem acrescentar nada."
        if entrega
        else "O que quem comentar recebe é uma conversa no direct: você entende o negócio da "
        'pessoa e mostra o que daria para automatizar nele ("eu te chamo no direct e te mostro '
        'como automatizaria a sua empresa"). Nunca prometa brinde técnico (prompt, código, '
        "checklist de ferramenta, passo a passo): atrai curioso técnico, não empresário. Nunca "
        "invente preço, bônus ou prazo da oferta."
    )
    palavra_txt = (
        f'O que comentar: "{palavra}".'
        if palavra
        else "O que comentar é a palavra do problema que o vídeo resolveu (não o ramo de quem "
        'assiste, que já pode ser outro), curta, até 16 letras: "COBRANÇA", "ORÇAMENTO", '
        '"ESTOQUE", "RELATÓRIO", "AGENDA". O fecho fala com qualquer negócio: "comenta '
        'COBRANÇA que eu te mostro como isso ficaria na sua empresa". Qualquer comentário vale; '
        "a palavra só dá o contexto da conversa."
    )
    return (
        "## Linha e convite (o motivo de comentar)\n"
        f"{linha_txt}\n"
        'O vídeo termina com o fecho "comenta". '
        f'{entrega_txt} {palavra_txt} Não anuncie o convite antes do fim ("no fim eu te '
        'digo", "fica até o fim"): a história é que segura. A fala do '
        "fecho diz o que comentar e o que a pessoa ganha; a legenda do Instagram repete. No JSON, "
        '"palavra" (o que comentar) e "entrega" (o que a pessoa ganha) no topo.\n'
    )
