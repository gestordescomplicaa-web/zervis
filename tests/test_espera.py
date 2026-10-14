"""A escolha "Espera" da página Voz: quanto o Zé espera antes de achar que a pessoa terminou."""

from pathlib import Path

import pytest

from jarvis.voz import espera


def test_padrao_e_normal_e_grava(tmp_path: Path) -> None:
    arquivo = tmp_path / "espera.json"
    assert espera.ler(arquivo) == "normal"
    assert espera.gravar("longa", arquivo) == "longa"
    assert espera.ler(arquivo) == "longa"


def test_recusa_o_que_nao_conhece(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        espera.gravar("infinita", tmp_path / "espera.json")
    (tmp_path / "x.json").write_text("{lixo")
    assert espera.ler(tmp_path / "x.json") == "normal"


def test_quanto_mais_longa_mais_paciente() -> None:
    r, n, lg = (espera.TEMPOS[m] for m in ("rapida", "normal", "longa"))
    assert r[0] < n[0] < lg[0] and r[1] <= n[1] < lg[1]
