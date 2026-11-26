# 0142 — Dispensar no sino, e o link para fora abre no navegador de quem usa

- Data: 25/11/2026
- Status: **Aceito** (pedido de quem usa, 25/11/2026).
- Ajusta os ADRs [0133](0133-inicio-precisa-de-voce-e-avisos.md) (o "Precisa de você") e
  [0139](0139-historico-datas-e-sino-com-lidas.md) (as marcas do sino).

## Contexto

Em 25/11/2026 o sino mostrava um "Responder" a um contato do WhatsApp cuja mensagem não
pedia resposta, e não havia como tirá-lo: o "Marcar todas como lidas" só apaga o ponto, e o item do
"Precisa de você" fica até ser resolvido (o lead, até 24 horas).

E "Responder" abria o WhatsApp no lugar do Zérvis. No Início, o item era um link comum (a própria
janela ia para o wa.me); no sino, a guia nova abria no perfil do Zé. O painel no PC é uma janela
de aplicativo (`chromium --app`, `deploy/abrir-painel.sh`), sem abas nem botão de voltar, e o perfil
do Zé não tem as contas de quem usa (o WhatsApp Web).

## Decisão

1. **Dispensar (×) em cada item do "Precisa de você"**, menos na aprovação do WhatsApp, que se
   resolve aprovando ou negando. O lead recebe o "já vi" de sempre (para de lembrar, também no
   celular, e o contato não vira lead de novo por 6 horas); os outros itens ganham a marca
   `dispensado` (`avisos/lidos.py`) e saem da lista, no sino, no Início e na voz, até mudar (a
   chave muda quando o item muda).
2. **O link para fora abre no navegador de quem usa.** Pelo painel no PC (o endereço é o
   127.0.0.1), um clique num link de outro endereço vai ao Zé (`link/abrir`), que o abre com o
   `xdg-open` numa guia nova do navegador padrão, por `systemd-run` (reiniciar o Zé não fecha o
   navegador). O wa.me vira a conversa no WhatsApp Web. Fora do PC (a VPS, o celular), o link
   abre numa guia nova do próprio navegador; nunca no lugar do painel.

## Consequências

- Vale para todos os links para fora do painel ("Ver no Maps", "Obter chave de API"), não só o
  WhatsApp.
- Sem tela ou sem `xdg-open` no computador do Zé, o pedido falha e o painel abre a guia sozinho.
