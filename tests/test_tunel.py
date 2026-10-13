"""O túnel do Cloudflare (roteiro, passo 4.3): o endereço lido e a escolha guardada."""

import time
from collections.abc import Callable
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


def _falso(pasta: Path) -> Path:
    """Um cloudflared de mentira: a primeira subida cai logo; a segunda fica de pé."""
    programa = pasta / "cloudflared"
    programa.write_text(
        "#!/bin/sh\n"
        f'n=$(cat "{pasta}/n" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{pasta}/n"\n'
        'echo "INF |  https://tunel-$n.trycloudflare.com  |" >&2\n'
        '[ "$n" -ge 2 ] && exec sleep 30\n'
    )
    programa.chmod(0o755)
    return programa


def _esperar(condicao: Callable[[], bool]) -> None:
    fim = time.monotonic() + 10
    while not condicao():
        assert time.monotonic() < fim
        time.sleep(0.02)


def test_sobe_de_novo_sozinho_quando_cai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tunel, "ESPERA_S", (0.05,))
    prontos: list[str] = []
    caidos: list[str] = []
    t = tunel.Tunel(prontos.append, caidos.append)
    t.iniciar(8795, _falso(tmp_path))
    try:
        _esperar(lambda: t.endereco == "https://tunel-2.trycloudflare.com")
        assert prontos == ["https://tunel-1.trycloudflare.com", "https://tunel-2.trycloudflare.com"]
        assert caidos == ["https://tunel-1.trycloudflare.com"]
    finally:
        t.parar()
    assert not t.ativo and t.endereco == ""


def test_parado_de_proposito_nao_sobe_de_novo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tunel, "ESPERA_S", (0.05,))
    (tmp_path / "n").write_text("1")  # já na subida que fica de pé
    caidos: list[str] = []
    t = tunel.Tunel(lambda _: None, caidos.append)
    t.iniciar(8795, _falso(tmp_path))
    _esperar(lambda: bool(t.endereco))
    t.parar()
    time.sleep(0.3)
    assert not t.ativo and caidos == []
    assert (tmp_path / "n").read_text().strip() == "2"


def test_binario_da_maquina_tem_preferencia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("jarvis.portal.tunel.shutil.which", lambda nome: "/usr/bin/cloudflared")
    assert tunel.binario(tmp_path) == Path("/usr/bin/cloudflared")
    monkeypatch.setattr("jarvis.portal.tunel.shutil.which", lambda nome: None)
    assert tunel.binario(tmp_path) is None
    (tmp_path / "cloudflared").write_text("")
    assert tunel.binario(tmp_path) == tmp_path / "cloudflared"
