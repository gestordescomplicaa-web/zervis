# 0096 — A imagem Docker para a VPS

- Data: 17/11/2026
- Status: **Em validação** (a CI `imagem` sobe a imagem com o volume vazio; falta uma VPS de
  verdade).

## Contexto

O plano de maturidade (Frente 4) pede uma imagem Docker para a VPS, e a Frente 2 espera dela o
contêiner das sessões de código: na VPS, uma sessão roda como o mesmo usuário do Zé e alcança a
casa dele e as chaves do servidor. O ADR 0034 (ponto 15) já tinha decidido o formato: opcional,
ao lado do instalador, base glibc (Debian), `--init`, os dados em volume e só o papel de Central.

O Zé foi feito para o systemd do usuário, mas três peças já tinham o caminho sem ele, pensado
para contêiner: o túnel do Cloudflare, a Central do atendimento e o supervisor das sessões
(ADR 0068) sobem como processos filhos quando não há `systemd-run`. Faltavam o comando `zervis`,
a página de Atualizações e o primeiro acesso, que reiniciam ou atualizam pelo systemctl.

## Decisão

1. **A imagem** (`Dockerfile`, `compose.yaml`): Debian 13 slim, uv 0.11.32 (o mesmo do
   instalador), o Python e o ambiente em `/opt`, o Go do WhatsApp conferido pelo SHA-256 na
   construção, e o mesmo histórico Git local que o instalador cria num pacote sem `.git`. Um
   usuário comum (`ze`, UID 1000), o `tini` como processo 1 (recolhe os zumbis das sessões,
   ADR 0034, D18), sem capacidades e com `no-new-privileges`.
2. **Um volume só, a casa do usuário** (`/home/ze`): configuração, dados, estado, os logins do
   Claude e do Codex e os projetos. Recriar o contêiner não perde nada. Os modelos de som, o
   Codex e o resto que o Zé baixa ao subir vão para o volume na primeira subida.
3. **A imagem se declara** (`ZERVIS_CONTEINER=1`), sem adivinhar pelo cgroup
   (`zervis/conteiner.py`). Com ela:
   - `zervis doctor` e `status` olham o painel em vez do systemctl, e o início automático é a
     política `restart: unless-stopped` do Docker;
   - `zervis update`, `logs` e `uninstall` dizem o comando do Docker;
   - a página de Atualizações não oferece o que não dá para aplicar ("Esta instalação é
     atualizada pelo Docker, no servidor."). Atualizar é `git pull` e
     `docker compose up -d --build`, com os dados no volume.
4. **O primeiro acesso sem reiniciar.** Ao subir, o Zé só abre o túnel com a senha ou com um
   convite válido. Enquanto não há senha, a entrada do contêiner liga o acesso de qualquer
   lugar e cria um convite antes de virar o Zé. Depois,
   `docker compose exec zervis python -m zervis.portal.primeiro_acesso` cria o convite que
   mostra e espera o endereço, sem reiniciar nada.
5. **O painel não sai numa porta.** Ele escuta em `127.0.0.1` dentro do contêiner, e o acesso é
   pelo endereço seguro, que sai de dentro. Sem o Cloudflare, o contêiner sobe na rede do
   servidor (`deploy/conteiner/rede-do-servidor.yaml`) e vale o túnel SSH de sempre.
6. **A prova** (`.github/workflows/imagem.yml`): a imagem construída do zero, com o volume
   vazio, fica de pé, passa no `doctor` (serviço, painel, modelos, Go, disco), entrega o
   endereço e o código do primeiro acesso, e guarda os dados no volume depois de reiniciar.

## Consequências

- As sessões de código ficam presas no contêiner: a casa, as chaves e o resto do servidor ficam
  fora. Dentro dele, uma sessão ainda alcança os dados do Zé no volume, porque o bubblewrap
  (ADR 0074) não cria o espaço isolado sem as capacidades que o contêiner não tem. Separar a
  sessão dos dados do Zé dentro do contêiner é o próximo passo da Frente 2.
- A imagem é construída do repositório, no servidor. Publicar a imagem pronta (no GitHub
  Container Registry, a cada versão) fica para depois.
- Sem Chromium na imagem: os posts do Instagram (ADR 0093) e a leitura de páginas pelo navegador
  ficam indisponíveis no contêiner.
- O autodesenvolvimento trabalha na cópia do código dentro do contêiner: o que ele aplica some
  ao reconstruir a imagem, a menos que vire PR.
