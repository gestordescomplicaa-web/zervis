# Auditoria 4: Skills

Área 4 do checklist (`docs/checklist.md`). Um passo por vez.

**Conceito.** Skill é um **procedimento do seu jeito** ("como publico o site", "como faço o resumo
do dia"), escrito num `SKILL.md`, no mesmo formato do Claude Code, do Codex e do Hermes. Antes de
uma tarefa que uma skill cobre, quem vai fazer lê a skill e segue. Um fato é memória (área 3).

| | Onde fica | Quem usa |
|---|---|---|
| **Skills do Zé** | `<dados>/skills/` (página Skills: criar, editar, ligar, excluir) | o cérebro do Zé **e** as sessões de código |
| **Skills dos agentes** | as pastas `skills` do Claude Code e do Codex da conta em uso | só as sessões daquele agente (o próprio agente as lê); gerenciadas no agente |

No prompt vai só uma linha por skill (nome e descrição); o corpo é lido quando precisa. Skill sem
uso há 30 dias sai da lista para o arquivo, sem apagar nada.

## Achados

1. **As skills que a pessoa já tinha nos agentes não apareciam** (15 no Claude Code). As sessões
   já as usavam, mas o painel não mostrava, e parecia que não havia skill nenhuma. **Feito em
   13/10/2026:** cartão "Skills dos agentes" na página, só leitura, com o agente de cada uma.
2. **O editor mostrava o arquivo cru** (cabeçalho `---`, `name:`, `##`), coisa de programador.
   **Corrigido:** formulário com Nome, Quando usar, Do meu jeito, Passos e Pronto quando; o
   `SKILL.md` é montado por trás. "Editar como texto" continua para quem quiser; uma skill fora do
   modelo abre direto como texto, para não perder nada. A página Skills passou a carregar só quando
   aberta.
3. **Skill criada no meio da conversa não chegava ao cérebro.** A lista de skills também ia na foto
   do começo da conversa: a pessoa criou "resumo-do-dia", pediu o resumo, e o Zé respondeu pelo
   histórico, sem ler a skill. **Corrigido:** a mesma atualização da memória agora leva a lista de
   skills nova (e diz o que saiu).
4. **Editar uma skill não valia na conversa em andamento.** A pessoa mudou o "Pronto quando" e o Zé
   seguiu a versão que já tinha lido, porque a lista só mostra nome e descrição. **Corrigido:**
   skill editada gera o aviso "mudou, leia de novo antes de usar"; desligada, sai da lista com o
   aviso de que não vale mais. Desligar funcionava (o Zé não leu a skill), mas um resumo do dia ele
   sabe fazer sem skill, então o resultado parecia igual.

## Passos

### Passo 1. Criar uma skill pelo painel e o Zé usar

- **Como:** Nova skill → Nome "Resumo do dia"; Quando usar "Quando eu pedir o resumo do dia";
  Passos "O que ficou pendente" e "Lembretes de amanhã"; Pronto quando "No máximo 4 frases". Salvar.
  Depois: "Ei Zé, faz meu resumo do dia."
- **Esperado:** o Zé lê a skill antes de responder (o registro mostra) e segue o passo a passo.
- **Resultado:** ✅ 13/10/2026, depois do achado 3. A primeira vez (22:04) respondeu pelo
  histórico, sem ler; depois da correção, a Atividade registra "skills_ver: resumo-do-dia" e o
  contador de uso marcou 1.

### Passo 2. Editar, desligar e excluir

- **Como:** editar uma regra da skill e pedir de novo; desligar e pedir de novo; excluir.
- **Esperado:** a edição vale; desligada, o Zé não usa; excluída, some.
- **Resultado:** ❌ 13/10/2026, primeira tentativa: a edição não valeu (achado 4); desligada, não
  leu a skill, mas a resposta pareceu igual. Corrigido; para refazer.

### Passo 3. Criar pela voz

- **Como:** depois de ensinar algo ao Zé numa conversa: "Ei Zé, transforma isso numa skill."
- **Esperado:** ele mostra a skill e pede aprovação; aprovada, aparece na página.
- **Resultado:** ⬜

### Passo 4. As sessões recebem as skills do Zé

- **Como:** numa sessão de código, perguntar ao agente "quais skills do usuário você tem?".
- **Esperado:** ele lista as skills do Zé (e as do próprio agente).
- **Resultado:** ⬜

### Passo 5. Skills dos agentes

- **Como:** abrir Skills e conferir o cartão "Skills dos agentes".
- **Esperado:** aparecem as skills do Claude Code (e do Codex, se houver) da conta em uso.
- **Resultado:** ⬜
