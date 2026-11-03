"""O buscador próprio do Zé (ADR 0059): o SearXNG, rodando na máquina, só para ele.

O SearXNG (AGPL-3.0, como o Zé) junta os resultados de vários buscadores (Brave, DuckDuckGo,
Wikipédia...) sem chave, sem cota e sem conta. Ele não vem no repositório: na primeira vez, o Zé
baixa o código na versão fixada abaixo (conferido pelo SHA-256), monta um ambiente Python só dele
com o `uv` e o sobe como processo filho, ouvindo só em 127.0.0.1, numa porta livre, com um segredo
novo. Sem Docker e sem senha de administrador: o grupo `docker` daria poder de administrador a
qualquer processo do usuário, inclusive às sessões de código.

Sem o buscador (preparando, sem `uv`, fora do ar), a pesquisa usa a reserva, a busca pela conta
do Codex (ADR 0044). Atualizar o SearXNG é trocar COMMIT e SHA256, num commit testado.
"""

import hashlib
import io
import json
import logging
import secrets
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.filho import Filho, porta_ocupada

log = logging.getLogger(__name__)

COMMIT = "cccbc9e158b0ac3bb2158e9841a647a5bec57b57"  # o master de 03/11/2026
SHA256 = "fd685caeae4773d668c0fe8e8242986ca6a6e24ceb72449ff4fdf4abd8573a85"
FONTE = f"https://codeload.github.com/searxng/searxng/tar.gz/{COMMIT}"
PASTA = lugares.DADOS / "searxng"
REGISTRO = lugares.ESTADO / "searxng.log"
PYTHON = "3.13"  # o SearXNG testa nesta; o uv baixa se a máquina não tiver
TEMPO_PREPARAR_S = 600
TEMPO_BUSCA_S = 12.0
SUBIDA_S = 40.0
NOVA_TENTATIVA_S = 3600.0  # um preparo que falhou só é tentado de novo depois disto
TAR_MAX = 30 * 1024 * 1024
# Motores que não servem aqui: os da rede Tor (não sobem sem ela).
DESLIGADOS = ("ahmia", "torch")


class BuscadorErro(RuntimeError):
    pass


@dataclass(frozen=True)
class Resultado:
    titulo: str
    url: str
    trecho: str
    motores: tuple[str, ...]
    data: str = ""


def _baixar(url: str = FONTE) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Zervis"})  # noqa: S310 (https fixo)
    with urllib.request.urlopen(pedido, timeout=60) as r:  # noqa: S310
        dados: bytes = r.read(TAR_MAX + 1)
    if len(dados) > TAR_MAX:
        raise BuscadorErro("o pacote do SearXNG veio grande demais")
    return dados


def _extrair(dados: bytes, destino: Path) -> None:
    """O código do SearXNG em `destino`, sem caminho que escape da pasta."""
    destino.mkdir(parents=True, exist_ok=True, mode=0o700)
    raiz = destino.resolve()
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as tar:
        for membro in tar.getmembers():
            partes = membro.name.split("/", 1)
            if len(partes) < 2 or not partes[1] or not (membro.isfile() or membro.isdir()):
                continue
            alvo = (destino / partes[1]).resolve()
            if raiz not in alvo.parents and alvo != raiz:
                raise BuscadorErro("pacote do SearXNG com caminho fora da pasta")
            if membro.isdir():
                alvo.mkdir(parents=True, exist_ok=True)
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            arquivo = tar.extractfile(membro)
            if arquivo is not None:
                alvo.write_bytes(arquivo.read())


def configuracao(porta: int, segredo: str) -> str:
    """As configurações do SearXNG: só local, JSON ligado, sem o limitador (é só do Zé)."""
    return (
        "use_default_settings:\n  engines:\n    remove: [" + ", ".join(DESLIGADOS) + "]\n"
        "general:\n  instance_name: Zervis\n  enable_metrics: false\n"
        f"server:\n  bind_address: 127.0.0.1\n  port: {porta}\n  secret_key: {segredo}\n"
        "  limiter: false\n  public_instance: false\n  image_proxy: false\n"
        "search:\n  safe_search: 0\n  formats: [html, json]\n"
        "outgoing:\n  request_timeout: 4.0\n  max_request_timeout: 8.0\n"
    )


def ler_resultados(corpo: Any, quantos: int) -> list[Resultado]:
    itens = corpo.get("results") if isinstance(corpo, dict) else None
    saida = []
    for r in itens if isinstance(itens, list) else []:
        url = str(r.get("url") or "") if isinstance(r, dict) else ""
        if not url.startswith(("https://", "http://")):
            continue
        motores = r.get("engines") or [r.get("engine")]
        saida.append(
            Resultado(
                titulo=" ".join(str(r.get("title") or "").split())[:160],
                url=url[:500],
                trecho=" ".join(str(r.get("content") or "").split())[:400],
                motores=tuple(str(m) for m in motores if m),
                data=str(r.get("publishedDate") or "")[:20],
            )
        )
    return saida[:quantos]


