"""O manifesto do Núcleo: os orbes numa fonte só, para a voz e para a persona."""

import json
from pathlib import Path

from jarvis.rosto import manifesto

ORBES = {
    "orbs": [
        {"id": "mapa", "title": "Mapa", "kind": "brain", "apelidos": ["cérebro", "seu cérebro"]},
        {"title": "Identidade", "kind": "notes", "path": "/x", "descricao": "Quem o JARVIS é."},
        {"id": "orca", "title": "Orca", "kind": "orca", "apelidos": ["agentes de código"]},
        {"kind": "notes"},  # sem título: ignorado
    ]
}


def test_le_o_manifesto_e_os_nomes_falados(tmp_path: Path) -> None:
    arquivo = tmp_path / "barehands.json"
    arquivo.write_text(json.dumps(ORBES))
    orbes = manifesto.ler(arquivo)
    assert [o.titulo for o in orbes] == ["Mapa", "Identidade", "Orca"]
    assert orbes[1].id == "identidade"
    assert manifesto.falados(orbes) == {
        "mapa": "Mapa",
        "cerebro": "Mapa",
        "seu cerebro": "Mapa",
        "identidade": "Identidade",
        "orca": "Orca",
        "agentes de codigo": "Orca",
    }


def test_sem_manifesto_fica_o_padrao(tmp_path: Path) -> None:
    assert manifesto.ler(tmp_path / "nao-existe.json") == manifesto.PADRAO
    (tmp_path / "ruim.json").write_text("{")
    assert manifesto.ler(tmp_path / "ruim.json") == manifesto.PADRAO


def test_o_trecho_da_persona_sai_do_manifesto(tmp_path: Path) -> None:
    arquivo = tmp_path / "barehands.json"
    arquivo.write_text(json.dumps(ORBES))
    texto = manifesto.para_persona(manifesto.ler(arquivo))
    assert texto.splitlines()[0] == "## Os orbes do Núcleo (do manifesto)"
    assert "- **Mapa** (também: cérebro, seu cérebro): mapa de conexões" in texto
    assert "- **Identidade**: Quem o JARVIS é." in texto
