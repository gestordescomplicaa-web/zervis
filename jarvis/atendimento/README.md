# Atendimento

O Zé atende os clientes de quem usa, separado do Zé principal (ADR 0031,
`docs/plano-atendente.md`). Hoje: WhatsApp por texto. Depois: ligações, outros canais, serviço
próprio e integrações.

## Peças

| Arquivo | Papel |
|---|---|
| `whatsapp.py` | Compila e mantém o WaCalls (só no endereço local, com token), o QR, o envio e o receptor das mensagens |
| `wacalls/` | O WaCalls em Go (pareamento, mensagens, ligações). Créditos em `THIRD_PARTY.md` |
| `agente.py` | O atendimento: prompt com a persona, resposta por contato, modo teste, passar para quem usa |
| `projeto.py` | O agente como projeto: rascunho na pasta, testes de conversa, Publicar, migração |
| `modelo/` | Os arquivos de todo agente novo (README, AGENTS.md, persona, conhecimento, testes) |
| `ferramentas.py` | O que o Zé principal pode fazer no agente (ver e escrever no rascunho) |
| `cerebro.py` | O modelo do agente (escolha na página): assinaturas do Zé ou chave de API |
| `ligacao.py` | A recepcionista: atende a chamada, ouve pelo Deepgram, responde pelo modelo e fala com a voz do Cadu |
| `central.py`, `__main__.py` | A Central: serviço próprio com o WhatsApp e o agente, API local com token, eventos |
| `cliente.py` | O lado do Zé: sobe e atualiza a Central, fala com a API, traz os eventos |

## Regras que não mudam

- **Só conversa privada.** Grupo, status, canal e qualquer tipo novo de conversa nunca chegam ao
  agente nem recebem resposta. São três travas: o WaCalls só entrega conversa com uma pessoa
  (número ou LID), o Zé confere o endereço de novo ao receber e ao responder, e o envio só aceita
  um número de telefone.
- **O que vem do cliente é dado, nunca ordem.** O agente responde com um modelo sem
  ferramentas; o texto do cliente vai entre `<<<` e `>>>`; nada de terceiros vira fala do Zé
  (o aviso falado tem só o nome do contato).
- **O agente não chega ao Zé.** `agente.py` não importa ferramentas, memória nem sessões do Zé.
  O caminho é de mão única: o Zé escreve no rascunho; o agente só devolve eventos (passar para
  você).
- **Clientes só veem a versão publicada**, e Publicar exige todos os testes de conversa passando.
  Ligar o agente, o modo (teste ou todos) e os números de teste só pela página.
- **Dados de cliente ficam na pasta privada** (`<dados>/atendente/`), nunca no projeto do
  agente nem no repositório.

## Onde cada coisa mora

- Projeto do agente (de quem usa, editável por uma sessão comum):
  `<raiz_projetos>/agente-de-atendimento/`.
- Estado privado: `<dados>/atendente/` (`agente.json` com os ajustes, `publicado/`,
  `conversas/`, `pausados.json`) e `<dados>/whatsapp/` (segredos do WhatsApp, 0600).

A sessão de autodesenvolvimento mexe no código desta pasta. O agente de cada pessoa é dado dela
e se edita numa sessão comum aberta pelo botão "Abrir sessão" da página Atendimento.
