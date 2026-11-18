"""O Zé na imagem Docker (ADR 0096): sem systemd, o painel diz que ele está de pé, a atualização
é pela imagem e o primeiro acesso não depende de reiniciar o serviço."""

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from zervis import cli, conteiner, versoes
from zervis.portal import primeiro_acesso, tunel
from zervis.portal.senha import Acesso

RAIZ = Path(__file__).resolve().parent.parent


def _sem_systemd(comando: Sequence[str]) -> subprocess.CompletedProcess[str]:
    if comando and comando[0] == "systemctl":
        raise AssertionError(f"no contêiner não há systemctl: {' '.join(comando)}")
    return subprocess.CompletedProcess(comando, 0, "", "")


@pytest.fixture
def no_conteiner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZERVIS_CONTEINER", "1")


def test_so_a_imagem_declara_o_conteiner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZERVIS_CONTEINER", raising=False)
    assert not conteiner.em_conteiner()
    monkeypatch.setenv("ZERVIS_CONTEINER", "1")
    assert conteiner.em_conteiner()
    dockerfile = (RAIZ / "Dockerfile").read_text()
    assert "ZERVIS_CONTEINER=1" in dockerfile and "zervis.conteiner" in dockerfile


def test_doctor_no_conteiner_olha_o_painel_e_nao_o_systemd(
    no_conteiner: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    cli.doctor(_sem_systemd, responde=lambda _p: True)
    saida = capsys.readouterr().out
    assert "✓ Serviço" in saida and "Rodando no contêiner." in saida
    assert "Pelo Docker" in saida and "✓ Painel" in saida
    cli.doctor(_sem_systemd, responde=lambda _p: False)
    assert "Resolver: docker compose logs -f" in capsys.readouterr().out


def test_status_update_logs_e_uninstall_apontam_o_docker(
    no_conteiner: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.status(_sem_systemd, responde=lambda _p: True) == 0
    assert "Serviço: rodando" in capsys.readouterr().out
    assert cli.update(_sem_systemd, responde=lambda _p: True) == 1
    assert "docker compose up -d --build" in capsys.readouterr().out
    assert cli.uninstall(rodar=_sem_systemd) == 1
    assert "docker compose down" in capsys.readouterr().out
    assert cli.main(["logs"]) == 1
    assert "docker compose logs -f" in capsys.readouterr().out


def test_a_pagina_de_atualizacoes_nao_oferece_o_que_nao_da_para_aplicar(
    no_conteiner: None, tmp_path: Path
) -> None:
    pedidos: list[list[str]] = []

    def lancar(comando: Sequence[str]) -> subprocess.CompletedProcess[str]:
        pedidos.append(list(comando))
        return subprocess.CompletedProcess(comando, 0, "", "")

    v = versoes.Versoes(tmp_path / "estado", tmp_path / "config", lancar=lancar, rodar=_sem_systemd)
    achado = v.procurar()
    assert achado["motivo"] == "conteiner" and not achado["disponivel"]
    assert achado["texto"] == "Esta instalação é atualizada pelo Docker, no servidor."
    assert v.aplicar() == achado["texto"]
    assert pedidos == []  # nada de systemd-run


def test_sem_senha_a_entrada_abre_o_tunel_com_um_convite(tmp_path: Path) -> None:
    acesso, escolha = Acesso(tmp_path / "acesso.json"), tmp_path / "tunel.json"
    assert conteiner.primeiro_acesso_pelo_tunel(acesso, escolha)
    assert tunel.escolhido(escolha) and acesso.convite_valido
    acesso.definir("uma senha comprida o bastante")
    escolha.unlink()
    assert not conteiner.primeiro_acesso_pelo_tunel(acesso, escolha)  # com senha, nada muda
    assert not tunel.escolhido(escolha)


def test_o_primeiro_acesso_no_conteiner_nao_reinicia_nem_apaga_o_tunel(
    no_conteiner: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    chamado: dict[str, Any] = {}

    def preparar(acesso: Acesso, **extra: Any) -> list[str]:
        chamado.update(extra)
        return ["Abra no navegador: https://exemplo.trycloudflare.com"]

    monkeypatch.setattr(primeiro_acesso, "preparar", preparar)
    assert primeiro_acesso.main() == 0
    assert chamado["reiniciar"]() is None and chamado["tunel_no_ar"]() is True
    assert "trycloudflare" in capsys.readouterr().out
