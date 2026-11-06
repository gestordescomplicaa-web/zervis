# 0069 — A fila durável das automações: um reinício no meio não perde nem repete às cegas

- Data: 06/11/2026
- Status: **Aceito** (testado no `make check` com o Zé morto por SIGKILL no meio de uma pergunta
  e de uma ligação agendada).

## Contexto

As automações já ficavam em SQLite, mas não cada vez que uma delas rodava. Com o Zé morto no
meio de uma execução:

- a ligação agendada era marcada "ok" antes de discar: caindo entre as duas coisas, sumia sem
  aviso, e uma ligação que não saiu também aparecia como "ok";
- a pergunta era refeita ao subir sem nenhum controle de tentativas;
- o lembrete dependia de o aviso ser entregue antes da queda.

É o segundo item da Frente 1 do [plano de maturidade](../plano-maturidade.md).

## Decisão

1. **Vencer vira uma execução gravada** (`Jobs.disparar`, coleção `execucoes` no banco das
   automações), na mesma transação que avança a agenda: ou as duas ficam, ou nenhuma.
2. **Estados e tentativas:** pendente → rodando (uma tentativa a mais, gravada antes do efeito) →
   concluída ou falhou. A automação recebe o resultado (`ultimo_status`) só no fim; a ligação
   que não saiu fica como erro.
3. **Ao subir** (`retomar_ao_subir`), o que estava rodando segue pelo tipo:
   - lembrete: volta para a fila (repetir um lembrete é melhor que perdê-lo);
   - pergunta: volta para a fila até a segunda tentativa (só lê a internet, repetir é seguro);
     depois, interrompida;
   - ligação: interrompida, nunca refeita sozinha (pode ter sido feita, e ligar duas vezes não se
     desfaz). Vira aviso guardado na fila durável e registro na Atividade.
4. **Sem acúmulo:** uma automação que repete não dispara outra execução enquanto a anterior
   estiver aberta. O histórico guarda as últimas 200 execuções terminadas.
5. **As sessões de código não entram nesta fila:** o estado delas já é durável no banco das
   sessões, o agente continua no supervisor durante o reinício (ADR 0068) e a que perdeu o
   agente vira "interrompida", com a oferta de continuar.

## Consequências

- O aceite do plano ("matar o processo no meio de uma automação não a perde") está no
  `make check` (`tests/test_fila_duravel.py`).
- O painel e a voz continuam lendo `ultimo_status` como antes; a lista de execuções fica pronta
  para a Atividade mostrar o custo por tarefa (Frente 3).
