"""A caixa de entrada do WhatsApp do Zé (ADR 0054): as conversas privadas recentes, para ele
servir de recepcionista pela voz ("quem me mandou mensagem?", "o que a Ana disse?", "responde
para ela").

Chega pela Central (o WaCalls entrega só conversa privada) o que entra e o que sai, inclusive o
que você manda pelo celular, e a mídia só pelo tipo ("um áudio"), nunca o arquivo. Fica em
`<estado>/whatsapp-caixa.json` (0600), por 7 dias, até 100 conversas e as últimas 30 mensagens de
cada uma. O texto é de terceiros: o Zé lê como dado, nunca como instrução.
"""

import hashlib
import json
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.avisos.mensagens import nome_falado
from zervis.avisos.pendentes import pelo_nome

ARQUIVO = lugares.ESTADO / "whatsapp-caixa.json"
VALIDADE_S = 7 * 24 * 3600
CONVERSAS = 100
MENSAGENS = 30
TEXTO_MAXIMO = 1000
MIDIAS = {
    "audio": "um áudio",
    "image": "uma foto",
    "video": "um vídeo",
    "document": "um documento",
    "sticker": "uma figurinha",
}


def ident(chat: str) -> str:
    """Um id curto e estável da conversa, para o cérebro citar sem o JID."""
    return hashlib.sha256(chat.encode()).hexdigest()[:8]


def descrever(m: dict[str, Any]) -> str:
    """Uma mensagem em texto: o que foi escrito, ou o tipo da mídia (com a legenda)."""
    texto = str(m.get("texto", ""))
    midia = str(m.get("midia", ""))
    if not midia:
        return texto
    tipo = MIDIAS.get(midia, "um anexo")
    return f"[{tipo}] {texto}".strip() if texto else f"[{tipo}]"


@dataclass
class Conversa:
    chat: str
    nome: str
    telefone: str = ""
    mensagens: list[dict[str, Any]] = field(default_factory=list)  # de_mim, texto, midia, quando

    @property
    def id(self) -> str:
        return ident(self.chat)

    @property
    def ultima(self) -> dict[str, Any]:
        return self.mensagens[-1] if self.mensagens else {}

    @property
    def quando(self) -> float:
        return float(self.ultima.get("quando", 0.0))

    @property
    def sem_resposta(self) -> bool:
        """A última mensagem é dele: você ainda não respondeu."""
        return bool(self.mensagens) and not self.ultima.get("de_mim")


def _da_lista(brutos: Any) -> list[Conversa]:
    if not isinstance(brutos, list):
        return []
    saida = []
    for c in brutos:
        if isinstance(c, dict) and isinstance(c.get("chat"), str) and c.get("chat"):
            mensagens = [m for m in c.get("mensagens", []) if isinstance(m, dict)]
            telefone = str(c.get("telefone", ""))
            saida.append(Conversa(c["chat"], str(c.get("nome", "")), telefone, mensagens))
    return saida


class Caixa:
    def __init__(self, arquivo: Path = ARQUIVO, agora: Callable[[], float] = time.time) -> None:
        self.arquivo = arquivo
        self.agora = agora
        self._trava = threading.RLock()
        self._lista: list[Conversa] | None = None  # o núcleo é o único dono: lida uma vez

    def _ler(self) -> list[Conversa]:
        if self._lista is None:
            try:
                self._lista = _da_lista(json.loads(self.arquivo.read_text()))
            except (OSError, ValueError, TypeError):
                self._lista = []
        return self._lista

    def _gravar(self) -> None:
        limite = self.agora() - VALIDADE_S
        vivas = [c for c in self._ler() if c.quando > limite]
        vivas.sort(key=lambda c: -c.quando)
        self._lista = vivas[:CONVERSAS]
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.arquivo.parent, delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)  # nasce 0600: guarda o texto de terceiros
            try:
                json.dump([asdict(c) for c in self._lista], arquivo, ensure_ascii=False)
                arquivo.flush()
                temporario.replace(self.arquivo)
            finally:
                temporario.unlink(missing_ok=True)

    def _anotar(
        self, chat: str, mensagem: dict[str, Any], nome: str = "", telefone: str = ""
    ) -> None:
        with self._trava:
            lista = self._ler()
            conversa = next((c for c in lista if c.chat == chat), None)
            if conversa is None:
                conversa = Conversa(chat, nome_falado(nome) if nome else "")
                lista.append(conversa)
            if nome:
                conversa.nome = nome_falado(nome)  # o nome mais recente com que ele aparece
            if telefone and telefone.isdigit():
                conversa.telefone = telefone
            if mensagem in conversa.mensagens:
                return  # a mesma, repassada pela Central quando o Zé reinicia
            conversa.mensagens.append(mensagem)
            conversa.mensagens.sort(key=lambda m: float(m.get("quando", 0)))  # a repassada no lugar
            del conversa.mensagens[:-MENSAGENS]
            self._gravar()

    def receber(
        self, nome: str, texto: str, telefone: str, chat: str, midia: str = "", quando: float = 0.0
    ) -> None:
        """Uma mensagem que chegou para você."""
        if not chat:
            return
        m = {"de_mim": False, "texto": " ".join(texto.split())[:TEXTO_MAXIMO], "midia": midia}
        self._anotar(chat, {**m, "quando": quando or self.agora()}, nome, telefone)

    def enviada(self, chat: str, texto: str, midia: str = "", quando: float = 0.0) -> None:
        """Uma mensagem sua (pelo celular ou pelo Zé), só numa conversa que já está na caixa: o
        que você manda a quem nunca escreveu não vira conversa de recepção."""
        with self._trava:
            if not chat or not any(c.chat == chat for c in self._ler()):
                return
            m = {"de_mim": True, "texto": " ".join(texto.split())[:TEXTO_MAXIMO], "midia": midia}
            self._anotar(chat, {**m, "quando": quando or self.agora()})

    def conversas(self) -> list[Conversa]:
        """A mais recente primeiro, dentro dos 7 dias."""
        limite = self.agora() - VALIDADE_S
        with self._trava:
            vivas = [c for c in self._ler() if c.quando > limite]
        return sorted(vivas, key=lambda c: -c.quando)

    def achar(self, quem: str) -> Conversa | None:
        """Pelo id da conversa, ou pelo nome falado; quem espera resposta vem antes."""
        lista = self.conversas()
        if c := next((x for x in lista if quem in (x.id, x.chat)), None):
            return c
        return pelo_nome(
            [[x for x in lista if x.sem_resposta], lista], quem, lambda x: (x.nome, x.chat)
        )
