# 0085 — O vigia da impressora: erros na hora, impressão mais segura e a câmera

- Data: 12/11/2026
- Status: **Aceita** (`tests/test_vigia_impressora.py`; com a A1 real: o vigia conectado e o
  retrato inteiro, a tabela de erros da Bambu, a câmera e a medida de balanço das peças de quem
  usa).

## Contexto

Depois da primeira impressão (ADR 0083), quem usa perguntou se o Zé avisa de um erro. Não avisava:
ele olhava a impressora a cada minuto e só dizia "terminou" ou "parou antes do fim"; uma pausa por
erro (o filamento acabou, o bico entupiu) contava como "imprimindo" e ficava em silêncio. O motivo
do erro não era lido, uma impressão mandada de fora do Zé não era vista, e o acompanhamento morria
num reinício. E o fatiamento ia sem suporte (o perfil padrão vem desligado) e sem uma prévia para
conferir antes do sim.

## Decisão

1. **Um vigia, com a conexão MQTT aberta enquanto o Zé roda** (e reconectando sozinho), que junta
   o que a impressora manda (ela manda só o que mudou; o `pushall` traz o retrato inteiro ao
   conectar). O status e os comandos usam essa conexão quando ela está de pé.
2. **O que vira aviso falado** (e fica na lista do painel): pausou por um erro, com o motivo;
   pausada; voltou; cancelada; falhou, com o motivo; terminou; e a primeira camada pronta. Também
   para impressões mandadas de fora do Zé, e depois de um reinício (o primeiro retrato só marca o
   ponto de partida). Um aviso sai mesmo no Silencioso: é uma máquina física.
3. **O motivo, da tabela oficial da Bambu** que o Bambu Studio guarda na máquina
   (`hms_<idioma>_<modelo>.json`; para a A1, 2.793 códigos). Em português quando existe; senão a
   categoria em português, tirada do próprio texto da Bambu ("acabou o filamento", "há algo sobre a
   mesa"), com o texto inteiro no painel. "A tarefa foi cancelada" (FAILED com 0300400C) aparece como
   cancelada, não como falha.
4. **A câmera:** nos avisos de erro, de fim e da primeira camada, uma foto da câmera da impressora
   (porta 6000, o protocolo da Bambu) fica em `<dados>/impressora/fotos` (as 20 mais novas). Pela
   voz, `impressora_foto` mostra a mesa ao cérebro (e, desde a ADR 0086, a manda à tela de quem
   fala pelo celular ou pelo navegador); no painel, "Ver câmera".
5. **Imprimir mais seguro:** o Zé mede no STL a área das faces inclinadas além de 45° que ficariam
   no ar (fora da mesa); acima de 25 mm², liga o suporte em árvore automático, com as pontes sem
   suporte. O teto reto não conta: a impressora faz ponte (o suporte de garrafinha de quem usa
   tinha 75 dos 92 mm² em ponte e imprimiu bem sem apoio). A fala diz quando vai com suporte.
6. **A prévia do fatiamento:** o caminho do bico, lido do G-code (paredes, preenchimento, pontes,
   suporte), desenhado camada por camada no painel, com uma barra para descer as camadas.

## Consequências

- A conexão com a impressora fica aberta enquanto o Zé roda (uma, além de uma rápida para os
  comandos quando o vigia está fora).
- As fotos mostram o cômodo em volta da impressora: ficam só na máquina, na pasta do Zé.
- Nenhum aviso promete que a impressão vai sair perfeita: o suporte e a prévia diminuem o risco.
