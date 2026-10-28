"""A voz pelo navegador dentro do HTTPS do painel (roteiro, passo 4.2).

O navegador manda o microfone em PCM de 16 bits pelo WebSocket do painel; o Zé o entrega à mesma
fila do laço, em quadros de 80 ms a 16 kHz, como o microfone local e a sala LiveKit. A voz do Piper
volta pelo mesmo canal: uma mensagem de texto anuncia a taxa da fala, os pedaços seguem em PCM de 16
bits e "parar" corta o que ainda não tocou (interrupção).

Funciona por onde o painel funcionar (Wi-Fi, 4G, túnel, domínio da VPS), sem UDP nem TURN: o
caminho que o Chrome do Android não fazia pela VPN (teste de 12/10/2026).
"""

import contextlib
import json
import logging
import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from zervis.transporte.websocket import BINARIO, Conexao, FechouErro

log = logging.getLogger(__name__)
TAXA = 16000
BYTES_QUADRO = 2560  # 80 ms a 16 kHz, 16 bits
LACUNA_S = 0.5  # sem quadro de áudio por mais que isto: vai para o registro
FOLGA_S = 0.5  # quanto a voz pode ir à frente do que já tocou (interromper corta isto)


def reamostrar(pcm: bytes, taxa: int) -> bytes:
    """PCM de 16 bits de outra taxa (o navegador que não aceitou 16 kHz) para 16 kHz."""
    if taxa == TAXA or not pcm:
        return pcm
    entrada = np.frombuffer(pcm, "<i2").astype(np.float32)
    n = max(1, round(len(entrada) * TAXA / taxa))
    saida = np.interp(np.linspace(0, len(entrada) - 1, n), np.arange(len(entrada)), entrada)
    return saida.astype("<i2").tobytes()


class VozNavegador:
    """Uma conexão de voz aberta pelo botão "Conectar voz" do navegador (antes, "Ao vivo")."""

    def __init__(
        self, conexao: Conexao, taxa: int = TAXA, ao_vivo: bool = True, do_app: bool = False
    ) -> None:
        self.conexao = conexao
        self.taxa = taxa if 8000 <= taxa <= 96000 else TAXA
        # O navegador é sempre ao vivo (ADR 0023); o app de voz do celular escolhe: ao vivo ou o
        # chamado ("Ei Zé" e o botão do fone), como o microfone do PC.
        self.ao_vivo = ao_vivo
        # O app de voz fala e ouve mesmo com o Zé no Silencioso, que vale para o PC (ADR 0018).
        self.do_app = do_app

    @property
    def conectada(self) -> bool:
        return self.conexao.aberta

    def ouvir(
        self,
        ao_quadro: Callable[[bytes], None],
        ao_controle: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        """Entrega o microfone em quadros de 80 ms até a conexão fechar; as mensagens de texto
        (o botão do fone, no app) vão para `ao_controle`."""
        resto = b""
        ultimo = time.monotonic()
        try:
            while True:
                tipo, dados = self.conexao.receber()
                if tipo != BINARIO:
                    if ao_controle is not None:
                        with contextlib.suppress(ValueError, UnicodeDecodeError):
                            if isinstance(mensagem := json.loads(dados), dict):
                                ao_controle(mensagem)
                    continue
                agora = time.monotonic()
                if agora - ultimo > LACUNA_S:
                    # O navegador manda um quadro a cada 80 ms, mesmo no silêncio: um buraco
                    # destes é rede (4G, túnel) ou o celular com a tela apagada.
                    log.warning("voz do navegador: %.1f s sem áudio", agora - ultimo)
                ultimo = agora
                resto += reamostrar(dados[: len(dados) // 2 * 2], self.taxa)
                while len(resto) >= BYTES_QUADRO:
                    ao_quadro(resto[:BYTES_QUADRO])
                    resto = resto[BYTES_QUADRO:]
        except FechouErro:
            return

    def controle(self, **dados: object) -> None:
        with contextlib.suppress(FechouErro):
            self.conexao.texto(json.dumps(dados))

    def tocador(self, taxa: int) -> "TocadorNavegador":
        return TocadorNavegador(self, taxa)

    def tocar_wav(self, arquivo: Path) -> None:
        """Um som curto (o bip) pelo navegador, até o fim."""
        with wave.open(str(arquivo)) as w:
            taxa, canais, pcm = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
        amostras = np.frombuffer(pcm, "<i2").reshape(-1, canais).mean(axis=1) / 32768.0
        t = self.tocador(taxa)
        t.write(amostras.astype("<f4").tobytes())
        t.close()
        t.wait()


class TocadorNavegador:
    """O pedaço do `subprocess.Popen` que a saída de voz usa, mandando a fala ao navegador:
    float32 do Piper vira PCM de 16 bits, no ritmo da fala (no máximo `FOLGA_S` adiantado), para
    o fim da fala e a interrupção valerem como no alto-falante."""

    def __init__(self, voz: VozNavegador, taxa: int) -> None:
        self.voz = voz
        self.taxa = taxa
        self.codigo: int | None = None
        self.stdin = self
        self.enviado_s = 0.0
        self.inicio: float | None = None
        self._resto = b""
        self._parado = threading.Event()
        voz.controle(tipo="voz", taxa=taxa)

    def write(self, dados: bytes) -> int:
        if self.codigo is not None or not self.voz.conectada:
            raise BrokenPipeError
        junto = self._resto + dados
        corte = len(junto) // 4 * 4
        self._resto = junto[corte:]
        if not corte:
            return len(dados)
        amostras = np.frombuffer(junto[:corte], "<f4")
        try:
            self.voz.conexao.binario((np.clip(amostras, -1, 1) * 32767).astype("<i2").tobytes())
        except FechouErro as erro:
            raise BrokenPipeError from erro
        if self.inicio is None:
            self.inicio = time.monotonic()
        self.enviado_s += len(amostras) / self.taxa
        adiante = self.enviado_s - (time.monotonic() - self.inicio) - FOLGA_S
        if adiante > 0 and self._parado.wait(adiante):
            raise BrokenPipeError
        return len(dados)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self.codigo is None:
            self.voz.controle(tipo="fim")

    def poll(self) -> int | None:
        return self.codigo

    def wait(self) -> int:
        if self.codigo is None:
            fim = (self.inicio or time.monotonic()) + self.enviado_s + 0.15
            self._parado.wait(max(0.0, fim - time.monotonic()))
            if self.codigo is None:
                self.codigo = 0
        return self.codigo

    def kill(self) -> None:
        self.codigo = -9
        self._parado.set()
        self.voz.controle(tipo="parar")
