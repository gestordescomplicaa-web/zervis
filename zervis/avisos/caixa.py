"""O arquivo do WhatsApp do Zé (ADR 0054 e 0056): tudo o que passa pelo WhatsApp conectado, para
ele servir de recepcionista pela voz e lembrar ("quem me mandou mensagem?", "o que a Ana disse do
orçamento semana passada?", "o que falaram no grupo da equipe hoje?").

Chega pela Central o que entra e o que sai, das conversas privadas e dos grupos, inclusive o que
você manda pelo celular; da mídia, só o tipo e a legenda ("um áudio"), nunca o arquivo. Fica em
`<dados>/whatsapp-arquivo.db` (SQLite, 0600), com a busca por palavras (FTS5, sem acento), para
sempre, até você mandar esquecer uma conversa. Responder é só no privado: o grupo é para lembrar.
O texto é de terceiros: o Zé lê como dado, nunca como instrução.
"""

import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.avisos.mensagens import nome_falado
from zervis.avisos.pendentes import candidatos
from zervis.avisos.prioridade import digitos, mesmo_numero
from zervis.dados import Banco

ARQUIVO = lugares.DADOS / "whatsapp-arquivo.db"
ANTIGO = lugares.ESTADO / "whatsapp-caixa.json"  # a caixa de 7 dias (ADR 0054), importada uma vez
TEXTO_MAXIMO = 4000  # o mesmo teto do WaCalls
MIDIAS = {
    "audio": "um áudio",
    "image": "uma foto",
    "video": "um vídeo",
    "document": "um documento",
    "sticker": "uma figurinha",
}
_VAZIAS = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "um",
           "uma", "que", "pra", "para", "com", "por", "se", "me", "eu", "ele", "ela"}  # fmt: skip
_NUMERO = re.compile(r"\+?[\d\s().-]+")  # "4321", "98765-4321", "+55 (81) 9..."
FINAL = 4  # os últimos dígitos que bastam para achar um contato


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
    # A última mensagem (na lista) ou as últimas (de `mensagens`): de_mim, autor, texto, midia,
    # quando.
    mensagens: list[dict[str, Any]] = field(default_factory=list)
    grupo: bool = False

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
        """A última mensagem é dele: você ainda não respondeu (grupo não cobra resposta)."""
        return not self.grupo and bool(self.mensagens) and not self.ultima.get("de_mim")


def esquema(db: sqlite3.Connection) -> None:
    for sql in (
        "CREATE TABLE conversas (chat TEXT PRIMARY KEY, ident TEXT NOT NULL, nome TEXT NOT NULL, "
        "telefone TEXT NOT NULL DEFAULT '', grupo INTEGER NOT NULL DEFAULT 0)",
        "CREATE INDEX conversas_ident ON conversas(ident)",
        "CREATE TABLE mensagens (id INTEGER PRIMARY KEY AUTOINCREMENT, evento TEXT NOT NULL "
        "UNIQUE, chat TEXT NOT NULL REFERENCES conversas(chat) ON DELETE CASCADE, "
        "de_mim INTEGER NOT NULL, autor TEXT NOT NULL, texto TEXT NOT NULL, midia TEXT NOT NULL, "
        "quando REAL NOT NULL)",
        "CREATE INDEX mensagens_chat ON mensagens(chat, quando)",
        "CREATE INDEX mensagens_quando ON mensagens(quando)",
        # Sem acento ("orcamento" acha "orçamento"); o rowid é o da mensagem.
        "CREATE VIRTUAL TABLE busca USING fts5(texto, autor, "
        "tokenize='unicode61 remove_diacritics 2')",
    ):
        db.execute(sql)


def _consulta(texto: str) -> str:
    """As palavras do pedido, em OU e por prefixo ("orçamen" acha "orçamento"): a ordem pela
    relevância (bm25) põe primeiro o que tem mais delas."""
    palavras = [p for p in re.findall(r"\w+", texto.casefold()) if len(p) > 1]
    uteis = [p for p in palavras if p not in _VAZIAS] or palavras
    return " OR ".join(f'"{p}"*' for p in uteis[:12])


