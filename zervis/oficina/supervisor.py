"""O supervisor das sessões (`zervis-oficina`): o dono dos terminais dos agentes, fora do Zé.

Antes, cada sessão era um pseudo-terminal filho do processo do Zé, e reiniciar o Zé encerrava
todas (visto em 06/11/2026, com três sessões trabalhando). Agora o terminal nasce num processo
próprio, num serviço do usuário à parte (`systemd-run`, como o túnel): o systemd encerra o grupo
inteiro do Zé ao reiniciá-lo, mas não o do supervisor. O Zé conversa com ele por um socket local
(só o próprio usuário entra) e, ao subir de novo, reencontra os terminais que continuaram
(ADR 0068).

O protocolo é pequeno de propósito: o supervisor não sabe o que é uma sessão, só guarda
terminais por nome e devolve a saída a partir de uma posição. Tudo o que é do Zé (eventos,
conversa, permissões) continua no Zé. Uma linha JSON por pedido e uma por resposta.

Rodar: `python -m zervis.oficina.supervisor <socket>`.
"""

import base64
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import shutil
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from zervis.oficina.terminal import BUFFER, Colagem, Terminal

log = logging.getLogger(__name__)

# Muda quando um pedido ou uma resposta muda de forma. Um supervisor antigo sem terminais é
# trocado pelo novo; com terminais, continua até eles fecharem (o Zé usa terminais locais).
PROTOCOLO = 1
ESPERA_MAXIMA_S = 25.0  # a leitura longa nunca segura uma conexão mais que isto
TEMPO_CONEXAO_S = ESPERA_MAXIMA_S + 10
SUBIDA_S = 8.0  # quanto o Zé espera o supervisor recém-lançado atender
# Pedidos que podem ir de novo por uma conexão refeita. Escrever, não: a tecla iria duas vezes.
REPETIVEIS = frozenset({"ola", "listar", "redimensionar", "esquecer", "encerrar"})


class SupervisorErro(OSError):
    """O supervisor recusou o pedido (nome desconhecido, terminal ocupado...)."""

    def __init__(self, codigo: str, mensagem: str = "") -> None:
        super().__init__(mensagem or codigo)
        self.codigo = codigo


def caminho_padrao() -> Path:
    from zervis.lugares import ESTADO

    return ESTADO / "oficina.sock"


def unidade(caminho: Path) -> str:
    """O nome do serviço: `zervis-oficina` na instalação de sempre (`zervis-teste-oficina` num
    perfil); com outra pasta (testes, instalação portátil), um sufixo da pasta evita choque."""
    from zervis import lugares

    nome = f"{lugares._nome()}-oficina"
    if caminho != caminho_padrao() or os.environ.get("ZERVIS_RAIZ", "").strip():
        nome += "-" + hashlib.sha256(str(caminho).encode()).hexdigest()[:8]
    return nome


# --- o supervisor ----------------------------------------------------------------------------


class _Registro:
    def __init__(self, terminal: Terminal, meta: dict[str, Any]) -> None:
        self.terminal = terminal
        self.meta = meta
        self.criado = time.time()


