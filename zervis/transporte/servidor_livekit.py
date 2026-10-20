"""O servidor LiveKit da voz remota (plano da voz remota, etapa 1): baixado, conferido e mantido
pelo Zé, como o ai-memory.

O LiveKit (livekit/livekit, Apache-2.0; ver THIRD_PARTY.md) é a sala de áudio em tempo real: o
navegador da pessoa (PC, celular) publica o microfone, o Zé entra como participante, ouve e fala.
O Zé:

- usa o `livekit-server` da máquina, se houver; senão baixa o binário oficial na versão fixada
  abaixo e confere o SHA-256;
- gera na primeira vez a chave e o segredo da sala em `<config>/livekit.json` (0600);
- sobe o servidor como processo filho, só no endereço local (a rede privada entra na etapa 2),
  com a configuração passada pelo ambiente, sem arquivo com o segredo.

Os tokens de quem entra na sala são assinados aqui (HS256, o formato do LiveKit), sem SDK de
servidor: identidade, sala e validade curta.
"""

import base64
import hashlib
import hmac
import json
import logging
import platform
import secrets
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.filho import Filho, porta_ocupada
from zervis.preparar import Modelo, PrepararErro, baixar

log = logging.getLogger(__name__)

VERSAO = "1.13.9"
_BASE = f"https://github.com/livekit/livekit/releases/download/v{VERSAO}"
PACOTES = {
    "x86_64": Modelo(
        f"livekit_{VERSAO}_linux_amd64.tar.gz",
        f"{_BASE}/livekit_{VERSAO}_linux_amd64.tar.gz",
        "0b7fa208b662d09cfdeae8c06cf4c481aead0556086558b48250501e2e2d6e20",
        "sala de áudio da voz remota (LiveKit, Apache-2.0)",
    ),
    "aarch64": Modelo(
        f"livekit_{VERSAO}_linux_arm64.tar.gz",
        f"{_BASE}/livekit_{VERSAO}_linux_arm64.tar.gz",
        "c5e4e5a6d6cf0a449651aa3178532ecc7a2bf2502538396ebe6e51ff13424056",
        "sala de áudio da voz remota (LiveKit, Apache-2.0)",
    ),
}
PASTA = lugares.DADOS / "livekit" / VERSAO
CREDENCIAIS = lugares.CONFIG / "livekit.json"
PORTA = 7880  # sinalização (WebSocket); 7882 UDP para a mídia
SALA = "ze"
VALIDADE_S = 600


def binario(pasta: Path = PASTA) -> Path | None:
    """O `livekit-server` da máquina, senão o que o Zé baixou; None se não houver nenhum."""
    if achado := shutil.which("livekit-server"):
        return Path(achado)
    proprio = pasta / "livekit-server"
    return proprio if proprio.is_file() else None


def garantir(pasta: Path = PASTA, abrir: Any = urllib.request.urlopen) -> bool:
    """Baixa e extrai o servidor se a máquina não tiver; True se baixou agora."""
    if binario(pasta) is not None:
        return False
    pacote = PACOTES.get(platform.machine())
    if pacote is None:
        raise PrepararErro(f"sem LiveKit pronto para {platform.machine()}")
    baixar(pacote, pasta.parent, abrir)
    arquivo = pasta.parent / pacote.nome
    try:
        with tarfile.open(arquivo) as tar:
            tar.extractall(pasta, filter="data")  # nada fora da pasta, sem links perigosos
    finally:
        arquivo.unlink(missing_ok=True)
    (pasta / "livekit-server").chmod(0o755)
    return True


