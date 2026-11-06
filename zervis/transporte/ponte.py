"""A ponte de uma ligação do WhatsApp com o app de voz (ADR 0066): você atende pelo celular.

Quando alguém liga e pede para falar com você, e você diz "sim", a Central passa a ligação para
cá: a voz da pessoa chega pela ponte (WebSocket local da Central, PCM 16 kHz) e vai ao app como a
fala do Zé; o microfone do app, em vez do "Ei Zé", vai à pessoa. O app já toca e grava ao mesmo
tempo, no modo de ligação do celular, que tira o eco: não muda nada nele para o áudio.

Fecha quando a pessoa desliga (a Central fecha a ponte), quando você encerra (`fechar`) ou quando
o app cai.
"""

import contextlib
import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)
TAXA = 16000


class Ponte:
    def __init__(
        self,
        url: str,
        token: str,
        voz: Any,  # a VozNavegador do app
        ao_fim: Callable[["Ponte"], None],
        conectar: Callable[..., Any] | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.voz = voz
        self.ao_fim = ao_fim
        self._conectar = conectar
        self._ws: Any = None
        self._trava = threading.Lock()
        self.ativa = False
        self.chamada = ""  # o id da ligação na Central

    def iniciar(self) -> None:
        if self._conectar is None:
            from websockets.sync.client import connect

            self._conectar = connect
        self._ws = self._conectar(
            self.url, additional_headers={"X-Atendimento-Token": self.token}, max_size=2**16
        )
        self.ativa = True
        self.voz.controle(tipo="voz", taxa=TAXA)  # o app toca a pessoa como toca a fala do Zé
        threading.Thread(target=self._receber, name="ponte-da-ligacao", daemon=True).start()

    def _receber(self) -> None:
        try:
            for mensagem in self._ws:
                if isinstance(mensagem, bytes) and self.voz.conectada:
                    self.voz.conexao.binario(mensagem)
        except Exception:
            log.info("ponte: a ligação fechou")
        finally:
            self._encerrar()

    def enviar(self, quadro: bytes) -> None:
        """Um quadro do microfone do app (80 ms) para a pessoa."""
        if not self.ativa:
            return
        try:
            with self._trava:
                self._ws.send(quadro)
        except Exception:
            self.fechar()

    def fechar(self) -> None:
        with contextlib.suppress(Exception):
            self._ws.close()

    def _encerrar(self) -> None:
        if not self.ativa:
            return
        self.ativa = False
        with contextlib.suppress(Exception):
            self.voz.controle(tipo="fim")
        self.ao_fim(self)
