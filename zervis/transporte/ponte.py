"""A ponte de uma ligação do WhatsApp com o app de voz (ADR 0066): você atende pelo celular.

Quando alguém liga e pede para falar com você, e você diz "sim", a Central passa a ligação para
cá: a voz da pessoa chega pela ponte (WebSocket local da Central, PCM 16 kHz) e vai ao app como a
fala do Zé; o microfone do app, em vez do "Ei Zé", vai à pessoa. O app já toca e grava ao mesmo
tempo, no modo de ligação do celular, que tira o eco: não muda nada nele para o áudio.

Enquanto a ligação dura, **só a ponte fala com o app** (`SoAPonte`). Na primeira ligação de verdade
(06/11/2026), o Zé respondeu ao seu "sim" pelo Live depois que a ponte abriu: a fala dele anunciou
outra taxa ao app, que passou a tocar a pessoa nela (a voz alterada), e o "fim" de cada frase
silenciava o microfone do celular por um instante (o áudio travado). Agora a fala do Zé, a taxa e
o fim de frase que não vêm da ponte são descartados; o resto (as notificações) passa.

Fecha quando a pessoa desliga (a Central fecha a ponte), quando você encerra (`fechar`) ou quando
o app cai.
"""

import contextlib
import json
import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)
TAXA = 16000
FOLGA_S = 0.2  # silêncio no começo: o app guarda essa folga contra os soluços da rede
_DO_AUDIO = frozenset({"voz", "fim", "parar"})


class SoAPonte:
    """A conexão do app durante a ligação: a fala do Zé (avisos, o Live, a resposta ao "sim") não
    entra; a ponte usa a conexão de verdade (`real`)."""

    def __init__(self, real: Any) -> None:
        self.real = real

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.real, nome)

    def binario(self, dados: bytes) -> None:
        return None

    def texto(self, dados: str) -> None:
        with contextlib.suppress(ValueError, TypeError):
            if json.loads(dados).get("tipo") in _DO_AUDIO:
                return
        self.real.texto(dados)


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
        self._app: Any = None  # a conexão de verdade com o app
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
        self._app = self.voz.conexao
        self.voz.conexao = SoAPonte(self._app)  # daqui em diante, só a ponte fala com o app
        self.voz.sem_eco = True
        self.ativa = True
        with contextlib.suppress(Exception):
            # O app toca a pessoa como toca a fala do Zé, a 16 kHz, com uma folga no começo.
            self._app.texto(json.dumps({"tipo": "voz", "taxa": TAXA}))
            self._app.binario(b"\0\0" * int(TAXA * FOLGA_S))
        threading.Thread(target=self._receber, name="ponte-da-ligacao", daemon=True).start()

    def _receber(self) -> None:
        try:
            for mensagem in self._ws:
                if isinstance(mensagem, bytes) and self._app.aberta:
                    self._app.binario(mensagem)
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
        if isinstance(self.voz.conexao, SoAPonte):
            self.voz.conexao = self._app  # o Zé volta a falar com o app
        self.voz.sem_eco = False
        with contextlib.suppress(Exception):
            self._app.texto(json.dumps({"tipo": "fim"}))
        self.ao_fim(self)
