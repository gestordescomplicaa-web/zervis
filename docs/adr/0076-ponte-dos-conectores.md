# 0076 — A ponte dos conectores: o segredo fica com o Zé

- Data: 10/11/2026
- Status: **Aceita** (testada no `make check`, com um conector de mentira, e com o Claude Code
  2.1 e o Codex 0.167 desta máquina conectando de verdade pela ponte).

## Contexto

Um conector com segredo (token no ambiente, cabeçalho de autorização, login OAuth) ia inteiro
ao processo do agente: no ambiente do Codex e no arquivo de configuração do Claude, na pasta da
sessão. Um `env` ou um `cat` bastava para o segredo ir ao modelo. Mesmo dentro do isolamento
(ADR 0074), o servidor do conector rodava ao lado do agente, que podia ler o ambiente dele.

É o resto do item "cofre de segredos fora do agente" da Frente 2 do
[plano de maturidade](../plano-maturidade.md); o ADR 0075 tirou os segredos do próprio Zé.

## Decisão

1. **O Zé abre o conector; o agente fala com o Zé.** Para cada conector com segredo, o agente
   recebe só um endereço do Zé (`/sessoes/conectores/<nome>`, na porta do painel) e a chave da
   sessão no cabeçalho `Authorization`. O Zé abre o conector de verdade (com o segredo, na pasta
   do projeto) e repassa as ferramentas (`zervis/oficina/ponte.py`).
2. **Escopo e prazo pela chave da sessão:** a mesma do gancho de permissão (ADR 0039), trocada a
   cada abertura do terminal e sem valor depois que ele fecha. Ela só abre os conectores marcados
   para o projeto daquela sessão; o conector aberto fecha depois de 10 minutos parado ou quando a
   sessão perde a chave.
3. **As bloqueadas são recusadas na ponte**, além de sumirem da lista: uma chamada direta, sem o
   agente, também não passa.
4. **O servidor MCP é o do SDK oficial**, sem estado e com resposta em JSON: o painel entrega o
   pedido HTTP e devolve a resposta. Sem estado, um terminal que sobrevive ao reinício do Zé
   (ADR 0068) continua usando os conectores: a chave é adotada e a ponte reabre o conector no
   primeiro pedido.
5. **Conector sem segredo não muda:** continua rodando ao lado do agente, como antes.

## Consequências

- A aprovação das ferramentas que não são livres continua no agente (o gancho de permissão). Um
  agente que chame a ponte direto, com a chave da sessão, pula a pergunta; antes ele podia o
  mesmo, e ainda levava o segredo. Pedir a aprovação também na ponte fica para depois: quando a
  pessoa responde no terminal, o Zé não fica sabendo.
- Os servidores dos conectores com segredo passam a rodar no processo do Zé, fora do isolamento
  da sessão protegida: é código que a pessoa configurou, com o segredo dela.
- Valem só nas sessões de terminal (o caminho normal, e o único da sessão protegida). O modo
  antigo pelo SDK e o `codex exec` sem painel seguem com os segredos diretos.
