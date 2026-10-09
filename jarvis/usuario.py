"""Quem usa o Zé (docs/plano-distribuicao.md, 09/10/2026): o "Quem sou eu" da primeira configuração.

Fica em `<config>/perfil.json`: `nome` (como o Zé chama a pessoa) e `sobre` (algumas linhas que a
pessoa escreve sobre si, o jeito de trabalhar). Nada de nome fixo no código: a persona recebe isso
no começo de cada conversa e as falas usam o nome daqui. Sem perfil, o Zé fala sem nome.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "perfil.json"


@dataclass(frozen=True)
class Perfil:
    nome: str = ""
    sobre: str = ""

    @property
    def rotulo(self) -> str:
        """Como a pessoa aparece nas transcrições (o nome, ou "Usuário")."""
        return self.nome or "Usuário"

    def vocativo(self, frase: str) -> str:
        """`"Bom dia"` -> `"Bom dia, Ana"`; sem nome, a frase fica como está."""
        return f"{frase}, {self.nome}" if self.nome else frase

    def para_persona(self) -> str:
        if not self.nome and not self.sobre:
            return "## Quem usa você\n(Ainda sem perfil: pergunte o nome da pessoa quando couber.)"
        linhas = [f"## Quem usa você\nVocê atende {self.nome or 'uma pessoa'}."]
        if self.sobre:
            linhas.append(self.sobre.strip())
        return "\n".join(linhas)


def ler(arquivo: Path | None = None) -> Perfil:
    try:
        dados = json.loads((arquivo or ARQUIVO).read_text())
    except (OSError, ValueError):
        return Perfil()
    if not isinstance(dados, dict):
        return Perfil()
    return Perfil(
        str(dados.get("nome", "")).strip()[:60], str(dados.get("sobre", "")).strip()[:2000]
    )


def gravar(perfil: Perfil, arquivo: Path | None = None) -> None:
    destino = arquivo or ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".next")
    temporario.write_text(
        json.dumps({"nome": perfil.nome, "sobre": perfil.sobre}, ensure_ascii=False, indent=1)
    )
    temporario.replace(destino)


PERFIL = ler()
