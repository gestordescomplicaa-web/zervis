"""WebSocket mínimo (RFC 6455) sobre o servidor HTTP do painel, para a voz pelo navegador.

O áudio do celular entra pelo mesmo endereço do painel (roteiro, passo 4.2): onde o HTTPS do
painel chega (Wi-Fi, 4G, túnel, domínio da VPS), a voz chega junto, sem outra porta. Só o que a
voz usa: mensagens de texto e binárias inteiras, ping e fechamento; quadros do cliente sempre
mascarados, como manda a norma.
"""

import base64
import contextlib
import hashlib
import struct
import threading
from http.server import BaseHTTPRequestHandler
from io import BufferedIOBase

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAXIMO = 1024 * 1024  # uma mensagem; o áudio vai em pedaços de 80 ms (2,5 KB)
TEXTO, BINARIO, FECHAR, PING, PONG = 1, 2, 8, 9, 10


class FechouErro(ConnectionError):
    pass


def aceite(chave: str) -> str:
    return base64.b64encode(hashlib.sha1((chave + GUID).encode()).digest()).decode()  # noqa: S324 (exigido pela norma)


def aceitar(tratador: BaseHTTPRequestHandler) -> "Conexao | None":
    """Responde ao pedido de upgrade; None se não for um pedido de WebSocket válido."""
    cab = tratador.headers
    chave = cab.get("Sec-WebSocket-Key", "")
    if cab.get("Upgrade", "").lower() != "websocket" or not chave:
        return None
    # Escrito à mão: o servidor do painel responde em HTTP/1.0, e o aceite precisa ser HTTP/1.1.
    tratador.wfile.write(
        b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        + f"Sec-WebSocket-Accept: {aceite(chave)}\r\n\r\n".encode()
    )
    tratador.wfile.flush()
    tratador.close_connection = True
    return Conexao(tratador.rfile, tratador.wfile)


class Conexao:
    def __init__(self, leitura: BufferedIOBase, escrita: BufferedIOBase) -> None:
        self.leitura = leitura
        self.escrita = escrita
        self.aberta = True
        self._trava = threading.Lock()

    def _ler(self, n: int) -> bytes:
        dados = self.leitura.read(n)
        if dados is None or len(dados) < n:
            self.aberta = False
            raise FechouErro("conexão encerrada")
        return dados

    def receber(self) -> tuple[int, bytes]:
        """A próxima mensagem inteira (texto ou binária); responde ao ping sozinho."""
        partes: list[bytes] = []
        tipo = 0
        while True:
            b0, b1 = self._ler(2)
            opcode, fim = b0 & 0x0F, bool(b0 & 0x80)
            tamanho = b1 & 0x7F
            if tamanho == 126:
                tamanho = struct.unpack("!H", self._ler(2))[0]
            elif tamanho == 127:
                tamanho = struct.unpack("!Q", self._ler(8))[0]
            if tamanho > MAXIMO or not b1 & 0x80:
                self.fechar()
                raise FechouErro("quadro inválido")
            mascara = self._ler(4)
            bruto = self._ler(tamanho)
            chave = (mascara * (tamanho // 4 + 1))[:tamanho]
            carga = (int.from_bytes(bruto) ^ int.from_bytes(chave)).to_bytes(tamanho)
            if opcode == FECHAR:
                self.fechar()
                raise FechouErro("fechada pelo cliente")
            if opcode == PING:
                self._enviar(PONG, carga)
                continue
            if opcode == PONG:
                continue
            if opcode in (TEXTO, BINARIO):
                tipo = opcode
            partes.append(carga)
            if sum(len(p) for p in partes) > MAXIMO:
                self.fechar()
                raise FechouErro("mensagem grande demais")
            if fim:
                return tipo, b"".join(partes)

    def _enviar(self, opcode: int, carga: bytes) -> None:
        n = len(carga)
        if n < 126:
            cabeca = struct.pack("!BB", 0x80 | opcode, n)
        elif n < 65536:
            cabeca = struct.pack("!BBH", 0x80 | opcode, 126, n)
        else:
            cabeca = struct.pack("!BBQ", 0x80 | opcode, 127, n)
        with self._trava:
            if not self.aberta:
                raise FechouErro("conexão encerrada")
            try:
                self.escrita.write(cabeca + carga)
                self.escrita.flush()
            except OSError as erro:
                self.aberta = False
                raise FechouErro("conexão encerrada") from erro

    def texto(self, mensagem: str) -> None:
        self._enviar(TEXTO, mensagem.encode())

    def binario(self, dados: bytes) -> None:
        self._enviar(BINARIO, dados)

    def fechar(self) -> None:
        if self.aberta:
            with contextlib.suppress(FechouErro):
                self._enviar(FECHAR, b"")
        self.aberta = False
