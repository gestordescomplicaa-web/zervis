# 0035 — Agentes prontos na instalação: Claude Code e Codex nativos, chaves pelo painel

- Data: 16/10/2026
- Status: **Aceito** (pedido da pessoa em 16/10/2026, no primeiro teste numa VPS real: "estou tendo
  muita dificuldade de colocar o Codex ou o Claude no Zérvis que está na VPS").
- Detalha o ponto 11 do [ADR 0034](0034-central-estacoes-e-instalacao.md) para os agentes.

## Contexto

No teste numa VPS (Ubuntu 24.04, 16/10/2026), o Zé subiu, mas o painel mostrava o Claude e o
Codex como "Não instalado" e pedia para rodar o login no terminal:

- **Claude Code:** já vinha dentro do `claude-agent-sdk` (o cérebro e as sessões usam ele), mas não
  como o comando `claude`, que o painel procura.
- **Codex:** não vinha. Instalar exigiu baixar o binário à mão, ajustar o PATH e rodar
  `codex login --with-api-key` no terminal.
- **Chave da OpenAI:** só existia para as Respostas rápidas. O cérebro só aceitava a chave da
  Anthropic, ou o login de cada agente.

Para quem instala numa VPS, cada passo desses é atrito, e o terminal é o pior deles.

## Decisão

1. **Os dois agentes vêm com o Zé.**
   - **Claude Code:** o que vem no `claude-agent-sdk` (distribuído pela Anthropic no PyPI; o Zé não
     redistribui o binário, o uv o instala como dependência). Sem `claude` na máquina, o Zé põe a
     pasta dele no PATH dos agentes e das sessões.
   - **Codex:** o binário oficial (github.com/openai/codex, Apache-2.0), versão fixa, baixado e
     conferido por SHA-256 na primeira subida, como o ai-memory e o cloudflared. O da máquina, se
     houver, tem a vez.
   - O instalador do servidor cria `claude` e `codex` em `~/.local/bin` (quando não existem), para
     quem quiser usá-los no terminal.
2. **Cada agente aceita as duas formas de acesso, pelo painel:** a conta (assinatura) ou a chave de
   API.
   - Claude: token de `claude setup-token` ou chave da Anthropic (já existia).
   - Codex: login da conta do ChatGPT (`codex login --device-auth`, sem navegador no servidor) ou
     **chave da OpenAI** (novo). A chave entra pelo painel, o Zé a entrega ao Codex pelo
     `codex login --with-api-key` e não a guarda em lugar nenhum além do próprio Codex.
   - A mesma chave da OpenAI das Respostas rápidas pode ser usada no Codex com um clique.
3. **"OpenAI pela chave" no cérebro é o Codex com a chave da OpenAI.** O Codex já tem as ferramentas
   e as sessões; não se cria um terceiro tipo de cérebro.

## Consequências

- A primeira subida baixa ~100 MB a mais (o Codex). O instalador baixa antes de subir o serviço.
- Uma versão do Codex fixada: atualizar é um commit próprio, com o SHA-256 novo.
- Login real do Codex e da chave só se provam na máquina de quem instala; os testes cobrem o fluxo
  com um Codex falso.

## Andamento

| Parte | Estado | Resultado |
|---|---|---|
| Agentes com o Zé | Feito em 16/10/2026 | Codex 0.163.0 baixado e conferido; Claude Code do SDK. Num usuário limpo, sem nenhum dos dois: `codex --version` e `claude --version` responderam, e o painel passou de "Não instalado" para instalado nos dois. |
| Chave da OpenAI no Codex | Feito em 16/10/2026 | Pelo painel, entregue ao `codex login --with-api-key` pela entrada do processo. Com o Codex real, uma conta nova falhava porque o Codex recusa um `CODEX_HOME` que não existe: o Zé cria a pasta antes (regressão no teste). |
| Entrar na conta pelo painel | Feito em 16/10/2026 | "Entrar" abria uma janela de terminal, que num servidor não existe. Agora o login do agente (`claude auth login`, `codex login --device-auth`) roda no Zé e o painel mostra o texto, "Abrir link" e o campo do código, do PC ou do celular. Prova com o Claude Code real: o link de autorização apareceu e o campo do código ficou pronto. |
