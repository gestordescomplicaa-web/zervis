"""O manifesto do Núcleo: os orbes que alimentam o JARVIS, numa fonte só.

Mora no `barehands.json` (a página monta os orbes dele). Cada orbe tem um id estável, o nome
mostrado, o tipo (brain = Mapa, notes, media = Acervo, orca), apelidos falados e o que guarda.
Daqui saem os nomes que a voz entende e o trecho do Núcleo que entra na persona; para mudar
ou entregar o JARVIS a outra pessoa, edita-se o manifesto, não o código.
"""

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

TIPOS = {
    "brain": "o que o Zé sabe e faz, com as vistas Geral, Trabalho e Foco",
    "hoje": "a frente atual, o próximo passo e os lembretes",
    "trabalho": "as sessões de agentes de código",
    "notes": "notas",
    "media": "arquivos (modelos 3D, imagens, efeitos)",
}


@dataclass(frozen=True)
class Orbe:
    id: str
    titulo: str
    tipo: str
    apelidos: tuple[str, ...] = field(default=())
    descricao: str = ""


RESERVA = (
    Orbe("mapa", "Mapa", "brain", ("cérebro", "seu cérebro"), TIPOS["brain"]),
    Orbe("guia", "Guia", "notes", ("manual",), "Como usar o modo imersivo."),
    Orbe("acervo", "Acervo", "media", ("arquivos",), TIPOS["media"]),
)
PADRAO_ARQUIVO = Path(__file__).resolve().parents[1] / "imersivo" / "barehands.padrao.json"


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def _do_arquivo(arquivo: Path) -> tuple[Orbe, ...]:
    try:
        dados = json.loads(arquivo.read_text())
        return tuple(
            Orbe(
                id=str(o.get("id") or o.get("title", "")).casefold(),
                titulo=str(o.get("title", "")),
                tipo=str(o.get("kind", "notes")),
                apelidos=tuple(str(a) for a in o.get("apelidos", [])),
                descricao=str(o.get("descricao", "")),
            )
            for o in dados["orbs"]
            if o.get("title")
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ()


# O manifesto que vem com o Zé (o mesmo que a página do modo imersivo usa sem um próprio).
PADRAO = _do_arquivo(PADRAO_ARQUIVO) or RESERVA


def ler(arquivo: Path) -> tuple[Orbe, ...]:
    """Os orbes do manifesto de quem usa; sem ele ou ilegível, os do padrão (nunca fica sem)."""
    return _do_arquivo(arquivo) or PADRAO


def falados(orbes: tuple[Orbe, ...]) -> dict[str, str]:
    """Nome falado (sem acento, minúsculo) -> título: o título, o id e cada apelido."""
    nomes: dict[str, str] = {}
    for o in orbes:
        for nome in (o.titulo, o.id, *o.apelidos):
            nomes.setdefault(_sem_acento(nome), o.titulo)
    return nomes


def para_persona(orbes: tuple[Orbe, ...]) -> str:
    """O trecho do Núcleo que entra na persona, gerado do manifesto."""
    linhas = ["## Os orbes do Núcleo (do manifesto)"]
    for o in orbes:
        apelidos = f" (também: {', '.join(o.apelidos)})" if o.apelidos else ""
        linhas.append(f"- **{o.titulo}**{apelidos}: {o.descricao or TIPOS.get(o.tipo, o.tipo)}")
    return "\n".join(linhas)
