# 0068 — O supervisor das sessões: reiniciar o Zé não derruba os agentes

- Data: 06/11/2026
- Status: **Aceito** (testado no `make check` com o Zé morto por SIGKILL e na máquina, em
  06/11/2026: `systemctl --user restart zervis` com duas sessões abertas, Claude e Codex; os dois
  agentes continuaram com os mesmos processos e voltaram ao painel em 4,4 s, com a tela de antes.
  Falta repetir com uma sessão no meio de um pedido.)

## Contexto

Cada sessão de código era um pseudo-terminal filho do processo do Zé (ADR 0017). O systemd
encerra o grupo inteiro de um serviço ao reiniciá-lo, então reiniciar o Zé (uma atualização, um
ajuste, uma queda) encerrava todas as sessões: visto em 06/11/2026, com três sessões trabalhando.
É o primeiro item da Frente 1 do [plano de maturidade](../plano-maturidade.md).

## Decisão

1. **Os terminais ficam num processo próprio**, o supervisor (`zervis/oficina/supervisor.py`),
   que roda num serviço do usuário à parte (`zervis-oficina`, criado pelo próprio Zé com
   `systemd-run`, como o túnel). Sem o systemd do usuário (contêiner), um processo de sessão
   própria. Nada muda no instalador: o Zé sobe o supervisor quando não o encontra.
2. **O supervisor não sabe o que é uma sessão.** Guarda terminais por nome (o id da sessão) e
   devolve a saída a partir de uma posição, como o `Terminal` local. Eventos, conversa,
   permissões e avisos continuam no Zé. Protocolo: uma linha JSON por pedido e por resposta,
   num socket Unix em `<estado>/oficina.sock`, 0600, com a credencial do outro lado conferida
   (só o próprio usuário entra).
3. **O ambiente vai inteiro do Zé** a cada terminal aberto. O do supervisor não se mistura: ele
   subiu antes e não tem, por exemplo, a conta do Claude que o Zé aplicou depois.
4. **Ao subir, o Zé reencontra os terminais.** Cada um volta com a mesma tela (o espelho do
   buffer, então o painel não recomeça), a chave do gancho de permissão (o supervisor guarda só
   o resumo dela) e a posição no arquivo de eventos, guardada no banco das sessões a cada
   leitura. Assim, um turno que terminou enquanto o Zé estava fora é contado uma vez, com a
   resposta, e nenhum evento se repete. A saída antiga não volta para a conferência de limite:
   um aviso de limite de antes não dispara a troca de conta.
5. **Só vira "interrompida" a sessão cujo agente não continuou.**
6. **Falhar fechado é seguir funcionando:** sem o supervisor (não subiu, protocolo diferente com
   terminais abertos), o terminal abre no próprio Zé, como antes, com um aviso no registro.
7. **Versão do protocolo:** um supervisor de protocolo antigo sem terminais é trocado pelo novo;
   com terminais, continua até eles fecharem. O código do supervisor só muda quando ele sobe de
   novo, por isso o protocolo é pequeno de propósito.

## Consequências

- Reiniciar o Zé, inclusive pela atualização do autodesenvolvimento, mantém as sessões vivas.
  O aceite do plano (três sessões, de volta em menos de 10 s) está no `make check`
  (`tests/test_supervisor.py`).
- Parar de vez as sessões é parar o supervisor: `systemctl --user stop zervis-oficina`.
- Os terminais de login das contas (`cerebro/logins.py`) continuam no Zé: duram minutos e
  recomeçam sem perda.
- Não é uma sandbox: o supervisor roda como o mesmo usuário (Frente 2 do plano).
