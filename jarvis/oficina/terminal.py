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


def _grupo_ativo(grupo: int) -> bool:
    """Algum processo do grupo ainda roda. Zumbi não conta: ele já terminou e só espera ser
    coletado. Num contêiner sem init (Docker sem `--init`), o neto órfão vira zumbi que ninguém
    coleta, e o `killpg(grupo, 0)` acharia o grupo vivo para sempre (lição de 16/10/2026)."""
    try:
        os.killpg(grupo, 0)
    except ProcessLookupError:
        return False
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return True  # sem /proc, vale a resposta do killpg
    for pid in pids:
        try:
            # Depois do nome (entre parênteses, pode ter espaço): estado, pai e grupo.
            campos = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            if int(campos[2]) == grupo and campos[0] not in ("Z", "X"):
                return True
        except (OSError, IndexError, ValueError):
            continue  # terminou durante a leitura
    return False


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
        self.leitor = threading.Thread(target=self._ler, name=f"terminal-{pid}", daemon=True)
        self.leitor.start()

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

    def rascunho(
        self, texto: str, quieto_s: float = 1.5, minimo_s: float = 3.0, limite_s: float = 30.0
    ) -> None:
        """Cola `texto` no campo do agente sem Enter, quando ele terminar de abrir (passados
        `minimo_s`, a tela fica quieta por `quieto_s`). Vai junto com o próximo pedido."""

        def esperar_e_colar() -> None:
            inicio = time.monotonic()
            visto = self.fim
            while time.monotonic() - inicio < limite_s and self.vivo:
                time.sleep(quieto_s)
                pronto = time.monotonic() - inicio >= minimo_s
                if pronto and self.fim == visto and visto > 0:
                    break
                visto = self.fim
            self.escrever(b"\x1b[200~" + texto.encode() + b"\x1b[201~")

        threading.Thread(target=esperar_e_colar, name=f"rascunho-{self.pid}", daemon=True).start()

    def redimensionar(self, colunas: int, linhas: int) -> None:
        if self.vivo:
            tamanho = struct.pack("HHHH", max(2, linhas), max(10, colunas), 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, tamanho)

    def encerrar(self, espera_s: float = 5.0) -> None:
        """Encerra o grupo do agente e o comando em primeiro plano; espera também os callbacks."""
        grupos: set[int] = set()
        with self.cond:
            # O fd pode ser reutilizado depois da saída. Só consulta o terminal ainda vivo.
            if self.vivo:
                grupos.add(self.pid)
                with contextlib.suppress(OSError):
                    if primeiro_plano := os.tcgetpgrp(self.fd):
                        grupos.add(primeiro_plano)
        for grupo in grupos:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(grupo, signal.SIGTERM)
        self.leitor.join(espera_s)
        # Um filho pode ignorar SIGTERM e fechar a saída: o fim do leitor não prova seu fim.
        for grupo in grupos:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(grupo, signal.SIGKILL)
        if self.leitor.is_alive():
            self.leitor.join(espera_s)
        if self.leitor.is_alive():
            raise TimeoutError("O terminal ainda está encerrando.")
        # SIGKILL é assíncrono: não remove a sessão enquanto o grupo ainda existir.
        prazo = time.monotonic() + espera_s
        while grupos:
            for grupo in tuple(grupos):
                if not _grupo_ativo(grupo):
                    grupos.remove(grupo)
            if grupos:
                if time.monotonic() >= prazo:
                    raise TimeoutError("Os processos do terminal ainda estão encerrando.")
                time.sleep(0.01)
