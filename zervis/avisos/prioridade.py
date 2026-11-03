"""A lista de prioridade do WhatsApp (ADR 0055): os contatos que o Zé vigia em tempo real.

Dois jeitos de entrar:
- **pedido**: "Zé, monitora a Ana" (ou um número). Fica até você dizer "não monitora mais a Ana";
  qualquer mensagem dela vira aviso, lida, com lembrete até você responder.
- **resposta**: quando o Zé responde alguém por você, ele espera a resposta dessa pessoa por 24
  horas. A primeira mensagem dela vira aviso ("a Ana respondeu: ...") e a espera acaba.

Fica em `<estado>/whatsapp-prioridade.json` (0600). Só conversa privada chega até aqui.
"""

import json
import re
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.avisos.mensagens import nome_falado
from zervis.avisos.pendentes import pelo_nome

ARQUIVO = lugares.ESTADO / "whatsapp-prioridade.json"
ESPERA_S = 24 * 3600  # quanto o Zé espera a resposta ao que ele mandou por você
MAXIMO = 50


def digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero or "")


def mesmo_numero(a: str, b: str) -> bool:
    """O mesmo telefone escrito de dois jeitos: com ou sem o código do país, e o celular do
    Brasil com ou sem o nono dígito (o WhatsApp guarda muitos sem ele)."""
    a, b = digitos(a), digitos(b)
    if len(a) < 8 or len(b) < 8:
        return False
    if a == b or (min(len(a), len(b)) >= 10 and (a.endswith(b) or b.endswith(a))):
        return True
    x, y = _nacional(a), _nacional(b)
    return bool(x and y) and x[:2] == y[:2] and x[-8:] == y[-8:]  # o mesmo DDD e os 8 finais


def _nacional(numero: str) -> str:
    """DDD e número (10 ou 11 dígitos), com ou sem o 55 na frente; vazio se não tiver o jeito."""
    if numero.startswith("55") and len(numero) in (12, 13):
        return numero[2:]
    return numero if len(numero) in (10, 11) else ""


@dataclass
class Vigiado:
    nome: str
    chat: str = ""  # a conversa, quando já existe na caixa
    telefone: str = ""  # o número dito por voz, para quem ainda não escreveu
    motivo: str = "pedido"  # pedido | resposta
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    desde: float = field(default_factory=time.time)
    ate: float = 0.0  # 0 = até você tirar

    def confere(self, chat: str, telefone: str) -> bool:
        if self.chat and chat and self.chat == chat:
            return True
        return bool(self.telefone and telefone) and mesmo_numero(self.telefone, telefone)


def _da_lista(brutos: Any) -> list[Vigiado]:
    campos = set(Vigiado.__dataclass_fields__)
    if not isinstance(brutos, list):
        return []
    return [
        Vigiado(**{k: v for k, v in v.items() if k in campos})
        for v in brutos
        if isinstance(v, dict) and isinstance(v.get("nome"), str)
    ]


class Prioridade:
    def __init__(self, arquivo: Path = ARQUIVO, agora: Callable[[], float] = time.time) -> None:
        self.arquivo = arquivo
        self.agora = agora
        self._trava = threading.RLock()
        self._lista: list[Vigiado] | None = None

    def _ler(self) -> list[Vigiado]:
        if self._lista is None:
            try:
                self._lista = _da_lista(json.loads(self.arquivo.read_text()))
            except (OSError, ValueError, TypeError):
                self._lista = []
        agora = self.agora()
        return [v for v in self._lista if not v.ate or v.ate > agora]

    def _gravar(self, lista: list[Vigiado]) -> None:
        self._lista = lista[-MAXIMO:]
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.arquivo.parent, delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)  # nasce 0600
            try:
                json.dump([asdict(v) for v in self._lista], arquivo, ensure_ascii=False)
                arquivo.flush()
                temporario.replace(self.arquivo)
            finally:
                temporario.unlink(missing_ok=True)

    def todos(self) -> list[Vigiado]:
        with self._trava:
            return list(self._ler())

    def monitorar(self, nome: str, chat: str = "", telefone: str = "") -> Vigiado:
        """Na lista até você tirar. Quem já estava esperando resposta passa a ficar de vez."""
        with self._trava:
            lista = [v for v in self._ler() if not v.confere(chat, digitos(telefone))]
            v = Vigiado(nome_falado(nome), chat, digitos(telefone), desde=self.agora())
            lista.append(v)
            self._gravar(lista)
            return v

    def esperar_resposta(self, nome: str, chat: str) -> None:
        """O Zé mandou algo por você: espera a resposta por 24 horas (sem tirar quem já está na
        lista de vez)."""
        with self._trava:
            lista = self._ler()
            atual = next((v for v in lista if v.confere(chat, "")), None)
            if atual is not None and atual.motivo == "pedido":
                return
            lista = [v for v in lista if v is not atual]
            agora = self.agora()
            lista.append(
                Vigiado(
                    nome_falado(nome), chat, motivo="resposta", desde=agora, ate=agora + ESPERA_S
                )
            )
            self._gravar(lista)

    def remover(self, quem: str) -> Vigiado | None:
        """Pelo id, pelo nome falado ou pelo número."""
        with self._trava:
            lista = self._ler()
            alvo = next((v for v in lista if quem == v.id), None)
            if alvo is None and len(digitos(quem)) >= 8:
                alvo = next((v for v in lista if v.confere("", digitos(quem))), None)
            if alvo is None:
                alvo = pelo_nome([lista], quem, lambda v: (v.nome, v.chat or v.id))
            if alvo is None:
                return None
            self._gravar([v for v in lista if v is not alvo])
            return alvo

    def chegou(self, chat: str, telefone: str) -> Vigiado | None:
        """Uma mensagem de quem está na lista: devolve o vigiado (a espera de resposta acaba aqui;
        o de vez continua) e guarda a conversa, para os próximos casarem por ela."""
        with self._trava:
            lista = self._ler()
            v = next((x for x in lista if x.confere(chat, telefone)), None)
            if v is None:
                return None
            if v.motivo == "resposta":
                lista = [x for x in lista if x is not v]
            elif chat and not v.chat:
                v.chat = chat
            self._gravar(lista)
            return v
