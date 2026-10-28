# 0044 — A pesquisa na internet do próprio Zé, sem sessão, com qualquer cérebro

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026: "dar a ele capacidade de busca na internet
  pra me dar uma resposta rápida sem sessão").

## Contexto

Caso real de 27/10/2026, pela voz: "pesquise e descubra alguma notícia sobre o Flávio
Bolsonaro". Com o Codex como cérebro, o Zé respondeu "a ferramenta de pesquisa não está
disponível nesta conversa". O cérebro do Codex só tem as ferramentas do Zé, de propósito, com a
pesquisa nativa desligada (`web_search = "disabled"`). Só o cérebro Claude pesquisava, com
WebSearch, e cada uso pedia aprovação falada. A saída que a pessoa achou foi abrir uma sessão
para pesquisar, e a sessão gerou nove pedidos de aprovação (uma busca ou uma página cada).

## Decisão

1. **Uma ferramenta do Zé, `internet_pesquisar`, livre.** Ela recebe o pedido completo e devolve
   um resumo curto com "Fontes:" no fim (as fontes vão para a tela, não são faladas). Como é do
   servidor do Zé, vale com qualquer cérebro: Claude, Codex ou outro. A via rápida do Live já
   passa a vez em "pesquisa", "notícia" e "preço".
2. **Uma consulta à parte, que só pesquisa.** O cérebro não ganha a busca nativa. A pesquisa roda
   numa conversa nova e efêmera, sem as ferramentas do Zé, sem arquivos e sem comandos. O que uma
   página tentar mandar fica nela, e ao cérebro chega só o resumo, como dado. Por isso ela passa
   sem pergunta: só lê a internet.
3. **Por onde vai.** Primeiro a conta do Codex em uso, se for a assinatura, com
   `web_search = "live"` só nessa consulta (prova: 6 a 7 s, notícia do dia com fonte). Sem ela,
   ou se ela falhar, pelo Claude só com WebSearch e WebFetch, como as automações (13 s). Conta de
   provedor (outro modelo pela chave) não tem a busca do Codex e vai pelo Claude.
4. **O Zé sabe que pesquisa.** A persona manda usar a ferramenta direto, sem sessão, e nunca
   dizer que não tem internet. O retrato (ADR 0043) diz "Pesquisa na internet: sim".

## Consequências

- Notícia e assunto resumido saem em 10 a 20 s pela voz, sem aprovação e sem abrir sessão.
- Cada pesquisa gasta a cota da conta que respondeu (Codex ou Claude), como uma pergunta comum.
- Ler um site com calma, comparar e clicar continua no navegador do Zé, com as regras dele.
