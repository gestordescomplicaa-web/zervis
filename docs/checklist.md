# Checklist funcional do Zé

Cada coisa do Zé, área por área, com base no painel. Uma área só fica **Pronta** quando cada item
foi usado de verdade (não só nos testes automáticos) e o conceito está claro em uma frase
(`docs/conceitos.md`). Trabalhamos uma área por vez, até fechar, antes de abrir a próxima.

Auditorias em andamento: `docs/auditoria/`.

Legenda: ✅ usado de verdade e funciona · 🟡 só nos testes automáticos · ❌ defeito ou lacuna
conhecida · ⬜ ainda não verificado.

Última revisão: 13/10/2026.

## 1. Voz e comunicação — **Pronta** (13/10/2026, `docs/auditoria/01-voz-e-comunicacao.md`)

Conceito: o canal da conversa (ouvir pelo Deepgram, falar pelo Piper). Não guarda nada, só leva e
traz. Três escolhas: Ativação, Escuta e Modo de fala.

- ✅ "Ei Zé" universal, sem gravar a voz de ninguém; ignora silêncio e som de fundo
- ✅ Só o botão; Falar (segurar e soltar); Ao vivo no PC e no celular
- ✅ Voz pelo celular (navegador, WebSocket), em casa e no 4G, com reconexão
- ✅ Escuta: Sempre (qualquer Linux) e Com a janela aberta (Hyprland)
- ✅ Modo de fala: Silencioso (não fala nem ouve), Normal, Mãos livres; Alt+M
- ✅ Conversa no painel: o fio do dia e o pedido escrito
- ✅ Central de avisos (ADR 0029): o Zé narra as sessões, por prioridade; "próximo", "repete"
- ✅ O Zé tem a vez: vídeo e música pausam enquanto ele ouve ou fala
- 🟡 Regras de fala (ADR 0027): uma repetição e sem duplicados, só nos testes automáticos
- Em aberto: cancelamento de eco (decidir com o uso); latência da conversa simples (~3 s)

## 2. Cérebro e contas — **Pronta** (13/10/2026, `docs/auditoria/02-cerebro-e-contas.md`)

Conceito: o cérebro é o Zé em si (entende, decide, usa as ferramentas do Zé), com as Respostas
rápidas como atalho para conversa simples; as sessões de código são outra coisa (área 5).

- ✅ Cérebro Claude e Codex; o modelo se escolhe no painel, com a versão (Opus 5.5, Sonnet 5.5…)
- ✅ Teste do modelo antes de trocar (o Fable 5.1 sem créditos é recusado com a razão)
- ✅ Respostas rápidas: ligar e desligar, motor e modelo da lista
- ✅ Contas: trocar a conta em uso atualiza os modelos
- ⬜ OmniRoute (endereço e chave de quem usa): feito, falta o teste com uma chave real
- Não se aplica aqui: chave de API da Anthropic (a pessoa usa a assinatura)

## 3. Memória — **Pronta** (13/10/2026, `docs/auditoria/03-memoria.md`)

Conceito: memória curta (o que vale agora, em toda conversa), memória longa (o histórico, buscado
quando precisa), memória dos projetos (ai-memory, por sessão) e sugestões (só com aprovação).

- ✅ Adicionar e remover pelo painel; vale já no próximo pedido, e o que saiu deixa de valer
- ✅ Guardar pela voz
- ✅ Memória longa: "o que conversamos ontem?"
- ✅ Sugestões no painel, com Aprovar e Descartar
- ✅ Memória dos projetos (ai-memory) com estado e páginas na página

## 4. Skills — **Pronta** (13/10/2026, `docs/auditoria/04-skills.md`)

Conceito: um procedimento do seu jeito, lido antes de agir. Skills do Zé (página Skills) valem
para o cérebro; só as marcadas "Também nas sessões de código" vão para os agentes. Skills dos
agentes (Claude Code, Codex) aparecem na página só para leitura.

- ✅ Criar pelo formulário e pela voz; o Zé lê a skill antes de agir
- ✅ Editar, desligar e excluir valem já na conversa em andamento
- ✅ Só as marcadas chegam às sessões, como skill nativa do agente (`.claude/skills`,
  `.agents/skills`), mesmo ao retomar a conversa
- ✅ Skills dos agentes visíveis na página
- Ideia para depois: "Instalar skill" a partir de um link do GitHub ou de um registro
  (anthropics/skills, skills.sh), mostrando o conteúdo, verificando e pedindo aprovação; nunca
  rodar script sozinho.

## 5. Sessões — **Pronta** (14/10/2026, `docs/auditoria/05-sessoes.md`)

Conceito: um agente de código (Claude Code ou Codex) numa pasta de projeto, com a conversa dele;
cada sessão escolhe agente, conta e modelo. O cérebro delega; as sessões programam.

