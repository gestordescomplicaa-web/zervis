# 0033 — Pacotes de extensão: o Zé ganha capacidades sem mudar o próprio código

- Data: 15/10/2026
- Status: **Proposta**, adiada para depois da liberação (roteiro, MVP). Etapa E6 do
  [ADR 0032](0032-arquitetura-para-crescer.md).

## Contexto
O Zé cresce de dois jeitos. O primeiro já existe: o **auto-desenvolvimento** (ADR 0026), em que o
próprio código muda numa cópia isolada, passa no `make check` e só entra com aprovação. O segundo
é o deste ADR: **ganhar capacidades sem mudar o código**, instalando algo pronto.

Hoje isso já é possível peça por peça: uma skill é uma pasta com `SKILL.md`
(`jarvis/habilidades/skills.py`) e um conector é um servidor MCP cadastrado no painel
(`jarvis/cerebro/conectores.py`). Falta juntar as peças que andam juntas. Uma integração com a
agenda, por exemplo, é um conector (as ferramentas da agenda) mais uma skill (como marcar reunião
do jeito de quem usa). Hoje são dois cadastros manuais, sem versão e sem remoção conjunta.

O Claude Code resolve o mesmo problema com plugins (`.claude-plugin/plugin.json`, skills em
`skills/`, servidores MCP em `.mcp.json`). Adotar o mesmo formato aproveita o que já se publica
para ele.

## Decisão
1. **Um pacote é uma pasta ou um repositório Git** com `.claude-plugin/plugin.json` (o formato do
   Claude Code: `name`, `version`, `description`, `author`, `license`) e, opcionalmente:
   - `skills/<nome>/SKILL.md`: skills, no formato que o Zé já usa;
   - `.mcp.json`: conectores MCP (`mcpServers`, stdio ou http), traduzidos para o formato dos
     conectores do painel. `${CLAUDE_PLUGIN_ROOT}` vira a pasta instalada do pacote.
   O Zé aceita qualquer plugin do Claude Code nesse formato. As peças que ele não usa (`commands/`,
   `agents/`, `hooks/`) são listadas na aprovação como "Não instalado" e ficam fora.
2. **Nada do pacote roda dentro do processo do Zé** (ADR 0032, "O que não fazer"). Hooks e scripts
   nunca executam. Um conector stdio é um programa no computador de quem usa, num processo
   próprio: por isso a aprovação mostra o comando exato antes de instalar.
3. **Instalação com aprovação na tela**, só pelo próprio computador (como os ajustes de acesso).
   A tela mostra nome, versão, autor, licença, origem, as skills, cada conector com o comando ou o
   endereço, os segredos que ele pede e as peças não instaladas. Nada é gravado antes de "Instalar".
4. **Ferramentas de conector instalado começam pedindo aprovação**, como todo MCP externo hoje. O
   pacote não decide o que é livre: `livres` e `bloqueadas` do manifesto, se vierem, são só
   sugestões mostradas na tela; quem usa escolhe depois de "Testar".
5. **Versão fixada.** De Git, o pacote fica preso ao commit instalado (mostrado na tela);
   atualizar é uma nova instalação, com nova aprovação e a diferença do que muda. De pasta, o
   conteúdo é copiado e conferido por SHA-256.
6. **Onde fica:** `DADOS/pacotes/<nome>/` (cópia fixa) e um registro em SQLite (ADR 0032, E1) com
   origem, commit ou hash, data e o que o pacote instalou. Skills e conectores de pacote aparecem
   em Skills e Conectores com a origem "Pacote <nome>" e não se editam por lá.
7. **Remoção sem rastro:** apaga a pasta, as skills, os conectores, os segredos deles e o
   registro. Um teste confere que nada do pacote sobra.
8. **Atendimento:** o agente de atendimento só usa ferramenta de pacote que estiver na lista de
   ações liberadas dele (ADR 0031). Instalar um pacote não libera nada para o atendimento.
9. **Fora desta etapa:** loja ou busca de pacotes, atualização automática, pacotes que mudam
   persona, voz ou regras do Zé.

## Pronto quando (do ADR 0032)
Um pacote de exemplo (uma skill e um conector MCP) instala pela tela, aparece em Skills e
Conectores e é removido sem rastro; um plugin real do Claude Code, no formato publicado, é aceito.

## Consequências
- Um formato só para quem já publica plugins do Claude Code.
- O risco real é o conector stdio, que é um programa de terceiro com as permissões de quem usa.
  A mitigação é a aprovação com o comando à vista, as ferramentas pedindo aprovação por padrão e
  a remoção completa. O isolamento desses processos (contêiner) fica para depois, como a auditoria
  de 14/10/2026 já aponta.
