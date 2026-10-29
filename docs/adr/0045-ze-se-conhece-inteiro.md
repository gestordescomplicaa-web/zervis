# 0045 — O Zé se conhece por inteiro: o que sabe fazer e o que fez, numa fonte só para a tela

- Data: 29/10/2026
- Status: **Aceito** (pedido da pessoa em 29/10/2026, ao desenhar as apresentações da Imersão).

## Contexto

O retrato do ADR 0043 descreve só a configuração: o modelo que responde, a voz, a escuta, os modos,
o acesso e a versão. Perguntado "o que você sabe fazer?" ou "o que você fez esta semana?", o Zé
não tinha de onde responder sem inventar. As respostas existiam, mas espalhadas pelo painel: as
ferramentas do servidor `jarvis`, as skills, os conectores, as sessões, as automações, a memória e
a Atividade.

A Imersão vai ganhar apresentações: o Zé vai para o canto e mostra, em painéis holográficos, dados
sobre ele mesmo. A pessoa pediu que tudo o que ele mostra saia primeiro do que ele sabe de si, e só
depois ele passe a criar apresentações novas.

## Decisão

1. **O retrato ganha duas partes**, montadas pelo núcleo na hora (`Nucleo.capacidades()` e
   `Nucleo.historico()`), sem segredo nenhum:
   - **O que eu sei fazer** (`Capacidades`): as próprias ferramentas por grupo, com uma linha do
     que cada grupo faz (`GRUPOS`) e quantas passam sem perguntar; as skills com os usos; os
     conectores com quantas ferramentas estão liberadas; as sessões de código e o estado; as
     automações; a memória (lembranças e páginas da memória das sessões); o WhatsApp.
   - **O que eu fiz** (`Historico`): a Atividade dos últimos 7 dias, numa passada só
     (`Atividade.balanco`): quantos de cada tipo, registros e falhas por dia no fuso de quem usa,
     as ferramentas mais executadas e os registros mais recentes.
2. **Uma fonte, duas leituras.** `autoconhecimento.texto` leva as duas partes ao `ze_sobre` (e à
   nota "Quem sou"); `autoconhecimento.dados` entrega o mesmo retrato como dados para a tela, pela
   leitura `/api/autoconhecimento` do painel. A tela não recebe o acesso nem as contas.
3. **Nenhuma parte derruba a resposta.** Uma fonte ilegível (um arquivo de automações quebrado, a
   memória das sessões fora do ar) fica vazia e o resto segue. A contagem das páginas da memória lê
   só o banco (`aimemory.paginas`), sem a checagem de rede, porque roda a cada pergunta.

## Consequências

- Grupo novo de ferramentas aparece sozinho no retrato (`ferramentas.por_grupo`); sem linha em
  `GRUPOS`, entra com o nome do módulo, e o teste avisa.
- A resposta rápida continua recebendo só o resumo curto da configuração; para "o que você faz?"
  ela passa a vez ao cérebro completo, que consulta o `ze_sobre`.
- As apresentações da Imersão (etapa seguinte) leem `/api/autoconhecimento`. Criar apresentações
  novas a partir de pedidos (um catálogo de cenas preenchido por um modelo rápido) fica para depois
  e terá o seu próprio ADR.
