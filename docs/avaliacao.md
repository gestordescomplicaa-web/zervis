# Avaliação do cérebro

A bateria de avaliação mede o julgamento do Zé: dado um pedido e o que as ferramentas respondem,
ele usa as ferramentas certas, com os argumentos certos, e responde como deve? O cérebro é o de
verdade (a persona, o modelo e as descrições reais das ferramentas); só a execução das
ferramentas é simulada, e nada é criado, enviado nem apagado.

```sh
zervis avaliar                     # todos os cenários, uma vez cada
zervis avaliar --repetir 3         # cada cenário três vezes: a taxa de acerto
zervis avaliar lembrete nao-inventa  # só estes
zervis avaliar --assinatura        # pelo login da assinatura, não pela chave do painel
```

Gasta a conta do Claude de quem usa, por isso não roda no `make check` (lá, o motor é testado com
um cérebro falso, em `tests/test_avaliacao.py`). O relatório de cada rodada vai para
`~/.local/state/zervis/avaliacao/` e é comparado, cenário a cenário, com a última vez que cada um
rodou ("melhorou", "piorou"). Uma rodada em que o cérebro não respondeu (limite da conta, rede)
fica sem nota, e no limite da conta a bateria para.

## Escrever um cenário

Um arquivo em `zervis/avaliacao/cenarios/<nome>.toml`, de preferência nascido de um erro real
(diga qual, num comentário):

```toml
nome = "Quando o n8n voltar, não cria lembrete: o vigia avisa"
pedido = "O n8n do cliente João caiu. Quando ele voltar, me avisa."
aprovar = true          # a resposta falada a um pedido de aprovação (padrão: sim)

[ferramentas]           # o que cada ferramenta responde; as outras respondem {"ok": true}
conectores_listar = '[{"nome": "n8n-joao", "vigia": "fora do ar: sem resposta"}]'

[espera]
usa = ["conectores_listar"]                 # todas estas são chamadas
usa_alguma = ["sessao_ler", "sessao_enviar"]  # ao menos uma destas
nao_usa = ["automacao_lembrete"]            # nenhuma destas
entrada = { sessao_criar = ["landing"] }    # os argumentos têm todos os trechos
entrada_alguma = { sessao_enviar = ["s1", "loja"] }  # ...ao menos um dos trechos
entrada_em_alguma = { sessao_ler = ["s1"], sessao_enviar = ["s1"] }  # ao menos uma das chamadas
resposta = ["Jo[aã]o"]                      # expressões que a resposta tem (todas)
resposta_alguma = ["avis", "vigia"]         # ...ao menos uma
resposta_nao = ['(?<!não )\bmandei\b']      # ...nenhuma
pergunta = true                             # a resposta pergunta algo de volta
voz = true                                  # sem Markdown e até 80 palavras (padrão)
```

Os nomes das ferramentas são os curtos (`sessoes_listar`, não `mcp__jarvis__sessoes_listar`), e
um nome que não existe é recusado. Nada de dado real de ninguém nos cenários: pessoas, empresas e
endereços são inventados.

## Referência

20/10/2026, Claude Sonnet 5.5, 11 cenários, 2 vezes cada: **91%**. Falha estável: explicações
faladas longas demais (86 e 89 palavras, em dois parágrafos), em `voz-explicacao`.
