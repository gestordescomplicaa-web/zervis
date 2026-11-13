"""Câmeras iCSee/Xiongmai na rede local: cadastro e cliente DVRIP/Sofia."""

from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import json
import os
import select
import shutil
import socket
import struct
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

PORTA = 34567
PORTA_RTSP = 554
ESPERA_S = 8.0
MAX_CARGA = 16 * 1024 * 1024
FOTOS = 500
ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
# A conversa pelo alto-falante e pelo microfone (ADR 0088): G.711 A-law, 8 kHz, mono.
FALA = {"BitRate": 128, "EncodeType": "G711_ALAW", "SampleBit": 16, "SampleRate": 8000}
VIVA = 1007  # a resposta do KeepAlive (1006): chega a qualquer hora e não responde a nada
AUDIO = b"\x00\x00\x01\xfa\x0e\x02"  # quadro de áudio: marca, A-law (0x0E), 8 kHz (0x02)


class CameraErro(RuntimeError):
    """Falha explicável ao encontrar, configurar ou acessar a câmera."""


class CredenciaisInvalidas(CameraErro):
    """O aparelho recusou o usuário ou a senha informados."""


@dataclass(frozen=True)
class Conexao:
    ip: str
    usuario: str
    senha: str
    intervalo_s: int = 30
    ligado: bool = True
    girar: tuple[int, ...] = ()  # as lentes (1, 2…) montadas de cabeça para baixo
    enviar: bool = True  # a foto de movimento vai ao celular (o app Zé Voz)
    # As lentes (1, 2…) cujo alarme não vira foto: a detecção da câmera dispara nelas sem
    # ninguém na imagem (a luz atrás de uma porta de vidro, por exemplo).
    sem_fotos: tuple[int, ...] = ()


def hash_sofia(senha: str) -> str:
    """Senha equivalente do DVRIP: MD5 e soma de cada par de bytes em base 62."""
    digest = hashlib.md5(senha.encode("utf-8"), usedforsecurity=False).digest()
    return "".join(ALFABETO[(digest[i] + digest[i + 1]) % 62] for i in range(0, 16, 2))