class Buscador:
    """O SearXNG do Zé: preparado uma vez, subido quando a primeira busca precisa."""

    def __init__(self, pasta: Path = PASTA, abrir: Any = urllib.request.urlopen) -> None:
        self.pasta = pasta
        self.abrir = abrir
        self.filho: Filho | None = None
        self.porta = 0
        self.preparando = False
        self.falha = ""
        self._trava = threading.Lock()
        self._tentou = -NOVA_TENTATIVA_S

    @property
    def codigo(self) -> Path:
        return self.pasta / COMMIT[:12] / "src"

    @property
    def python(self) -> Path:
        return self.pasta / COMMIT[:12] / "venv" / "bin" / "python"

    @property
    def preparado(self) -> bool:
        return (self.codigo / "searx" / "webapp.py").is_file() and self.python.is_file()

    def preparar(self, baixar: Any = _baixar, executar: Any = subprocess.run) -> None:
        """Baixa o código fixado (conferido), monta o ambiente e instala as dependências."""
        if self.preparado:
            return
        uv = shutil.which("uv")
        if uv is None:
            raise BuscadorErro("uv não encontrado")
        dados = baixar(FONTE)
        if hashlib.sha256(dados).hexdigest() != SHA256:
            raise BuscadorErro("o pacote do SearXNG não confere com o esperado")
        base = self.pasta / COMMIT[:12]
        _extrair(dados, self.codigo)
        for passo in (
            [uv, "venv", "-q", "--python", PYTHON, str(base / "venv")],
            [uv, "pip", "install", "-q", "--python", str(self.python), "-r",
             str(self.codigo / "requirements.txt")],
        ):  # fmt: skip
            r = executar(
                passo, capture_output=True, text=True, timeout=TEMPO_PREPARAR_S, check=False
            )
            if r.returncode != 0:
                log.warning("searxng: preparo falhou: %s", (r.stderr or "")[-400:])
                raise BuscadorErro("não foi possível preparar o SearXNG")
        for antigo in self.pasta.iterdir() if self.pasta.is_dir() else []:
            if antigo.is_dir() and antigo.name != COMMIT[:12]:
                shutil.rmtree(antigo, ignore_errors=True)  # a versão anterior
        log.info("searxng: preparado (%s)", COMMIT[:12])

    def preparar_em_segundo_plano(self) -> None:
        with self._trava:
            agora = time.monotonic()
            if self.preparando or self.preparado or agora - self._tentou < NOVA_TENTATIVA_S:
                return
            self.preparando, self._tentou = True, agora

        def preparar() -> None:
            try:
                self.preparar()
                self.falha = ""
            except (BuscadorErro, OSError, urllib.error.URLError, subprocess.SubprocessError) as e:
                self.falha = str(e)[:200]
                log.warning("searxng: %s", self.falha)
            finally:
                self.preparando = False

        threading.Thread(target=preparar, name="searxng-preparar", daemon=True).start()

    def iniciar(self) -> None:
        """Sobe o SearXNG numa porta livre, com um segredo novo; espera responder."""
        if not self.preparado:
            self.preparar_em_segundo_plano()
            motivo = f" (da última vez: {self.falha})" if self.falha else ""
            raise BuscadorErro(f"o buscador próprio ainda está sendo preparado{motivo}")
        with self._trava:
            if self.filho is not None:
                self._esperar_subir()  # outra busca já subiu: espera a porta junto
                return
            from zervis.atendimento.whatsapp import porta_livre

            self.porta = porta_livre()
            config = self.pasta / "settings.yml"
            config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            config.touch(mode=0o600)
            config.write_text(configuracao(self.porta, secrets.token_hex(32)))
            self.filho = Filho(
                "searxng",
                [str(self.python), "-m", "searx.webapp"],
                {"SEARXNG_SETTINGS_PATH": str(config), "PYTHONPATH": str(self.codigo)},
                registro=REGISTRO,
            )
            self.filho.iniciar()
            try:
                self._esperar_subir()
            except BuscadorErro:
                self.filho.parar()  # a próxima busca tenta subir de novo
                self.filho = None
                raise

    def _esperar_subir(self) -> None:
        fim = time.monotonic() + SUBIDA_S
        while not porta_ocupada(self.porta):
            if time.monotonic() > fim:
                raise BuscadorErro("o SearXNG não subiu")
            time.sleep(0.2)

    def parar(self) -> None:
        with self._trava:
            filho, self.filho = self.filho, None
        if filho is not None:
            filho.parar()

    def buscar(self, consulta: str, quantos: int = 10, idioma: str = "pt-BR") -> list[Resultado]:
        self.iniciar()  # já de pé: só confere a porta
        params = urllib.parse.urlencode({"q": consulta, "format": "json", "language": idioma})
        url = f"http://127.0.0.1:{self.porta}/search?{params}"
        try:
            with self.abrir(url, timeout=TEMPO_BUSCA_S) as r:  # só a porta local do SearXNG
                corpo = json.loads(r.read())
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise BuscadorErro(f"o SearXNG não respondeu ({type(erro).__name__})") from erro
        return ler_resultados(corpo, quantos)
