# 0125 — A trava de temas e a fala para o ouvido

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa, 24/11/2026; vídeo de referência aprovado).
- Completa o [ADR 0123](0123-capa-e-ganchos.md).

## Contexto

Quem usa vai automatizar dois ou mais vídeos por semana e não quer temas repetidos. A memória do
diretor (os 5 últimos roteiros) só pedia "não repita"; nada conferia, e o descarte de um vídeo
apagava a lembrança dele. A fala narrada também confundia quem escuta: cada cena é gravada
sozinha, e o diretor escrevia frases de legenda (sem conectivo, sem sujeito, cortadas entre
cenas). E o fluxo da solução aparecia em fotos, quando a animação o explica melhor.

## Decisão

1. **Processo e assunto em cada roteiro:** o diretor diz o processo da empresa (atendimento,
   financeiro, fiscal, operação, pessoas, gestão, pós-venda) e o assunto em poucas palavras. Os
   dois vão para `<pasta dos vídeos>/temas.json` (os últimos 200), que fica mesmo se o vídeo for
   descartado.
2. **A trava, no tema livre** (o agendado sem tema da lista nem artigo novo): o diretor vê os
   assuntos já feitos e os processos que pode usar (nenhum dos dois últimos); o roteiro volta a
   ele se repetir o processo ou um assunto parecido (metade das palavras de peso em comum). Depois
   da segunda volta, a trava ainda vale: o vídeo fica com o erro, não com o tema repetido. O tema
   que quem usa escreve não passa pela trava.
3. **A fala para o ouvido:** as falas lidas em sequência contam uma história a outra pessoa;
   cada uma é uma frase completa (o Zé fecha com ponto a que vier sem); conectivos falados entre
   as partes; nada de pronome solto, dois-pontos, siglas ou listas; a pontuação é a respiração.
   O diretor marca até três "pausas longas" (0,8 s a mais) depois do gancho, da conta e da
   virada.
4. **O fluxo é animado:** a solução do "caso" é obrigatoriamente uma cena "conexao" ou "hub",
   e o nó do fluxo aceita o logo da ferramenta ("logo: whatsapp"), com o ícone de reserva.
5. **A duração** desconta as pausas longas: 2,0 palavras por segundo (o medido em seis vídeos,
   com os respiros) sobre o tempo menos 2,4 s.

## Consequências

- Uma volta a mais ao diretor quando ele repete um tema (a mesma chamada de correção de antes).
- Sem processo no roteiro (um vídeo antigo), a trava confere só o assunto.
