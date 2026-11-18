"""A Imersão pelo painel (ADR 0100): o palco do Zé, com o avatar e os cards, aberto de qualquer
aparelho que entrou no painel, e não só do próprio PC.

O servidor do palco (`zervis/imersivo/servidor.py`) só aceita o próprio PC (ADR 0019). O painel
repassa a ele, em `/imersao/...`, o que chega de quem já entrou com a senha. O pedido vai como se
fosse do PC (o `Host` do palco, sem `Origin` nem cookie) e continua precisando do token do
palco, que vem na página. O que mexe na máquina do Zé não passa: a câmera, e gravar a
calibração das mãos (ler o perfil passa). De fora, o palco abre sem câmera (`camera=0`).
"""

import http.client
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

PREFIXO = "/imersao/"
CAMERA = "/camera/"
MAOS = "/maos/"
MAXIMO_CORPO = 1_000_000
PRAZO_S = 15.0
PEDACO = 64 * 1024
# O que o navegador manda e o palco usa; o resto (cookie, origem, endereço de quem pediu) fica.
CABECALHOS_DO_PEDIDO = (
    "content-type",
    "x-ze-token",
    "range",
    "accept",
    "if-none-match",
    "if-modified-since",
)
# O que não atravessa um repasse (RFC 9110, seção 7.6.1) e o que o painel reescreve.
SEM_REPASSE = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "proxy-connection",
    "date",
    "server",
}


@dataclass
class Resposta:
    status: int
    cabecalhos: list[tuple[str, str]]
    _resposta: http.client.HTTPResponse
    _conexao: http.client.HTTPConnection

    def pedacos(self) -> Iterator[bytes]:
        try:
            while dados := self._resposta.read(PEDACO):
                yield dados
        finally:
            self._conexao.close()


def bloqueado(metodo: str, caminho: str) -> bool:
    """O que de fora não alcança: a câmera da máquina do Zé e gravar a calibração das mãos."""
    return caminho.startswith(CAMERA) or (metodo != "GET" and caminho.startswith(MAOS))


def repassar(
    metodo: str, alvo: str, cabecalhos: Mapping[str, str], corpo: bytes, porta: int
) -> Resposta:
    """`alvo` é o caminho no palco, com a consulta (`/stage.html?camera=0`)."""
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=PRAZO_S)
    enviados = {k: v for k, v in cabecalhos.items() if k.lower() in CABECALHOS_DO_PEDIDO}
    enviados["Host"] = f"127.0.0.1:{porta}"
    if metodo == "POST":
        enviados["Content-Length"] = str(len(corpo))
    try:
        conexao.request(metodo, alvo, body=corpo if metodo == "POST" else None, headers=enviados)
        resposta = conexao.getresponse()
    except Exception:
        conexao.close()
        raise
    saida = [(k, v) for k, v in resposta.getheaders() if k.lower() not in SEM_REPASSE]
    return Resposta(resposta.status, saida, resposta, conexao)