# As consultas, fixas: os valores vão sempre por parâmetro.
_CONVERSAS = (
    "SELECT c.chat, c.nome, c.telefone, c.grupo, m.de_mim, m.autor, m.texto, m.midia, m.quando "
    "FROM conversas c JOIN mensagens m ON m.id = (SELECT id FROM mensagens WHERE chat = c.chat "
    "ORDER BY quando DESC, id DESC LIMIT 1) WHERE (? OR c.grupo = 0) ORDER BY m.quando DESC LIMIT ?"
)
_BUSCA = (
    "SELECT c.chat, c.nome, c.telefone, c.grupo, m.de_mim, m.autor, m.texto, m.midia, m.quando "
    "FROM busca JOIN mensagens m ON m.id = busca.rowid JOIN conversas c ON c.chat = m.chat "
    "WHERE busca MATCH ? AND (? = '' OR m.chat = ?) AND (? = 0 OR m.quando >= ?) "
    "ORDER BY bm25(busca), m.quando DESC LIMIT ?"
)
_RECEBIDAS = (
    "SELECT c.chat, c.nome, c.telefone, c.grupo, m.de_mim, m.autor, m.texto, m.midia, m.quando "
    "FROM conversas c JOIN mensagens m ON m.id = (SELECT id FROM mensagens WHERE chat = c.chat "
    "AND de_mim = 0 ORDER BY quando DESC, id DESC LIMIT 1) WHERE c.grupo = 0 "
    "ORDER BY m.quando DESC LIMIT ?"
)
_RECENTES = (
    "SELECT c.chat, c.nome, c.telefone, c.grupo, m.de_mim, m.autor, m.texto, m.midia, m.quando "
    "FROM mensagens m JOIN conversas c ON c.chat = m.chat "
    "WHERE (? = '' OR m.chat = ?) AND (? = 0 OR m.quando >= ?) ORDER BY m.quando DESC LIMIT ?"
)


def _conversa(linha: sqlite3.Row, mensagens: list[dict[str, Any]]) -> "Conversa":
    return Conversa(
        linha["chat"], linha["nome"], linha["telefone"], mensagens, bool(linha["grupo"])
    )


def _mensagem(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "de_mim": bool(linha["de_mim"]),
        "autor": linha["autor"],
        "texto": linha["texto"],
        "midia": linha["midia"],
        "quando": linha["quando"],
    }


