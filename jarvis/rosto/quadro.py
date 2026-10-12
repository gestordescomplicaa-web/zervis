"""Cards no quadro do Barehands (portado de VIBE-CODING/jarvis/board.py, 06/10/2026).

Só o "present": centro do palco, o resto escurecido, para o que precisa de uma decisão (o diff de
uma skill que o usuário vai aprovar por voz). Só envia com a janela aberta: o servidor guarda os
comandos na memória até a página buscar, e abrir a janela depois despejaria tudo de uma vez.
"""

import json
import logging
import urllib.request
from collections.abc import Callable

log = logging.getLogger(__name__)
URL = "http://127.0.0.1:8794/cmd"


class Quadro:
    def __init__(self, aberto: Callable[[], bool], url: str = URL, token: str = "") -> None:
        self.aberto = aberto
        self.url = url
        self.token = token

    def apresentar(self, titulo: str, corpo: str, ttl: int = 60) -> bool:
        if not self.aberto():
            return False
        comando = {"a": "present", "title": titulo[:60], "body": corpo[:1500], "ttl": ttl}
        pedido = urllib.request.Request(  # noqa: S310 (URL fixa em loopback)
            self.url,
            data=json.dumps(comando, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "X-Ze-Token": self.token},
        )
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            abridor.open(pedido, timeout=2).close()
        except OSError as erro:
            log.info("quadro indisponível: %s", erro)
            return False
        return True
