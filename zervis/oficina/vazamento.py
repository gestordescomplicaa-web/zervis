"""Antes de publicar uma melhoria no GitHub: a mudança não leva dados de quem usa (06/11/2026).

O repositório é público. Uma melhoria feita no autodesenvolvimento pode, sem querer, copiar para um
teste o número real de um contato (aconteceu em 04/11/2026, com o telefone do próprio usuário), uma
chave, um nome da agenda ou um caminho da máquina. Aqui a mudança é comparada com os dados reais
desta máquina, lidos na hora e nunca gravados:

- os números e os identificadores (LID) da agenda do WhatsApp e o número conectado;
- os nomes completos da agenda (duas palavras ou mais) e o nome do perfil;
- o conteúdo das chaves e tokens guardados na configuração do Zé;
- a pasta pessoal de quem usa;
- formatos conhecidos de chave (Anthropic, OpenAI, GitHub, AWS, Google, Meta, chave privada);
- arquivos que não entram num repositório (banco, chave, `.env`, perfil, configuração).

Só as linhas acrescentadas e as mensagens dos commits contam. O que for achado é dito pelo tipo e
pelo lugar (arquivo e linha), nunca pelo valor.
"""

import contextlib
import getpass
import json
import re
import sqlite3
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from zervis import lugares, usuario

FORMATOS = {
    "chave da Anthropic": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "chave de API": r"\bsk-(?!ant-)[A-Za-z0-9_-]{32,}",
    "token do GitHub": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}",
    "chave da AWS": r"\bAKIA[0-9A-Z]{16}\b",
    "chave do Google": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "token da Meta": r"\bEAA[A-Za-z0-9]{40,}",
    "token do Slack": r"\bxox[abposr]-[A-Za-z0-9-]{20,}",
    "chave privada": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
_FORMATOS = [(tipo, re.compile(padrao)) for tipo, padrao in FORMATOS.items()]
PROIBIDOS = re.compile(
    r"(^|/)(\.env(\..+)?|perfil\.json|config\.toml|.+\.(db|sqlite3?|key|pem|p12|jks|keystore|token))$"
)
_DIGITOS = re.compile(r"\+?\d[\d ().-]{8,}\d")
_SEGREDO_MINIMO = 16  # um valor de configuração mais curto que isso não é segredo


@dataclass(frozen=True)
class Achado:
    tipo: str  # "número da agenda", "chave de API"...
    onde: str  # "tests/test_x.py:12" ou "mensagem do commit"

    def __str__(self) -> str:
        return f"{self.tipo} em {self.onde}"


@dataclass
class Sensiveis:
    """Os dados reais desta máquina, só na memória, para comparar."""

    telefones: set[str] = field(default_factory=set)  # chaves de `_chave_telefone`
    lids: set[str] = field(default_factory=set)
    nomes: set[str] = field(default_factory=set)  # normalizados, duas palavras ou mais
    segredos: set[str] = field(default_factory=set)
    caminhos: set[str] = field(default_factory=set)


def _normal(texto: str) -> str:
    """Sem acento e sem maiúsculas, só letras e dígitos: "Família Souza" -> "familia souza"."""
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    limpo = "".join(c if c.isascii() and c.isalnum() else " " for c in sem_acento)
    return " ".join(limpo.split())


def _chave_telefone(digitos: str) -> str:
    """Um número do Brasil vira DDD + os 8 últimos dígitos (com ou sem o 55 e o nono dígito);
    os de fora ficam inteiros."""
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return digitos[2:4] + digitos[-8:]
    if len(digitos) in (10, 11) and not digitos.startswith("0"):
        return digitos[:2] + digitos[-8:]
    return digitos


def coletar(
    config: Path | None = None,
    whatsapp: Path | None = None,
    casa: Path | None = None,
) -> Sensiveis:
    """Lê os dados reais desta máquina. Uma fonte que não existe ou não abre só não entra."""
    config = config or lugares.CONFIG
    whatsapp = whatsapp or lugares.DADOS / "whatsapp" / "wacalls.db"
    s = Sensiveis()
    _da_agenda(whatsapp, s)
    nome = usuario.ler(config / "perfil.json").nome
    if len(_normal(nome).split()) >= 2:
        s.nomes.add(_normal(nome))
    s.segredos |= set(_segredos(config))
    casa = casa or Path.home()
    with contextlib.suppress(Exception):
        s.caminhos.add(str(casa))
        s.caminhos.add(f"{Path('/home') / getpass.getuser()}/")
    return s


