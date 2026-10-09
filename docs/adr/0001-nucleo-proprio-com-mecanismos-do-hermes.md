# 0001 — Núcleo próprio, copiando mecanismos do Hermes

- Data: 06/10/2026
- Status: **Aceito** (o usuário: "reaproveitar a tecnologia do Hermes para criar a base ideal")

## Contexto
O Hermes Agent já tem memória curada, skills que se aperfeiçoam, curadoria, cron e escuta por
palavra de ativação. Mas é um produto enorme (centenas de módulos, 20+ plataformas de mensagem,
desktop, nuvem), com configuração que muda muito (versão 49, dezenas de backups no perfil) e o
perfil atual ocupa ~1,6 GB. O JARVIS precisa de poucas dessas capacidades, sob controle total.

## Opções
1. **JARVIS como perfil do Hermes** (usar o Hermes como motor). Mais rápido no começo; fica refém
   das atualizações e da complexidade dele, e mistura o JARVIS com o uso do Hermes para o JEV.
2. **Núcleo próprio, copiando mecanismos** (MIT permite). Mais trabalho inicial; código pequeno,
   entendido e testado por nós.
3. **Do zero, sem olhar o Hermes.** Desperdiça soluções já testadas em produção.

## Decisão
Opção 2. Reimplementar enxuto: memória com limite e varredura, skills com pendência e diff,
revisão em segundo plano com os critérios do Hermes, curadoria determinística, jobs com escrita
atômica. Trechos copiados levam aviso de autoria e entram em `THIRD_PARTY.md`.

## Consequências
- Cada mecanismo vem com testes próprios antes de ser usado.
- O Hermes continua instalado e intocado (o coletor de WhatsApp do JEV depende dele).
- O JARVIS deixa de depender do venv do Hermes na Fase 1.
