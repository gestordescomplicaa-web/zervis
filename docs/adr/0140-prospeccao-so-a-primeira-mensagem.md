# 0140 — Prospecção: só a primeira mensagem, e as empresas por ramo numa linha cada

- Data: 25/11/2026
- Status: **Aceito** (pedido de quem usa, depois de dois dias de prospecção de verdade).
- Ajusta o [ADR 0127](0127-prospeccao.md) (a página e as marcas "Reunião marcada" e "Sem
  interesse") e o [ADR 0128](0128-ze-conhece-todas-as-paginas.md) (as ferramentas da Prospecção).

## Contexto

Em 25/11/2026 a Prospecção tinha 19 empresas, e 14 eram descartadas (8 por nota baixa, 3 sem
WhatsApp, 2 sem telefone, 1 por quem usa). A página mostrava até 80 empresas, cada uma com o
motivo, o sinal e a mensagem inteira: quase tudo o que aparecia era empresa que não vai receber
nada, e com 2 envios por dia a lista cresce uns 40 por mês.

O botão "Reunião marcada" também não servia: o link de agendamento vai para todas, e quem agenda
escreve o que quiser no formulário, então quem usa não sabe de qual empresa veio a reunião. A
conversa depois da primeira mensagem, por enquanto, é de quem usa, no WhatsApp.

## Decisão

1. **A Prospecção cuida da primeira mensagem.** Saem o "Reunião marcada" e o "Sem interesse" da
   página, a rota `prospeccao/marcar` e a ferramenta `prospeccao_marcar`. "Respondeu" e "Sem
   interesse" continuam como estado, quando o Zé reconhece a resposta sozinho (e a recusa conta no
   freio). O estado "Reunião marcada" fica só para os dados de antes.
2. **As descartadas saem da tela, não do banco.** É o registro delas que garante que ninguém
   recebe duas vezes (o lugar do Google, o CNPJ e o telefone). Na página, só a contagem
   ("14 descartadas"); pela voz, a contagem por motivo ("Pouco sinal: 8"), e uma pelo nome ainda
   diz tudo.
3. **Uma linha por empresa:** o nome, o número (o que recebeu a mensagem; antes do envio, o
   primeiro da lista) e o estado. A resposta aparece embaixo quando há, e o "Descartar" fica na
   empresa que está na fila. A mensagem enviada sai da página; pela voz, continua.
4. **Por ramo, o da Configuração que buscou a empresa** (guardado em `ramo` a partir de agora), não
   a categoria do Maps, que vem picada ("Loja de autopeças", "Loja de baterias de carro"…). As
   empresas de antes vão para o ramo cujas palavras estão na categoria; com um ramo só na
   Configuração, para ele (foi o único a buscar); senão, "Outros". As postas pelo CNPJ têm o grupo
   delas. A ordem é a dos ramos na Configuração.
5. **Cada ramo recolhido**, com a contagem no título ("12 contatadas · 1 respondeu · 1 na fila").
   Abre sozinho o ramo com resposta, ou o único. Cada um mostra as 30 mais recentes; o resto fica
   no total e se lê pela voz.

## Consequências

- O que vai à página é pequeno (sete campos por empresa) e limitado por ramo: a lista não pesa com
  o tempo.
- Uma empresa descartada não se vê na página. Se for preciso, pela voz ("por que a X foi
  descartada?").
- A etapa 2 do ADR 0127 (o Zé conduzir a conversa até a reunião) fica para depois; quando vier,
  volta a fazer sentido marcar o resultado de cada conversa.
