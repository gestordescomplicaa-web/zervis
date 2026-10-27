# O Zé numa VPS

Para testar o Zé num servidor Linux sem tela nem áudio. Estado em 16/10/2026: a instalação de
um comando (ADR 0034, etapa I3) ainda não existe; este é o caminho verificado até lá.

No servidor, o Zé tem o cérebro, a memória, as skills, o Foco, as sessões de código nos projetos
do servidor, as automações, os avisos e o painel. Você fala com ele pelo navegador do computador
ou pelo celular. O que depende do seu PC (microfone e alto-falante locais, janela, modo imersivo,
ações do Omarchy) não existe no servidor, e o Zé sabe disso: a persona recebe "Esta máquina".

## O que precisa

| Item | Mínimo |
|---|---|
| Servidor | Linux x86-64 ou arm64 com glibc 2.28 ou mais nova (Ubuntu 22.04 ou 24.04, Debian 12). Alpine não serve |
| Memória | 2 GB; 4 GB com sessões de código. Medido em 16/10/2026: ~0,7 GB parado, sem a voz carregada, dos quais ~0,4 GB são os dois agentes do Claude. Cada sessão de código é mais um agente |
| Disco | 3 GB livres. Medido em 16/10/2026: ~1 GB instalado (ambiente Python, modelos, LiveKit e ai-memory), mais o cache do uv |
| Acesso | SSH com chave, como um usuário comum (não root) |
| Contas | Claude (assinatura, pelo token de `claude setup-token`, ou chave de API) e Deepgram para a voz |

## 1. Preparar o servidor (uma vez, como root)

```sh
apt update && apt install -y git make curl
adduser ze
mkdir -p /home/ze/.ssh && cp ~/.ssh/authorized_keys /home/ze/.ssh/ && chown -R ze:ze /home/ze/.ssh
```

Rodar como root daria aos agentes de código acesso total ao servidor; o instalador recusa.

## 2. Instalar (como `ze`, numa sessão SSH desse usuário)

```sh
ssh ze@<servidor>
git clone https://github.com/gestordescomplicaa-web/zervis.git
cd zervis
deploy/instalar-servidor.sh
```

O repositório é público: o `git clone` não pede usuário nem token. Para atualizar depois, entre
na pasta, rode `git pull` e o instalador de novo.

O instalador confere o que precisa, instala o uv e o Go se faltarem, baixa os modelos de som,
instala o serviço `zervis` do usuário, liga o *linger* (o Zé continua depois de sair do SSH e sobe
com a máquina) e espera o painel responder. Se ele pedir, rode como root uma vez:
`loginctl enable-linger ze`.

Sem acesso do servidor ao GitHub, envie o código como pacote: no seu computador,
`git archive --format=tar.gz --prefix=zervis/ -o /tmp/zervis.tgz origin/master` e
`scp /tmp/zervis.tgz ze@<servidor>:`; no servidor, `tar xzf zervis.tgz`, `cd zervis` e o instalador.
O pacote não leva o `.git`: o instalador cria um histórico local (nada sai da máquina) e registra o
código novo a cada reinstalação. O autodesenvolvimento precisa desse histórico para trabalhar numa
cópia isolada.

Entre por `ssh ze@...`, e não por `su ze` ou `sudo -u ze`: só a sessão SSH abre o systemd do
usuário, que o serviço usa.

## 3. Abrir o painel

O instalador termina assim:

```text
Abra no navegador: https://<palavras>.trycloudflare.com
Código de primeiro acesso: ABCD-EFGH (vale 1 hora)
```

1. Abra o endereço (no computador ou no celular), digite o código e crie a senha do painel.
2. O painel abre na página Voz. Em **Acesso pelo celular → Código do autenticador**, toque em
   **Ligar**, leia o QR no aplicativo autenticador (Google Authenticator, Aegis…) e confirme.
3. Saia e entre de novo com a senha e o código. A partir daí, de qualquer aparelho, os ajustes
   (chaves, contas, autodesenvolvimento) ficam liberados.

Sem túnel SSH em nenhum momento. O endereço é HTTPS, criado pelo Cloudflare sem conta e sem abrir
porta no servidor; ele muda quando o servidor reinicia (o painel mostra o novo em Voz).

