"""Acesso pelo celular (plano da voz remota, etapa 2): o painel e a sala de voz pela rede privada
do Tailscale, sem nada aberto na internet.

O `tailscale serve` publica o painel em `https://<máquina>.<rede>.ts.net` (certificado válido: o
navegador do celular só libera o microfone em HTTPS) e a sinalização da sala de voz na porta 8443
do mesmo nome. A mídia da voz vai direto pelo endereço da máquina na rede privada (100.x). Só os
aparelhos da conta Tailscale de quem usa alcançam esses endereços.

O Zé só liga e desliga o `serve` quando a pessoa pede (Voz > Acesso pelo celular); a instalação e
o login do Tailscale são da pessoa (no Omarchy, `omarchy-install-service-tailscale`).
"""

import ipaddress
import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
PORTA_PAINEL = 443
PORTA_VOZ = 8443
PORTA_MIDIA = 7882  # UDP do LiveKit: o áudio chega direto, não pelo `serve`
REGRAS_UFW = Path("/etc/ufw/user.rules")
COMANDO_FIREWALL = (
    f"sudo ufw allow in on tailscale0 to any port {PORTA_MIDIA} proto udp comment 'Zervis voz'"
)
# Interfaces que não são a rede de casa (contêineres, pontes, a própria VPN).
VIRTUAIS = ("lo", "tailscale", "docker", "br-", "veth", "virbr", "wg", "tun")


class RemotoErro(ValueError):
    pass


@dataclass(frozen=True)
class Rede:
    instalado: bool = False
    conectado: bool = False
    nome: str = ""  # omarchy.tail1234.ts.net
    ip: str = ""  # 100.x.y.z
    ativo: bool = False  # o painel publicado pelo `serve`
    firewall: str = ""  # o comando que libera o áudio, se um firewall o estiver barrando
    casa: str = ""  # o endereço do PC na rede de casa (o celular no mesmo Wi-Fi fala por ele)

    @property
    def endereco(self) -> str:
        return f"https://{self.nome}" if self.nome else ""

    def para_tela(self) -> dict[str, Any]:
        return {**asdict(self), "endereco": self.endereco}


def _tailscale(*args: str, espera_s: float = 10.0) -> subprocess.CompletedProcess[str]:
    programa = shutil.which("tailscale") or "/usr/bin/tailscale"
    return subprocess.run(  # noqa: S603 (o tailscale da máquina, argumentos montados aqui)
        [programa, *args], capture_output=True, text=True, timeout=espera_s, check=False
    )


def _json(*args: str) -> dict[str, Any]:
    try:
        r = _tailscale(*args, "--json")
        dados = json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def rede(porta_painel: int) -> Rede:
    """Como está o Tailscale nesta máquina e se o painel já está publicado nele."""
    if shutil.which("tailscale") is None:
        return Rede()
    status = _json("status")
    eu = status.get("Self") or {}
    if status.get("BackendState") != "Running" or not eu.get("DNSName"):
        return Rede(instalado=True)
    nome = str(eu["DNSName"]).rstrip(".")
    ip = next((str(i) for i in eu.get("TailscaleIPs") or [] if "." in str(i)), "")
    destino = f"127.0.0.1:{porta_painel}"
    web = (_json("serve", "status").get("Web") or {}).get(f"{nome}:{PORTA_PAINEL}") or {}
    ativo = any(destino in str(h.get("Proxy", "")) for h in (web.get("Handlers") or {}).values())
    local = rede_local()
    return Rede(
        instalado=True,
        conectado=True,
        nome=nome,
        ip=ip,
        ativo=ativo,
        firewall=firewall(local[1] if local else ""),
        casa=local[0] if local else "",
    )


def rede_local(saida: str | None = None) -> tuple[str, str] | None:
    """O endereço do PC na rede de casa e a faixa dela ("192.168.0.6", "192.168.0.0/24").

    O Chrome do Android não usa a VPN do Tailscale para o áudio das chamadas (WebRTC): ele só
    oferece o endereço do Wi-Fi. Com o celular no mesmo Wi-Fi, o áudio vai por esta rede
    (teste de 12/10/2026). Fora de casa, o caminho é o áudio dentro do HTTPS (plano da voz
    remota)."""
    if saida is None:
        try:
            r = subprocess.run(
                ["/usr/bin/ip", "-4", "-o", "addr", "show", "scope", "global"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        saida = r.stdout
    for linha in saida.splitlines():
        partes = linha.split()
        if len(partes) < 4 or partes[1].startswith(VIRTUAIS) or partes[2] != "inet":
            continue
        interface = ipaddress.ip_interface(partes[3])
        if interface.ip.is_private:
            return str(interface.ip), str(interface.network)
    return None


def firewall(faixa_casa: str = "", regras: Path = REGRAS_UFW) -> str:
    """O ufw (padrão no Omarchy e comum no Ubuntu) barra o áudio da voz que chega de fora;
    devolve o comando que libera a porta só no Tailscale e na rede de casa, ou vazio."""
    if shutil.which("ufw") is None or not regras.is_file():
        return ""
    try:
        texto = regras.read_text()
    except OSError:
        return ""
    if "### tuple ###" not in texto:  # sem regras do usuário: ufw nunca configurado
        return ""
    regras_midia = [
        linha
        for linha in texto.splitlines()
        if f"--dport {PORTA_MIDIA}" in linha and "-p udp" in linha and "ACCEPT" in linha
    ]
    faltam = []
    if not any("tailscale0" in linha for linha in regras_midia):
        faltam.append(COMANDO_FIREWALL)
    if faixa_casa and not any(f"-s {faixa_casa}" in linha for linha in regras_midia):
        faltam.append(
            f"sudo ufw allow from {faixa_casa} to any port {PORTA_MIDIA} proto udp "
            "comment 'Zervis voz em casa'"
        )
    return " && ".join(faltam)


def _serve(porta: int, alvo: str) -> None:
    r = _tailscale("serve", "--bg", f"--https={porta}", alvo, espera_s=30.0)
    if r.returncode != 0:
        saida = (r.stderr or r.stdout).strip()
        log.warning("tailscale serve: %s", saida[:300])
        if "HTTPS" in saida or "cert" in saida.lower():
            raise RemotoErro("Ative os certificados HTTPS no painel do Tailscale (DNS).")
        if "operator" in saida or "permission" in saida.lower() or "denied" in saida:
            raise RemotoErro(
                "Sem permissão no Tailscale. Rode: sudo tailscale set --operator=$USER"
            )
        raise RemotoErro("O Tailscale recusou a publicação.")


def ativar(porta_painel: int, porta_livekit: int) -> None:
    _serve(PORTA_PAINEL, f"http://127.0.0.1:{porta_painel}")
    _serve(PORTA_VOZ, f"http://127.0.0.1:{porta_livekit}")


def desativar() -> None:
    for porta in (PORTA_PAINEL, PORTA_VOZ):
        _tailscale("serve", f"--https={porta}", "off", espera_s=30.0)
