"""Instâncias dos serviços, preservadas também nos adaptadores de compatibilidade."""

from collections.abc import Callable
from typing import Any, cast


def servico[T](contexto: Any, tipo: Callable[[Any], T]) -> T:
    guardados = contexto.__dict__.setdefault("_servicos_por_tipo", {})
    if tipo not in guardados:
        guardados[tipo] = tipo(contexto)
    return cast(T, guardados[tipo])


class InterfaceServico:
    pass
