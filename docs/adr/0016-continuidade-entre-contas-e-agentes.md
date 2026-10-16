# 0016 — Continuidade entre contas e agentes, com o ai-memory embutido

- Data: 10/10/2026
- Status: **Aceito** (pedido do usuário: "continuar de outra sessão do Codex ou do Claude, o mesmo
  projeto, selecionando as contas"; o ai-memory embutido no Zé)

## Contexto
No Orca, cada conta do Codex é uma pasta (`CODEX_HOME`) e trocar de conta no meio de uma sessão
não continua: a sessão nativa fica na pasta da conta antiga e o caminho é recomeçar. O ai-memory
(akitaonrails/ai-memory, MIT) resolve a troca de agente com um "workstream": cada agente mantém a
sua sessão nativa e um registro portátil da parte visível leva ao próximo só o que mudou.

## Testes (10/10/2026, Codex 0.160.1, Claude Code 2.1.291)
| Teste | Resultado |
|---|---|
| Claude: criar sessão e retomar (`claude -p --resume`) | lembrou a palavra secreta |
| Codex: criar sessão e retomar (`codex exec resume`) | lembrou |
| Codex: copiar a sessão (`sessions/AAAA/MM/DD/rollout-*.jsonl`) para outra `CODEX_HOME`, mesma conta | retomou |
| Codex: sessão criada na conta Plus, com raciocínio criptografado, retomada na conta gratuita | **retomou e lembrou**; só avisou da troca de modelo (o plano gratuito usa outro) |
| Codex: entrar numa segunda conta derrubou a primeira? | não |
| Claude: copiar a sessão (`projects/<pasta>/<id>.jsonl`) para outro `CLAUDE_CONFIG_DIR` | retomou (uma conta só disponível; o mecanismo é o mesmo) |

## Decisão
1. **Conta = pasta de login do próprio agente** (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`), criada pelo
   Zé e com o login feito pela pessoa no agente. A pasta padrão (`~/.claude`, `~/.codex`) é a
   primeira conta.
2. **Trocar de conta no mesmo agente** copia a sessão nativa para a pasta da conta nova e retoma
   com o resume do próprio agente: continuidade completa, sem resumo.
3. **Trocar de agente** retoma a sessão nativa daquele agente nesse trabalho, se houver, e entrega
   o que aconteceu desde a última vez dele (o registro da sessão no Zé e o estado do git); sem
   sessão anterior, começa com o resumo e as mensagens recentes. Mesmo padrão do ai-memory.
4. **O ai-memory vem embutido:** o Zé baixa o binário oficial fixado por versão e SHA-256 (como a
   voz) e o roda como serviço filho; as sessões do Zé alimentam o ai-memory e ganham a busca dele.
   Se a máquina já tiver o ai-memory rodando, o Zé usa esse.
5. A troca automática foi autorizada em 15/10/2026 para contas cadastradas do mesmo agente,
   preservando modelo e esforço. Sem configuração compatível, avisa e aguarda escolha.
   Ver os critérios abaixo; o plano serve para ordenar, não para presumir saldo.

## Fallback de contas (15/10/2026)

Pedido: continuar sessões comuns e a central de autodesenvolvimento quando uma conta atingir
limite, priorizando Pro, Plus e Gratuita. A pessoa escolheu explicitamente preservar modelo e
esforço; trocar de modelo ou de agente exige escolha manual.

- O aviso do terminal dispara uma conferência do registro nativo. Texto de resposta ou ferramenta
  não muda o estado nem exibe alerta de saldo. O bloqueio precisa ter timestamp posterior à
  abertura do processo atual; um erro antigo redesenhado é ignorado. No Codex, conferem-se o
  erro ou a indicação explícita de bloqueio, o último pedido,
  o modelo e o esforço do turno. No Claude, o erro estruturado e o modelo da transcrição; esforço
  fixado por `CLAUDE_CODE_EFFORT_LEVEL`. O esforço salvo em configurações pode diferir de uma
  escolha feita só para a conversa, portanto não é usado como prova. Sem evidência suficiente,
  pausa com uma mensagem. Não adivinha padrões, equivalência de modelos nem esforço.
- O catálogo local de cada conta Codex precisa oferecer exatamente o modelo e o esforço.
  O plano é lido pelo mecanismo existente de contas; desconhecidos ficam depois dos planos
  reconhecidos, mantendo a ordem de cadastro entre iguais. Login existente e catálogo em cache
  não garantem saldo nem acesso atual: a tentativa real pode ser recusada e encerrar a retomada.
- Cada conta esgotada fica fora das alternativas por uma hora, em SQLite, inclusive entre
  sessões e reinícios. Para o mesmo pedido, contas já tentadas não são reutilizadas, mesmo
  depois dessa hora. Novo pedido reinicia a cadeia; troca manual continua disponível.
- O agente anterior encerra antes da abertura do próximo. A conversa nativa atual substitui
  atomicamente uma cópia antiga no destino, com permissão privada. Pasta, branch, ID da sessão
  e pedidos da manutenção continuam os mesmos. A mensagem de retomada exige conferir o que já
  foi feito e executar apenas o restante; isso não oferece garantia de execução única de efeitos
  externos já realizados pelo modelo.
- Interromper, digitar, enviar ou trocar manualmente cancela a tentativa pendente. Atualização,
  unificação e exclusão impedem a retomada. Após reiniciar o Zérvis, não há envio espontâneo:
  a recuperação de tarefas interrompidas continua dependendo da pessoa.
- Troca registrada na Atividade e no histórico, com aviso próprio, sem anunciar conclusão.
  O painel acompanha a geração do terminal e reinicia o cursor de leitura após a troca.
- Correção de 16/10/2026: o limite é vinculado à conta que o apresentou. Marcas e bloqueios
  legados sem identificação/prova deixam de autorizar alerta ou exclusão de alternativas.
  Escolher conta no seletor não reenvia tarefas; o botão Continuar é uma ação separada,
  validada e serializada na API. Desligar manutenção impede encaminhar comandos enfileirados.

Referências: [contexto e erros nativos do Codex](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/protocol.rs),
[modelo e esforço do Claude Code](https://code.claude.com/docs/en/model-config).
Os adaptadores dependem dos formatos das versões instaladas. Formato desconhecido interrompe
a automação. Não há consulta de cobrança nem mudança de plano ou de credenciais.

## Implementado e conferido (12/10/2026)
Uma sessão real do Zé: Codex na conta Plus cria o arquivo e guarda uma palavra-chave; troca para o
Codex na conta gratuita (a conversa nativa é copiada e retomada inteira); troca para o Claude
(começa pela passagem: objetivo, mensagens desde a última vez dele e o estado do git); volta ao
Codex gratuito (retoma a conversa dele e recebe só o que o Claude fez). Nas quatro rodadas o
agente sabia a palavra-chave e o que os outros fizeram. A troca fica no painel (botão Trocar da
sessão) e no cérebro (`sessao_trocar`, com aprovação); quando a conta bate o limite, o Zé avisa e
oferece trocar.

## Precisão da passagem e memória comum (15/10/2026)

A continuidade imediata continua no Zérvis: sessão nativa, cópia e registros locais. O último
pedido registrado e a resposta correspondente substituem o primeiro pedido como referência
da passagem. O relato do agente não comprova entrega, aprovação ou testes; estado da sessão,
interrupção, limite da conta e Git são apresentados separadamente. Pedidos importados de
outras sessões não substituem o trabalho atual da central.

O pedido e a resposta recebem até oito mil caracteres cada na passagem; o delta recente é
limitado a seis mil. Cortes explícitos preservam início e fim dos trechos. O registro local
conserva as mensagens completas, sem aplicar esses limites de apresentação. Um arquivo
privado e substituído atomicamente, na pasta de dados da própria sessão, contém todo o histórico
registrado e as origens importadas para consulta. Não inclui raciocínio interno nem restaura
conteúdo que já havia sido cortado na captura original. Histórico continua sendo dado;
instruções e aprovações atuais têm precedência.

Novas conversas e passagens entre agentes recebem orientação de busca pelo mesmo binário e
raiz de dados do ai-memory,
no diretório original do projeto, respeitando seu marcador. A busca de conhecimento duradouro
é feita quando necessária; indisponibilidade da memória não impede a passagem local.

Os hooks do Claude e os eventos de turnos concluídos do Codex usam a estratégia `repo-root`
para reunir as cópias do mesmo projeto. A captura do Codex usa o comando nativo `hook`, com sua
política de captura, sanitização e spool. Publicação em fila limitada, fora da trava e da fala de
conclusão. O turno produz `user-prompt-submit` e `stop`; fechar o agente produz `session-end`,
permitindo a consolidação configurada no ai-memory. Não se simula `session-start`, que poderia
consumir um handoff de outra sessão. Capturar o texto da resposta requer também a opção
`capture_assistant` do servidor; a integração respeita essa política e não a altera.
Não se migram os registros antigos nem se alteram configurações globais das contas.

Referência do contrato nativo e das políticas: [ai-memory, instalação e captura](https://github.com/akitaonrails/ai-memory/blob/v2.6.3/docs/install.md).
