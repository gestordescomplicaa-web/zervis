"""O que o Zé fez e onde tropeçou: a atividade (ADR 0025, camada 1 do auto-aperfeiçoamento).

Separada da conversa: uma linha por acontecimento, em `<estado>/atividade.jsonl` (0600), só para
ler. Tipos:

- **execucao**: uma ferramenta rodou (o comando, como foi autorizada, o resultado);
- **negada**: uma ferramenta foi recusada (pela política, pela pessoa, sem a frase exata);
- **falha**: algo deu errado (ferramenta, transcrição, cérebro, conexão de voz);
- **nao_entendi**: o Zé não entendeu um pedido;
- **correcao**: a pessoa corrigiu o Zé ("não, eu disse...");
- **pedido**: um pedido atendido (o que deu certo também conta, para comparar depois).

O diagnóstico (camada 2) lê daqui. Segredos não entram: chaves com nome de senha, token ou chave
viram "•••", e textos longos são cortados. Passou de 5 MB, o arquivo vira `.1` e recomeça.
"""

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from jarvis import lugares

ARQUIVO = lugares.ESTADO / "atividade.jsonl"
LIMITE_BYTES = 5 * 1024 * 1024
TIPOS = ("execucao", "negada", "falha", "nao_entendi", "correcao", "pedido")
SEGREDO = re.compile(r"senha|password|token|segredo|secret|chave|key|cookie|codigo", re.I)
VALOR_SECRETO = re.compile(r"(sk-[a-z]{2,4}-[\w-]{8,}|gh[pousr]_[\w]{20,}|eyJ[\w-]{20,}\.[\w.-]+)")
CORRECAO = re.compile(
    r"^\s*(n[aã]o[,!.]?\s+(eu\s+)?(disse|falei|pedi|era|foi isso|é isso)|errado|"
    r"voc[eê] n[aã]o entendeu|n[aã]o entendeu)",
    re.I,
)
TEXTO_MAX = 300


def limpar(valor: Any, chave: str = "") -> Any:
    """O valor pronto para o registro: sem segredos e sem textos longos."""
    if chave and SEGREDO.search(chave):
        return "•••"
    if isinstance(valor, dict):
        return {str(k): limpar(v, str(k)) for k, v in list(valor.items())[:30]}
    if isinstance(valor, (list, tuple)):
        return [limpar(v) for v in list(valor)[:30]]
    if isinstance(valor, str):
        texto = VALOR_SECRETO.sub("•••", valor)
        return texto if len(texto) <= TEXTO_MAX else texto[: TEXTO_MAX - 1] + "…"
    if isinstance(valor, (int, float, bool)) or valor is None:
        return valor
    return limpar(str(valor))


def e_correcao(texto: str) -> bool:
    return bool(CORRECAO.search(texto))


class Atividade:
    def __init__(self, arquivo: Path = ARQUIVO) -> None:
        self.arquivo = arquivo
        self.origem = "voz"  # de onde vem o pedido em curso: voz, celular, texto, automação
        self._autorizacoes: dict[str, str] = {}
        self._trava = threading.Lock()

    def autorizada(self, ferramenta: str, como: str) -> None:
        """Como a próxima execução desta ferramenta foi autorizada (o cérebro decide antes)."""
        with self._trava:
            self._autorizacoes[ferramenta] = como

    def autorizacao(self, ferramenta: str) -> str:
        with self._trava:
            return self._autorizacoes.pop(ferramenta, "livre")

    def registrar(self, tipo: str, titulo: str, **detalhes: Any) -> dict[str, Any]:
        linha = {
            "quando": time.time(),
            "tipo": tipo if tipo in TIPOS else "falha",
            "titulo": limpar(titulo),
            "origem": detalhes.pop("origem", self.origem),
            **{k: limpar(v, k) for k, v in detalhes.items() if v not in (None, "", {}, [])},
        }
        with self._trava:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            if self.arquivo.exists() and self.arquivo.stat().st_size > LIMITE_BYTES:
                self.arquivo.replace(self.arquivo.with_suffix(".jsonl.1"))
            novo = not self.arquivo.exists()
            with self.arquivo.open("a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            if novo:
                os.chmod(self.arquivo, 0o600)
        return linha

    def listar(self, limite: int = 300, tipos: tuple[str, ...] = TIPOS) -> list[dict[str, Any]]:
        """As mais recentes primeiro."""
        try:
            linhas = self.arquivo.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        saida: list[dict[str, Any]] = []
        for bruta in reversed(linhas):
            try:
                item = json.loads(bruta)
            except ValueError:
                continue
            if item.get("tipo") in tipos:
                saida.append(item)
                if len(saida) >= limite:
                    break
        return saida

    def resumo(self, desde_s: float = 7 * 86400) -> dict[str, int]:
        """Quantos de cada tipo nos últimos dias (para o diagnóstico comparar)."""
        limite = time.time() - desde_s
        contagem = dict.fromkeys(TIPOS, 0)
        for item in self.listar(limite=100_000):
            if float(item.get("quando", 0)) < limite:
                break
            contagem[item["tipo"]] = contagem.get(item["tipo"], 0) + 1
        return contagem


PADRAO = Atividade()  # o registro do Zé em execução (os testes apontam o arquivo para outro lugar)


def titulo_da_ferramenta(nome: str, entrada: dict[str, Any]) -> str:
    """Uma linha legível do que a ferramenta fez ("sistema_executar · system-shutdown")."""
    curto = nome.removeprefix("mcp__jarvis__")
    if curto == "sistema_executar":
        partes = [str(entrada.get("acao", "")), *map(str, entrada.get("argumentos") or [])]
        return f"Omarchy: {' '.join(p for p in partes if p)}"
    valores = [str(v) for v in entrada.values() if isinstance(v, (str, int, float)) and str(v)]
    resumo = " · ".join(v if len(v) <= 60 else v[:59] + "…" for v in valores[:2])
    return f"{curto}: {resumo}" if resumo else curto
