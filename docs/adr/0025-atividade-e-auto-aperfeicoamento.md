# 0025 — Atividade e auto-aperfeiçoamento: o Zé registra o que fez e aprende com os tropeços

- Data: 13/10/2026
- Status: **Aceito**; camada 1 feita (pedido do usuário: o Zé desligou o PC com a frase exata, mas
  no dia seguinte não havia sinal do que ele tinha executado; "auditoria simples" de tudo, e um
  botão para o Zé se diagnosticar e acertar onde errou)

## Contexto
O registro técnico dizia "sistema_executar aprovada", sem o quê. A conversa guarda o que foi dito,
não o que foi feito. Já havia uma semente herdada: `evidencias.jsonl` (não entendi, transcrição
vazia, falha do cérebro) e a "rodada de melhoria", que pede propostas à sessão de manutenção.

## Decisão
1. **Camada 1, a atividade** (`jarvis/atividade.py`, `<estado>/atividade.jsonl`, 0600, só leitura):
   execuções de ferramentas (o comando, como foi autorizada — livre, aprovada, frase exata —, a
   origem — voz, voz remota, texto — e o resultado), negadas, falhas (ferramenta, transcrição,
   cérebro, voz do navegador, túnel), "não entendi" com o que foi ouvido, correções da pessoa e os
   pedidos atendidos (o que deu certo também conta, para comparar). Segredos cobertos, textos
   cortados, arquivo girado aos 5 MB. Toda ferramenta do Zé passa por um único registro
   (`ferramentas.auditada`); a autorização vem do cérebro, na hora da permissão.
2. **Página Atividade** no painel: execuções e sinais (contagem de 7 dias, filtros) e o registro
   técnico do serviço (erros, avisos, tudo; "Copiar diagnóstico"). Carregada sob demanda.
3. **Camada 2, "Diagnosticar"** (a seguir): o Zé lê a atividade e o registro técnico, agrupa por
   causa e propõe: *aprender* (sinônimo, memória, skill: um clique), *ajustar* (configuração) ou
   *corrigir código*. É a rodada de melhoria com dados mais ricos.
4. **Camada 3** (depois): diagnóstico periódico e medida de melhora (o mesmo erro diminuiu?).
5. **Trava:** o Zé **nunca altera o próprio código sozinho**. Correção de código vai para uma cópia
   isolada (modo manutenção), passa no `make check` e só entra com a aprovação da pessoa.
6. **Suspender** entra no catálogo (`systemctl suspend`, confirmação falada): o pedido que, sem
   ele, virou "desligar".

## Consequências
- Tudo o que o Zé executa fica visível; tentativas negadas também.
- O diagnóstico tem matéria-prima concreta (o que foi ouvido, o que falhou, o que deu certo).
- Os registros ficam só no computador da pessoa, como a conversa.
