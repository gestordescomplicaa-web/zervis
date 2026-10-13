# 0027 — Regras de fala: quando o Zé fala sozinho, sobre o quê e quantas vezes

- Data: 13/10/2026
- Status: **Aceito** (pedido do usuário: o Zé falava o tempo todo e leu as cinco propostas da
  sessão de melhorias quatro vezes seguidas no fone)

## Contexto
O ADR 0018 decide *se* um aviso vira voz (Silencioso, Avisos, Mãos livres). Faltava decidir *o
quê* e *quantas vezes*. O aviso de que a sessão de melhorias terminou levava a resposta inteira
(1296 caracteres). A cada reconexão do celular a fala era cortada, o aviso voltava para a fila e
recomeçava do início: quatro leituras completas.

## Decisão
1. **Manchete.** Aviso falado tem no máximo 30 palavras (`modo.manchete`): as frases inteiras que
   couberem e "O resto está na tela." O texto inteiro fica na linha do tempo.
2. **Uma frase, nunca o conteúdo.** O fim da sessão de melhorias vira "A sessão de melhorias
   terminou." e o que fazer ("Há mudanças para aprovar em Melhorias."); as propostas ficam na
   sessão, na tela.
3. **Uma repetição no máximo.** Um aviso que começou a ser falado e foi cortado volta uma vez; se
   for cortado de novo, fica só na tela. Aviso retido porque o Zé estava ocupado (sem ter começado)
   espera sem contar.
4. **Sem duplicados.** O mesmo aviso não se repete em 2 minutos (salvo a volta do cortado).
5. Os modos de fala do ADR 0018 continuam valendo antes de tudo isto; respostas a pedidos da
   pessoa não mudam.

## Consequências
- Menos voz e mais tela: quem quer o detalhe abre a página indicada no aviso.
- O estado (avisos começados, cortados e dados) é só em memória e limitado; reiniciar zera.
