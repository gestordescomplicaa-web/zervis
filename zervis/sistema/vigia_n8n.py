"""O n8n de cada cliente está de pé? (ADR 0038, etapa F2.)

Todo conector ligado cujo endereço termina em `/mcp-server/http` é um n8n: da base saem
`/healthz` (o processo responde) e `/healthz/readiness` (o banco responde), os dois abertos, sem
chave. Uma consulta por minuto, sem modelo. "Fora do ar" só depois de `FALHAS_PARA_AVISAR`
falhas seguidas, para uma oscilação não virar alarme; "voltou" na primeira resposta boa depois
disso. Um aviso por mudança de estado, guardado em SQLite: reiniciar o Zé não repete nem perde.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from zervis import lugares
from zervis.dados.documentos import Documentos

ARQUIVO = lugares.DADOS / "vigia-n8n.db"
SUFIXO = "/mcp-server/http"
FALHAS_PARA_AVISAR = 3  # com uma consulta por minuto, uns três minutos
LIMITE_S = 10.0
OK = "ok"
SEM_RESPOSTA, ERRO_DO_SERVIDOR, BANCO_FORA = "sem resposta", "erro do servidor", "banco fora"
COLECAO = "n8n"

Abrir = Callable[..., Any]
Prioridade = Literal["urgente", "notificacao"]  # as da central de avisos (avisos/modo.py)


def alvos(lista: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Nome do conector → base do n8n, dos conectores ligados que são o MCP de um n8n."""
    if lista is None:
        from zervis.cerebro import conectores

        lista = conectores.listar()
    saida = {}
    for k in lista:
        url = str(k.get("url", "")).split("?", 1)[0].rstrip("/")
        if k.get("ligado") and k.get("tipo") == "http" and url.endswith(SUFIXO):
            saida[str(k["nome"])] = url.removesuffix(SUFIXO)
    return saida


def _responde_ok(url: str, abrir: Abrir) -> bool | None:
    """True com `{"status": "ok"}`; False com outra resposta; None sem resposta nenhuma."""
    from zervis.cerebro.mcp_oauth import AGENTE

    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310
    try:
        with abrir(pedido, timeout=LIMITE_S) as resp:
            corpo = resp.read(4096)
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, OSError):
        return None
    try:
        return bool(json.loads(corpo).get("status") == "ok")
    except (ValueError, AttributeError):
        return False


def conferir(base: str, abrir: Abrir = urllib.request.urlopen) -> str:
    """O estado do n8n em `base`: ok, sem resposta, erro do servidor ou banco fora."""
    vivo = _responde_ok(f"{base}/healthz", abrir)
    if vivo is None:
        return SEM_RESPOSTA
    if not vivo:
        return ERRO_DO_SERVIDOR
    return OK if _responde_ok(f"{base}/healthz/readiness", abrir) else BANCO_FORA


def _rotulo(nome: str) -> str:
    return nome if "n8n" in nome.lower() else f"n8n {nome}"


class VigiaN8n:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        conferir: Callable[[str], str] = conferir,
        alvos: Callable[[], dict[str, str]] = alvos,
    ) -> None:
        self._dados = Documentos(arquivo)
        self._conferir = conferir
        self._alvos = alvos

    def amostrar(self) -> list[tuple[Prioridade, str]]:
        """Confere todos (em paralelo: um n8n fora não atrasa os outros) e devolve os avisos
        das mudanças, como (prioridade, texto)."""
        atuais = self._alvos()
        with ThreadPoolExecutor(max_workers=8) as grupo:
            estados = dict(zip(atuais, grupo.map(self._conferir, atuais.values()), strict=True))
        avisos: list[tuple[Prioridade, str]] = []
        for nome, estado in estados.items():
            antes: dict[str, Any] = self._dados.ler(COLECAO, nome) or {"falhas": 0, "fora": False}
            depois: dict[str, Any] = {"nome": nome, "falhas": 0, "fora": False}
            if estado == OK and antes["fora"]:
                avisos.append(("notificacao", f"{_rotulo(nome)} voltou."))
            elif estado != OK:
                depois = {**antes, "nome": nome, "falhas": antes["falhas"] + 1, "motivo": estado}
                if depois["falhas"] >= FALHAS_PARA_AVISAR and not antes["fora"]:
                    depois["fora"] = True
                    avisos.append(("urgente", f"{_rotulo(nome)} fora do ar: {estado}."))
            self._dados.guardar(COLECAO, depois, nome)
        for guardado in self._dados.listar(COLECAO):  # conector removido ou desligado
            if guardado.get("nome") not in atuais:
                self._dados.remover(COLECAO, str(guardado.get("nome")))
        return avisos

    def fora(self) -> dict[str, str]:
        """Os n8n fora do ar agora, com o motivo (para a tela)."""
        return {
            str(d["nome"]): str(d.get("motivo", ""))
            for d in self._dados.listar(COLECAO)
            if d.get("fora")
        }