def _da_agenda(arquivo: Path, s: Sensiveis) -> None:
    if not arquivo.exists():
        return
    try:
        db = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return
    try:
        with contextlib.suppress(sqlite3.Error):
            contatos = "SELECT their_jid, coalesce(full_name, ''), coalesce(first_name, '')"
            for jid, nome, primeiro in db.execute(f"{contatos} FROM whatsmeow_contacts"):
                _guardar_jid(str(jid), s)
                completo = _normal(str(nome) or str(primeiro))
                if len(completo.split()) >= 2 and len(completo) >= 8:
                    s.nomes.add(completo)
        with contextlib.suppress(sqlite3.Error):  # o mapa LID -> número: só os usuários
            for lid, pn in db.execute("SELECT lid, pn FROM whatsmeow_lid_map"):
                _guardar_jid(f"{lid}@lid", s)
                _guardar_jid(f"{pn}@s.whatsapp.net", s)
        with contextlib.suppress(sqlite3.Error):  # o número conectado
            for (jid,) in db.execute("SELECT jid FROM whatsmeow_device"):
                _guardar_jid(str(jid), s)
    finally:
        db.close()


def _guardar_jid(jid: str, s: Sensiveis) -> None:
    usuario_, _, servidor = jid.partition("@")
    usuario_ = usuario_.split(":")[0].split(".")[0]
    if not usuario_.isdigit():
        return
    if servidor == "lid":
        s.lids.add(usuario_)
    elif servidor == "s.whatsapp.net":
        s.telefones.add(_chave_telefone(usuario_))


def _segredos(config: Path) -> Iterator[str]:
    """Os valores das chaves e tokens que o Zé guarda: o arquivo inteiro, ou os textos longos de
    um JSON de configuração."""
    if not config.is_dir():
        return
    for arquivo in config.rglob("*"):
        with contextlib.suppress(OSError, ValueError, UnicodeDecodeError):
            if not arquivo.is_file() or arquivo.stat().st_size > 256_000:
                continue
            texto = arquivo.read_text()
            if arquivo.suffix == ".json":
                yield from (v for v in _textos(json.loads(texto)) if _parece_segredo(v))
            elif arquivo.suffix in ("", ".key", ".token", ".txt") and _parece_segredo(
                texto.strip()
            ):
                yield texto.strip()


def _textos(dados: object) -> Iterator[str]:
    if isinstance(dados, str):
        yield dados
    elif isinstance(dados, dict):
        for v in dados.values():
            yield from _textos(v)
    elif isinstance(dados, list):
        for v in dados:
            yield from _textos(v)


def _parece_segredo(valor: str) -> bool:
    """Longo, sem espaços, com letras e dígitos: um token, não uma frase nem um caminho."""
    return (
        len(valor) >= _SEGREDO_MINIMO
        and not re.search(r"\s", valor)
        and not valor.startswith(("/", "~", "http://", "https://"))
        and bool(re.search(r"\d", valor))
        and bool(re.search(r"[A-Za-z]", valor))
    )


def linhas_acrescentadas(diff: str) -> Iterator[tuple[str, int, str]]:
    """(arquivo, linha, texto) de cada linha acrescentada num `git diff --unified=0`."""
    arquivo, linha = "", 0
    for bruta in diff.splitlines():
        if bruta.startswith("+++ "):
            arquivo = bruta[6:] if bruta.startswith("+++ b/") else ""
        elif bruta.startswith("@@"):
            m = re.search(r"\+(\d+)", bruta)
            linha = int(m.group(1)) if m else 0
        elif bruta.startswith("+") and arquivo:
            yield arquivo, linha, bruta[1:]
            linha += 1


def arquivos_novos(diff: str) -> Iterator[str]:
    for bruta in diff.splitlines():
        if bruta.startswith("+++ b/"):
            yield bruta[6:]


def conferir(diff: str, mensagens: str, s: Sensiveis) -> list[Achado]:
    """O que a mudança levaria de dados de quem usa, um achado por tipo e lugar."""
    achados: dict[tuple[str, str], Achado] = {}

    def achou(tipo: str, onde: str) -> None:
        achados.setdefault((tipo, onde), Achado(tipo, onde))

    for arquivo in arquivos_novos(diff):
        if PROIBIDOS.search(arquivo):
            achou("arquivo que não vai para o repositório", arquivo)
    trechos: Iterable[tuple[str, str]] = [
        *((f"{a}:{n}", t) for a, n, t in linhas_acrescentadas(diff)),
        *(("mensagem do commit", t) for t in mensagens.splitlines()),
    ]
    for onde, texto in trechos:
        for tipo, padrao in _FORMATOS:
            if padrao.search(texto):
                achou(tipo, onde)
        if any(segredo in texto for segredo in s.segredos):
            achou("chave ou token desta máquina", onde)
        if any(caminho in texto for caminho in s.caminhos):
            achou("caminho da sua pasta pessoal", onde)
        for bruto in _DIGITOS.findall(texto):
            digitos = re.sub(r"\D", "", bruto)
            if digitos in s.lids:
                achou("identificador de um contato do WhatsApp", onde)
            elif 10 <= len(digitos) <= 15 and _chave_telefone(digitos) in s.telefones:
                achou("número de telefone da sua agenda", onde)
        normal = f" {_normal(texto)} "
        if any(f" {nome} " in normal for nome in s.nomes):
            achou("nome de um contato seu", onde)
    return list(achados.values())
