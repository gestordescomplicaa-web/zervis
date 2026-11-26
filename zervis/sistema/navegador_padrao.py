"""Abrir um link no navegador de quem usa, numa guia nova, pelo painel no PC (ADR 0142).

O painel abre numa janela própria (`--app`, com o perfil do Zé, `deploy/abrir-painel.sh`): um link
para fora aberto ali vira uma janela desse perfil por cima do Zérvis, sem as abas e sem as contas
de quem usa (o WhatsApp Web, o Google). Pelo painel no PC, o link vai ao navegador padrão do
sistema (`xdg-open`). Fora de um PC com tela (a VPS, o celular), o painel abre como sempre.

O navegador sobe por `systemd-run`, fora do serviço do Zé: reiniciar o Zé não fecha o navegador.
"""

import os
import re
import shutil
import subprocess
from urllib.parse import urlsplit


class LinkErro(ValueError):
    """Mensagem curta, pronta para a tela."""


_TELEFONE = re.compile(r"^/(\d{8,15})/?$")


def no_computador(url: str) -> str:
    """O endereço como abre melhor no computador: a conversa do WhatsApp no WhatsApp Web, sem a
    página do wa.me que pergunta se é o app ou a web."""
    partes = urlsplit(url)
    achado = _TELEFONE.match(partes.path)
    if partes.netloc.lower() in ("wa.me", "www.wa.me") and achado:
        return f"https://web.whatsapp.com/send?phone={achado[1]}"
    return url


def validar(url: str) -> str:
    partes = urlsplit(str(url or "").strip())
    if partes.scheme not in ("http", "https") or not partes.netloc or len(url) > 2000:
        raise LinkErro("Link inválido.")
    return partes.geturl()


def abrir(url: str) -> str:
    """Abre no navegador padrão e devolve o endereço aberto. Sem tela ou sem `xdg-open`:
    LinkErro (o painel abre por conta própria)."""
    alvo = no_computador(validar(url))
    xdg, systemd_run = shutil.which("xdg-open"), shutil.which("systemd-run")
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")) or not xdg:
        raise LinkErro("Sem navegador neste computador.")
    comando = [xdg, alvo]
    if systemd_run:
        comando = [systemd_run, "--user", "--collect", "--quiet", "--", *comando]
    try:
        subprocess.run(comando, capture_output=True, timeout=10, check=True)  # noqa: S603
    except (OSError, subprocess.SubprocessError) as erro:
        raise LinkErro("Não foi possível abrir o navegador.") from erro
    return alvo
