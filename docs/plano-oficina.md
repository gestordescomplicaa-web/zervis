# Plano — a oficina própria do Zé (09/10/2026)

Pedido do usuário: o Zé não pode depender do Orca para codificar, porque quem instalar o Zé
não vai ter o Orca. O Orca (MIT) não tem agente de código: ele roda os dos outros (Claude Code,
Codex, OpenCode) em worktrees e terminais, com orquestração. O Hermes (MIT) cria subagentes
filhos com objetivo autossuficiente, sem delegação recursiva, com limite de paralelos, worktree
opcional, correção de rumo e só o resumo de volta. O Zé já carrega o Claude Code inteiro (o
Agent SDK do cérebro), e o Codex roda sem tela pelo `codex exec`, ambos pelo login de
assinatura ou por chave. Então a oficina passa a ser do Zé, com motores trocáveis.

Complementa a [ADR 0006](adr/0006-orca-continua-como-oficina.md): o Orca deixa de ser
requisito e vira um dos motores, para quem já usa e quer os terminais ao vivo.

## Conceito: sessões

Como os "bots" do Hermes: cada **sessão** é um agente de código com nome, uma **pasta** (o
projeto), um motor (Claude ou Codex) e a sua conversa. O usuário conversa com cada uma pelo
painel ou pela voz ("pede para a sessão do Ligatia rodar os testes"); o Zé avisa quando ela
termina. Opcionalmente a sessão trabalha numa **cópia isolada** (git worktree, branch
`ze/<id>`), para não mexer no projeto até ele aprovar.

Guardado em `~/.local/share/zervis/sessoes/<id>/`: `sessao.json` (nome, pasta, motor, modelo,
estado, worktree, a sessão do SDK para continuar) e `mensagens.jsonl` (o que ele pediu, o que o
agente disse, as ferramentas usadas, o fim). Nada se apaga sozinho.

## Regras (do Hermes e do Orca)

- O pedido vira uma tarefa autossuficiente; o agente não delega de novo.
- No máximo três sessões trabalhando ao mesmo tempo.
- O agente edita só dentro da pasta da sessão (Claude Code com `acceptEdits` e o diretório de
  trabalho); comandos passam por uma lista de proibidos (sudo, push, apagar fora da pasta,
  formatar disco...). O CLAUDE.md do projeto vale (`setting_sources=["project"]`).
- Parar a qualquer momento; continuar depois (a sessão do SDK é retomada com `resume`).
- No fim: resumo de uma frase falado pelo Zé, o que mudou (`git diff --stat`) e, na cópia
  isolada, a branch para revisar.

## Fases

1. **Núcleo das sessões e motor Claude** (`jarvis/oficina/sessoes.py`): criar, listar,
   conversar, parar, worktree opcional, política de comandos, aviso ao terminar.
2. **Painel: aba Sessões** no estilo da referência do Hermes: lista à esquerda (nome, pasta,
   último recado, estado), conversa à direita e a caixa de mensagem com a pasta embaixo; "+"
   cria uma sessão escolhendo a pasta e o motor.
3. **Pela voz**: ferramentas do cérebro para criar, mandar, ver e parar sessões (servidor MCP
   próprio, montado no laço, como o Foco).
4. **Motor Codex** (`codex exec --json`, login do ChatGPT ou chave).
5. **Aprovar e juntar**: da cópia isolada para o projeto, com o diff na tela.
6. **Memória**: cada sessão publicada no ai-memory (projeto da pasta), para o Zé e os próximos
   agentes lembrarem do que já foi feito; o diferencial do Zé.
7. **Orca como motor opcional**, pela CLI de hoje.

Depois: o painel de arquivos (ver e anexar documentos das pastas).