class Caixa:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        agora: Callable[[], float] = time.time,
        antigo: Path | None = ANTIGO,
    ) -> None:
        self.agora = agora
        self.banco = Banco(arquivo, (esquema,))
        if antigo is not None and antigo.is_file():
            self._importar(antigo)

    def _importar(self, antigo: Path) -> None:
        """A caixa de 7 dias (JSON) entra no arquivo uma vez e fica guardada ao lado."""
        try:
            conversas = json.loads(antigo.read_text())
        except (OSError, ValueError):
            conversas = []
        for c in conversas if isinstance(conversas, list) else []:
            if not isinstance(c, dict) or not isinstance(c.get("chat"), str):
                continue
            for m in c.get("mensagens", []):
                if not isinstance(m, dict):
                    continue
                if m.get("de_mim"):
                    self.enviada(c["chat"], str(m.get("texto", "")), str(m.get("midia", "")),
                                 float(m.get("quando", 0)))  # fmt: skip
                else:
                    self.receber(str(c.get("nome", "")), str(m.get("texto", "")),
                                 str(c.get("telefone", "")), c["chat"], str(m.get("midia", "")),
                                 float(m.get("quando", 0)))  # fmt: skip
        antigo.replace(antigo.with_suffix(".importado"))

    # --- o que chega ------------------------------------------------------------------------

    def _anotar(
        self,
        chat: str,
        nome: str,
        de_mim: bool,
        autor: str,
        texto: str,
        midia: str,
        quando: float,
        evento: str,
        telefone: str = "",
        grupo: bool = False,
    ) -> bool:
        texto = " ".join(texto.split())[:TEXTO_MAXIMO]
        quando = quando or self.agora()
        # Sem o id do WhatsApp (a caixa antiga, um teste), a própria mensagem faz as vezes dele.
        evento = (
            evento
            or hashlib.sha256(f"{chat}|{quando}|{de_mim}|{texto}|{midia}".encode()).hexdigest()
        )
        with self.banco.transacao() as db:
            atual = db.execute(
                "SELECT nome, telefone FROM conversas WHERE chat=?", (chat,)
            ).fetchone()
            if atual is not None and nome.isdigit():
                nome = ""  # o número, na falta do nome de perfil, não apaga o nome guardado
            if atual is None:
                db.execute(
                    "INSERT INTO conversas(chat, ident, nome, telefone, grupo) VALUES (?,?,?,?,?)",
                    (chat, ident(chat), nome or _do_chat(chat, grupo), telefone, int(grupo)),
                )
            elif nome or (telefone and telefone != atual["telefone"]):
                db.execute(
                    "UPDATE conversas SET nome=?, telefone=? WHERE chat=?",
                    (nome or atual["nome"], telefone or atual["telefone"], chat),
                )
            cursor = db.execute(
                "INSERT OR IGNORE INTO mensagens(evento, chat, de_mim, autor, texto, midia, "
                "quando) VALUES (?,?,?,?,?,?,?)",
                (evento, chat, int(de_mim), autor, texto, midia, quando),
            )
            if not cursor.rowcount:
                return False  # a mesma, repassada pela Central quando o Zé reinicia
            db.execute(
                "INSERT INTO busca(rowid, texto, autor) VALUES (?,?,?)",
                (cursor.lastrowid, texto, autor),
            )
        return True

    def receber(
        self,
        nome: str,
        texto: str,
        telefone: str,
        chat: str,
        midia: str = "",
        quando: float = 0.0,
        evento: str = "",
        grupo: bool = False,
        grupo_nome: str = "",
    ) -> bool:
        """Uma mensagem que chegou: no privado, de quem é a conversa; no grupo, de quem falou."""
        if not chat:
            return False
        autor = nome_falado(nome) if nome else ""
        if grupo:
            nome_da_conversa = " ".join(grupo_nome.split())[:80]
            return self._anotar(chat, nome_da_conversa, False, autor or "alguém", texto, midia,
                                quando, evento, grupo=True)  # fmt: skip
        telefone = telefone if telefone.isdigit() else ""
        return self._anotar(chat, autor, False, autor or "o contato", texto, midia, quando, evento,
                            telefone)  # fmt: skip

    def enviada(
        self,
        chat: str,
        texto: str,
        midia: str = "",
        quando: float = 0.0,
        evento: str = "",
        grupo: bool = False,
        grupo_nome: str = "",
        nome: str = "",
    ) -> bool:
        """Uma mensagem sua (pelo celular ou pelo Zé); `nome` é o de quem recebe, na agenda."""
        if not chat:
            return False
        if grupo:
            nome = " ".join(grupo_nome.split())[:80]
        else:
            nome = nome_falado(nome) if nome.strip() else ""
        return self._anotar(chat, nome, True, "você", texto, midia, quando, evento, grupo=grupo)

    # --- o que o Zé lê ---------------------------------------------------------------------

    def conversas(self, grupos: bool = True, limite: int = -1) -> list[Conversa]:
        """A mais recente primeiro, com a última mensagem de cada uma."""
        with self.banco.conexao() as db:
            linhas = db.execute(_CONVERSAS, (int(grupos), limite)).fetchall()
        return [_conversa(x, [_mensagem(x)]) for x in linhas]

    def recebidas(self, limite: int = 5) -> list[Conversa]:
        """As conversas privadas pela última mensagem que chegou (não a sua): "quem me mandou
        mensagem?". Cada uma vem com essa mensagem, e `sem_resposta` diz se você respondeu."""
        with self.banco.conexao() as db:
            linhas = db.execute(_RECEBIDAS, (limite,)).fetchall()
        saida = []
        for x in linhas:
            c = _conversa(x, [_mensagem(x)])
            respondeu = self.mensagens(c.chat, 1)
            c.mensagens = [*c.mensagens, *(m for m in respondeu if m.get("de_mim"))]
            saida.append(c)
        return saida

    def mensagens(self, chat: str, quantas: int = 10) -> list[dict[str, Any]]:
        """As últimas `quantas` mensagens de uma conversa, na ordem em que aconteceram."""
        with self.banco.conexao() as db:
            linhas = db.execute(
                "SELECT * FROM (SELECT * FROM mensagens WHERE chat=? ORDER BY quando DESC, id DESC "
                "LIMIT ?) ORDER BY quando, id",
                (chat, quantas),
            ).fetchall()
        return [_mensagem(x) for x in linhas]

    def ultima_dele(self, chat: str) -> float:
        """Quando ele escreveu por último (0 se nunca): marca a vez de responder."""
        with self.banco.conexao() as db:
            linha = db.execute(
                "SELECT MAX(quando) FROM mensagens WHERE chat=? AND de_mim=0", (chat,)
            ).fetchone()
        return float(linha[0] or 0.0)

    def achar(self, quem: str) -> Conversa | None:
        """A conversa pedida, se só uma serve (`candidatos`); mais de uma não escolhe sozinho."""
        achados = self.candidatos(quem)
        return achados[0] if len(achados) == 1 else None

    def candidatos(self, quem: str) -> list[Conversa]:
        """As conversas que servem ao pedido: pelo id; pelos últimos dígitos do número (4 ou mais)
        ou o número inteiro; ou pelo nome falado (contato ou grupo), inteiro, uma palavra ou parte
        dele, quem espera resposta antes."""
        quem = " ".join(quem.split())
        if not quem:
            return []
        lista = self.conversas()
        if c := next((x for x in lista if quem in (x.id, x.chat)), None):
            return [c]
        if _NUMERO.fullmatch(quem):
            final = digitos(quem)
            if len(final) < FINAL:
                return []
            return [x for x in lista if not x.grupo and _confere_numero(_numero(x), final)]
        return candidatos(
            [[x for x in lista if x.sem_resposta], lista], quem, lambda x: (x.nome, x.chat)
        )

    def buscar(
        self, consulta: str = "", chat: str = "", desde: float = 0.0, limite: int = 20
    ) -> list[tuple[Conversa, dict[str, Any]]]:
        """As mensagens que casam com as palavras (as mais relevantes primeiro) ou, sem palavras,
        as mais recentes; filtradas pela conversa e pelo período."""
        filtro = (chat, chat, desde, desde)
        with self.banco.conexao() as db:
            if busca := _consulta(consulta):
                linhas = db.execute(_BUSCA, (busca, *filtro, limite)).fetchall()
            else:
                linhas = db.execute(_RECENTES, (*filtro, limite)).fetchall()
        return [(_conversa(x, []), _mensagem(x)) for x in linhas]

    def esquecer(self, chat: str) -> int:
        """Apaga uma conversa inteira do arquivo; devolve quantas mensagens saíram."""
        with self.banco.transacao() as db:
            ids = [x[0] for x in db.execute("SELECT id FROM mensagens WHERE chat=?", (chat,))]
            for i in ids:
                db.execute("DELETE FROM busca WHERE rowid=?", (i,))
            db.execute("DELETE FROM mensagens WHERE chat=?", (chat,))
            db.execute("DELETE FROM conversas WHERE chat=?", (chat,))
        return len(ids)


def _do_chat(chat: str, grupo: bool) -> str:
    """O nome provisório de quem ainda não se apresentou: o número, ou "um grupo"."""
    if grupo:
        return "um grupo"
    numero = re.match(r"\d+", chat)
    return numero.group(0) if numero and chat.endswith("@s.whatsapp.net") else "um contato"


def _numero(c: Conversa) -> str:
    """O telefone da conversa: o que chegou com a mensagem ou, sem ele, o do JID."""
    if c.telefone:
        return c.telefone
    numero = re.match(r"\d+", c.chat)
    return numero.group(0) if numero and c.chat.endswith("@s.whatsapp.net") else ""


def _confere_numero(numero: str, dito: str) -> bool:
    """O final do número, ou ele inteiro (com ou sem o país e o nono dígito)."""
    return bool(numero) and (numero.endswith(dito) or mesmo_numero(numero, dito))
