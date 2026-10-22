"""Consumo de tokens do dia: cada resposta do cérebro soma aqui (pedido do usuário, 06/10/2026).

Na assinatura não se paga por token, mas tudo gasta as janelas de uso (as baterias). Medido em
06/10/2026: um turno lê ~6,4 mil tokens de contexto, quase todos do cache; o primeiro turno de
uma sessão cria o cache (~3,2 mil). O total do dia vai para o log, o `status.json` e o relatório
de baterias, para dar para ver quando algo novo (skill, MCP, revisão) começar a pesar.

Ao virar o dia, o dia anterior é arquivado em `consumo.db` (os últimos `DIAS_GUARDADOS`): a
pasta do Zé mostra a média por resposta caindo (ou não) conforme ele aprende.
"""

import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any

from jarvis.dados.documentos import Documentos, lista_json, objeto_json

log = logging.getLogger(__name__)
DIAS_GUARDADOS = 60
CAMPOS = {
    "entrada": "input_tokens",
    "cache_lido": "cache_read_input_tokens",
    "cache_criado": "cache_creation_input_tokens",
    "saida": "output_tokens",
}


class Consumo:
    def __init__(self, arquivo: Path, legado: Path | None = None) -> None:
        self._dados = Documentos(arquivo)
        self.arquivo = self._dados.banco.arquivo
        antigo = legado or arquivo
        self.dias = antigo.with_name("consumo-dias.json")
        self._dados.importar(self.dias, lista_json, "dias", campo_chave="dia")
        self._dados.importar(antigo, objeto_json, "consumo", chave="hoje")
        self.trava = threading.Lock()
        self._hoje: dict[str, Any] = self._dados.ler("consumo", "hoje") or {}

    @property
    def hoje(self) -> dict[str, Any]:
        return self.retrato()

    def _do_dia(self) -> dict[str, Any]:
        self._hoje = self._dados.ler("consumo", "hoje") or self._hoje
        dia = date.today().isoformat()
        if self._hoje.get("dia") != dia:
            if self._hoje.get("respostas"):
                self._guardar_dia(self._hoje)
            self._hoje = {"dia": dia, "respostas": 0, "locais": 0, **dict.fromkeys(CAMPOS, 0)}
            self._salvar()
        return self._hoje

    def _guardar_dia(self, dia: dict[str, Any]) -> None:
        historico = [d for d in self.historico() if d.get("dia") != dia.get("dia")]
        self._dados.substituir("dias", [*historico, dia][-DIAS_GUARDADOS:], "dia")

    def historico(self) -> list[dict[str, Any]]:
        return self._dados.listar("dias")

    def retrato(self) -> dict[str, Any]:
        with self.trava, self._dados.banco.transacao():
            return dict(self._do_dia())

    def _salvar(self) -> None:
        self._dados.guardar("consumo", self._hoje, "hoje")

    def somar_local(self) -> None:
        """Um pedido resolvido pelo próprio núcleo, sem ir ao cérebro (zero token)."""
        with self.trava, self._dados.banco.transacao():
            hoje = self._do_dia()
            hoje["locais"] = hoje.get("locais", 0) + 1
            self._salvar()

    def somar(self, uso: dict[str, Any] | None, provedor: str) -> None:
        if not uso:
            return
        with self.trava, self._dados.banco.transacao():
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
        with self.trava, self._dados.banco.transacao():
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
        self._dados = Documentos(arquivo)
        self.arquivo = self._dados.banco.arquivo
        self._dados.importar(arquivo, objeto_json, "uso", chave="atual")
        self.trava = threading.Lock()

    def ler(self) -> dict[str, dict[str, int]]:
        return self._dados.ler("uso", "atual") or {}

    def somar(self, nomes: list[str], agora: float) -> None:
        if not nomes:
            return
        with self.trava, self._dados.banco.transacao():
            uso = self.ler()
            for nome in nomes:
                registro = uso.setdefault(nome, {"usos": 0})
                registro["usos"] += 1
                registro["ultimo"] = round(agora)
            self._dados.guardar("uso", uso, "atual")
