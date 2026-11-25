# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary:** quem roda o Zé no próprio computador (ou servidor) e trabalha com ele o dia todo:
  um gestor ou consultor de automação e IA que atende clientes pelo WhatsApp, monta integrações,
  fluxos e agentes, prospecta e faz marketing. Usa o painel **no PC, aberto enquanto trabalha, com
  o celular de apoio** para conferir e aprovar rápido (confirmado em 25/11/2026).
- **Também:** outros gestores e consultores que instalam o Zé do zero (projeto aberto, AGPL).
  O desenho serve primeiro a quem usa hoje, pensado para quem instalar.

## Product Purpose

O Zérvis ("o Zé") é um assistente de voz de trabalho: fala, ouve e avisa; a tela acompanha. Ele
conduz trabalho real: sessões de código com Claude e Codex, o atendimento do WhatsApp (leads), a
prospecção de empresas, o marketing (blog, Reels, Instagram), os grupos das empresas atendidas e
aparelhos da casa (câmera, impressora, TV). Sucesso é a pessoa delegar pela voz e só entrar nas
decisões.

## Positioning

Voz em primeiro lugar ("Ei Zé", o modo Live como uma ligação, o app Zé Voz com a tela
bloqueada), rodando na máquina e nas contas de quem usa, com o sim da pessoa antes de tudo que tem
efeito, e a Imersão em holograma. Os vizinhos (Hermes, OpenBot, Grok Bot) giram em torno de chat,
agentes e administração; nenhum é de voz primeiro.

## Operating Context

- O que mais se faz no painel (confirmado): **conversar com o Zé**, **acompanhar e aprovar** o que
  ele fez ou espera o sim (prospecção, leads, PRs, vídeos, posts) e **acompanhar as sessões de
  código** (o terminal dos agentes). Configurar é secundário.
- A voz está sempre à mão: Silencioso, Normal e Live; conectar a voz e falar de qualquer página.
- Acesso de qualquer lugar pelo túnel, com senha e código do autenticador; no celular pelo
  navegador; a voz no celular também pelo app Zé Voz (Android).

## Capabilities and Constraints

- Painel em JavaScript (módulos do navegador, tipos conferidos pelo `tsc`), HTML e CSS, sem
  framework nem etapa de compilação; abertura abaixo de 130 KB (teste). 28 páginas e a Imersão.
- **A Imersão** (o Zé 3D em holograma, outro servidor) continua exatamente como está.
- **O app Zé Voz** e o canal de voz não podem quebrar (`tests/test_protocolo_do_app.py`).
- As funções de cada página ficam (`tests/test_painel_contratos.py`); toda página tem uma
  ferramenta para o Zé ler o estado dela (ADR 0128).
- Ação com efeito pede o sim; tudo o que o Zé executa fica na Atividade.
- Texto em português, linguagem de produto: títulos pelo que a função é, estado em uma ou duas
  palavras, mensagens curtas e factuais, sem tom coloquial na tela (CLAUDE.md).

## Brand Commitments

- Nome Zérvis, o assistente "Zé"; o logo do macaco ciano (`.github/ze-logo.svg`).
- Escuro com o ciano `#46d9de`, como o painel de hoje e o app Zé Voz.
- A linguagem do estado: respira pronto, ondas ouvindo, arco pensando, pulso falando, âmbar
  esperando o sim (o ícone do painel e o centro do app).

## Evidence on Hand

- Dados de quem usa nunca aparecem em referências nem em testes: os exemplos vêm de
  `tests/painel_respostas.json` ou são fictícios e marcados como exemplo.

## Product Principles

1. Voz primeiro; a tela acompanha e nunca é o único caminho.
2. Quanto mais o Zé faz, menos a tela pede da pessoa: o que espera o sim vai até ela.
3. Nada com efeito sem o sim; tudo registrado.
4. Produto, não protótipo: consistente, objetivo, sem enfeite.
5. De quem usa: roda no computador dela, com as contas dela.
