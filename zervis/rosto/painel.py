"""Painel de cérebros no Barehands: baterias e o ativo, e o clique de volta (ADR 0010).

Mesmo contrato do anel: arquivos pequenos em `state/`. O Zé escreve `cerebros.json`; o
`server.py` do Barehands o serve em `GET /cerebros` e, num clique, grava `escolha.json` só com
um id que esteja na lista. O Zé consome a escolha (apaga o arquivo) e faz a troca.
"""

import contextlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from zervis.cerebro.baterias import Bateria
from zervis.cerebro.catalogo import OPCOES

PRAZO_ESCOLHA_S = 30.0  # clique mais velho que isso (Zé parado na hora) é ignorado
RENOVAR_S = 30.0  # o Barehands esconde o painel se o arquivo envelhecer (Zé parado)


class Painel:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self.mostrado: dict[str, object] | None = None
        self.renovado = 0.0

    def mostrar(
        self, ativo: str, baterias: dict[str, Bateria], modelos: dict[str, str], agora: float
    ) -> None:
        lista = []
        for opcao in OPCOES.values():
            bateria = baterias.get(opcao.familia or "")
            lista.append(
                {
                    "id": opcao.id,
                    "nome": opcao.nome,
                    "modelo": modelos.get(opcao.id),
                    "ativo": opcao.id == ativo,
                    "bateria": asdict(bateria) if bateria else None,
                }
            )
        conteudo: dict[str, object] = {"lista": lista}
        if conteudo == self.mostrado and agora - self.renovado < RENOVAR_S:
            return
        self.mostrado, self.renovado = conteudo, agora
        with contextlib.suppress(OSError):
            arquivo = self.pasta / "cerebros.json"
            temporario = arquivo.with_suffix(".next")
            temporario.write_text(json.dumps({**conteudo, "ts": agora}, ensure_ascii=False))
            temporario.replace(arquivo)

    def escolha(self, agora: float | None = None) -> str | None:
        """O id clicado no Barehands, uma vez só; None se não houver clique válido."""
        arquivo = self.pasta / "escolha.json"
        try:
            dados = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            return None
        with contextlib.suppress(OSError):
            arquivo.unlink()
        agora = time.time() if agora is None else agora
        if not isinstance(dados, dict) or agora - float(dados.get("ts", 0)) > PRAZO_ESCOLHA_S:
            return None
        id_ = dados.get("id")
        return id_ if id_ in OPCOES else None
