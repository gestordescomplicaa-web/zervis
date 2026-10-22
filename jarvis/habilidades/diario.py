"""Diário de aprendizado: o que o Zé aprendeu, quando e de onde veio (pedido do usuário,
06/10/2026).

Antes, uma sugestão aprovada sumia da lista e só restava a frase na memória, sem data nem a
conversa de origem. Aqui cada mudança aprovada (sugestão, memória, skill) e cada skill arquivada
pela curadoria vira uma linha. Só cresce; a pasta do Zé no Barehands mostra as últimas.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any

LIMITE_RESUMO = 300

# Rótulo legível de cada tipo de evento (a pasta do Zé mostra isso).
EVENTOS = {
    "aprovada": "Sugestão aprovada",
    "descartada": "Sugestão descartada",
    "memoria": "Memória mudada a pedido",
    "skill": "Skill gravada a pedido",
    "arquivada": "Skill arquivada sem uso",
}


class Diario:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self.trava = threading.Lock()  # o cérebro e o núcleo escrevem de threads diferentes

    def registrar(self, evento: str, resumo: str, **extra: Any) -> None:
        linha = {"em": round(time.time()), "evento": evento, "resumo": resumo[:LIMITE_RESUMO]}
        linha |= {chave: valor for chave, valor in extra.items() if valor}
        with self.trava:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.arquivo.open("a") as saida:
                saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
            self.arquivo.chmod(0o600)

    def ultimos(self, quantos: int = 50) -> list[dict[str, Any]]:
        """Os eventos mais novos primeiro; linha corrompida é pulada."""
        try:
            linhas = self.arquivo.read_text().splitlines()
        except OSError:
            return []
        eventos = []
        for linha in reversed(linhas):
            try:
                dado = json.loads(linha)
            except ValueError:
                continue
            if isinstance(dado, dict):
                eventos.append(dado)
            if len(eventos) >= quantos:
                break
        return eventos
