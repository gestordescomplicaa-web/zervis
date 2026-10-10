# Zérvis: o Zé, um assistente pessoal local

O Zé é um assistente pessoal que roda na sua máquina Linux. Você conversa com ele por voz ("Ei Zé")
ou pelo painel. Ele lê e opera o computador, tem memória própria, aprende skills com o uso, roda
automações em segundo plano e manda agentes de código trabalharem nos seus projetos.
Inspirado no Hermes e no OpenClaw, mas mais enxuto, rápido e eficiente.

> **Estado:** em desenvolvimento, ainda sem instalação de um comando. O caminho até lá está em
> [docs/roteiro.md](docs/roteiro.md).

## Princípios

1. **Seu, na sua máquina.** Os dados ficam em pastas suas (padrão XDG), fora do repositório.
   Nada de nome, fuso ou caminho de alguém fixo no código: o que é seu vem da configuração.
2. **Só fala quando faz sentido.** Responde ao que você pede, avisa o que você delegou e o que
   precisa da sua decisão.
3. **Cérebro trocável.** Claude pela assinatura (Agent SDK), chaves da Anthropic, da OpenAI ou do
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

## Rodar (desenvolvimento)

Precisa de Linux, Python 3.12+ e [uv](https://docs.astral.sh/uv/).

```sh
uv sync
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

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/roteiro.md](docs/roteiro.md) | Para onde o projeto vai, em ordem |
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
