"""Acesso de qualquer lugar sem nada no celular: o túnel do Cloudflare (roteiro, passo 4.3).

O PC está atrás da rede de casa; para o celular alcançá-lo no 4G, sem abrir porta no roteador, um
intermediário é inevitável. O `cloudflared` (cloudflare/cloudflared, Apache-2.0; ver
THIRD_PARTY.md) abre uma conexão de saída do PC e devolve um endereço HTTPS público
(`https://<palavras>.trycloudflare.com`), por onde passam o painel e a voz (WebSocket, ADR 0024).
No celular basta o navegador, a senha do painel e, se quiser, o ícone na tela inicial.

- O Zé usa o `cloudflared` da máquina, ou baixa o binário oficial na versão fixada e confere o
  SHA-256, só quando a pessoa ativa o acesso.
- O túnel rápido não pede conta, mas o endereço muda a cada vez que sobe: o painel mostra o novo
  endereço e o QR.
- O túnel fixo (26/10/2026) usa um domínio da pessoa no Cloudflare: ela cria o túnel no painel do
  Cloudflare, cola aqui o comando que ele dá (o token vai para um arquivo 0600, lido pelo
  `--token-file`, nunca na linha de comando) e diz o endereço. O endereço não muda mais: o app
  instalado no celular, o app de voz e as notificações dependem disso.
- Tudo o que chega pelo túnel é de outro aparelho: o painel exige a senha (o cabeçalho do
  Cloudflare marca o pedido como remoto, mesmo que o `Host` diga o contrário).
"""

import base64
import binascii
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

