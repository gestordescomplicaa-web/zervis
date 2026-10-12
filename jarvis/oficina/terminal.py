"""O terminal real de cada sessão de código: o `claude` ou o `codex` num pseudo-terminal (PTY).

Como no Orca, a sessão é o próprio agente rodando, com todos os comandos dele (`/model`,
`/effort`, `/compact`, aprovações...); o painel só desenha o terminal (xterm.js). O Zé guarda a
saída num buffer circular (o painel lê com long-poll a partir de uma posição, então reabrir a tela
mostra o que já passou), escreve o que a pessoa digita e redimensiona.
"""

import contextlib
import fcntl
import logging
import os
import pty
import shutil
import signal
import struct
import termios
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

log = logging.getLogger(__name__)
BUFFER = 512 * 1024  # o que fica guardado da saída (o painel reabre e vê o fim da conversa)


class Terminal:
    def __init__(
        self,
        comando: Sequence[str],
        pasta: Path,
        ambiente: dict[str, str],
        ao_sair: Callable[[int], None] | None = None,
        ao_ler: Callable[[bytes], None] | None = None,
        colunas: int = 120,
        linhas: int = 32,
    ) -> None:
        self.comando = list(comando)
        self.saida = bytearray()
        self.inicio = 0  # posição absoluta do primeiro byte ainda no buffer
        self.cond = threading.Condition()
        self.ao_sair = ao_sair
        self.ao_ler = ao_ler
        self.codigo: int | None = None
        # Tudo montado antes do fork: o Zé tem várias threads, e o filho só pode chamar o sistema
        # (chdir e execve) até virar o agente, sem rodar mais nada do Python.
        programa = shutil.which(self.comando[0])
        if programa is None:
            raise FileNotFoundError(self.comando[0])
        env = {**os.environ, **ambiente, "TERM": "xterm-256color", "COLORTERM": "truecolor"}
        pasta_ = os.fsencode(pasta)
        pid, fd = pty.fork()
        if pid == 0:  # o filho: vira o agente
            try:
                os.chdir(pasta_)
                os.execve(programa, self.comando, env)  # noqa: S606 (o agente, em lista)
            finally:
                os._exit(127)
        self.pid, self.fd = pid, fd
        self.redimensionar(colunas, linhas)
        threading.Thread(target=self._ler, name=f"terminal-{pid}", daemon=True).start()

    @property
    def fim(self) -> int:
        return self.inicio + len(self.saida)

    @property
    def vivo(self) -> bool:
        return self.codigo is None

    def _ler(self) -> None:
        while True:
            try:
                dados = os.read(self.fd, 65536)
            except OSError:
                dados = b""
            if not dados:
                break
            with self.cond:
                self.saida += dados
                if len(self.saida) > BUFFER:
                    corte = len(self.saida) - BUFFER
                    del self.saida[:corte]
                    self.inicio += corte
                self.cond.notify_all()
            if self.ao_ler is not None:
                try:
                    self.ao_ler(dados)
                except Exception:
                    log.exception("leitura do terminal falhou")
        try:
            _, status = os.waitpid(self.pid, 0)
            codigo = os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            codigo = 0
        with self.cond:
            self.codigo = codigo
            self.cond.notify_all()
        os.close(self.fd)
        if self.ao_sair is not None:
            self.ao_sair(codigo)

    def ler(self, desde: int, espera_s: float = 20.0) -> tuple[int, bytes, bool]:
        """O que saiu a partir de `desde` (posição absoluta); espera até `espera_s` por novidade.
        Devolve a nova posição, os bytes e se o agente ainda está rodando."""
        prazo = time.monotonic() + espera_s
        with self.cond:
            while self.fim <= desde and self.vivo:
                restante = prazo - time.monotonic()
                if restante <= 0:
                    break
                self.cond.wait(restante)
            desde = max(desde, self.inicio)
            return self.fim, bytes(self.saida[desde - self.inicio :]), self.vivo

    def escrever(self, dados: bytes) -> None:
        if self.vivo:
            os.write(self.fd, dados)

    def colar(self, texto: str) -> None:
        """Um pedido inteiro, como colado (bracketed paste) e confirmado com Enter."""
        self.escrever(b"\x1b[200~" + texto.encode() + b"\x1b[201~")
        time.sleep(0.15)  # o agente separa o colar do Enter
        self.escrever(b"\r")

    def redimensionar(self, colunas: int, linhas: int) -> None:
        if self.vivo:
            tamanho = struct.pack("HHHH", max(2, linhas), max(10, colunas), 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, tamanho)

    def encerrar(self, espera_s: float = 5.0) -> None:
        if not self.vivo:
            return
        try:
            os.kill(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        with self.cond:
            self.cond.wait_for(lambda: not self.vivo, espera_s)
        if self.vivo:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self.pid, signal.SIGKILL)
