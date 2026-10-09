"""Presença no modo mesa: a janela do Barehands aberta no Hyprland (Prova 3, ADR 0003).

Fonte primária: o socket de eventos (`.socket2.sock`), que empurra `openwindow`/`closewindow`
sem consulta. Conferência: `hyprctl clients -j` ao conectar e a cada 5 s, porque um evento pode
se perder numa reconexão. Socket caído e consulta falhando ⇒ ausente (falhar fechado).

A janela é reconhecida pela classe, não pelo título: o título nasce como o endereço da página
e só depois vira "barehands".
"""

import json
import logging
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

CLASSE = "chrome-127.0.0.1__stage.html-Default"
# O painel (docs/plano-painel.md) traz o modo imersivo numa aba: a janela dele também é a do Zé.
CLASSE_PAINEL = "chrome-127.0.0.1__-Default"
CONFERENCIA_S = 5.0
log = logging.getLogger(__name__)


class Janelas:
    """Endereços das janelas do Barehands abertas agora. Pura: só interpreta o que recebe."""

    def __init__(self, classe: str = CLASSE) -> None:
        self.classes = {classe, CLASSE_PAINEL}
        self.enderecos: set[str] = set()

    @property
    def aberta(self) -> bool:
        return bool(self.enderecos)

    def evento(self, linha: str) -> None:
        nome, _, dados = linha.partition(">>")
        if nome == "openwindow":
            # openwindow>>ENDEREÇO,ÁREA,CLASSE,TÍTULO (o título pode ter vírgulas)
            partes = dados.split(",", 3)
            if len(partes) >= 3 and partes[2] in self.classes:
                self.enderecos.add(partes[0])
        elif nome == "closewindow":
            self.enderecos.discard(dados.strip())

    def conciliar(self, clientes: list[dict[str, object]]) -> None:
        # O hyprctl escreve "0x59fe...", os eventos "59fe...": guarda sem o prefixo.
        self.enderecos = {
            str(c.get("address", "")).removeprefix("0x")
            for c in clientes
            if c.get("class") in self.classes
        }


def pastas_de_instancia(base: Path, assinatura: str | None) -> list[Path]:
    """A instância do ambiente primeiro; depois as outras, da mais nova para a mais velha."""
    if not base.is_dir():
        return []
    outras = sorted(
        (p for p in base.iterdir() if p.is_dir() and p.name != assinatura),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return ([base / assinatura] if assinatura else []) + outras


class MonitorPresenca(threading.Thread):
    """Avisa `ao_mudar(aberta)` a cada mudança. Começa ausente até a primeira leitura."""

    def __init__(
        self,
        ao_mudar: Callable[[bool], None],
        parar: threading.Event,
        base: Path | None = None,
        classe: str = CLASSE,
    ) -> None:
        super().__init__(name="presenca", daemon=True)
        self.ao_mudar = ao_mudar
        self.parar = parar
        self.base = base or Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")) / "hypr"
        self.janelas = Janelas(classe)
        self.assinatura: str | None = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        self.avisado: bool | None = None

    def _avisar(self) -> None:
        if self.janelas.aberta != self.avisado:
            self.avisado = self.janelas.aberta
            self.ao_mudar(self.janelas.aberta)

    def _hyprctl(self) -> list[dict[str, object]] | None:
        env = {**os.environ, "HYPRLAND_INSTANCE_SIGNATURE": self.assinatura or ""}
        try:
            r = subprocess.run(
                ["/usr/bin/hyprctl", "clients", "-j"],
                capture_output=True,
                timeout=2,
                check=True,
                env=env,
            )
            dados = json.loads(r.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
        return dados if isinstance(dados, list) else None

    def _conectar(self) -> socket.socket | None:
        for pasta in pastas_de_instancia(self.base, self.assinatura):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(str(pasta / ".socket2.sock"))
            except OSError:
                s.close()
                continue
            if pasta.name != self.assinatura:
                log.info("Hyprland em outra instância: %s", pasta.name)
            self.assinatura = pasta.name
            s.settimeout(0.5)
            return s
        return None

    def _conferir(self) -> bool:
        clientes = self._hyprctl()
        if clientes is None:
            return False
        self.janelas.conciliar(clientes)
        self._avisar()
        return True

    def run(self) -> None:
        while not self.parar.is_set():
            conexao = self._conectar()
            if conexao is None:
                if not self._conferir():
                    self.janelas.enderecos.clear()  # sem como saber: ausente
                    self._avisar()
                self.parar.wait(1.0)
                continue
            with conexao:
                self._ouvir(conexao)
            self.parar.wait(0.5)

    def _ouvir(self, conexao: socket.socket) -> None:
        self._conferir()
        proxima = time.monotonic() + CONFERENCIA_S
        resto = b""
        while not self.parar.is_set():
            try:
                bloco = conexao.recv(65536)
            except TimeoutError:
                bloco = None
            except OSError:
                return
            if bloco == b"":
                return  # Hyprland fechou o socket (reinício): reconecta
            if bloco:
                *linhas, resto = (resto + bloco).split(b"\n")
                for linha in linhas:
                    self.janelas.evento(linha.decode(errors="replace"))
                self._avisar()
            if time.monotonic() >= proxima:
                self._conferir()
                proxima = time.monotonic() + CONFERENCIA_S
