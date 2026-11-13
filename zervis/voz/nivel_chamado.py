"""O volume mínimo do "Ei Zé" no microfone deste computador, calibrado pela voz de quem usa.

O detector do chamado dispara também com o som que vaza do fone, como um vídeo. De 09 a
13/11/2026, 46 das 108 ativações no PC não viraram pedido; abaixo de -30 dBFS, foram 30 de 40. A
voz de quem chamava ao microfone do fone ficou entre -29 e -20 dBFS. O piso fixo da configuração
(`ativacao.nivel_minimo_dbfs`, -45) serve a qualquer microfone. Depois de dez chamados que
viraram pedido com texto, o mínimo passa a ser a mediana deles menos uma margem, sem descer do
piso nem passar do teto. Só o microfone deste computador conta: o do navegador ou do celular tem
outro volume.
"""

import json
import statistics
import threading
import time
from pathlib import Path

from zervis import lugares

AMOSTRAS = 30  # os chamados mais recentes que viraram pedido
MINIMO_DE_AMOSTRAS = 10
MARGEM_DB = 6.0  # abaixo da voz típica de quem chama
TETO_DBFS = -25.0  # nunca exige mais que isto, para quem fala baixo não ficar sem o chamado
PRAZO_S = 30.0  # a transcrição que conta é a do pedido logo depois do chamado


class NivelDoChamado:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self._pendente: tuple[float, float] | None = None  # (nível, quando)
        self._trava = threading.Lock()

    def niveis(self) -> list[float]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return []
        return (
            [float(v) for v in dados if isinstance(v, int | float)]
            if isinstance(dados, list)
            else []
        )

    def minimo(self, piso: float) -> float:
        niveis = self.niveis()
        if len(niveis) < MINIMO_DE_AMOSTRAS:
            return piso
        return min(TETO_DBFS, max(piso, statistics.median(niveis) - MARGEM_DB))

    def ativou(self, nivel: float, agora: float | None = None) -> None:
        """Um chamado passou: o nível dele conta se o pedido logo depois tiver texto."""
        self._pendente = (nivel, time.monotonic() if agora is None else agora)

    def ouviu(self, texto: str, agora: float | None = None) -> None:
        pendente, self._pendente = self._pendente, None
        agora = time.monotonic() if agora is None else agora
        if pendente is None or not texto.strip() or agora - pendente[1] > PRAZO_S:
            return
        with self._trava:
            niveis = [*self.niveis(), round(pendente[0], 1)][-AMOSTRAS:]
            self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporario = self.arquivo.with_suffix(".next")
            temporario.write_text(json.dumps(niveis))
            temporario.replace(self.arquivo)


PADRAO = NivelDoChamado(lugares.ESTADO / "chamado-niveis.json")
