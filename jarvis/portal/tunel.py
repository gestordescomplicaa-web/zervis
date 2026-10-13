"""Acesso de qualquer lugar sem nada no celular: o túnel do Cloudflare (roteiro, passo 4.3).

O PC está atrás da rede de casa; para o celular alcançá-lo no 4G, sem abrir porta no roteador, um
intermediário é inevitável. O `cloudflared` (cloudflare/cloudflared, Apache-2.0; ver
THIRD_PARTY.md) abre uma conexão de saída do PC e devolve um endereço HTTPS público
(`https://<palavras>.trycloudflare.com`), por onde passam o painel e a voz (WebSocket, ADR 0024).
No celular basta o navegador, a senha do painel e, se quiser, o ícone na tela inicial.

- O Zé usa o `cloudflared` da máquina, ou baixa o binário oficial na versão fixada e confere o
  SHA-256, só quando a pessoa ativa o acesso.
- O túnel rápido não pede conta, mas o endereço muda a cada vez que sobe: o painel mostra o novo
  endereço e o QR. Com um domínio próprio no Cloudflare, o endereço fica fixo (adiante).
- Tudo o que chega pelo túnel é de outro aparelho: o painel exige a senha (o cabeçalho do
  Cloudflare marca o pedido como remoto, mesmo que o `Host` diga o contrário).
"""

import json
import logging
import platform
import re
import shutil
import signal
import subprocess
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jarvis import atividade, lugares
from jarvis.preparar import Modelo, PrepararErro, baixar

log = logging.getLogger(__name__)

VERSAO = "2026.10.0"
_BASE = f"https://github.com/cloudflare/cloudflared/releases/download/{VERSAO}"
PACOTES = {
    "x86_64": Modelo(
        "cloudflared",
        f"{_BASE}/cloudflared-linux-amd64",
        "d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db",
        "túnel do acesso pelo celular (cloudflared, Apache-2.0)",
    ),
    "aarch64": Modelo(
        "cloudflared",
        f"{_BASE}/cloudflared-linux-arm64",
        "e6422b9d4f72d3194bc5a38676f13667c06666523217b842a877d72a80b5ac08",
        "túnel do acesso pelo celular (cloudflared, Apache-2.0)",
    ),
}
PASTA = lugares.DADOS / "cloudflared" / VERSAO
ESCOLHA = lugares.CONFIG / "tunel.json"
ENDERECO = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
ESPERA_S = (2.0, 5.0, 15.0, 30.0, 60.0)
ENCERRADO = frozenset({0, -signal.SIGTERM, -signal.SIGINT})


def binario(pasta: Path = PASTA) -> Path | None:
    if achado := shutil.which("cloudflared"):
        return Path(achado)
    proprio = pasta / "cloudflared"
    return proprio if proprio.is_file() else None


def garantir(pasta: Path = PASTA, abrir: Any = urllib.request.urlopen) -> Path:
    """O `cloudflared` pronto para usar; baixa e confere se a máquina não tiver."""
    if (achado := binario(pasta)) is not None:
        return achado
    pacote = PACOTES.get(platform.machine())
    if pacote is None:
        raise PrepararErro(f"sem cloudflared pronto para {platform.machine()}")
    baixar(pacote, pasta, abrir)
    (pasta / "cloudflared").chmod(0o755)
    return pasta / "cloudflared"


def escolhido(arquivo: Path = ESCOLHA) -> bool:
    try:
        return bool(json.loads(arquivo.read_text()).get("ativo"))
    except (OSError, ValueError, AttributeError):
        return False


def escolher(ativo: bool, arquivo: Path = ESCOLHA) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"ativo": ativo}))
    temporario.replace(arquivo)


class Tunel:
    """O `cloudflared` rodando para o painel; avisa o endereço quando o túnel fica pronto e sobe
    de novo sozinho se cair sem ninguém pedir (com espera crescente, e o endereço novo no painel).
    """

    def __init__(
        self,
        ao_endereco: Callable[[str], None],
        ao_cair: Callable[[str], None] | None = None,
    ) -> None:
        self.ao_endereco = ao_endereco
        self.ao_cair = ao_cair  # recebe o endereço que deixou de valer
        self.endereco = ""
        self.processo: subprocess.Popen[str] | None = None
        self._trava = threading.Lock()
        self._parado = threading.Event()
        self._comando: list[str] = []
        self._quedas = 0

    @property
    def ativo(self) -> bool:
        return self.processo is not None and self.processo.poll() is None

    def iniciar(self, porta: int, programa: Path) -> None:
        with self._trava:
            self._parado.clear()
            self._comando = [
                str(programa),
                "tunnel",
                "--no-autoupdate",
                "--url",
                f"http://127.0.0.1:{porta}",
            ]
            if self.ativo:
                return
            self._quedas = 0
            self._subir()

    def _subir(self) -> None:
        self.endereco = ""
        self.processo = subprocess.Popen(  # noqa: S603 (o binário conferido, argumentos fixos)
            self._comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=self._ler, args=(self.processo,), daemon=True).start()
        log.info("túnel: subindo")

    def _ler(self, processo: subprocess.Popen[str]) -> None:
        assert processo.stderr is not None  # noqa: S101 (criado com PIPE)
        for linha in processo.stderr:
            novo = processo is self.processo and not self.endereco
            if novo and (achado := ENDERECO.search(linha)):
                self.endereco = achado.group(0)
                self._quedas = 0
                log.info("túnel: pronto em %s", self.endereco)
                self.ao_endereco(self.endereco)
        processo.wait()
        if processo is not self.processo:  # parado ou trocado de propósito
            return
        if processo.returncode in ENCERRADO:
            # Término pedido de fora (o serviço parando: o systemd encerra todos os processos
            # juntos), não uma queda: sem falha na atividade e sem subir de novo.
            log.info("túnel: o cloudflared foi encerrado (código %s)", processo.returncode)
            self.endereco = ""
            return
        log.warning("túnel: o cloudflared saiu (código %s)", processo.returncode)
        atividade.PADRAO.registrar(
            "falha", "O túnel do acesso de fora caiu", origem="sistema", codigo=processo.returncode
        )
        antigo, self.endereco = self.endereco, ""
        if antigo and self.ao_cair is not None:
            self.ao_cair(antigo)
        espera = ESPERA_S[min(self._quedas, len(ESPERA_S) - 1)]
        self._quedas += 1
        log.warning("túnel: de novo em %.0f s", espera)
        if self._parado.wait(espera):
            return
        with self._trava:
            if processo is self.processo and not self._parado.is_set():
                self._subir()

    def parar(self) -> None:
        self._parado.set()
        with self._trava:
            processo, self.processo = self.processo, None
            self.endereco = ""
        if processo is not None and processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(5)
            except subprocess.TimeoutExpired:
                processo.kill()
