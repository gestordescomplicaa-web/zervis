# Agente de atendimento

O agente que atende seus clientes no WhatsApp pelo Zérvis. Esta pasta é o rascunho dele: edite
os arquivos (ou peça a uma sessão de código) e, na página **Atendimento** do Zé, clique em
**Publicar**. Os testes de conversa rodam, e só uma versão aprovada passa a atender clientes.

| Arquivo | O que é |
|---|---|
| `agente.toml` | Nome do agente e da empresa |
| `persona.md` | Como atender: tom, jeito, o que nunca dizer |
| `conhecimento/*.md` | O que o agente sabe: serviços, preços, horários, perguntas frequentes |
| `passar.md` | Quando passar a conversa para você (vazio: o padrão do Zé) |
| `testes/*.toml` | Conversas de teste e o que se espera de cada resposta |

As conversas com os clientes não ficam aqui: ficam na pasta privada do Zé.
