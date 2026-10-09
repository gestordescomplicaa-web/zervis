"""As três raízes dos dados num lugar só, e o perfil limpo (docs/plano-distribuicao.md)."""

from pathlib import Path

import pytest

from jarvis import lugares


def test_padrao_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for v in ("JARVIS_PERFIL", "JARVIS_RAIZ", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert lugares.raizes() == (
        tmp_path / ".config/zervis",
        tmp_path / ".local/share/zervis",
        tmp_path / ".local/state/zervis",
    )


def test_perfil_limpo_e_raiz_unica(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("JARVIS_RAIZ", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados"))
    monkeypatch.setenv("JARVIS_PERFIL", "limpo")
    assert lugares.raizes()[1] == tmp_path / "dados/zervis-limpo"
    monkeypatch.setenv("JARVIS_RAIZ", str(tmp_path / "portatil"))
    assert lugares.raizes() == tuple(
        tmp_path / "portatil" / n for n in ("config", "dados", "estado")
    )
    monkeypatch.delenv("JARVIS_RAIZ")
    monkeypatch.setenv("JARVIS_PERFIL", "../fora")
    with pytest.raises(ValueError, match="JARVIS_PERFIL"):
        lugares.raizes()
