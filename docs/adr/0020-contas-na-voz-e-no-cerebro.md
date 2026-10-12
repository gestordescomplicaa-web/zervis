# 0020 — Contas dos agentes na voz e no cérebro

**Estado:** aceito. **Data:** 12/10/2026.

A voz rápida e o cérebro usavam Claude mesmo quando havia outra conta cadastrada. Um limite
retornado como `is_error=true` com subtipo `success` virava uma falha genérica. A opção OpenAI
na voz era a API por chave; não aproveitava o login do Codex.

## Decisão

- Codex disponível na voz rápida e no cérebro pelo `codex app-server` oficial, com `CODEX_HOME`
  da conta cadastrada. Modelo vazio usa o padrão da conta. OpenAI API continua com chave própria.
- Voz em **Automático** tenta as contas cadastradas: Codex primeiro, depois Claude; dentro de
  cada agente, a conta selecionada primeiro. Mantém a conta que respondeu durante a conversa.
- O cérebro tem alternativas entre contas cadastradas quando encontra limite, acesso inválido
  ou indisponibilidade. Só troca antes de produzir texto ou chamar qualquer ferramenta.
- A troca leva até seis pares de pergunta/resposta da conversa atual. Interrupção não inicia
  uma alternativa. Uma resposta parcial nunca é repetida em outro motor.
- Ferramentas do Codex são os conectores MCP publicados pelo Zérvis, com a política de aprovação
  existente. O app-server reserva o prefixo `mcp__`; os nomes públicos usam `ze__`, traduzidos
  internamente antes da autorização. Ferramentas nativas de shell, arquivos e agentes ficam
  desabilitadas; aprovações nativas recebidas são recusadas. Não há paridade das ferramentas
  nativas WebSearch/WebFetch do Claude: no Codex, essas capacidades dependem de conectores.
- O transporte usa stdio, sem porta de rede, e threads efêmeras. O consumo informado pelo Codex
  é normalizado para o registro existente, sem contar o cache duas vezes.
- A primeira resposta dos motores Codex/Automático tem pelo menos 30 segundos de prazo para
  permitir autenticação e troca de conta; motores HTTP conservam o prazo configurado.

## Verificação

Testes cobrem o limite real do Claude, alternativas, contexto, ausência de repetição após ação
ou texto, isolamento de eventos por conversa e autorização com um servidor MCP real em memória.
Protocolo conferido no schema gerado pelo CLI 0.162.1. Teste real de pergunta simples respondeu
pela conta alternativa cadastrada; a conta padrão falhou ao iniciar. A ferramenta de diagnóstico retornou o código sintético esperado, com uma chamada MCP real.
O motor Automático passou pela conta inválida e respondeu em 2,73 s até o primeiro texto
(2,99 s no total, em um teste); isso não é garantia de latência. Limites de todos os
provedores continuam podendo impedir a resposta; a interface informa limite ou acesso inválido.

Referências: [app-server](https://developers.openai.com/codex/app-server) e
[autenticação](https://developers.openai.com/codex/auth).
