# 0009 — Conversa contínua: "ok" encerra, sem repetir "Hey Orca"

- Data: 06/10/2026
- Status: **Aceito** (decisão do usuário, depois do primeiro teste de voz da Fase 1)
- Altera: invariante 2 do [04](../04-arquitetura.md)

## Contexto
No primeiro teste com a voz do usuário, cada pergunta exigia um novo "Hey Orca". Ele pediu que
a conversa continue sem repetir a ativação e que "ok" sirva de pausa.

## Decisão
1. "Hey Orca" **abre uma conversa**. Depois de cada resposta o JARVIS volta a ouvir a próxima
   pergunta sem ativação (anel em "ouvindo").
2. A conversa fecha com um bip curto quando o usuário diz uma **frase curta (até 4 palavras) só
   de palavras de encerramento**, com ao menos uma principal (ok/okay/okey, obrigado, valeu,
   tchau, chega, parar): "ok", "ok, ok", "tá bom, obrigado", "pode parar". Também fecha depois
   de **8 s sem fala** (`escuta.conversa_s`) ou ao fechar a janela. "ok" num pedido
   ("ok, abre o navegador") é pedido, não encerramento.
3. Depois de uma resposta, transcrição vazia ou ininteligível **encerra** a conversa em silêncio
   (responder "não entendi" e voltar a ouvir virava laço). Frases que o Whisper inventa em áudio
   curto ("Legendas pela comunidade Amara.org", "Obrigado por assistir") contam como vazio.
4. Continua valendo: **cada pedido consome uma autorização** e só a resposta a ele concede a
   próxima; enquanto pensa ou fala, nada do microfone vira pedido (eco).
5. Só uma conversa aberta pelo usuário continua: um aviso falado pelo próprio JARVIS **não** abre
   escuta depois dele.
6. "Hey Orca" no meio da resposta continua interrompendo.

## Histórico
- Primeira versão (só "ok" exato) falhou no teste do usuário: a conversa não fechava e o eco
  repetia sem parar. As transcrições não eram registradas, então a causa não foi confirmada;
  a regra ampla, o fim do laço com transcrição vazia e o filtro de alucinações cobrem as causas
  prováveis. No reteste o Whisper escreveu `Ok.` e a conversa fechou.
- Para diagnosticar transcrições existe `escuta.registrar_texto` (desligado por padrão).

## Consequências
- Por até 8 s depois de cada resposta, fala de fundo (vídeo, outra pessoa) pode virar pergunta.
  É o preço da conversa sem ativação; o prazo é configurável e o anel mostra que está ouvindo.
- Testes em `tests/test_estados.py` (seção "conversa contínua") e ponta a ponta em
  `provas/prova_ciclo.py` ("Ok." encerra com bip).
