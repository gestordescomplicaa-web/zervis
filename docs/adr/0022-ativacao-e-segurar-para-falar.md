# 0022 — Ativação ("Ei Zé" ou botão) separada do modo de fala; segurar para falar

- Data: 12/10/2026
- Status: **Aceito**; revisto em 13/10/2026: o Silencioso volta a fechar o microfone, agora por inteiro (o chamado, o botão e o ao vivo), a pedido do usuário: "no modo silencioso não quero que ele atrapalhe o YouTube; o microfone deveria ficar travado" (pedido do usuário: diferenciar o "Ei Zé" ao vivo, o botão, o modo
  silencioso e o texto; no celular, com fone, poupando bateria). Altera o
  [ADR 0018](0018-modos-de-fala.md) num ponto: o Silencioso não desliga mais o chamado.

## Contexto
O modo Silencioso misturava duas perguntas: quando o Zé fala sozinho e como a pessoa o chama.
No celular, o "Ei Zé" contínuo é o menos confiável (outro microfone, ruído, processamento do
navegador) e gasta bateria, porque o áudio sai o tempo todo.

## Decisão
1. **Duas escolhas independentes na página Voz:**
   - **Ativação** (`<config>/chamado.json`): **"Ei Zé"** (padrão: o chamado falado e o botão) ou
     **Só o botão** (o detector do chamado fica desligado);
   - **Modo de fala** (ADR 0018): Silencioso, Avisos ou Mãos livres. O Silencioso passa a ser só
     "o Zé não fala; tudo fica na tela".
2. **Segurar para falar:** o botão no menu lateral (e o espaço, fora de campos de texto e do
   terminal). Segurar abre o pedido como o chamado e o fecha ao soltar, sem fechar nas pausas;
   um toque curto começa e outro toque envia, para pedidos longos. Na máquina de estados:
   eventos `Apertou` e `Soltou`, efeito `FecharPedido`; o segmentador não fecha o pedido
   enquanto o botão está apertado. O painel espera 0,3 s depois de soltar, para o fim da fala
   que ainda está na rede entrar no pedido.
3. ~~Bateria no celular: com "Só o botão", a faixa do microfone do navegador fica muda.~~
   Substituído pelo [ADR 0023](0023-voz-ao-vivo.md): a voz conectada é sempre ao vivo.
4. **Uma faixa ouvida por vez** na voz remota: a mais recente; a anterior é encerrada.

## Consequências
- Quatro jeitos de usar: "Ei Zé" ao vivo, o botão, o texto (teclado e terminal) e o Silencioso,
  combináveis (por exemplo, "Só o botão" com "Avisos" para o fone no bolso).
- Próximos passos do mesmo pedido: a espera depois de um tempo parado (bateria) e o botão do fone
  como o botão de falar, que depende do teste do celular bloqueado (plano da voz remota, etapa 2).
