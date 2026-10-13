# Auditoria 1: Voz e comunicação

Área 1 do checklist (`docs/checklist.md`). Um passo por vez: a pessoa faz o teste, o resultado é
anotado aqui e, se falhar, corrige-se antes do passo seguinte. A área fecha quando todos os itens
estiverem ✅.

**Conceito.** A voz é o canal da conversa: leva e traz, não guarda nada. Três escolhas, cada uma
com uma pergunta:

| Escolha | Pergunta | Opções |
|---|---|---|
| Ativação | Como eu chamo o Zé no microfone do PC? | "Ei Zé" ou Só o botão |
| Escuta | Quando o "Ei Zé" funciona? | Sempre ou Com a janela aberta (painel ou imersão) |
| Modo de fala | Quando o Zé fala sem eu pedir? | Silencioso, Avisos, Mãos livres |

E duas formas de conversar: **Falar** (segurar e soltar, um pedido) e **Ao vivo** (conversa
contínua até desconectar), no PC ou no celular.

## Já verificado

| Item | Quando | Como |
|---|---|---|
| "Ei Zé" no microfone do PC | 12/10/2026 | Uso diário |
| Falar (segurar e soltar) | 12/10/2026 | Uso no PC e no celular |
| Ao vivo no PC | 12/10/2026 | Conversa contínua |
| Voz pelo celular, em casa e no 4G | 13/10/2026 | WebSocket pelo túnel, com senha e autenticador |
| Reconexão da voz do celular | 13/10/2026 | Corrigido pelo Autodesenvolvimento e aplicado |

## Passos

Estado inicial: Ativação "Ei Zé", Escuta Com a janela aberta, Fala Avisos.

### Passo 1. Modo Avisos

- **Como:** "Ei Zé, me lembra daqui a um minuto de beber água."
- **Esperado:** o Zé confirma; um minuto depois fala "Lembrete: beber água." e o aviso aparece na
  linha do tempo.
- **Resultado:** ✅ 13/10/2026. Confirmou, criou a automação e falou o lembrete na hora; o aviso
  entrou na linha do tempo.

### Passo 2. Modo Silencioso e o atalho Alt+M

- **Como:** ainda em Avisos, "Ei Zé, me lembra daqui a dois minutos de alongar." Com o painel em
  foco, Alt+M até "Silencioso". Dizer "Ei Zé" e esperar o lembrete.
- **Esperado:** Alt+M troca o modo e o menu lateral mostra "Fala: Silencioso"; o "Ei Zé" ainda
  funciona (ADR 0022), mas a resposta vem só na tela; o lembrete chega só na tela, sem voz.
- **Resultado:** ❌ 13/10/2026. Alt+M ✅. O lembrete disparou sem voz ✅, e a resposta ao "Ei Zé"
  saiu muda ✅, mas **nenhum dos dois aparece no painel** (achado 2): o Silencioso hoje é um
  buraco. Para refazer depois da correção.
  **Refeito: ✅ 13/10/2026.** Sem voz; a resposta ao "Ei Zé" e o lembrete escrito na Conversa
  apareceram como notificação e no fio. A notificação sumia rápido demais (2,6 s): agora fica de
  5 a 15 s, conforme o tamanho do texto.

### Passo 3. Modo Mãos livres e as regras de fala

- **Como:** Alt+M até "Mãos livres". Sem abrir a sessão, pedir: "Ei Zé, pede para a sessão
  Universo - Teste explicar em cinco parágrafos o que é o projeto." Ficar em outra tela.
- **Esperado:** ao terminar, o Zé fala "A sessão Universo - Teste terminou." e um resumo de no
  máximo umas 30 palavras, com "O resto está na tela."; não repete.
- **Resultado:** ❌ 13/10/2026. Dois defeitos (achados 4 e 5): o aviso de fim não foi falado e a
  sessão não foi achada pelo nome na primeira tentativa. Corrigidos; para refazer.
  Refeito: o aviso de fim foi falado ✅, mas lendo a resposta da sessão na voz do Zé ("Oi, Kiko!
  Como você está?"): quem ouve não sabe quem fala (achado 6). Passo em espera do ADR 0029.

### Passo 4. Escuta: Com a janela aberta

- **Como:** fechar a janela do painel (e a da imersão, se aberta) e dizer "Ei Zé". Abrir o painel
  e dizer "Ei Zé" de novo.
- **Esperado:** com a janela fechada, nada; com ela aberta, o bip e o Zé ouvindo.
- **Resultado:** ⬜

### Passo 5. Escuta: Sempre

- **Como:** Voz → Escuta → Sempre. Fechar a janela do painel e dizer "Ei Zé".
- **Esperado:** o Zé responde mesmo com a janela fechada.
- **Resultado:** ⬜

### Passo 6. Ativação: Só o botão

- **Como:** Voz → Ativação → Só o botão. Dizer "Ei Zé". Depois segurar **Falar** e pedir algo.
- **Esperado:** o "Ei Zé" não faz nada; o botão funciona.
- **Resultado:** ⬜

### Passo 7. Voz rápida

- **Como:** Modelos → Voz rápida → Testar. Depois, "Ei Zé, tudo bem?".
- **Esperado:** o Testar responde "funcionando" (ou parecido); a conversa simples responde rápido,
  sem passar pelo cérebro (o registro mostra a via rápida).
- **Resultado:** ⬜

### Passo 8. Voltar às preferências

- **Como:** deixar Ativação, Escuta e Modo de fala como a pessoa quer usar no dia a dia.
- **Resultado:** ⬜

## Fora dos passos (só testes automáticos)

- Regras de fala: aviso cortado volta uma vez; o mesmo aviso não se repete em 2 minutos. Difícil
  de provocar à mão; os testes cobrem (`tests/test_regras_de_fala.py`). Passa a ✅ quando for visto
  no uso.

## Achados

1. **Sem conversa por texto no painel.** O conceito Conversa diz "por voz ou texto", mas o painel
   não tem onde escrever ao Zé (o texto só existe pelo teclado no terminal do serviço). Afeta quem
   está em silêncio ou sem microfone. **Corrigido em 13/10/2026:** página Conversa, com o campo
   "Escreva para o Zé"; o texto segue o mesmo caminho da fala.
2. **"Fica na tela" não tem tela.** No Silencioso, avisos e respostas vão para a linha do tempo e
   para a conversa gravada, mas o painel não mostra nenhuma das duas: não há onde ler o que o Zé
   respondeu nem os avisos que chegaram. Junto com o achado 1, falta a **Conversa** no painel.
   **Corrigido em 13/10/2026:** a Conversa mostra o fio do dia (pedidos, respostas e avisos) e, no
   Silencioso, o que o Zé não falou aparece também como notificação em qualquer página.
3. **Lembrete que já tocou aparece como "desligado"** em Automações, como se a pessoa o tivesse
   desligado. É da área 7 (Automações); anotado para lá.
4. **O aviso de fim de sessão não foi falado.** Chegou com o Zé ainda respondendo, esperou e, ao
   sair, a regra "sem duplicados" (ADR 0027) o tomou por repetido: contava o aviso como dado na
   chegada, não na fala. Corrigido: só conta depois de começar a ser falado.
5. **"Universo teste" não achava a sessão "Universo - Teste".** O nome era comparado com a
   pontuação. Corrigido: sem acento, maiúscula nem pontuação.
6. **Com sessões, a voz confunde e acumula.** O Zé lê a resposta da sessão como se fosse dele, e
   não há prioridade, agrupamento nem "próximo". **Corrigido em 13/10/2026:** ADR 0029 (Central
   de avisos), implementado.
