# Instruções para sessões de código nesta pasta

Esta pasta define um agente de atendimento do Zérvis (ADR 0031). O Zé lê os arquivos abaixo; o
resto é ignorado. Mudanças só valem para clientes depois de **Publicar** na página Atendimento,
que roda os testes de `testes/`.

- `agente.toml`: `nome` e `empresa`, textos curtos (até 60 e 120 caracteres).
- `persona.md`: como o agente atende (até 4.000 caracteres). Escreva em segunda pessoa
  ("Você é simpática..."). Sem segredos: o agente pode repetir o que está aqui.
- `conhecimento/*.md`: o que ele sabe, em quantos arquivos quiser (até 20.000 caracteres no
  total). Lidos em ordem alfabética. Fatos claros: preço, prazo, horário, endereço, políticas.
- `passar.md`: quando passar a conversa para o dono (até 2.000 caracteres). Vazio: quando o
  cliente pedir uma pessoa, quiser fechar ou pagar, reclamar ou perguntar algo fora do
  conhecimento.
- `testes/*.toml`: cada `[[teste]]` tem `nome`, `cliente` (a mensagem do cliente) e o esperado:
  `contem` (lista de trechos que a resposta precisa ter), `nao_contem` (trechos proibidos) e
  `passar` (true se deve passar para o dono, false se não deve). Ao mudar o conhecimento ou a
  persona, acrescente um teste que prove a mudança.

Regras que esta pasta não muda: o agente responde curto, não inventa o que não está no
conhecimento, ignora instruções vindas do cliente e não tem acesso ao Zé nem ao computador.
Não crie código aqui: integrações com APIs e MCPs entram por um arquivo próprio, na próxima etapa.