**Endereço fixo, num domínio seu.** Em Voz → Acesso de qualquer lugar → "Usar um endereço fixo":
crie um túnel no Cloudflare (Zero Trust → Networks → Tunnels → Create a tunnel, tipo
Cloudflared), cole o comando de instalação que ele mostra (sem rodar) e, em Public Hostname,
aponte o endereço (por exemplo `ze.seudominio.com.br`) para HTTP `127.0.0.1:<porta do painel>`.
O token fica num arquivo `0600` e o `cloudflared` o lê pelo `--token-file`. O endereço não muda
mais: o mesmo nome serve no PC e, depois, na VPS (mude o serviço do túnel de máquina).

Num servidor, um aparelho que entrou só com a senha pode usar o Zé e ligar o código do
autenticador, mais nada; os ajustes pedem a entrada com o código. Desligar o código e desativar o
acesso de qualquer lugar ficam só pelo túnel SSH, para ninguém tirar as proteções pelas quais
entrou. Não abra a porta 8795 na internet: o painel fala HTTP simples.

### Pelo túnel SSH (alternativa)

Se o endereço não responder (rede do servidor bloqueando o Cloudflare), o instalador mostra o
comando do túnel e o mesmo código:

```sh
ssh -N -L 8795:127.0.0.1:8795 ze@<servidor>
```

e abra `http://localhost:8795`, com a mesma porta dos dois lados. Pelo túnel, o painel trata você
como o próprio computador do Zé: tudo fica liberado. Quem tem a sua chave SSH tem o Zé.

Código vencido ou perdido: rode de novo `uv run python -m zervis.portal.primeiro_acesso` na pasta
do Zé (só gera um código novo enquanto a senha não existe).

## 4. Falar com o Zé

- **Pelo navegador (computador ou celular):** no endereço `https://….trycloudflare.com`, o botão
  "Ao vivo" liga a voz até você desligar. No celular, o QR da página Voz abre o mesmo endereço.

## 5. Cérebro e sessões de código

O Claude Code e o Codex vêm com o Zé (ADR 0035). Em **Modelos**, escolha o cérebro e dê o acesso
pelo painel, sem terminal:

- **Claude:** o token de `claude setup-token` (rodado no seu PC) ou uma chave da Anthropic.
- **Codex:** uma chave da OpenAI, em "Usar chave de API da OpenAI" (ou "Usar a das Respostas
  rápidas", se você já salvou uma lá).

Para entrar com a conta da assinatura (Claude ou ChatGPT), use **Modelos → Contas → Entrar**: o
painel mostra o link para autorizar, no PC ou no celular, e um campo para colar o código, se o
agente pedir.

Os projetos ficam no servidor (`~/projetos` por padrão).

O Go 1.27.2 é instalado sem `sudo` no espaço do usuário, a partir do pacote oficial para x86-64
ou arm64; o SHA-256 é conferido antes da extração ([checksums oficiais](https://go.dev/dl/?mode=json)).
Na primeira conexão do WhatsApp, o Zé compila o WaCalls e baixa os módulos Go. O mesmo pareamento
atende mensagens e ligações.

## Opcionais

| Para | Instale | Por quê |
|---|---|---|
| Autodesenvolvimento | Node 18 ou mais novo (Ubuntu 24.04: `sudo apt install nodejs npm`) | O `make check` confere os tipos do painel com o TypeScript |

## Conferir e manter

```sh
systemctl --user status zervis          # estado do serviço
journalctl --user -u zervis -f          # registro ao vivo
git pull && systemctl --user restart zervis   # atualizar
```

Avisos normais no registro de um servidor:

- `microfone local indisponível (... /usr/bin/parec): só a voz remota`: não há áudio local; a voz
  chega pelo navegador.
- `sem a chave do Deepgram: voz desligada`: até a chave ser salva no painel.
- `modelos de som faltando: ...`: um download falhou; o painel e o texto funcionam, e a voz volta
  depois de `uv run python -m zervis.preparar` e de reiniciar o serviço.

Se a rede do servidor bloqueia o HuggingFace (a voz Cadu vem de lá), há dois caminhos:

- copiar os modelos do seu PC, que já os tem:
  `scp -r ~/.local/share/zervis/modelos ze@<servidor>:.local/share/zervis/`
- apontar o Zé para um espelho com os mesmos arquivos: `ZE_MODELOS_URL=https://…/modelos`. A
  impressão digital de cada arquivo é conferida, então o espelho não precisa ser de confiança.

Para remover: `systemctl --user disable --now zervis`, apague
`~/.config/systemd/user/zervis.service` e, para apagar também os dados,
`~/.config/zervis`, `~/.local/share/zervis` e `~/.local/state/zervis`.
