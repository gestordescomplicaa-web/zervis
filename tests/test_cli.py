"""O comando `zervis` (ADR 0034, ponto 10): git e systemd falsos, pastas temporárias."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from zervis import cli, lugares


class Maquina:
    """Responde aos comandos como a máquina responderia, e guarda o que foi pedido."""

    def __init__(self, **respostas: tuple[int, str]) -> None:
        self.respostas = respostas
        self.pedidos: list[str] = []

    def __call__(self, comando: Sequence[str]) -> subprocess.CompletedProcess[str]:
        texto = " ".join(comando).replace(f"git -C {cli.REPO} ", "git ")
        self.pedidos.append(texto)
        for inicio, (codigo, saida) in self.respostas.items():
            if texto.startswith(inicio.replace("_", " ")):
                return subprocess.CompletedProcess(comando, codigo, saida, "")
        return subprocess.CompletedProcess(comando, 0, "", "")


@pytest.fixture(autouse=True)
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados"))
    return tmp_path


def _git_limpo(**extra: tuple[int, str]) -> dict[str, tuple[int, str]]:
    """Árvore limpa, seguindo origin/master, e o HEAD atrás da versão v0.1.0 e da origem."""
    return {
        "git_status": (0, ""),
        "git_rev-parse_--abbrev-ref": (0, "origin/master"),
        "git_rev-parse_HEAD": (0, "a" * 40),
        "git_rev-parse_@{u}": (0, "b" * 40),
        "git_tag": (0, "v0.1.0\nv0.0.9\n"),
        "git_rev-parse_v0.1.0^{commit}": (0, "b" * 40),
        f"git_merge-base_--is-ancestor_{'b' * 40}_HEAD": (1, ""),  # a versão não está atrás
        "git_log": (0, "bbbbbbb Vigia do n8n\ncccccc1 Conectores"),
        **extra,
    }


def _ordem(maquina: Maquina, *trechos: str) -> list[int]:
    return [next(i for i, p in enumerate(maquina.pedidos) if p.startswith(t)) for t in trechos]


@pytest.mark.parametrize("nome", ["ZERVIS_PAINEL_PORTA", "JARVIS_PAINEL_PORTA"])
def test_porta_vem_da_unidade_instalada(nome: str) -> None:
    """A unidade de antes de 20/10/2026 tem o nome antigo da variável."""
    cli.unidade().parent.mkdir(parents=True, exist_ok=True)
    cli.unidade().write_text(f"[Service]\nEnvironment={nome}=8796\n")
    assert cli.porta() == 8796


def test_update_avanca_reinicia_e_confere_o_painel(capsys: pytest.CaptureFixture[str]) -> None:
    maquina = Maquina(**_git_limpo())
    assert cli.update(maquina, responde=lambda _p: True, pausa=lambda _s: None) == 0
    assert _ordem(
        maquina, "git fetch", "git merge --ff-only", "systemctl --user restart"
    ) == sorted(_ordem(maquina, "git fetch", "git merge --ff-only", "systemctl --user restart"))
    assert any(p.endswith(f"sync --frozen --project {cli.REPO}") for p in maquina.pedidos)
    assert not any(p.startswith("git reset") for p in maquina.pedidos)
    saida = capsys.readouterr().out
    assert "aaaaaaa → v0.1.0 (2 mudanças)" in saida and "Atualizado para v0.1.0." in saida
    assert f"git merge --ff-only --quiet {'b' * 40}" in maquina.pedidos


def test_update_volta_para_a_anterior_se_o_painel_nao_sobe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    maquina = Maquina(**_git_limpo())

    def responde(_porta: int) -> bool:  # a versão nova não responde; a anterior, sim
        return any(p.startswith("git reset") for p in maquina.pedidos)

    assert cli.update(maquina, responde=responde, espera_s=0.05, pausa=lambda _s: None) == 1
    assert f"git reset --hard --quiet {'a' * 40}" in maquina.pedidos
    assert sum(p.startswith("systemctl --user restart") for p in maquina.pedidos) == 2
    assert "Versão anterior (aaaaaaa) de volta." in capsys.readouterr().out


@pytest.mark.parametrize(
    ("respostas", "motivo"),
    [
        ({"git_status": (0, " M zervis/cli.py")}, "alterações locais"),
        ({"git_rev-parse_--abbrev-ref": (128, "")}, "não segue uma branch"),
        ({"git_merge-base": (1, "")}, "commits locais"),
        ({"git_fetch": (1, "")}, "Sem conexão"),
    ],
)
def test_update_recusa_sem_mexer_em_nada(
    respostas: dict[str, tuple[int, str]], motivo: str, capsys: pytest.CaptureFixture[str]
) -> None:
    maquina = Maquina(**_git_limpo(**respostas))
    assert cli.update(maquina, responde=lambda _p: True, pausa=lambda _s: None) == 1
    assert motivo in capsys.readouterr().out
    assert not any(
        p.startswith(("git merge --ff", "git reset", "systemctl")) for p in maquina.pedidos
    )


def test_update_ja_na_mais_nova(capsys: pytest.CaptureFixture[str]) -> None:
    maquina = Maquina(**_git_limpo(**{"git_rev-parse_v0.1.0^{commit}": (0, "a" * 40)}))
    assert cli.update(maquina, responde=lambda _p: True) == 0
    assert "Já está na versão mais nova (v0.1.0)." in capsys.readouterr().out
    assert not any(p.startswith("systemctl") for p in maquina.pedidos)


def test_update_a_frente_da_versao_nao_volta_para_tras(capsys: pytest.CaptureFixture[str]) -> None:
    """Quem está na master, depois da v0.1.0, não é levado de volta para ela."""
    respostas = _git_limpo()
    del respostas[f"git_merge-base_--is-ancestor_{'b' * 40}_HEAD"]  # a versão está atrás
    maquina = Maquina(**respostas)
    assert cli.update(maquina, responde=lambda _p: True) == 0
    assert "à frente da versão mais nova (v0.1.0)" in capsys.readouterr().out
    assert not any(p.startswith(("git merge --ff", "systemctl")) for p in maquina.pedidos)


def test_update_sem_versao_publicada_aponta_o_desenvolvimento(
    capsys: pytest.CaptureFixture[str],
) -> None:
    maquina = Maquina(**_git_limpo(git_tag=(0, "")))
    assert cli.update(maquina, responde=lambda _p: True) == 0
    assert "zervis update --desenvolvimento" in capsys.readouterr().out


def test_update_desenvolvimento_segue_a_branch_da_origem(
    capsys: pytest.CaptureFixture[str],
) -> None:
    maquina = Maquina(**_git_limpo(**{"git_rev-parse_@{u}": (0, "c" * 40)}))
    assert (
        cli.update(maquina, responde=lambda _p: True, pausa=lambda _s: None, desenvolvimento=True)
        == 0
    )
    assert f"git merge --ff-only --quiet {'c' * 40}" in maquina.pedidos
    assert "Atualizado para origin/master." in capsys.readouterr().out


def test_uninstall_tira_servico_atalho_e_comando_e_deixa_os_dados(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for arquivo in (cli.unidade(), cli.atalho(), cli.icone()):
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("x")
    cli.comando().parent.mkdir(parents=True)
    cli.comando().symlink_to(cli.REPO / ".venv/bin/zervis")
    maquina = Maquina()
    assert cli.uninstall(rodar=maquina) == 0
    assert not any(
        a.exists() or a.is_symlink()
        for a in (cli.unidade(), cli.atalho(), cli.icone(), cli.comando())
    )
    assert "systemctl --user disable --now zervis" in maquina.pedidos
    assert "Os seus dados ficaram em:" in capsys.readouterr().out


def test_uninstall_nao_apaga_um_zervis_alheio() -> None:
    cli.comando().parent.mkdir(parents=True)
    cli.comando().write_text("#!/bin/sh\n")
    cli.uninstall(rodar=Maquina())
    assert cli.comando().read_text() == "#!/bin/sh\n"


def test_apagar_dados_so_com_a_frase_e_so_as_pastas_do_ze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raizes = {nome: tmp_path / "xdg" / nome / "zervis" for nome in ("CONFIG", "DADOS", "ESTADO")}
    for nome, raiz in raizes.items():
        raiz.mkdir(parents=True)
        (raiz / "algo").write_text("x")
        monkeypatch.setattr(lugares, nome, raiz)
    assert cli.uninstall(True, Maquina(), perguntar=lambda _p: "sim") == 1
    assert all(r.is_dir() for r in raizes.values())  # frase errada: nada sai, nem o serviço
    assert cli.uninstall(True, Maquina(), perguntar=lambda _p: cli.FRASE_APAGAR) == 0
    assert not any(r.exists() for r in raizes.values())
    assert (tmp_path / "xdg" / "CONFIG").is_dir()  # a pasta de cima não é do Zé


def test_doctor_marca_o_que_falta_e_como_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    parado = Maquina(
        **{"systemctl_--user_is-active": (3, ""), "systemctl_--user_is-enabled": (1, "")}
    )
    assert cli.doctor(parado, responde=lambda _p: False) == 1
    saida = capsys.readouterr().out
    assert "✗ Serviço" in saida and "Resolver: systemctl --user start zervis" in saida
    assert "✗ Painel" in saida and "- Áudio local" in saida  # sem tela: não se aplica
    assert "Indisponível" in saida and "Não se aplica" in saida
