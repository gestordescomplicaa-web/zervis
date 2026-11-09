# 0071 — O foco: voz e oficina; o resto fica como está até a 0.5.0

- Data: 09/11/2026
- Status: **Aceito** (vale até a versão 0.5.0; depois, um ADR novo revê o congelamento).

## Contexto

Em um mês o Zérvis ganhou muitas frentes: Instagram (ADR 0057), imagens reais na Imersão (0058),
pesquisa profunda e pesquisas guardadas (0059 e 0060), cérebro local (0063), ligações com recado
(0067). A análise do [plano de maturidade](../plano-maturidade.md) mostrou o custo disso: uma pessoa
só mantém o projeto, a avaliação mede 14 cenários e três módulos passam de 1.400 linhas. O que o
Zérvis faz melhor que Hermes Agent, OpenClaw, Grok Bot e Meta Muse é a voz e a condução de sessões
de código, que são os pontos 1 e 2 da [essência](../essencia.md). É o ADR da Frente 5 na Fase A.

## Decisão

1. **O núcleo é voz e oficina.** Voz: escutar, falar, a via rápida, o Ao vivo, a voz pelo
   navegador e o app de voz. Oficina: as sessões de Claude e Codex, o supervisor (ADR 0068), as
   aprovações, os avisos de fim e de falha, e o autodesenvolvimento. É o que a Frente 3 mede
   primeiro e o que recebe correção antes de tudo.
2. **Ficam, sem funções novas até a 0.5.0:** Instagram e redes sociais, a Imersão 3D, a pesquisa
   (profunda e guardadas) e o cérebro local. Recebem correção, segurança, teste e desempenho.
3. **WhatsApp, atendimento e ligações também só recebem correção** até a Fase C, quando o
   atendimento passa para a API oficial (Frente 4).
4. **O que entra nas Fases A e B:** correção de falha, segurança, teste e avaliação, desempenho,
   divisão de módulos sem mudar o comportamento, documentação e o que um item do plano pede.
   **Função nova** é o resto: ferramenta nova do cérebro, página nova no painel, integração nova
   ou opção nova de configuração que nenhum item do plano pede. Função nova só entra com um ADR
   que justifique a exceção.
5. **O autodesenvolvimento segue a mesma regra:** as propostas do diagnóstico (ADR 0025 e 0026)
   continuam a aprender, ajustar ou corrigir o que existe; pedido de função nova vai para depois
   da 0.5.0.

## Consequências

- O modelo de PR ganha a caixa "Não é função nova (ADR 0071)", e o CONTRIBUTING explica a regra a
  quem chega de fora.
- Nada sai do Zérvis: quem usa Instagram, Imersão ou pesquisa continua usando, com correções.
- Ideia nova não se perde: vira uma *issue* marcada para depois da 0.5.0.
- Na 0.5.0, um ADR novo revê a lista do item 2 com os números do placar.
