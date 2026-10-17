<div align="center">
  <img src=".github/ze-logo.png" width="112" alt="Logo do Zé, o assistente Zérvis">
  <h1>Zérvis</h1>
  <p><strong>Seu assistente pessoal, rodando no seu Linux.</strong></p>
  <p>Converse por voz ou pelo painel. Organize tarefas, memória e automações.<br>Trabalhe nos seus projetos com agentes Claude e Codex.</p>
  <p><a href="docs/vps.md">Começar pela VPS</a> · <a href="docs/roteiro.md">Ver o roteiro</a> · <a href="CONTRIBUTING.md">Contribuir</a></p>
  <p><a href="LICENSE"><img alt="Licença AGPL-3.0-or-later" src="https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0--or--later-45c6d8?style=flat-square"></a></p>
</div>

> **Em desenvolvimento.** O Zérvis é código aberto e já tem um guia para testar numa
> [VPS](docs/vps.md); a instalação simplificada no PC ainda está no roteiro.

## O que o Zé faz

- **Conversa com você:** por voz ("Ei Zé") ou pelo painel local.
- **Cuida do trabalho recorrente:** organiza contexto e memória, oferece skills iniciais opcionais,
  aprende procedimentos com sua aprovação e roda automações em segundo plano.
- **Acompanha seus projetos:** abre sessões com agentes Claude e Codex no seu computador.

Seus dados ficam na sua máquina. O Zé não presume seu nome, fuso ou caminhos; ações que podem
enviar, aprovar ou apagar falham fechadas quando há dúvida.

## Princípios

1. **Seu, na sua máquina.** Os dados ficam em pastas suas (padrão XDG), fora do repositório.
   Nada de nome, fuso ou caminho de alguém fixo no código: o que é seu vem da configuração.
2. **Só fala quando faz sentido.** Responde ao que você pede, avisa o que você delegou e o que
   precisa da sua decisão.
3. **Cérebro trocável.** Claude pela assinatura (Agent SDK), Codex pela conta cadastrada, chaves da Anthropic, da OpenAI ou do
   OpenRouter, ou qualquer proxy no formato OpenAI, atrás de uma interface única.
4. **Aprende com aprovação.** Memória e skills evoluem, mas o que o próprio Zé propõe passa por
   você antes de valer.
5. **Falhar fechado.** Na dúvida, não envia, não aprova, não apaga, e diz por quê.

## Onde ficam os seus dados

| Raiz | Padrão | O que tem |
|---|---|---|
| Configuração | `~/.config/zervis` | `config.toml`, `perfil.json` (quem é você), chaves (0600), conectores MCP |
| Dados | `~/.local/share/zervis` | memória curta, skills, conversas, linha do tempo, Foco, sessões, automações |
| Estado | `~/.local/state/zervis` | o momento: status, tempos, consumo, avisos |

`JARVIS_PERFIL=<nome>` usa outro conjunto de pastas (`zervis-<nome>`); `JARVIS_RAIZ=<pasta>` põe as
três dentro de uma pasta só. O fuso vem do sistema (ou de `JARVIS_FUSO`).

## Instalar num servidor (VPS)

Num Ubuntu 24.04 ou parecido, com um usuário comum (não root) e Git, Make e curl instalados:

```sh
git clone https://github.com/gestordescomplicaa-web/zervis.git
cd zervis && deploy/instalar-servidor.sh
```

O instalador prepara tudo, deixa o Zé rodando como serviço e termina com um endereço HTTPS e um
código de primeiro acesso: abra o endereço, crie a senha e ligue o código do autenticador. Sem túnel
SSH. O passo a passo e o login do Claude e do Codex estão em [docs/vps.md](docs/vps.md).

## Rodar (desenvolvimento)

Para desenvolvimento: Linux, Python 3.12+, Node.js 22+ e [uv](https://docs.astral.sh/uv/).

```sh
uv sync
npm ci
make check                 # formatação, lint, tipos e testes
uv run python -m jarvis    # sobe o Zé; o painel abre em http://127.0.0.1:8795/
```

Na primeira subida, o Zé baixa os modelos de som e a voz (Cadu, 63 MB) e confere o SHA-256 de
cada um, e o painel abre na configuração inicial: perfil, acesso ao Claude (assinatura ou chave de
API) e a chave do Deepgram para a voz. Sem a palavra de ativação treinada, ele atende pelo painel e
pelo teclado. A fala sai pelo Piper, que vem junto e roda dentro do Zé (primeiro som em ~150 ms).
`make instalar` instala o serviço do systemd do usuário e o atalho "Zérvis" no menu de aplicativos
(`PORTA=8796 make instalar` para outra porta).

Plataformas: Linux primeiro. O controle completo da máquina é no Omarchy; outros Linux têm o
controle reduzido.

As personas ficam em `jarvis/persona/` e acompanham o pacote instalado. Excluir uma sessão ativa
encerra o agente antes de remover a conversa; os arquivos do projeto ficam. Uma sessão com cópia
isolada só pode ser excluída depois de preservar as alterações locais, inclusive arquivos novos
ou ignorados pelo Git. A branch com os commits continua no projeto.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/roteiro.md](docs/roteiro.md) | Para onde o projeto vai, em ordem |
| [docs/vps.md](docs/vps.md) | Testar o Zé numa VPS: instalação, acesso pelo túnel SSH e pelo celular |
| [docs/conceitos.md](docs/conceitos.md) | Conversa, voz, foco, sessão, tarefa, automação, memória e skill |
| [docs/01-visao-e-requisitos.md](docs/01-visao-e-requisitos.md) | O que o Zé deve fazer e o que fica de fora |
| [docs/04-arquitetura.md](docs/04-arquitetura.md) | Componentes, estado, fluxos e contratos |
| [docs/06-qualidade.md](docs/06-qualidade.md) | Regras de engenharia (obrigatórias) |
| [docs/imersivo/](docs/imersivo/) | O modo imersivo: holograma, Núcleo, mãos e desempenho |
| [docs/07-sistema-omarchy.md](docs/07-sistema-omarchy.md) | O Omarchy como parte do núcleo: ações, eventos e risco |
| [docs/03-reaproveitamento.md](docs/03-reaproveitamento.md) | O que vem de outros projetos, e com que licença |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Código e modelos de terceiros |

## Licença

[AGPL-3.0-or-later](LICENSE). A voz usa o [Piper](https://github.com/OHF-Voice/piper1-gpl)
(GPL-3.0) e a voz Cadu (CC0); outros componentes de terceiros estão em
[THIRD_PARTY.md](THIRD_PARTY.md).

A voz rápida pode usar **Automático**, aproveitando as contas Claude e Codex cadastradas em
**Contas**. Codex também pode ser escolhido como cérebro em **Modelos**. A troca automática só
ocorre antes de qualquer resposta ou ferramenta; OpenAI API usa uma chave separada do login
Codex. Detalhes em [ADR 0020](docs/adr/0020-contas-na-voz-e-no-cerebro.md).
