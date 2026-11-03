"""Leads do WhatsApp esperando a sua resposta (ADR 0053).

Um lead qualificado numa conversa privada vira pendência: o Zé avisa na hora, lendo a mensagem,
e lembra de 10 em 10 minutos, até 6 vezes, enquanto você não responder. Responder pelo celular
(a mensagem que você envia volta pelo WhatsApp conectado), pedir ao Zé que responda ou dizer que
já viu encerra. Depois dos lembretes, a pendência fica na lista, sem insistir, por um dia.

O arquivo guarda o texto do lead até lá (0600): é o que o Zé lê quando você pede. Grupo nunca
chega aqui (o WhatsApp do Zé só entrega conversa privada).
"""

import json
import re
import tempfile
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.avisos.mensagens import nome_falado
from zervis.avisos.modo import para_ouvir

ARQUIVO = lugares.ESTADO / "whatsapp-pendentes.json"
INTERVALO_S = 10 * 60
LEMBRETES = 6  # 10 min até 1 h; depois só na lista
VALIDADE_S = 24 * 3600  # aberta ou respondida, some depois disto
TEXTO_MAXIMO = 1200  # o que se guarda de um lead (as últimas mensagens dele, juntas)
FALA_MAXIMA = 300  # o que o Zé lê no aviso; o resto, quando você pede
NUMEROS = {2: "dois", 3: "três", 4: "quatro", 5: "cinco"}


@dataclass
class Pendente:
    nome: str
    texto: str
    chat: str  # o JID da conversa privada: o que liga a sua resposta ao lead
    telefone: str = ""  # a forma discável, quando o WhatsApp entrega (para o Zé responder)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    chegou: float = field(default_factory=time.time)
    ultima: float = 0.0  # a última mensagem dele
    lembretes: int = 0
    proximo: float = 0.0  # quando lembrar de novo; 0 = não lembra mais
    respondida: float = 0.0  # quando você respondeu ou dispensou; 0 = esperando

    @property
    def aberta(self) -> bool:
        return not self.respondida


def _da_lista(brutos: Any) -> list[Pendente]:
    campos = set(Pendente.__dataclass_fields__)
    if not isinstance(brutos, list):
        return []
    return [
        Pendente(**{k: v for k, v in p.items() if k in campos})
        for p in brutos
        if isinstance(p, dict) and {"nome", "texto", "chat"} <= p.keys()
    ]


def lista_falada(nomes: list[str]) -> str:
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def chamando(quem_usa: str, frase: str) -> str:
    """Com o nome do perfil, "Marta, ..."; sem ele, a frase sozinha."""
    return f"{quem_usa}, {frase}" if quem_usa else frase[:1].upper() + frase[1:]


def anuncio(p: Pendente, quem_usa: str) -> str:
    """A fala da chegada: quem é e o que mandou, lido como dado."""
    texto = para_ouvir(p.texto, limite=FALA_MAXIMA) or "uma mensagem sem texto"
    return chamando(quem_usa, f"{p.nome} é um lead qualificado e lhe mandou esta mensagem: {texto}")


def lembrete(abertas: list[Pendente], quem_usa: str) -> str:
    if len(abertas) == 1:
        return chamando(quem_usa, f"{abertas[0].nome} ainda espera sua resposta no WhatsApp.")
    n = len(abertas)
    nomes = [p.nome for p in abertas[:3]] + ([f"mais {n - 3}"] if n > 3 else [])
    quantos = NUMEROS.get(n, str(n))
    return chamando(
        quem_usa, f"{quantos} leads esperam sua resposta no WhatsApp: {lista_falada(nomes)}."
    )


def para_o_celular(p: Pendente) -> dict[str, Any]:
    """O que o app de voz mostra na notificação (e o número, para abrir a conversa)."""
    return {
        "id": p.id,
        "nome": p.nome,
        "texto": p.texto,
        "telefone": p.telefone,
        "lembretes": p.lembretes,
        "chegou": round(p.chegou * 1000),
    }