- ✅ Criar (pasta existente e projeto novo); Claude e Codex; trocar de agente com a conversa
- ✅ Modelo da sessão no cabeçalho, com a versão
- ✅ Anexos, Arquivos e Mencionar
- ✅ Cópia isolada com Aplicar e Descartar
- ✅ Pedido por voz; aviso de fim e de aprovação (Central de avisos)
- ✅ Tarefa interrompida por reinício: avisada e retomada de onde parou
- 🟡 No máximo 3 trabalhando (testes automáticos)
- Para depois: agentes fora do processo do Zé (nem serem interrompidos)

Ideias para avaliar nesta área (do Botloft, github.com/httpsphl/botloft; licença FSL-1.1, que não
permite copiar código para o Zé: só ideias, escritas do zero):
- tarefa com prazo e resultado (`complete_task`), e fila por sessão em vez de recusar quando ocupada;
- sessões mandando mensagens e tarefas umas às outras, com o Zé no meio e só com permissão;
- o cérebro sugerindo uma sessão nova (papel, modelo pelo custo do trabalho) e a pessoa aprovando;
- perguntas das sessões guardadas numa caixa, respondidas quando a pessoa puder.

## 6. Foco

Conceito: no que **você** está. No máximo três frentes ativas, cada uma com o próximo passo.

- ⬜ "Comecei…" cria a frente; próximo passo; Pausar, Retomar, Concluir
- ⬜ Virar frente (a partir de uma sessão ou conversa)
- ⬜ "Onde eu estava?" e o bom dia com o Foco

## 7. Automações

Conceito: o que roda sozinho, e quando. Lembrete (só fala) ou rotina (faz).

- ⬜ "Me lembra amanhã às nove de…" cria e o Zé avisa na hora
- ⬜ Rotina (pergunta ao Zé ou manda tarefa a uma sessão)
- ⬜ Ligar e desligar no painel

## 8. Conectores

Conceito: a porta do Zé para outros sistemas, por MCP. Encanamento, não um conceito de uso.

- ⬜ Adicionar local e remoto; guardar segredo
- ⬜ Ferramentas: ver, e para cada uma livre, com aprovação ou bloqueada
- ⬜ Aplicar agora (o cérebro passa a usar)

Ideias para avaliar nesta área:
- **Navegador** (Playwright MCP num Chromium separado; o código existe, nunca foi ligado nesta
  instalação): ligar, testar e medir o gasto de tokens antes de decidir.
- **Aprender uma vez, repetir sem modelo:** na primeira vez o Zé faz o fluxo no site com o modelo e
  grava os passos como roteiro; nas próximas, repete o roteiro sem gastar tokens e só chama o
  modelo se a tela mudar. Bom para sistemas legados sem API.
- **Visão da tela** (ver um print e entender onde está cada coisa): depois, é bem mais caro.

## 9. Acesso pelo celular

Conceito: o Zé no navegador do celular, em casa ou fora, com senha e autenticador.

- ✅ Senha, código do autenticador, bloqueio por tentativas
- ✅ Túnel (Cloudflare) com QR; num serviço próprio, o endereço só muda quando o computador
  reinicia (antes, a cada reinício do Zé, e o celular pedia login de novo)
- ⬜ Endereço fixo (domínio próprio no Cloudflare): para quem tem domínio
- ✅ Aviso de aparelho novo; lista de aparelhos; desconectar
- ⬜ Ícone na tela inicial (PWA)
- ❌ A seção "Rede privada (Tailscale)" continua no painel, mas o caminho escolhido é o túnel.
  Decidir: tirar ou deixar como alternativa documentada.

## 10. Imersão

- ✅ Holograma no PC; desliga ao sair da tela
- ⬜ Mãos (modo imersivo) movendo a tela
- ⬜ Holograma no celular reagindo à conversa

## 11. Atividade

- ✅ Execuções, negadas, falhas, não entendi, pedidos; filtros
- ✅ Registro técnico
- 🟡 Reinício sem falsas falhas (corrigido em 13/10/2026)

## 12. Autodesenvolvimento

- ✅ Estado de manutenção em laranja; entrar e sair pelo painel
- ✅ Diagnosticar, propor, implementar na cópia
- ✅ Aplicar, volta automática, descartar, conflito
- 🟡 Aplicar espera as outras sessões; só do próprio PC
- ⬜ Pedido por voz no modo manutenção

## 13. Perfil, configuração inicial e painel

- ⬜ Configuração inicial do zero (perfil, acesso ao Claude, reconhecimento de fala)
- ✅ Perfil: nome, sobre você, fuso
- ⬜ Painel no celular (menu, sessões, holograma)
- 🟡 Painel recarrega sozinho depois de um reinício
