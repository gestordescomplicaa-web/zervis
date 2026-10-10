# Roteiro

O objetivo: o Zé completo no GitHub e fácil de instalar do zero, para qualquer pessoa. Ele espelha
o Hermes e o OpenClaw, só que mais enxuto, rápido e eficiente. Linux primeiro: Omarchy com o
controle completo da máquina, outro Linux (Ubuntu) com o controle reduzido e, depois, uma VPS sem
tela e sem microfone (painel, texto e, adiante, o celular). Windows fica fora por enquanto.

## Já decidido

- **Dados em três raízes XDG** (`jarvis/lugares.py`): `~/.config/zervis`, `~/.local/share/zervis`,
  `~/.local/state/zervis`.
- **"Quem sou eu"** em `<config>/perfil.json` (nome e sobre), lido por `jarvis/usuario.py`; a
  persona recebe isso no começo de cada conversa. Nenhum nome fixo no código.
- **Fuso** do sistema (`jarvis/fuso.py`), ou `JARVIS_FUSO`.
- **Voz só pelo Deepgram.** Sem a chave, o Zé não escuta (painel e teclado funcionam).
- **Acesso ao Claude** (`jarvis/cerebro/acesso.py`): token da assinatura (`claude setup-token`) ou
  chave de API colados no painel, senão o que a máquina já tem (variáveis ou login do Claude Code).
  Aplicado no ambiente do processo, vale para cérebro, via rápida, automações, sessões e revisão.
- **Licença AGPL-3** (ADR 0013).
- **Piper dentro do Zé** (dependência Python, GPL-3) e a voz Cadu (CC0) baixada e conferida na
  primeira subida: primeiro som em ~150 ms, sem serviço à parte.
- **Imersivo dentro do Zé** (ADR 0014): holograma, Núcleo e mãos em `jarvis/imersivo/`, subido
  pelo próprio Zé, com estado e manifesto nas pastas de dados.
- **Memória longa pelo ai-memory embutido** (MIT, ADR 0016): o da máquina, ou o binário oficial
  baixado e conferido pelo Zé; as sessões de código alimentam e recebem a passagem dele.
- **Registros de funcionamento em SQLite** (`ze.db`): sessões, Foco, automações e tempos. O que o
  usuário edita (memória curta, skills no padrão `SKILL.md`) continua em arquivo.

## Próximos passos, em ordem

1. **Configuração da primeira vez no painel.** Feito: sem perfil, o painel abre nela (perfil com
   nome, sobre e fuso; acesso ao Claude por assinatura ou chave; chave do Deepgram). Falta:
   **"Ei Zé" genérico** que vem junto e funciona ao instalar, com "Personalizar a ativação" opcional
   (gravação de ~4 min com a voz de quem usa), proposto como passo da configuração inicial. O "Ei
   Zé" segue interrompendo a fala do Zé; a voz do Cadu entra no treino só como exemplo negativo. Depois:
   ai-memory e pasta dos projetos.
2. **Três camadas de modelos, sem o Orca (ADR 0015):** feito: a página Modelos com um cartão
   por camada (voz rápida, cérebro, sessões de código) e o modo manutenção sobre as sessões
   próprias, e o Orca fora do núcleo (o cérebro delega pelas ferramentas `sessao_*`). Falta:
   motor Codex no cérebro e nas sessões, com troca de agente na mesma sessão (passagem de
   contexto); a conversa continua na troca de cérebro, com o ai-memory comum aos dois.
3. **Padrões que ainda supõem uma máquina:** microfone `omarchy_mic_fx` e o OmniRoute (baterias) como
   opcionais que se desligam sozinhos quando não
   existem; Omarchy detectado em vez de suposto. **Escuta sem depender de janela:** hoje o
   microfone só abre com a janela do painel (modo aplicativo) aberta, e a classe da janela é a
   mesma de qualquer Zé na máquina; vira um interruptor "Escuta" no painel e um atalho. O painel
   segue como página web, instalável como aplicativo (manifesto).
4. **Instalação de um comando** (Linux): o Zé e o painel como serviço do usuário (a voz já vem
   junto), o ai-memory e o imersivo; README de quem chega.
5. **SQLite** para os registros, com migração automática dos arquivos.
6. **Revisão final** antes do primeiro envio público (inclui os documentos antigos que ainda
   falam do Orca e do JARVIS: visão, conceitos, reaproveitamento, plano da oficina).
7. **VPS** sem tela e sem microfone; depois o celular.

## Em aberto

- Nome do pacote e das variáveis: o código ainda é o pacote `jarvis` e usa `JARVIS_*`; as pastas
  de dados e os serviços já se chamam `zervis`.