class Pendentes:
    def __init__(self, arquivo: Path = ARQUIVO, agora: Callable[[], float] = time.time) -> None:
        self.arquivo = arquivo
        self.agora = agora
        self._trava = threading.RLock()
        self._lista: list[Pendente] | None = None  # o núcleo é o único dono: lido uma vez

    def _ler(self) -> list[Pendente]:
        if self._lista is None:
            try:
                self._lista = _da_lista(json.loads(self.arquivo.read_text()))
            except (OSError, ValueError, TypeError):
                self._lista = []
        limite = self.agora() - VALIDADE_S
        return [p for p in self._lista if max(p.chegou, p.ultima, p.respondida) > limite]

    def _gravar(self, lista: list[Pendente]) -> None:
        self._lista = lista
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.arquivo.parent, delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)  # nasce 0600: guarda o texto de terceiros
            try:
                json.dump([asdict(p) for p in lista], arquivo, ensure_ascii=False)
                arquivo.flush()
                temporario.replace(self.arquivo)
            finally:
                temporario.unlink(missing_ok=True)

    def todas(self) -> list[Pendente]:
        """As abertas primeiro (a mais antiga antes), depois as respondidas, da mais recente."""
        with self._trava:
            lista = self._ler()
        abertas = sorted((p for p in lista if p.aberta), key=lambda p: p.chegou)
        fechadas = sorted((p for p in lista if not p.aberta), key=lambda p: -p.respondida)
        return abertas + fechadas

    def abertas(self) -> list[Pendente]:
        return [p for p in self.todas() if p.aberta]

    def aberta_de(self, chat: str) -> Pendente | None:
        return next((p for p in self.abertas() if p.chat == chat), None)

    def novo(self, nome: str, texto: str, chat: str, telefone: str = "") -> Pendente:
        """Um lead qualificado; a primeira lembrança vem em 10 minutos."""
        agora = self.agora()
        p = Pendente(
            nome_falado(nome),
            " ".join(texto.split())[:TEXTO_MAXIMO],
            chat,
            telefone if re.fullmatch(r"\d{8,15}", telefone or "") else "",
            chegou=agora,
            ultima=agora,
            proximo=agora + INTERVALO_S,
        )
        with self._trava:
            lista = [x for x in self._ler() if x.chat != chat]  # a anterior dele já foi resolvida
            lista.append(p)
            self._gravar(lista)
        return p

    def continuar(self, chat: str, texto: str) -> Pendente | None:
        """Ele mandou mais enquanto espera: o texto junta, os lembretes seguem como estavam."""
        with self._trava:
            lista = self._ler()
            p = next((x for x in lista if x.chat == chat and x.aberta), None)
            if p is None:
                return None
            junto = f"{p.texto} {' '.join(texto.split())}".strip()
            p.texto = junto[-TEXTO_MAXIMO:]
            p.ultima = self.agora()
            self._gravar(lista)
            return p

    def responder(self, chat: str, quando: float = 0.0) -> Pendente | None:
        """Você respondeu na conversa (pelo celular ou pelo Zé): a pendência encerra. `quando`, a
        hora da resposta: a que veio antes da última mensagem dele não responde a ela (o Zé, ao
        reiniciar, repassa as respostas da última hora)."""
        with self._trava:
            lista = self._ler()
            p = next((x for x in lista if x.chat == chat and x.aberta), None)
            if p is None or (quando and quando < p.ultima):
                return None
            p.respondida, p.proximo = self.agora(), 0.0
            self._gravar(lista)
            return p

    def dispensar(self, ident: str) -> Pendente | None:
        """O "já vi": encerra sem resposta (pelo id ou pelo chat)."""
        with self._trava:
            lista = self._ler()
            p = next((x for x in lista if ident in (x.id, x.chat) and x.aberta), None)
            if p is None:
                return None
            p.respondida, p.proximo = self.agora(), 0.0
            self._gravar(lista)
            return p

    def vencidas(self) -> list[Pendente]:
        """As que pedem lembrete agora; cada uma passa ao próximo (ou para de lembrar)."""
        agora = self.agora()
        with self._trava:
            lista = self._ler()  # a cada segundo: da memória, sem disco
            vencidas = [p for p in lista if p.aberta and 0 < p.proximo <= agora]
            if not vencidas:
                return []
            for p in vencidas:
                p.lembretes += 1
                p.proximo = agora + INTERVALO_S if p.lembretes < LEMBRETES else 0.0
            self._gravar(lista)
        return sorted(vencidas, key=lambda p: p.chegou)

    def achar(self, quem: str) -> Pendente | None:
        """Pelo id, ou pelo nome falado ("a Ana", "o João Silva"); a aberta antes da respondida.
        Nome que serve a mais de um contato não escolhe sozinho: devolve None."""
        lista = self.todas()
        if p := next((x for x in lista if x.id == quem), None):
            return p
        procurado = _chave(quem)
        if not procurado:
            return None
        for grupo in ([x for x in lista if x.aberta], lista):
            for confere in (
                lambda nome: nome == procurado,
                lambda nome: procurado in nome.split(),  # só o primeiro nome
            ):
                achados = {x.chat: x for x in grupo if confere(_chave(x.nome))}
                if achados:
                    return next(iter(achados.values())) if len(achados) == 1 else None
        return None


def _chave(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome.casefold())
    limpo = "".join(c for c in sem_acento if c.isascii() and (c.isalnum() or c == " "))
    palavras = [p for p in limpo.split() if p not in ("a", "o", "do", "da", "de", "pra", "para")]
    return " ".join(palavras)
