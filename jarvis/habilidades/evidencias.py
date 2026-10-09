"""Evidências do uso real, para a rodada de melhoria: onde o JARVIS falhou ou gastou à toa.

Uma linha JSON por evento em `evidencias.jsonl` (local; nada sai da máquina sem a rodada). Os
tipos são poucos e acionáveis:
- `nao_entendi`: a fala não virou pedido;
- `transcricao_vazia`: o Whisper não devolveu nada;
- `falha_cerebro`: o cérebro deu erro;
- `so_tela`: um pedido foi ao cérebro só para mexer na tela; candidato a comando local, a
  economia de tokens pelo aprendizado (memória "inteligência antes de economia");
- `nao_achei`: um nome que o Núcleo não achou.
Guarda trinta dias; a rodada resume os últimos sete com exemplos.
"""

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

GUARDAR_S = 30 * 86400.0
ROTULOS = {
    "nao_entendi": "fala que não virou pedido",
    "transcricao_vazia": "transcrição vazia",
    "falha_cerebro": "erro do cérebro",
    "so_tela": "pedido ao cérebro só para mexer na tela (candidato a comando local)",
    "nao_achei": "nome que o Núcleo não achou",
}


class Evidencias:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self._podado = False

    def registrar(self, tipo: str, detalhe: str = "", agora: float | None = None) -> None:
        linha = {"em": round(agora or time.time()), "tipo": tipo, "detalhe": detalhe[:200]}
        try:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            with self.arquivo.open("a") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError:
            return
        if not self._podado:
            self._podado = True
            self.podar(agora or time.time())

    def ler(self, desde: float) -> list[dict[str, Any]]:
        try:
            linhas = self.arquivo.read_text().splitlines()
        except OSError:
            return []
        eventos = []
        for linha in linhas:
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("em", 0) >= desde:
                eventos.append(d)
        return eventos

    def podar(self, agora: float) -> None:
        recentes = self.ler(agora - GUARDAR_S)
        try:
            temporario = self.arquivo.with_suffix(".next")
            temporario.write_text(
                "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in recentes)
            )
            temporario.replace(self.arquivo)
        except OSError:
            pass

    def resumo(self, agora: float, dias: int = 7) -> str:
        """Contagem por tipo, com até três exemplos diferentes, em texto para a sessão de código."""
        eventos = self.ler(agora - dias * 86400)
        if not eventos:
            return f"Nenhuma evidência registrada nos últimos {dias} dias."
        contagem = Counter(d.get("tipo", "?") for d in eventos)
        partes = []
        for tipo, n in contagem.most_common():
            exemplos = list(
                dict.fromkeys(str(d.get("detalhe")) for d in eventos if d.get("tipo") == tipo)
            )
            exemplos = [x for x in exemplos if x][:3]
            texto = f"{ROTULOS.get(tipo, tipo)}: {n} vez(es)"
            if exemplos:
                texto += " (ex.: " + "; ".join(f'"{x}"' for x in exemplos) + ")"
            partes.append(texto)
        return f"Últimos {dias} dias: " + ". ".join(partes) + "."


def maos(arquivo: Path) -> str:
    """O diagnóstico das pinças do Barehands, em uma linha (contagem dos resultados)."""
    try:
        d = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return ""
    contagem = d.get("contagem") or {}
    if not isinstance(contagem, dict) or not contagem:
        return ""
    itens = ", ".join(f"{k} {v}" for k, v in sorted(contagem.items(), key=lambda x: -x[1]))
    return f"Pinças (diagnóstico das mãos, calibração {d.get('origem', '?')}): {itens}."