from zervis import atividade, lugares
from zervis.preparar import Modelo, PrepararErro, baixar

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
TOKEN = lugares.CONFIG / "tunel-token"  # o token do túnel fixo (0600)
CONECTADO = re.compile(r"Registered tunnel connection")  # o túnel fixo ligou ao Cloudflare
_TOKEN = re.compile(r"eyJ[A-Za-z0-9_\-+/=]{40,}")
_NOME = re.compile(r"(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
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


def _escolha(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_escolha(arquivo: Path, dados: dict[str, Any]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps(dados))
    temporario.replace(arquivo)


def escolhido(arquivo: Path = ESCOLHA) -> bool:
    return bool(_escolha(arquivo).get("ativo"))


def escolher(ativo: bool, arquivo: Path = ESCOLHA) -> None:
    _gravar_escolha(arquivo, {**_escolha(arquivo), "ativo": ativo})


class TunelErro(ValueError):
    """O que a pessoa colou ou digitou não serve (a mensagem vai para a tela)."""


def fixo(arquivo: Path = ESCOLHA, token: Path = TOKEN) -> str:
    """O endereço do túnel fixo (`https://ze.exemplo.com.br`), ou "" no túnel rápido."""
    endereco = _escolha(arquivo).get("fixo", "")
    return endereco if isinstance(endereco, str) and endereco and token.is_file() else ""


def ler_token(colado: str) -> str:
    """O token no que o Cloudflare mostra (`cloudflared service install <token>`, o comando com
    `--token`, ou só o token), conferido: é um JSON em base64 com a conta, o túnel e o segredo."""
    achado = _TOKEN.search(colado.strip())
    if achado is None:
        raise TunelErro("Não achei o token do túnel. Cole o comando que o Cloudflare mostra.")
    token = achado.group(0)
    try:
        dados = json.loads(base64.b64decode(token + "=" * (-len(token) % 4)))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise TunelErro("O token do túnel está incompleto. Copie o comando inteiro.") from None
    if not isinstance(dados, dict) or not {"a", "t", "s"} <= dados.keys():
        raise TunelErro("Isso não é um token de túnel do Cloudflare.")
    return token


def ler_endereco(digitado: str) -> str:
    """`ze.exemplo.com.br` ou `https://ze.exemplo.com.br/` vira `https://ze.exemplo.com.br`."""
    nome = re.sub(r"^https?://", "", digitado.strip().lower()).split("/", 1)[0]
    if not _NOME.fullmatch(nome) or nome.endswith(".trycloudflare.com"):
        raise TunelErro("Digite o endereço do seu domínio, como ze.seudominio.com.br.")
    return f"https://{nome}"


def guardar_fixo(colado: str, digitado: str, arquivo: Path = ESCOLHA, token: Path = TOKEN) -> str:
    """Guarda o token (0600) e o endereço; devolve o endereço."""
    segredo, endereco = ler_token(colado), ler_endereco(digitado)
    token.parent.mkdir(parents=True, exist_ok=True)
    temporario = token.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(segredo)
    temporario.replace(token)
    _gravar_escolha(arquivo, {**_escolha(arquivo), "fixo": endereco})
    return endereco


def esquecer_fixo(arquivo: Path = ESCOLHA, token: Path = TOKEN) -> None:
    """Volta ao túnel rápido: o token sai do disco."""
    token.unlink(missing_ok=True)
    dados = _escolha(arquivo)
    dados.pop("fixo", None)
    _gravar_escolha(arquivo, dados)


UNIDADE = "zervis-tunel"  # o serviço do usuário que roda o cloudflared, fora do Zé
REGISTRO = lugares.ESTADO / "cloudflared.log"  # a saída do cloudflared, onde vem o endereço


class Direto:
    """O cloudflared como processo filho do Zé: morre junto com ele (testes e máquinas sem
    systemd)."""

    def __init__(self) -> None:
        self.processo: subprocess.Popen[bytes] | None = None

    def ativo(self) -> bool:
        return self.processo is not None and self.processo.poll() is None

    def codigo(self) -> int | None:
        return self.processo.poll() if self.processo is not None else None

    def iniciar(self, comando: list[str], registro: Path) -> None:
        with registro.open("ab") as saida:
            self.processo = subprocess.Popen(  # noqa: S603 (binário conferido, argumentos fixos)
                comando, stdout=subprocess.DEVNULL, stderr=saida
            )

    def parar(self) -> None:
        processo, self.processo = self.processo, None
        if processo is not None and processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(5)
            except subprocess.TimeoutExpired:
                processo.kill()


class Systemd:
    """O cloudflared num serviço próprio do usuário (`zervis-tunel`): reiniciar o Zé não o
    derruba, então o endereço (e o login do celular, que é por endereço) continua o mesmo até o
    computador reiniciar (14/10/2026). Serve também a outros serviços do Zé (a Central de
    Atendimento): `unidade` e o `ambiente` repassado (o systemd não herda o de quem chama)."""

    def __init__(self, unidade: str = UNIDADE, ambiente: dict[str, str] | None = None) -> None:
        self.unidade = unidade
        self.ambiente = ambiente or {}

    def _systemctl(self, *args: str) -> int:
        return subprocess.run(  # noqa: S603
            ["systemctl", "--user", *args],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=10,
        ).returncode

    def ativo(self) -> bool:
        return self._systemctl("is-active", "--quiet", self.unidade) == 0

    def codigo(self) -> int | None:
        return None  # o systemd não diz: qualquer saída sem pedido é queda

    def iniciar(self, comando: list[str], registro: Path) -> None:
        self._systemctl("reset-failed", self.unidade)
        subprocess.run(  # noqa: S603
            [  # noqa: S607
                "systemd-run",
                "--user",
                "--collect",
                f"--unit={self.unidade}",
                *(f"--setenv={k}={v}" for k, v in self.ambiente.items()),
                "-p",
                "StandardOutput=null",
                "-p",
                f"StandardError=append:{registro}",
                "--",
                *comando,
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )

    def parar(self) -> None:
        self._systemctl("stop", self.unidade)


def endereco_pronto(registro: Path, endereco_fixo: str = "") -> str:
    """O endereço pronto: o que o túnel rápido escreveu, ou o fixo depois de conectar."""
    if not endereco_fixo:
        return ultimo_endereco(registro)
    try:
        conectou = CONECTADO.search(registro.read_text(errors="replace"))
    except OSError:
        return ""
    return endereco_fixo if conectou else ""


def tem_systemd() -> bool:
    usuario = shutil.which("systemd-run") and subprocess.run(
        ["systemctl", "--user", "is-system-running"],  # noqa: S607
        capture_output=True,
        check=False,
        timeout=5,
    ).stdout.strip() not in (b"", b"offline")
    return bool(usuario)


def lancador_padrao() -> "Direto | Systemd":
    return Systemd() if tem_systemd() else Direto()


def ultimo_endereco(registro: Path) -> str:
    try:
        achados = ENDERECO.findall(registro.read_text(errors="replace"))
    except OSError:
        return ""
    return achados[-1] if achados else ""


class Tunel:
    """O `cloudflared` para o painel: avisa o endereço quando fica pronto, sobe de novo sozinho
    se cair sem ninguém pedir (espera crescente, endereço novo no painel) e, rodando num serviço
    próprio, continua de pé quando o Zé reinicia: ao subir, o Zé o reencontra.
    """

    def __init__(
        self,
        ao_endereco: Callable[[str], None],
        ao_cair: Callable[[str], None] | None = None,
        lancador: "Direto | Systemd | None" = None,
        registro: Path = REGISTRO,
        escolha: Path = ESCOLHA,
        token: Path = TOKEN,
    ) -> None:
        self.ao_endereco = ao_endereco
        self.escolha, self.token = escolha, token
        self.fixo = ""  # o endereço do túnel fixo em uso ("" no túnel rápido)
        self.ao_cair = ao_cair  # recebe o endereço que deixou de valer
        self.lancador = lancador if lancador is not None else lancador_padrao()
        self.registro = registro
        self.endereco = ""
        self._trava = threading.Lock()
        self._parado = threading.Event()
        self._comando: list[str] = []
        self._quedas = 0
        self._vigia: threading.Thread | None = None

    @property
    def ativo(self) -> bool:
        return self.lancador.ativo()

    def iniciar(self, porta: int, programa: Path) -> None:
        with self._trava:
            self._parado.clear()
            self.fixo = fixo(self.escolha, self.token)
            # O túnel fixo leva ao painel pelo que a pessoa configurou no Cloudflare (o endereço
            # público e o serviço http://127.0.0.1:<porta>); o token vem do arquivo, não da linha.
            self._comando = (
                [str(programa), "tunnel", "--no-autoupdate", "run", "--token-file", str(self.token)]
                if self.fixo
                else [
                    str(programa),
                    "tunnel",
                    "--no-autoupdate",
                    "--url",
                    f"http://127.0.0.1:{porta}",
                ]
            )
            self.registro.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.lancador.ativo() and (antes := self._lido()):
                self.endereco = antes  # o túnel sobreviveu ao reinício do Zé: o mesmo endereço
                log.info("túnel: já estava no ar em %s", antes)
                self.ao_endereco(antes)
            else:
                if self.lancador.ativo():
                    # De pé, mas sem o endereço anotado (o registro foi apagado, por exemplo numa
                    # reinstalação): sem parar, o serviço de mesmo nome não sobe de novo.
                    log.info("túnel: no ar sem endereço conhecido; subindo de novo")
                    self.lancador.parar()
                self._quedas = 0
                self._subir()
            if self._vigia is None or not self._vigia.is_alive():
                self._vigia = threading.Thread(target=self._vigiar, name="tunel", daemon=True)
                self._vigia.start()

    def _subir(self) -> None:
        self.endereco = ""
        self.registro.write_bytes(b"")  # endereço novo: o anterior não vale mais
        self.lancador.iniciar(self._comando, self.registro)
        log.info("túnel: subindo")

    def _lido(self) -> str:
        return endereco_pronto(self.registro, self.fixo)

    def _vigiar(self) -> None:
        """Lê o endereço que o cloudflared escreve e percebe quando ele cai."""
        while not self._parado.wait(1.0):
            atual = self._lido()
            if atual and atual != self.endereco:
                self.endereco, self._quedas = atual, 0
                log.info("túnel: pronto em %s", atual)
                self.ao_endereco(atual)
            if self.lancador.ativo():
                continue
            codigo = self.lancador.codigo()
            if self._parado.is_set():
                return
            if codigo in ENCERRADO:
                log.info("túnel: o cloudflared foi encerrado (código %s)", codigo)
                self.endereco = ""
                return
            log.warning("túnel: o cloudflared saiu (código %s)", codigo)
            atividade.PADRAO.registrar(
                "falha", "O túnel do acesso de fora caiu", origem="sistema", codigo=codigo
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
                if not self._parado.is_set():
                    self._subir()

    def soltar(self) -> None:
        """O Zé vai parar: deixa de vigiar, mas o túnel continua (no serviço próprio)."""
        self._parado.set()

    def parar(self) -> None:
        """A pessoa desligou o acesso de fora: o túnel sai de verdade."""
        self._parado.set()
        with self._trava:
            self.endereco = ""
            self.lancador.parar()
