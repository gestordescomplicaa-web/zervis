"""O placar publicado acompanha a versão (plano de maturidade, fecho da Fase B): parou na 0.3.0
enquanto o Zé ia para a 0.5.1, sem nada avisar."""

import tomllib
from pathlib import Path

from zervis.avaliacao import placar

RAIZ = Path(__file__).resolve().parent.parent


def test_o_placar_publicado_e_o_da_versao_do_projeto() -> None:
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["version"]
    publicado = placar.versao_do_placar((RAIZ / "docs" / "placar.md").read_text())
    assert publicado == projeto, (
        f"docs/placar.md é da versão {publicado}, o projeto está na {projeto}: rode "
        "`zervis placar --saida docs/placar.md` (docs/06-qualidade.md, Publicar uma versão)"
    )


def _rodada(**extra: object) -> dict[str, object]:
    cenario = {"arquivo": "voz-1", "area": "voz", "rodadas": [{"passou": True, "tokens": 10}]}
    return {"quando": "2026-11-09T03:00:00", "rotulo": "claude:x", "cenarios": [cenario], **extra}


def test_a_rodada_de_outra_versao_e_avisada() -> None:
    antiga = placar.markdown(_rodada(), [], "0.5.1", 7)
    assert placar.versao_do_placar(antiga) == "0.5.1"
    assert "Rodada de 2026-11-09, claude:x" in antiga
    assert "Rodada de uma versão anterior" in antiga
    anterior = placar.markdown(_rodada(versao="0.5.0"), [], "0.5.1", 7)
    assert "(versão 0.5.0)" in anterior and "Rodada de uma versão anterior" in anterior
    desta = placar.markdown(_rodada(versao="0.5.1"), [], "0.5.1", 7)
    assert "(versão 0.5.1)" in desta and "versão anterior" not in desta