def girar_180(jpeg: bytes, hora: str = "") -> bytes:
    """A foto da lente montada invertida, de pé. As lentes extras de algumas câmeras ignoram o
    `PictureFlip` do aparelho (ADR 0087), então o giro fica no Zé. O relógio que a câmera grava
    na imagem gira junto e fica de ponta-cabeça; `hora` volta a ficar legível no alto, à direita,
    onde a câmera o põe."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    with Image.open(BytesIO(jpeg)) as original:
        imagem = original.convert("RGB").rotate(180)
    if hora:
        tamanho = max(12, imagem.height // 18)
        fonte = ImageFont.load_default(tamanho)
        desenho = ImageDraw.Draw(imagem)
        margem = tamanho
        largura = desenho.textlength(hora, font=fonte)
        desenho.text(
            (imagem.width - largura - margem, margem // 2),
            hora,
            font=fonte,
            fill="white",
            stroke_width=2,
            stroke_fill="black",
        )
    saida = BytesIO()
    imagem.save(saida, "JPEG", quality=90)
    return saida.getvalue()


def _lentes(valor: Any) -> tuple[int, ...]:
    if not isinstance(valor, list):
        return ()
    return tuple(sorted({int(v) for v in valor if isinstance(v, int) and 1 <= v <= 16}))


def _json(carga: bytes) -> dict[str, Any]:
    try:
        dados = json.loads(carga.rstrip(b"\0\n").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


class Cliente:
    """Uma sessão TCP Sofia. Não registra a senha nem o hash em mensagens de erro."""

    def __init__(self, conexao: Conexao, espera_s: float = ESPERA_S) -> None:
        self.conexao = conexao
        self.espera_s = espera_s
        self.socket: socket.socket | None = None
        self.sessao = 0
        self.sequencia = 0
        self.intervalo_vivo = 20
        self.canais = 1
        # Alarmes que chegam no meio de outra resposta: ficam para o laço dos alarmes.
        self.alarmes: list[dict[str, Any]] = []

    def __enter__(self) -> Cliente:
        try:
            self.socket = socket.create_connection((self.conexao.ip, PORTA), timeout=self.espera_s)
            self.socket.settimeout(self.espera_s)
            resposta = self.pedido(
                1000,
                {
                    "EncryptType": "MD5",
                    "LoginType": "DVRIP-Web",
                    "PassWord": hash_sofia(self.conexao.senha),
                    "UserName": self.conexao.usuario,
                },
                resposta=1001,
            )
        except (OSError, ValueError, CameraErro):
            self.fechar()
            raise
        codigo = resposta.get("Ret")
        if codigo not in (100, 515):
            self.fechar()
            raise CredenciaisInvalidas("Usuário ou senha inválidos.")
        self.sessao = _sessao(resposta.get("SessionID"), self.sessao)
        self.intervalo_vivo = max(5, min(300, int(resposta.get("AliveInterval", 20) or 20)))
        self.canais = max(1, min(16, int(resposta.get("ChannelNum", 1) or 1)))
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        if self.socket is not None:
            with contextlib.suppress(OSError):
                self.socket.close()
            self.socket = None

    def _ler(self, tamanho: int) -> bytes:
        if self.socket is None:
            raise CameraErro("A conexão com a câmera foi fechada.")
        partes = bytearray()
        while len(partes) < tamanho:
            bloco = self.socket.recv(tamanho - len(partes))
            if not bloco:
                raise CameraErro("A câmera encerrou a conexão.")
            partes.extend(bloco)
        return bytes(partes)

    def _enviar(self, codigo: int, carga: bytes) -> None:
        if self.socket is None:
            raise CameraErro("A conexão com a câmera foi fechada.")
        self.socket.sendall(quadro(self.sessao, self.sequencia, codigo, carga))
        self.sequencia += 1

    def conversa(self) -> socket.socket:
        """Abre a conversa nos dois sentidos e devolve o canal do áudio: uma segunda conexão,
        reservada (`Claim`) com a sessão desta. A ordem importa: reservar e só então mandar o
        `Start`. Ao contrário, a câmera aceita os dois, mas a conversa não abre (ADR 0088)."""
        sessao = f"0x{self.sessao:08X}"
        canal = socket.create_connection((self.conexao.ip, PORTA), timeout=self.espera_s)
        try:
            reserva = {"Name": "OPTalk", "SessionID": sessao,
                       "OPTalk": {"Action": "Claim", "AudioFormat": FALA}}  # fmt: skip
            canal.sendall(quadro(self.sessao, 0, 1434, _corpo(reserva)))
            cabecalho = _ler_de(canal, 20)
            resposta = _json(_ler_de(canal, struct.unpack_from("<I", cabecalho, 16)[0]))
            if resposta.get("Ret") != 100:
                raise CameraErro("A câmera não abriu o alto-falante.")
            inicio = self.pedido(
                1430,
                {
                    "Name": "OPTalk",
                    "SessionID": sessao,
                    "OPTalk": {"Action": "Start", "AudioFormat": FALA},
                },
                resposta=1431,
            )
            if inicio.get("Ret") not in (100, 503):  # 503: já estava aberta
                raise CameraErro("A câmera não abriu o alto-falante.")
        except (OSError, CameraErro):
            canal.close()
            raise
        return canal

    def encerrar_conversa(self) -> None:
        with contextlib.suppress(OSError, CameraErro):
            self.pedido(
                1430,
                {
                    "Name": "OPTalk",
                    "SessionID": f"0x{self.sessao:08X}",
                    "OPTalk": {"Action": "Stop", "AudioFormat": FALA},
                },
                resposta=1431,
            )

    def receber(self) -> tuple[int, bytes, int]:
        cabecalho = self._ler(20)
        if cabecalho[0] != 0xFF:
            raise CameraErro("A câmera enviou uma resposta inválida.")
        sessao = struct.unpack_from("<I", cabecalho, 4)[0]
        total, atual = cabecalho[12], cabecalho[13]
        codigo = struct.unpack_from("<H", cabecalho, 14)[0]
        tamanho = struct.unpack_from("<I", cabecalho, 16)[0]
        if tamanho > MAX_CARGA:
            raise CameraErro("A resposta da câmera excede o limite permitido.")
        self.sessao = sessao or self.sessao
        partes = [self._ler(tamanho)]
        # Algumas versões dividem uma resposta grande em vários quadros DVRIP.
        for _ in range(max(0, min(255, total - atual - 1))):
            proximo = self._ler(20)
            if proximo[0] != 0xFF or struct.unpack_from("<H", proximo, 14)[0] != codigo:
                raise CameraErro("A câmera dividiu a resposta de forma inválida.")
            tamanho_parte = struct.unpack_from("<I", proximo, 16)[0]
            if tamanho_parte > MAX_CARGA:
                raise CameraErro("A resposta da câmera excede o limite permitido.")
            partes.append(self._ler(tamanho_parte))
        return codigo, b"".join(partes), sessao

    def pedido(
        self,
        codigo: int,
        dados: dict[str, Any],
        resposta: int | None = None,
    ) -> dict[str, Any]:
        corpo = json.dumps(dados, separators=(",", ":"), ensure_ascii=False).encode() + b"\n\0"
        self._enviar(codigo, corpo)
        while True:
            recebido, carga, _sessao = self.receber()
            if recebido == 1504:
                self._guardar_alarme(carga)  # chegou entre o pedido e a resposta
                continue
            if recebido == VIVA and codigo != 1006:
                continue  # a resposta de um KeepAlive anterior, atrasada
            if resposta is not None and recebido != resposta:
                raise CameraErro("A câmera respondeu com uma operação inesperada.")
            return _json(carga)

    def manter_viva(self) -> None:
        self._enviar(
            1006,
            json.dumps(
                {"Name": "KeepAlive", "SessionID": f"0x{self.sessao:08X}"},
                separators=(",", ":"),
            ).encode()
            + b"\n\0",
        )

    def assinar_alarmes(self) -> None:
        self.pedido(
            1500,
            {"Name": "", "SessionID": f"0x{self.sessao:08X}"},
        )

    def _guardar_alarme(self, carga: bytes) -> None:
        evento = _json(carga)
        nome = str(evento.get("Name", ""))
        conteudo = evento.get(nome) if nome else None
        if isinstance(conteudo, dict):
            self.alarmes.append(conteudo)

    def ligar_alarmes_na_rede(self) -> bool:
        """Liga o envio do alarme de movimento aos clientes da rede (`MsgtoNetEnable`), que vem
        desligado de fábrica: sem ele, a câmera detecta mas não avisa ninguém na rede local.
        Só esse campo muda; o resto da configuração de detecção fica como está. True se mudou."""
        nome = "Detect.MotionDetect"
        sessao = f"0x{self.sessao:08X}"
        lido = self.pedido(1042, {"Name": nome, "SessionID": sessao}, resposta=1043)
        lentes = lido.get(nome)
        if lido.get("Ret") != 100 or not isinstance(lentes, list):
            raise CameraErro("A câmera não informou a detecção de movimento.")
        faltando = [
            lente
            for lente in lentes
            if isinstance(lente, dict)
            and isinstance(lente.get("EventHandler"), dict)
            and lente["EventHandler"].get("MsgtoNetEnable") is not True
        ]
        if not faltando:
            return False
        for lente in faltando:
            lente["EventHandler"]["MsgtoNetEnable"] = True
        gravado = self.pedido(
            1040, {"Name": nome, nome: lentes, "SessionID": sessao}, resposta=1041
        )
        if gravado.get("Ret") not in (100, 603):  # 603: aceito, vale depois de reiniciar
            raise CameraErro("A câmera não aceitou ligar o aviso de movimento.")
        return True

    def esperar_alarmes(
        self,
        parar: threading.Event,
        receber_alarme: Callable[[dict[str, Any]], None],
        ociosa: Callable[[], None] | None = None,
    ) -> None:
        if self.socket is None:
            raise CameraErro("A conexão com a câmera foi fechada.")
        proximo_vivo = time.monotonic() + self.intervalo_vivo
        self.socket.settimeout(self.espera_s)
        while not parar.is_set():
            agora = time.monotonic()
            if agora >= proximo_vivo:
                self.manter_viva()
                proximo_vivo = agora + self.intervalo_vivo
            if ociosa is not None:
                ociosa()
            while self.alarmes:
                receber_alarme(self.alarmes.pop(0))
            restante = max(0.0, proximo_vivo - time.monotonic())
            prontos, _escrita, _excecao = select.select([self.socket], [], [], min(0.5, restante))
            if not prontos:
                continue
            codigo, carga, _sessao = self.receber()
            if codigo == 1504:
                self._guardar_alarme(carga)

    def foto(self, canal: int = 0) -> bytes:
        if self.socket is None:
            raise CameraErro("A conexão com a câmera foi fechada.")
        # OPSNAP devolve um quadro binário (JPEG), não JSON.
        corpo = (
            json.dumps(
                {
                    "Name": "OPSNAP",
                    "SessionID": f"0x{self.sessao:08X}",
                    "OPSNAP": {"Channel": canal},
                },
                separators=(",", ":"),
            ).encode()
            + b"\n\0"
        )
        self._enviar(1560, corpo)
        while True:
            codigo, carga, _sessao = self.receber()
            if codigo == 1504:
                self._guardar_alarme(carga)
                continue
            if codigo == VIVA:
                continue  # o KeepAlive mandado logo antes respondeu primeiro
            if codigo != 1561:
                raise CameraErro("A câmera não respondeu ao pedido de foto.")
            jpeg = _jpeg(carga)
            if jpeg is None:
                raise CameraErro("A câmera respondeu sem uma foto JPEG.")
            return jpeg


def quadro(sessao: int, sequencia: int, codigo: int, carga: bytes) -> bytes:
    """Cabeçalho DVRIP de 20 bytes, little-endian, e a carga."""
    cabecalho = struct.pack(
        "<BBHIIBBHI", 0xFF, 0, 0, sessao, sequencia & 0xFFFFFFFF, 0, 0, codigo, len(carga)
    )
    return cabecalho + carga


def quadro_de_audio(alaw: bytes) -> bytes:
    return AUDIO + struct.pack("<H", len(alaw)) + alaw


def _corpo(dados: dict[str, Any]) -> bytes:
    return json.dumps(dados, separators=(",", ":"), ensure_ascii=False).encode() + b"\n\0"


def _ler_de(sock: socket.socket, tamanho: int) -> bytes:
    partes = bytearray()
    while len(partes) < tamanho:
        bloco = sock.recv(tamanho - len(partes))
        if not bloco:
            raise CameraErro("A câmera encerrou a conexão.")
        partes.extend(bloco)
    return bytes(partes)


def _sessao(valor: Any, atual: int) -> int:
    if isinstance(valor, str):
        try:
            return int(valor, 16) if valor.lower().startswith("0x") else int(valor)
        except ValueError:
            return atual
    return int(valor) if isinstance(valor, (int, float)) else atual


def _jpeg(carga: bytes) -> bytes | None:
    inicio = carga.find(b"\xff\xd8")
    if inicio < 0:
        # Algumas câmeras precedem o JPEG por um cabeçalho de mídia de 16 bytes.
        inicio = carga.find(b"\x00\x00\x01\xfe")
        if inicio >= 0:
            inicio += 16
            inicio = carga.find(b"\xff\xd8", inicio)
    if inicio < 0:
        return None
    fim = carga.find(b"\xff\xd9", inicio + 2)
    if fim < 0:
        return None
    return carga[inicio : fim + 2]


def _foto_rtsp(conexao: Conexao, canal: int = 0, espera_s: float = 12.0) -> bytes:
    """Decodifica um quadro por RTSP com ffmpeg opcional, sem pôr a senha nos argumentos."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise CameraErro("A câmera não respondeu ao pedido de foto.")
    url = (
        f"rtsp://{conexao.ip}:{PORTA_RTSP}/user={quote(conexao.usuario, safe='')}"
        f"&password={quote(conexao.senha, safe='')}&channel={canal + 1}&stream=0.sdp"
    )
    # O manifesto entra por um descritor anônimo herdado pelo ffmpeg. Assim a credencial não
    # aparece na lista de processos nem em arquivo temporário.
    manifesto = f"ffconcat version 1.0\nfile '{url}'\n".encode()
    leitura, escrita = os.pipe()
    try:
        os.write(escrita, manifesto)
    finally:
        os.close(escrita)
    try:
        processo = subprocess.run(  # noqa: S603 - executável local fixo, argumentos estruturados.
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-protocol_whitelist",
                "file,pipe,concat,rtsp,tcp,udp,crypto",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                f"pipe:{leitura}",
                "-an",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=espera_s,
            check=False,
            pass_fds=(leitura,),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise CameraErro("A câmera não respondeu ao pedido de foto.") from None
    finally:
        os.close(leitura)
    jpeg = _jpeg(processo.stdout or b"")
    if processo.returncode != 0 or jpeg is None:
        raise CameraErro("A câmera não respondeu ao pedido de foto.")
    return jpeg


def ip_local() -> str:
    """Escolhe o endereço de origem da rota local sem enviar pacotes."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))
        return str(s.getsockname()[0])


def porta_sofia_aberta(ip: str, espera_s: float = 0.35) -> bool:
    try:
        with socket.create_connection((ip, PORTA), timeout=espera_s):
            return True
    except OSError:
        return False


def descobrir() -> list[dict[str, str]]:
    """Procura a porta DVRIP apenas na sub-rede /24 privada desta máquina."""
    try:
        rede = ipaddress.ip_network(f"{ip_local()}/24", strict=False)
    except (OSError, ValueError):
        return []
    if not rede.is_private:
        return []
    with ThreadPoolExecutor(max_workers=64) as fila:
        ips = [str(ip) for ip in rede.hosts()]
        abertas = [
            ip for ip, aberta in zip(ips, fila.map(porta_sofia_aberta, ips), strict=True) if aberta
        ]
    return [{"ip": ip} for ip in abertas]


class Camera:
    """Configuração XDG da câmera e operações de teste/foto."""

    def __init__(
        self,
        arquivo: Path,
        criar_cliente: Callable[[Conexao], Cliente] = Cliente,
        localizar: Callable[[], list[dict[str, str]]] = descobrir,
        fotografar_rtsp: Callable[[Conexao, int], bytes] = _foto_rtsp,
    ) -> None:
        self.arquivo = arquivo
        self._criar_cliente = criar_cliente
        self._localizar = localizar
        self._fotografar_rtsp = fotografar_rtsp
        self.ao_mudar: Callable[[], None] | None = None

    def conexao(self) -> Conexao | None:
        try:
            dados = json.loads(self.arquivo.read_text())
            return Conexao(
                str(dados["ip"]),
                str(dados["usuario"]),
                str(dados["senha"]),
                int(dados.get("intervalo_s", 30)),
                bool(dados.get("ligado", True)),
                _lentes(dados.get("girar")),
                bool(dados.get("enviar", True)),
                _lentes(dados.get("sem_fotos")),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def guardar(
        self,
        ip: str,
        usuario: str,
        senha: str,
        intervalo_s: int = 30,
        ligado: bool = True,
        girar: list[int] | None = None,
        enviar: bool | None = None,
        sem_fotos: list[int] | None = None,
    ) -> None:
        """`girar`, `enviar` e `sem_fotos` None mantêm o que já estava no cadastro."""
        try:
            endereco = ipaddress.ip_address(ip.strip())
        except ValueError:
            raise CameraErro("Endereço IP inválido.") from None
        if not endereco.is_private or endereco.version != 4:
            raise CameraErro("A câmera precisa estar na rede local IPv4.")
        usuario = usuario.strip()
        if not usuario or len(usuario) > 64 or any(ord(c) < 32 for c in usuario):
            raise CameraErro("Usuário inválido.")
        atual = self.conexao()
        senha = senha or (atual.senha if atual else "")
        lentes = _lentes(girar) if girar is not None else (atual.girar if atual else ())
        if enviar is None:
            enviar = atual.enviar if atual else True
        caladas = (
            _lentes(sem_fotos) if sem_fotos is not None else (atual.sem_fotos if atual else ())
        )
        if not senha or len(senha) > 128 or any(ord(c) < 32 for c in senha):
            raise CameraErro("Senha do dispositivo inválida.")
        if not 1 <= intervalo_s <= 86400:
            raise CameraErro("O intervalo precisa ficar entre 1 e 86400 segundos.")
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(
            json.dumps(
                {
                    "ip": str(endereco),
                    "usuario": usuario,
                    "senha": senha,
                    "intervalo_s": intervalo_s,
                    "ligado": bool(ligado),
                    "girar": list(lentes),
                    "enviar": bool(enviar),
                    "sem_fotos": list(caladas),
                },
                ensure_ascii=False,
            )
        )
        os.chmod(temporario, 0o600)
        temporario.replace(self.arquivo)
        if self.ao_mudar is not None:
            self.ao_mudar()

    def para_tela(self) -> dict[str, Any]:
        conexao = self.conexao()
        if conexao is None:
            return {
                "configurada": False,
                "ip": "",
                "usuario": "admin",
                "intervalo_s": 30,
                "ligado": False,
                "girar": [],
                "enviar": True,
                "sem_fotos": [],
            }
        return {
            "configurada": True,
            "ip": conexao.ip,
            "usuario": conexao.usuario,
            "intervalo_s": conexao.intervalo_s,
            "ligado": conexao.ligado,
            "girar": list(conexao.girar),
            "enviar": conexao.enviar,
            "sem_fotos": list(conexao.sem_fotos),
        }

    def procurar(self) -> list[dict[str, str]]:
        return self._localizar()

    def testar(self) -> None:
        conexao = self._exigir()
        try:
            with self._criar_cliente(conexao):
                return
        except CredenciaisInvalidas:
            raise
        except (OSError, CameraErro):
            raise CameraErro("Sem conexão com a câmera.") from None

    def foto(self, canal: int = 0) -> bytes:
        conexao = self._exigir()
        try:
            with self._criar_cliente(conexao) as cliente:
                return cliente.foto(canal)
        except CredenciaisInvalidas:
            raise
        except (OSError, CameraErro):
            try:
                return self._fotografar_rtsp(conexao, canal)
            except (OSError, CameraErro):
                raise CameraErro("A câmera não respondeu ao pedido de foto.") from None

    def foto_rtsp(self, canal: int = 0) -> bytes:
        """Usa o fluxo RTSP como alternativa dentro da sessão do vigia."""
        try:
            return self._fotografar_rtsp(self._exigir(), canal)
        except (OSError, CameraErro):
            raise CameraErro("A câmera não respondeu ao pedido de foto.") from None

    def _exigir(self) -> Conexao:
        if (conexao := self.conexao()) is None:
            raise CameraErro("Câmera não configurada.")
        return conexao