def credenciais(arquivo: Path = CREDENCIAIS) -> tuple[str, str]:
    """A chave e o segredo da sala; criados na primeira vez, só legíveis pelo usuário."""
    try:
        dados = json.loads(arquivo.read_text())
        if dados.get("chave") and len(dados.get("segredo", "")) >= 32:
            return str(dados["chave"]), str(dados["segredo"])
    except (OSError, ValueError, AttributeError):
        pass
    chave, segredo = f"ze{secrets.token_hex(6)}", secrets.token_urlsafe(32)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(json.dumps({"chave": chave, "segredo": segredo}))
    temporario.replace(arquivo)
    return chave, segredo


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def token(
    chave: str,
    segredo: str,
    identidade: str,
    nome: str,
    sala: str = SALA,
    validade_s: int = VALIDADE_S,
    agora: float | None = None,
) -> str:
    """Um token de acesso do LiveKit (JWT HS256): entrar nesta sala, publicar só o microfone e
    ouvir; vale `validade_s` segundos."""
    instante = int(agora if agora is not None else time.time())
    carga = {
        "iss": chave,
        "sub": identidade,
        "name": nome,
        "nbf": instante - 10,
        "exp": instante + validade_s,
        "video": {
            "room": sala,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": False,
            "canPublishSources": ["microphone"],
        },
    }
    cabeca = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    corpo = _b64(json.dumps(carga, separators=(",", ":")).encode())
    assinatura = hmac.new(segredo.encode(), f"{cabeca}.{corpo}".encode(), hashlib.sha256)
    return f"{cabeca}.{corpo}.{_b64(assinatura.digest())}"


def configuracao(porta: int = PORTA, ip_rede: str = "", ip_casa: str = "") -> str:
    """A configuração do servidor (YAML; JSON é YAML válido). A sinalização fica no endereço local
    (o `tailscale serve` a publica); a mídia, no local e, com o acesso pelo celular, no da rede
    privada e no da rede de casa (o Chrome do Android só oferece o do Wi-Fi para o áudio)."""
    ips = ["127.0.0.1/32", *[f"{ip}/32" for ip in (ip_rede, ip_casa) if ip]]
    return json.dumps(
        {
            "port": porta,
            "bind_addresses": ["127.0.0.1"],
            # Mídia só nesses endereços (sem TCP, que escuta em todas as interfaces).
            "rtc": {
                "tcp_port": 0,
                "udp_port": porta + 2,
                "use_external_ip": False,
                # Sem `node_ip`: com ele, o LiveKit anuncia todos os endereços como esse
                # (NAT 1:1), e o da rede de casa nunca chegava ao celular (12/10/2026).
                "ips": {"includes": ips},
                "enable_loopback_candidate": True,
            },
            "room": {"empty_timeout": 300, "max_participants": 4},
            "logging": {"level": "info", "pion_level": "warn"},
        }
    )


class ServidorLiveKit:
    """O `livekit-server` como filho do Zé; um que já esteja na porta é usado como está."""

    def __init__(self, porta: int = PORTA, arquivo: Path = CREDENCIAIS) -> None:
        self.porta = porta
        self.arquivo = arquivo
        self.filho: Filho | None = None
        self.ip_rede = self.ip_casa = ""

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.porta}"

    def iniciar(self, ip_rede: str = "", ip_casa: str = "") -> bool:
        """Sobe o servidor; False se não houver binário (a voz remota fica indisponível)."""
        self.ip_rede, self.ip_casa = ip_rede, ip_casa
        if porta_ocupada(self.porta):
            log.info("LiveKit: usando o servidor já na porta %d", self.porta)
            return True
        bin_ = binario()
        if bin_ is None:
            log.warning("LiveKit ausente: a voz remota fica indisponível")
            return False
        chave, segredo = credenciais(self.arquivo)
        self.filho = Filho(
            "livekit",
            [str(bin_)],
            {
                "LIVEKIT_CONFIG": configuracao(self.porta, ip_rede, ip_casa),
                "LIVEKIT_KEYS": f"{chave}: {segredo}",
            },
            registro=lugares.ESTADO / "livekit.log",
        )
        self.filho.iniciar()
        return True

    def parar(self) -> None:
        if self.filho is not None:
            self.filho.parar()

    def reiniciar(self, ip_rede: str, ip_casa: str = "") -> bool:
        """Sobe de novo com outros endereços (o celular passou a alcançar a sala, ou deixou)."""
        if (ip_rede, ip_casa) == (self.ip_rede, self.ip_casa) or self.filho is None:
            return False
        self.filho.parar()
        prazo = time.monotonic() + 5
        while porta_ocupada(self.porta) and time.monotonic() < prazo:
            time.sleep(0.1)
        return self.iniciar(ip_rede, ip_casa)
