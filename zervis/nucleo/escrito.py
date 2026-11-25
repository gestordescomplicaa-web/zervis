"""O pedido escrito no chat do Início (ADR 0136): vira um Digitado, como no Teclado do Núcleo, com
os anexos no fim pelo nome guardado (ADR 0137); o cérebro os lê com anexo_ler."""

import logging
from typing import Any

from zervis.memoria import anexos
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import LIMITE_ESCRITO

log = logging.getLogger(__name__)


def pedir(n: Any, texto: str, nomes: list[str]) -> str:
    """O aviso para o painel ("Enviado." ou o motivo de não ter ido)."""
    texto = " ".join(texto.split())[:LIMITE_ESCRITO]
    if not texto and not nomes:
        return "Mensagem vazia."
    estado = n.maquina.estado
    if estado is e.Estado.INATIVO:
        return "O Zé está inativo."
    confirmando = estado is e.Estado.CONFIRMANDO
    if nomes:
        loja = getattr(n, "anexos", None) or anexos.PADRAO
        if len(nomes) > anexos.MAX_POR_PEDIDO or any(loja.caminho(x) is None for x in nomes):
            return "Anexo não encontrado."
        if confirmando:
            return "Responda a confirmação antes de anexar."
        texto = texto or ("Veja o anexo." if len(nomes) == 1 else "Veja os anexos.")
    if not confirmando and not e.pedido_valido(texto):
        return "Não entendi o que foi escrito."
    log.info("painel: pedido escrito (%d caracteres, %d anexos)", len(texto), len(nomes))
    n.eventos.put(e.Digitado(anexos.marcar(texto, nomes)))
    return "Enviado."
