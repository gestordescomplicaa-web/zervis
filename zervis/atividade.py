"""O que o Zé fez e onde tropeçou: a atividade (ADR 0025, camada 1 do auto-aperfeiçoamento).

Separada da conversa: um registro por acontecimento, em `<dados>/atividade.db` (0600), com
busca de texto. Os JSONL anteriores são importados e preservados. Tipos:

- **execucao**: uma ferramenta rodou (o comando, como foi autorizada, o resultado);
- **negada**: uma ferramenta foi recusada (pela política, pela pessoa, sem a frase exata);
- **falha**: algo deu errado (ferramenta, transcrição, cérebro, conexão de voz);
- **nao_entendi**: o Zé não entendeu um pedido;
- **correcao**: a pessoa corrigiu o Zé ("não, eu disse...");
- **pedido**: um pedido atendido (o que deu certo também conta, para comparar depois).

O diagnóstico (camada 2) lê daqui. Segredos não entram: chaves com nome de senha, token ou
chave
viram "•••", e textos longos são cortados. O histórico permanece no banco, sem rotação que
descarte eventos.
"""

import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.dados.documentos import Documentos, linhas_json

ARQUIVO = lugares.DADOS / "atividade.db"
LEGADO = lugares.ESTADO / "atividade.jsonl"
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
        self._dados = Documentos(arquivo)
        self.arquivo = self._dados.banco.arquivo
        antigo = LEGADO if arquivo == ARQUIVO else arquivo
        self._dados.importar(antigo.with_suffix(".jsonl.1"), linhas_json, "atividade")
        self._dados.importar(antigo, linhas_json, "atividade")
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
        self._dados.guardar("atividade", linha)
        return linha

    def listar(self, limite: int = 300, tipos: tuple[str, ...] = TIPOS) -> list[dict[str, Any]]:
        """As mais recentes primeiro, filtradas no banco."""
        return self._dados.filtrar("atividade", "tipo", list(tipos), limite)

    def buscar(self, texto: str, limite: int = 50) -> list[dict[str, Any]]:
        return self._dados.buscar(texto, "atividade", limite)

    def resumo(self, desde_s: float = 7 * 86400) -> dict[str, int]:
        """Quantos de cada tipo nos últimos dias (para o diagnóstico comparar)."""
        limite = time.time() - desde_s
        contagem = dict.fromkeys(TIPOS, 0)
        for item in self.listar(limite=100_000):
            if float(item.get("quando", 0)) < limite:
                break
            contagem[item["tipo"]] = contagem.get(item["tipo"], 0) + 1
        return contagem

    def balanco(self, dias: int = 7, fuso: tzinfo | None = None, top: int = 8) -> dict[str, Any]:
        """Os últimos `dias` dias (hoje incluso) numa passada só, para o Zé dizer o que fez (ADR
        0045): quantos de cada tipo, registros e falhas por dia no fuso de quem usa, e as
        ferramentas que mais rodaram."""
        zona = fuso or datetime.now().astimezone().tzinfo
        hoje = datetime.now(zona).date()
        datas = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]
        por_dia = {d: [0, 0] for d in datas}
        contagem = dict.fromkeys(TIPOS, 0)
        usadas: Counter[str] = Counter()
        for item in self.listar(limite=100_000):
            dia = datetime.fromtimestamp(float(item.get("quando", 0)), zona).date()
            if dia < datas[0]:
                break
            if dia not in por_dia:  # registro de um relógio adiantado
                continue
            tipo = item["tipo"]
            contagem[tipo] = contagem.get(tipo, 0) + 1
            por_dia[dia][0] += 1
            por_dia[dia][1] += tipo == "falha"
            if tipo in ("execucao", "falha") and item.get("ferramenta"):
                usadas[str(item["ferramenta"])] += 1
        return {
            "contagem": contagem,
            "por_dia": [(d.isoformat(), n, f) for d, (n, f) in por_dia.items()],
            "mais_usadas": usadas.most_common(top),
        }


PADRAO = Atividade()  # o registro do Zé em execução (os testes apontam o arquivo para outro lugar)


def externa(nome: str) -> bool:
    """Uma ferramenta de um conector MCP (as do Zé passam pelo registro delas, `auditada`)."""
    return nome.startswith("mcp__") and not nome.startswith("mcp__jarvis__")


def registrar_externa(nome: str, entrada: Any, resposta: Any) -> None:
    """O que o cérebro fez num sistema de fora (n8n, CRM…), como as ferramentas do Zé: a
    essência pede tudo o que ele executa na Atividade (item 6)."""
    if not externa(nome):
        return
    corpo = resposta if isinstance(resposta, dict) else {"content": resposta}
    conteudo = corpo.get("content")
    blocos: list[Any] = conteudo if isinstance(conteudo, list) else []
    texto = " ".join(str(b.get("text", "")) for b in blocos if isinstance(b, dict)).strip()
    erro = bool(corpo.get("isError") or corpo.get("is_error"))
    PADRAO.registrar(
        "falha" if erro else "execucao",
        titulo_da_ferramenta(nome, entrada if isinstance(entrada, dict) else {}),
        ferramenta=nome,
        entrada=entrada if isinstance(entrada, dict) else {},
        autorizacao=PADRAO.autorizacao(nome),
        resultado=texto or str(resposta)[:TEXTO_MAX],
    )


def titulo_da_ferramenta(nome: str, entrada: dict[str, Any]) -> str:
    """Uma linha legível do que a ferramenta fez ("sistema_executar · system-shutdown")."""
    curto = nome.removeprefix("mcp__jarvis__")
    if curto == "sistema_executar":
        partes = [str(entrada.get("acao", "")), *map(str, entrada.get("argumentos") or [])]
        return f"Omarchy: {' '.join(p for p in partes if p)}"
    valores = [str(v) for v in entrada.values() if isinstance(v, (str, int, float)) and str(v)]
    resumo = " · ".join(v if len(v) <= 60 else v[:59] + "…" for v in valores[:2])
    return f"{curto}: {resumo}" if resumo else curto
