"""O túnel do Cloudflare (roteiro, passo 4.3): o endereço lido e a escolha guardada."""

from pathlib import Path

import pytest

from jarvis.portal import tunel


def test_le_o_endereco_que_o_cloudflared_imprime() -> None:
    linha = (
        "2026-10-12T21:50:01Z INF |  https://utilize-inline-baby-simulations.trycloudflare.com  |"
    )
    achado = tunel.ENDERECO.search(linha)
    assert achado and achado.group(0) == "https://utilize-inline-baby-simulations.trycloudflare.com"


def test_escolha_sobrevive_ao_reinicio(tmp_path: Path) -> None:
    arquivo = tmp_path / "tunel.json"
    assert not tunel.escolhido(arquivo)
    tunel.escolher(True, arquivo)
    assert tunel.escolhido(arquivo)
    tunel.escolher(False, arquivo)
    assert not tunel.escolhido(arquivo)


def test_binario_da_maquina_tem_preferencia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("jarvis.portal.tunel.shutil.which", lambda nome: "/usr/bin/cloudflared")
    assert tunel.binario(tmp_path) == Path("/usr/bin/cloudflared")
    monkeypatch.setattr("jarvis.portal.tunel.shutil.which", lambda nome: None)
    assert tunel.binario(tmp_path) is None
    (tmp_path / "cloudflared").write_text("")
    assert tunel.binario(tmp_path) == tmp_path / "cloudflared"