class Supervisor:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.terminais: dict[str, _Registro] = {}
        self.trava = threading.Lock()
        self._servidor: socketserver.ThreadingUnixStreamServer | None = None
        self._trava_arquivo: int | None = None

    # Cada pedido devolve um dicionário; erro vira {"erro": código, "mensagem": ...}.
    def tratar(self, pedido: dict[str, Any]) -> dict[str, Any]:
        op = str(pedido.get("op", ""))
        metodo = getattr(self, f"_op_{op}", None)
        if metodo is None:
            return {"erro": "op", "mensagem": f"pedido desconhecido: {op}"}
        try:
            resposta: dict[str, Any] = metodo(pedido)
            return resposta
        except SupervisorErro as erro:
            return {"erro": erro.codigo, "mensagem": str(erro)}
        except FileNotFoundError as erro:
            return {"erro": "nao_instalado", "mensagem": str(erro)}
        except TimeoutError as erro:
            return {"erro": "encerrando", "mensagem": str(erro)}
        except (KeyError, TypeError, ValueError) as erro:
            return {"erro": "pedido", "mensagem": str(erro)}

    def _registro(self, pedido: dict[str, Any]) -> _Registro:
        with self.trava:
            registro = self.terminais.get(str(pedido["nome"]))
        if registro is None:
            raise SupervisorErro("desconhecido", "terminal desconhecido")
        return registro

    def _vivos(self) -> int:
        with self.trava:
            return sum(r.terminal.vivo for r in self.terminais.values())

    def _op_ola(self, _: dict[str, Any]) -> dict[str, Any]:
        return {"protocolo": PROTOCOLO, "pid": os.getpid(), "vivos": self._vivos()}

    def _op_abrir(self, p: dict[str, Any]) -> dict[str, Any]:
        nome = str(p["nome"])
        with self.trava:
            atual = self.terminais.get(nome)
            if atual is not None and atual.terminal.vivo:
                raise SupervisorErro("ocupado", "esse terminal já está aberto")
            terminal = Terminal(
                [str(c) for c in p["comando"]],
                Path(str(p["pasta"])),
                {str(k): str(v) for k, v in dict(p["ambiente"]).items()},
                colunas=int(p.get("colunas", 120)),
                linhas=int(p.get("linhas", 32)),
                herdar=False,
            )
            registro = _Registro(terminal, dict(p.get("meta") or {}))
            self.terminais[nome] = registro
        log.info("terminal %s aberto (pid %s)", nome, terminal.pid)
        return {"pid": terminal.pid, "criado": registro.criado}

    def _op_listar(self, _: dict[str, Any]) -> dict[str, Any]:
        with self.trava:
            itens = list(self.terminais.items())
        return {
            "terminais": [
                {
                    "nome": nome,
                    "pid": r.terminal.pid,
                    "fim": r.terminal.fim,
                    "vivo": r.terminal.vivo,
                    "codigo": r.terminal.codigo,
                    "criado": r.criado,
                    "meta": r.meta,
                }
                for nome, r in itens
            ]
        }

    def _op_ler(self, p: dict[str, Any]) -> dict[str, Any]:
        t = self._registro(p).terminal
        espera = min(max(0.0, float(p.get("espera", 0))), ESPERA_MAXIMA_S)
        fim, dados, vivo = t.ler(int(p.get("desde", 0)), espera)
        return {
            "fim": fim,
            "dados": base64.b64encode(dados).decode(),
            "vivo": vivo,
            "codigo": t.codigo,
        }

    def _op_escrever(self, p: dict[str, Any]) -> dict[str, Any]:
        self._registro(p).terminal.escrever(base64.b64decode(str(p["dados"])))
        return {}

    def _op_redimensionar(self, p: dict[str, Any]) -> dict[str, Any]:
        self._registro(p).terminal.redimensionar(int(p["colunas"]), int(p["linhas"]))
        return {}

    def _op_encerrar(self, p: dict[str, Any]) -> dict[str, Any]:
        self._registro(p).terminal.encerrar(float(p.get("espera", 5.0)))
        return {}

    def _op_esquecer(self, p: dict[str, Any]) -> dict[str, Any]:
        """O Zé já tratou a saída deste terminal: ele sai da lista."""
        nome = str(p["nome"])
        with self.trava:
            registro = self.terminais.get(nome)
            if registro is not None and not registro.terminal.vivo:
                del self.terminais[nome]
        return {}

    def _op_sair(self, _: dict[str, Any]) -> dict[str, Any]:
        """Só sem terminais vivos: o Zé troca um supervisor de protocolo antigo."""
        if self._vivos():
            raise SupervisorErro("ocupado", "há terminais abertos")
        if self._servidor is not None:
            threading.Thread(target=self._servidor.shutdown, daemon=True).start()
        return {}

    # --- o socket ------------------------------------------------------------------------------

    def preparar(self) -> None:
        """Trava a pasta (um supervisor por socket) e abre o socket, só para o usuário."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.caminho.with_suffix(".lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise SupervisorErro("ocupado", "outro supervisor já atende este socket") from None
        self._trava_arquivo = fd
        with contextlib.suppress(FileNotFoundError):
            self.caminho.unlink()  # de um supervisor que caiu: a trava prova que ninguém atende
        supervisor = self

        class Atendente(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                if not _mesmo_usuario(self.connection):
                    return
                for linha in self.rfile:
                    try:
                        pedido = json.loads(linha)
                        if not isinstance(pedido, dict):
                            raise ValueError("pedido")
                    except ValueError:
                        resposta: dict[str, Any] = {"erro": "pedido", "mensagem": "JSON inválido"}
                    else:
                        resposta = supervisor.tratar(pedido)
                    try:
                        self.wfile.write(json.dumps(resposta).encode() + b"\n")
                        self.wfile.flush()
                    except OSError:
                        return

        antes = os.umask(0o177)  # o socket nasce 0600
        try:
            self._servidor = socketserver.ThreadingUnixStreamServer(str(self.caminho), Atendente)
        finally:
            os.umask(antes)
        self._servidor.daemon_threads = True

    def servir(self) -> None:
        if self._servidor is None:
            self.preparar()
        servidor = self._servidor
        if servidor is None:
            raise SupervisorErro("socket", "o socket não abriu")
        log.info("supervisor das sessões em %s (protocolo %s)", self.caminho, PROTOCOLO)
        try:
            servidor.serve_forever(poll_interval=0.5)
        finally:
            servidor.server_close()
            with contextlib.suppress(OSError):
                self.caminho.unlink()
            if self._trava_arquivo is not None:  # o próximo supervisor pode subir já
                os.close(self._trava_arquivo)
                self._trava_arquivo = None

    def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()


def _mesmo_usuario(conexao: socket.socket) -> bool:
    """O socket já é 0600 numa pasta 0700; a credencial do outro lado confirma."""
    formato = "3i"  # pid, uid, gid
    try:
        _, uid, _ = struct.unpack(
            formato,
            conexao.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(formato)),
        )
    except OSError:
        return False
    return bool(uid == os.getuid())


# --- o lado do Zé ----------------------------------------------------------------------------


class _Conexao:
    """Uma conexão com o supervisor: um pedido de cada vez. Falha de conexão (socket ausente,
    supervisor caído, prazo) é sempre `ConnectionError`; as recusas do supervisor têm tipo
    próprio: `FileNotFoundError` (agente não instalado), `TimeoutError` (ainda encerrando) e
    `SupervisorErro`."""

    def __init__(self, caminho: Path, tempo_s: float = TEMPO_CONEXAO_S) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(tempo_s)
        try:
            self._sock.connect(str(caminho))
        except OSError as erro:
            self._sock.close()
            raise ConnectionError(f"supervisor das sessões indisponível: {erro}") from erro
        self._leitor = self._sock.makefile("rb")
        self._trava = threading.Lock()

    def pedir(self, op: str, **campos: Any) -> dict[str, Any]:
        try:
            with self._trava:
                self._sock.sendall(json.dumps({"op": op, **campos}).encode() + b"\n")
                linha = self._leitor.readline()
        except OSError as erro:
            raise ConnectionError(f"supervisor das sessões sem resposta: {erro}") from erro
        if not linha:
            raise ConnectionError("o supervisor fechou a conexão")
        try:
            resposta = json.loads(linha)
        except ValueError as erro:
            raise ConnectionError("resposta inválida do supervisor") from erro
        if not isinstance(resposta, dict):
            raise ConnectionError("resposta inválida do supervisor")
        if recusa := resposta.get("erro"):
            if recusa == "nao_instalado":
                raise FileNotFoundError(str(resposta.get("mensagem", "")))
            if recusa == "encerrando":
                raise TimeoutError(str(resposta.get("mensagem", "")))
            raise SupervisorErro(str(recusa), str(resposta.get("mensagem", "")))
        return resposta

    def fechar(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_RDWR)
        with contextlib.suppress(OSError):
            self._leitor.close()
            self._sock.close()


class TerminalRemoto(Colagem):
    """O terminal de uma sessão que vive no supervisor, com a mesma cara do `Terminal` local.

    Um fio acompanha a saída (leitura longa) e a guarda num espelho do buffer do supervisor:
    o painel lê daqui, como lia do terminal local. Ao reencontrar um terminal depois de o Zé
    reiniciar, a saída que já existia entra no espelho (a tela reaberta mostra o que passou),
    mas não volta para `ao_ler`: um aviso de limite antigo não pode disparar a troca de conta.
    """

    def __init__(
        self,
        oficina: "Oficina",
        nome: str,
        pid: int,
        ao_sair: Callable[[int], None] | None,
        ao_ler: Callable[[bytes], None] | None,
        ja_visto: int = 0,
    ) -> None:
        self.oficina = oficina
        self.nome = nome
        self.pid = pid
        self.ao_sair = ao_sair
        self.ao_ler = ao_ler
        self.saida = bytearray()
        self.inicio = 0
        self.codigo: int | None = None
        self.cond = threading.Condition()
        self._ja_visto = ja_visto
        self._parar = threading.Event()
        self._conexao: _Conexao | None = None
        self.leitor = threading.Thread(target=self._seguir, name=f"oficina-{nome}", daemon=True)
        self.leitor.start()

    @property
    def fim(self) -> int:
        return self.inicio + len(self.saida)

    @property
    def vivo(self) -> bool:
        return self.codigo is None

    def _guardar(self, comeco: int, dados: bytes) -> None:
        with self.cond:
            if comeco != self.fim:  # a primeira leitura, ou o supervisor já descartou o meio
                self.saida = bytearray()
                self.inicio = comeco
            self.saida += dados
            if len(self.saida) > BUFFER:
                corte = len(self.saida) - BUFFER
                del self.saida[:corte]
                self.inicio += corte
            self.cond.notify_all()

    def _seguir(self) -> None:
        codigo = -1  # sem resposta do supervisor, o agente foi junto com ele
        try:
            self._conexao = _Conexao(self.oficina.caminho)
            desde = 0
            while not self._parar.is_set():
                r = self._conexao.pedir("ler", nome=self.nome, desde=desde, espera=20.0)
                dados = base64.b64decode(str(r["dados"]))
                fim = int(r["fim"])
                if dados:
                    self._guardar(fim - len(dados), dados)
                    novos = dados[max(0, self._ja_visto - (fim - len(dados))) :]
                    if novos and self.ao_ler is not None:
                        try:
                            self.ao_ler(novos)
                        except Exception:
                            log.exception("leitura do terminal falhou")
                desde = fim
                if not r["vivo"] and not dados:
                    codigo = int(r["codigo"] if r["codigo"] is not None else 0)
                    break
        except (OSError, KeyError, TypeError, ValueError) as erro:
            if self._parar.is_set():
                return  # o Zé está fechando: o terminal continua no supervisor
            log.warning("terminal %s: supervisor sem resposta (%s)", self.nome, erro)
        finally:
            if self._conexao is not None:
                self._conexao.fechar()
        if self._parar.is_set():
            return
        with self.cond:
            self.codigo = codigo
            self.cond.notify_all()
        with contextlib.suppress(OSError):
            self.oficina.pedir("esquecer", nome=self.nome)
        if self.ao_sair is not None:
            self.ao_sair(codigo)

    def ler(self, desde: int, espera_s: float = 20.0) -> tuple[int, bytes, bool]:
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
            self.oficina.pedir("escrever", nome=self.nome, dados=base64.b64encode(dados).decode())

    def redimensionar(self, colunas: int, linhas: int) -> None:
        if self.vivo:
            self.oficina.pedir("redimensionar", nome=self.nome, colunas=colunas, linhas=linhas)

    def encerrar(self, espera_s: float = 5.0) -> None:
        """Encerra o agente no supervisor e espera a saída chegar aqui (e o `ao_sair`)."""
        if self.vivo:
            with contextlib.suppress(SupervisorErro):  # já saiu e foi esquecido
                self.oficina.pedir("encerrar", nome=self.nome, espera=espera_s)
        self.leitor.join(espera_s + 1)
        if self.leitor.is_alive():
            raise TimeoutError("O terminal ainda está encerrando.")

    def soltar(self) -> None:
        """Para de acompanhar sem encerrar o agente (o Zé está fechando)."""
        self._parar.set()
        if self._conexao is not None:
            self._conexao.fechar()
        self.leitor.join(2)


def lancar_padrao(caminho: Path) -> None:
    """Sobe o supervisor num serviço do usuário à parte (`systemd-run`), fora do grupo do Zé;
    sem o systemd do usuário (contêiner), num processo de sessão própria."""
    from zervis.portal.tunel import tem_systemd

    comando = [sys.executable, "-m", "zervis.oficina.supervisor", str(caminho)]
    registro = caminho.with_suffix(".log")
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if tem_systemd() and (systemd_run := shutil.which("systemd-run")):
        nome = unidade(caminho)
        subprocess.run(  # noqa: S603 (comando montado aqui)
            ["systemctl", "--user", "reset-failed", nome],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=10,
        )
        subprocess.run(  # noqa: S603 (comando montado aqui)
            [
                systemd_run,
                "--user",
                "--collect",
                f"--unit={nome}",
                "--description=Zérvis: terminais das sessões de código",
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
        return
    with registro.open("ab") as saida:
        subprocess.Popen(  # noqa: S603 (comando montado aqui)
            comando,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=saida,
            start_new_session=True,
            close_fds=True,
        )


class Oficina:
    """O cliente do supervisor, do lado do Zé: abre terminais nele e reencontra os que ficaram."""

    def __init__(
        self, caminho: Path, lancar: Callable[[Path], None] | None = lancar_padrao
    ) -> None:
        self.caminho = caminho
        self.lancar = lancar
        self._conexao: _Conexao | None = None
        self._trava = threading.Lock()
        self._remotos: list[TerminalRemoto] = []

    def _ola(self) -> dict[str, Any] | None:
        try:
            conexao = _Conexao(self.caminho, tempo_s=3.0)
        except OSError:
            return None
        try:
            return conexao.pedir("ola")
        except OSError:
            return None
        finally:
            conexao.fechar()

    def conectar(self) -> bool:
        """Garante um supervisor atendendo, com o protocolo deste Zé. Falso: terminais locais."""
        ola = self._ola()
        if ola is not None and ola.get("protocolo") != PROTOCOLO:
            if ola.get("vivos"):
                log.warning(
                    "supervisor das sessões com protocolo %s e terminais abertos: "
                    "as sessões novas abrem no Zé até eles fecharem",
                    ola.get("protocolo"),
                )
                return False
            with contextlib.suppress(OSError):
                self.pedir("sair")
            self._fechar_conexao()
            prazo = time.monotonic() + SUBIDA_S  # o antigo solta o socket e a trava
            while self._ola() is not None and time.monotonic() < prazo:
                time.sleep(0.1)
            time.sleep(0.2)
            ola = None
        if ola is None:
            if self.lancar is None:
                return False
            try:
                self.lancar(self.caminho)
            except (OSError, subprocess.SubprocessError) as erro:
                log.warning("supervisor das sessões não subiu: %s", erro)
                return False
            prazo = time.monotonic() + SUBIDA_S
            while (ola := self._ola()) is None and time.monotonic() < prazo:
                time.sleep(0.1)
        return ola is not None and ola.get("protocolo") == PROTOCOLO

    def _fechar_conexao(self) -> None:
        with self._trava:
            if self._conexao is not None:
                self._conexao.fechar()
                self._conexao = None

    def pedir(self, op: str, **campos: Any) -> dict[str, Any]:
        """Um pedido pela conexão de comandos; caída, ela é refeita (e o pedido repetido, se
        repetir não muda nada)."""
        for tentativa in (1, 2):
            with self._trava:
                if self._conexao is None:
                    self._conexao = _Conexao(self.caminho, tempo_s=TEMPO_CONEXAO_S)
                conexao = self._conexao
            try:
                return conexao.pedir(op, **campos)
            except ConnectionError:
                self._fechar_conexao()
                if tentativa == 2 or op not in REPETIVEIS:
                    raise
        raise AssertionError("inalcançável")

    def abrir(
        self,
        nome: str,
        comando: Sequence[str],
        pasta: Path,
        ambiente: dict[str, str],
        ao_sair: Callable[[int], None] | None = None,
        ao_ler: Callable[[bytes], None] | None = None,
        colunas: int = 120,
        linhas: int = 32,
        meta: dict[str, Any] | None = None,
    ) -> TerminalRemoto:
        """Como `Terminal(...)`, com o `ambiente` já inteiro (`agentes.ambiente_do_agente`)."""
        pedido = {
            "nome": nome,
            "comando": list(comando),
            "pasta": str(pasta),
            "ambiente": dict(ambiente),
            "colunas": colunas,
            "linhas": linhas,
            "meta": meta or {},
        }
        try:
            r = self.pedir("abrir", **pedido)
        except ConnectionError:
            if not self.conectar():  # o supervisor caiu: sobe de novo e tenta uma vez
                raise
            r = self.pedir("abrir", **pedido)
        remoto = TerminalRemoto(self, nome, int(r["pid"]), ao_sair, ao_ler)
        self._remotos.append(remoto)
        return remoto

    def listar(self) -> list[dict[str, Any]]:
        terminais = self.pedir("listar")["terminais"]
        return [dict(t) for t in terminais] if isinstance(terminais, list) else []

    def retomar(
        self,
        info: dict[str, Any],
        ao_sair: Callable[[int], None] | None = None,
        ao_ler: Callable[[bytes], None] | None = None,
    ) -> TerminalRemoto:
        """Volta a acompanhar um terminal que continuou no supervisor (de `listar`)."""
        remoto = TerminalRemoto(
            self, str(info["nome"]), int(info["pid"]), ao_sair, ao_ler, ja_visto=int(info["fim"])
        )
        self._remotos.append(remoto)
        return remoto

    def encerrar(self, nome: str, espera_s: float = 5.0) -> None:
        self.pedir("encerrar", nome=nome, espera=espera_s)
        with contextlib.suppress(OSError):
            self.pedir("esquecer", nome=nome)

    def soltar(self) -> None:
        """O Zé está fechando: para de acompanhar, e os agentes continuam no supervisor."""
        for remoto in self._remotos:
            remoto.soltar()
        self._remotos.clear()
        self._fechar_conexao()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    caminho = Path(args[0]) if args else caminho_padrao()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGHUP, signal.SIG_IGN)  # a sessão gráfica que fecha não leva junto
    supervisor = Supervisor(caminho)
    try:
        supervisor.preparar()
    except SupervisorErro as erro:
        log.error("%s", erro)
        return 75  # outra instância: o systemd não deve insistir
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=supervisor.parar).start())
    supervisor.servir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
