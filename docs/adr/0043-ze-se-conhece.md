# 0043 — O Zé se conhece: o retrato da própria configuração, para qualquer modelo

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026, depois do teste do Live).

## Contexto

No teste do Live, a pessoa perguntou "Zé, qual modelo você está usando?" e ele não soube
responder. O pedido dela: o Zé precisa se entender como um sistema independente, que funciona com
qualquer modelo por trás, para responder e ajudar quem usa, inclusive por voz.

Até aqui, só a nota "Quem sou", da pasta do Zé no Barehands, descrevia a configuração: cérebro,
reserva, voz e ferramentas. Mas o cérebro não lia essa nota, e ela não falava das respostas
rápidas, do Live nem dos modos.

## Decisão

1. **Um retrato só** (`zervis/nucleo/autoconhecimento.py`), montado pelo núcleo na hora
   (`Nucleo.retrato()`). Ele traz:
   - quem responde agora: o cérebro completo ou a via rápida, com o modelo;
   - a reserva e as respostas rápidas (motor, modelo, quando valem e se estão respondendo agora);
   - o modo de fala, o Live, a voz, a escuta, a ativação e a espera;
   - de onde dá para falar com o Zé, as contas em uso, a máquina e a versão.

   Junto vai um **mapa de onde mudar cada coisa**, no painel e por voz. Tudo em português, em
   Markdown curto, que qualquer modelo lê. **Sem segredo nenhum:** chaves, senhas e tokens nunca
   entram.
2. **Três leituras do mesmo retrato:**
   - **`ze_sobre`:** uma ferramenta do servidor `jarvis`, de leitura, que passa sem perguntar. O
     cérebro completo (Claude, Codex ou outro) a consulta. A persona manda consultá-la para
     qualquer pergunta sobre o próprio Zé e nunca responder isso de memória.
   - **A via rápida:** recebe o resumo ("Você agora") ao subir. Ela só sobe para responder,
     então o resumo diz que é ela quem responde, com o modelo escolhido. Ela responde sobre si
     sem passar a vez e passa a vez para mudar alguma configuração ou para o que não estiver no
     resumo.
   - **A nota "Quem sou":** passa a ser o retrato inteiro, mais a revisão em segundo plano.

## Correções do mesmo teste (27/10/2026)

O teste do Live mostrou cada resposta levando de 9 a 11 s. Os motivos:

- **A via rápida falhava em todo turno.** O motor "plano" (o Claude pela assinatura) herdava a
  chave de API da Anthropic do painel, que estava sem crédito e tem a vez sobre o login. Com o
  login feito, o motor agora roda sem a chave (`rapido.pela_assinatura`). Provado com uma chave
  inválida no ambiente: a primeira palavra saiu em 0,9 a 1,2 s.
- **A falha esperava 5 s.** O Zé esperava o motor parar antes de chamar o cérebro completo.
  Agora o motor para em segundo plano, e a interrupção pede aos dois cérebros juntos.
- **Frases curtas esperavam o resto da resposta.** O separador de frases do LiveKit (mínimo de
  20 caracteres) segurava "Deixa eu ver." até o resto chegar, e a voz levava de 1,4 a 4 s até o
  primeiro som. Cada frase que o laço entrega já está inteira, então vai à voz na hora
  (`FlushSentinel`).

## Consequências

- O retrato é montado a cada pergunta (barato: só lê o estado). A via rápida o recebe só ao
  subir: uma troca de voz no meio da conversa vale para ela na próxima conexão.
- Quando entrar uma configuração nova no Zé, o retrato e o mapa precisam dela. É um lugar só.
