"""Entrar na conta de um agente pelo painel, sem terminal na máquina (ADR 0035).

O "Entrar" abria uma janela de terminal com o login do agente. Num servidor não há janela, e o
login da assinatura do Claude Code e do Codex ficava impossível pelo painel (teste na VPS,
16/10/2026). Agora o login roda aqui, num pseudo-terminal, e a tela recebe só o texto limpo e os
links, com um campo para colar o código:

- Claude Code: `claude auth login` mostra o link e pede o código ("Paste code here").
- Codex: `codex login --device-auth` mostra o link e o código de uso único, e espera.

O agente grava o próprio login na pasta da conta, como faria no terminal; o Zé não vê a senha nem
guarda o código.
"""

import re
import shutil
import threading
from pathlib import Path

from jarvis.cerebro import contas
from jarvis.oficina.terminal import Terminal

# CSI (cores, cursor), OSC (o hiperlink do Claude: ESC ] 8 ;; url ESC \) e o resto de controle.
_CONTROLE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-_]|\r")
_LINK = re.compile(r"https://[^\s\x1b\x07\"'<>]+")
TEXTO_MAX = 4000  # o fim do que o agente escreveu: o link e o pedido do código cabem com folga


def limpar(bruto: bytes) -> str:
    return _CONTROLE.sub("", bruto.decode(errors="replace"))


def links(texto: str) -> list[str]:
    vistos: dict[str, None] = {}
    for achado in _LINK.findall(texto):
        vistos.setdefault(achado.rstrip(".,;)"), None)
    return list(vistos)


def comando(conta: contas.Conta) -> list[str]:
    """O login do próprio agente, na pasta da conta."""
    agente = ["claude", "auth", "login"] if conta.agente == "claude" else ["codex", "login"]
    if conta.agente == "codex":
        agente.append("--device-auth")  # o link e o código na tela, sem navegador na máquina
    if shutil.which(agente[0]) is None:
        raise contas.ContaErro(f"{contas.NOMES.get(conta.agente, conta.agente)} indisponível.")
    return agente


class Logins:
    """Um login em andamento por conta; abrir de novo recomeça."""

    def __init__(self) -> None:
        self._terminais: dict[str, Terminal] = {}
        self._trava = threading.Lock()

    def abrir(self, conta: contas.Conta) -> None:
        conta.onde.mkdir(parents=True, exist_ok=True, mode=0o700)  # o Codex recusa pasta que falta
        ambiente = {**conta.ambiente(), "BROWSER": "true", "NO_COLOR": "1"}  # nada de abrir janela
        with self._trava:
            if (antigo := self._terminais.pop(conta.id, None)) is not None:
                antigo.encerrar(espera_s=2)
            self._terminais[conta.id] = Terminal(
                comando(conta), Path.home(), ambiente, colunas=200, linhas=40
            )

    def ler(self, id_: str, espera_s: float = 2.0) -> dict[str, object]:
        t = self._terminais.get(id_)
        if t is None:
            return {"ativo": False, "texto": "", "links": [], "codigo": None}
        _, _, vivo = t.ler(t.fim, espera_s if t.vivo else 0)
        _, bruto, _ = t.ler(t.inicio, 0)
        texto = limpar(bruto)[-TEXTO_MAX:]
        return {"ativo": vivo, "texto": texto, "links": links(texto), "codigo": t.codigo}

    def escrever(self, id_: str, texto: str) -> None:
        t = self._terminais.get(id_)
        if t is None or not t.vivo:
            raise contas.ContaErro("O login não está em andamento.")
        if len(texto) > 2000 or "\n" in texto or "\r" in texto:
            raise contas.ContaErro("Código inválido.")
        t.escrever(texto.strip().encode() + b"\r")

    def fechar(self, id_: str) -> None:
        with self._trava:
            t = self._terminais.pop(id_, None)
        if t is not None:
            t.encerrar(espera_s=2)


PADRAO = Logins()  # os agentes acham o programa pelo PATH que o Zé montou (agentes_nativos)
