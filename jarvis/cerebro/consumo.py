"""Consumo de tokens do dia: cada resposta do cérebro soma aqui (pedido do usuário, 06/10/2026).

Na assinatura não se paga por token, mas tudo gasta as janelas de uso (as baterias). Medido em
06/10/2026: um turno lê ~6,4 mil tokens de contexto, quase todos do cache; o primeiro turno de
uma sessão cria o cache (~3,2 mil). O total do dia vai para o log, o `status.json` e o relatório
de baterias, para dar para ver quando algo novo (skill, MCP, revisão) começar a pesar.

Ao virar o dia, o dia anterior vai para `consumo-dias.json` (os últimos `DIAS_GUARDADOS`): a
pasta do JARVIS mostra a média por resposta caindo (ou não) conforme ele aprende.
"""

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
DIAS_GUARDADOS = 60
CAMPOS = {
    "entrada": "input_tokens",
    "cache_lido": "cache_read_input_tokens",
    "cache_criado": "cache_creation_input_tokens",
    "saida": "output_tokens",
}


class Consumo:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self.dias = arquivo.with_name("consumo-dias.json")
        self.trava = threading.Lock()
        try:
            self.hoje: dict[str, Any] = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            self.hoje = {}

    def _do_dia(self) -> dict[str, Any]:
        dia = date.today().isoformat()
        if self.hoje.get("dia") != dia:
            if self.hoje.get("respostas"):
                self._guardar_dia(self.hoje)
            self.hoje = {"dia": dia, "respostas": 0, "locais": 0, **dict.fromkeys(CAMPOS, 0)}
        return self.hoje

    def _guardar_dia(self, dia: dict[str, Any]) -> None:
        historico = [d for d in self.historico() if d.get("dia") != dia.get("dia")]
        historico = [*historico, dia][-DIAS_GUARDADOS:]
        temporario = self.dias.with_suffix(".next")
        temporario.write_text(json.dumps(historico))
        temporario.replace(self.dias)

    def historico(self) -> list[dict[str, Any]]:
        """Os dias anteriores, do mais velho ao mais novo."""
        try:
            dias = json.loads(self.dias.read_text())
        except (OSError, ValueError):
            return []
        return [d for d in dias if isinstance(d, dict)] if isinstance(dias, list) else []

    def retrato(self) -> dict[str, Any]:
        with self.trava:
            return dict(self._do_dia())

    def _salvar(self) -> None:
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps(self.hoje))
        temporario.replace(self.arquivo)

    def somar_local(self) -> None:
        """Um pedido resolvido pelo próprio núcleo, sem ir ao cérebro (zero token)."""
        with self.trava:
            hoje = self._do_dia()
            hoje["locais"] = hoje.get("locais", 0) + 1
            self._salvar()

    def somar(self, uso: dict[str, Any] | None, provedor: str) -> None:
        if not uso:
            return
        with self.trava:
            hoje = self._do_dia()
            turno = {nome: int(uso.get(chave) or 0) for nome, chave in CAMPOS.items()}
            for nome, valor in turno.items():
                hoje[nome] += valor
            hoje["respostas"] += 1
            self._salvar()
        log.info(
            "consumo (%s): leu %d (cache %d, criou %d), escreveu %d",
            provedor,
            turno["entrada"] + turno["cache_lido"] + turno["cache_criado"],
            turno["cache_lido"],
            turno["cache_criado"],
            turno["saida"],
        )

    def resumo_falado(self) -> str:
        with self.trava:
            hoje = dict(self._do_dia())
        if not hoje["respostas"]:
            return "Hoje ainda não respondi nada pelo cérebro."
        lido = hoje["entrada"] + hoje["cache_lido"] + hoje["cache_criado"]
        cache = round(100 * hoje["cache_lido"] / lido) if lido else 0
        saida = hoje["saida"]
        escritos = f"{saida}" if saida < 1000 else f"{round(saida / 1000)} mil"
        return (
            f"Hoje foram {hoje['respostas']} respostas, com {round(lido / 1000)} mil tokens lidos, "
            f"{cache}% do cache, e {escritos} escritos."
        )


class UsoDeFerramentas:
    """Quantas vezes cada ferramenta foi usada e quando (o mapa do cérebro mostra as conexões
    que de fato trabalham). Só o núcleo escreve, ao fim de cada resposta."""

    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self.trava = threading.Lock()

    def ler(self) -> dict[str, dict[str, int]]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def somar(self, nomes: list[str], agora: float) -> None:
        if not nomes:
            return
        with self.trava:
            uso = self.ler()
            for nome in nomes:
                registro = uso.setdefault(nome, {"usos": 0})
                registro["usos"] += 1
                registro["ultimo"] = round(agora)
            temporario = self.arquivo.with_suffix(".next")
            temporario.write_text(json.dumps(uso))
            temporario.replace(self.arquivo)
