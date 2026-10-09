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
- **Licença AGPL-3** (ADR 0013).
- **Piper dentro do Zé** (dependência Python, GPL-3) e a voz Cadu (CC0) baixada e conferida na
  primeira subida: primeiro som em ~150 ms, sem serviço à parte.
- **Imersivo** (Barehands, AGPL) pode vir embutido, sem dados de ninguém.
- **Memória longa pelo ai-memory** (MIT), opcional: sem ele, o Zé funciona sem memória longa.
- **Registros de funcionamento em SQLite** (`ze.db`): sessões, Foco, automações e tempos. O que o
  usuário edita (memória curta, skills no padrão `SKILL.md`) continua em arquivo.

## Próximos passos, em ordem

1. **Configuração da primeira vez no painel.** Sem perfil, o painel abre direto nela: quem sou eu
   (nome e sobre), fuso, idioma, como entrar no modelo (assinatura ou chave), chave do Deepgram,
   treinar o "Ei Zé", ai-memory e pasta dos projetos.
2. **Padrões que ainda supõem uma máquina:** microfone `omarchy_mic_fx`, integração com o Orca
   (oficina) e com o OmniRoute (baterias) como opcionais que se desligam sozinhos quando não
   existem; Omarchy detectado em vez de suposto.
3. **Instalação de um comando** (Linux): o Zé e o painel como serviço do usuário (a voz já vem
   junto), o ai-memory e o imersivo; README de quem chega.
4. **SQLite** para os registros, com migração automática dos arquivos.
5. **Revisão final** antes do primeiro envio público.
6. **VPS** sem tela e sem microfone; depois o celular.

## Em aberto

- Nome do pacote e das variáveis: o código ainda é o pacote `jarvis` e usa `JARVIS_*`; as pastas
  de dados e os serviços já se chamam `zervis`.
