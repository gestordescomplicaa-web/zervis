"""O isolamento das sessões (plano de maturidade, Frente 2; ADR 0074). O aceite do plano: uma
sessão protegida não lê `~/.ssh/id_*` nem os dados do Zé."""

import subprocess
from pathlib import Path

import pytest

from zervis.oficina import isolamento
from zervis.oficina.sessoes import Sessao, SessaoErro, Sessoes, git_comum, isolar

precisa_do_bwrap = pytest.mark.skipif(
    not isolamento.disponivel(), reason="sem bubblewrap (ou o sistema bloqueia o isolamento)"
)


def _casa(tmp_path: Path) -> tuple[Path, Path]:
    casa = tmp_path / "casa"
    (casa / ".ssh").mkdir(parents=True)
    (casa / ".ssh" / "id_ed25519").write_text("CHAVE-PRIVADA")
    (casa / ".config" / "zervis").mkdir(parents=True)
    (casa / ".config" / "zervis" / "deepgram.key").write_text("SEGREDO-DO-ZE")
    (casa / ".local" / "share" / "zervis").mkdir(parents=True)
    projeto = casa / "projetos" / "loja"
    projeto.mkdir(parents=True)
    (projeto / "LEIAME.md").write_text("Loja.\n")
    return casa, projeto


def _rodar(casa: Path, projeto: Path, script: str) -> subprocess.CompletedProcess[str]:
    comando = isolamento.envolver(["sh", "-c", script], [projeto], casa=casa, pasta=projeto)
    return subprocess.run(comando, capture_output=True, text=True, timeout=30)  # noqa: S603


@precisa_do_bwrap
def test_a_sessao_protegida_nao_le_a_chave_ssh_nem_os_dados_do_ze(tmp_path: Path) -> None:
    casa, projeto = _casa(tmp_path)
    for alvo in (".ssh/id_ed25519", ".config/zervis/deepgram.key"):
        feito = _rodar(casa, projeto, f"cat {casa / alvo}")
        assert (
            feito.returncode != 0 and "CHAVE" not in feito.stdout and "SEGREDO" not in feito.stdout
        )
    assert _rodar(casa, projeto, f"ls {casa / '.local/share/zervis'}").returncode != 0


@precisa_do_bwrap
def test_o_projeto_continua_dela_para_ler_e_escrever(tmp_path: Path) -> None:
    casa, projeto = _casa(tmp_path)
    feito = _rodar(casa, projeto, "cat LEIAME.md && echo novo > feito.txt && pwd")
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.splitlines() == ["Loja.", str(projeto)]
    assert (projeto / "feito.txt").read_text() == "novo\n"  # a escrita chega ao projeto de verdade


def test_so_a_sessao_protegida_roda_no_isolamento(tmp_path: Path) -> None:
    s = Sessao("a1b2c3d4", "Loja", str(tmp_path), protegida=False)
    assert isolar(s, ["claude"], tmp_path / "sessao") == ["claude"]
    s.protegida = True
    comando = isolar(s, ["claude", "--resume", "x"], tmp_path / "sessao")
    assert comando[0] == "bwrap" and comando[-3:] == ["claude", "--resume", "x"]
    assert ["--bind", str(tmp_path), str(tmp_path)] == comando[
        comando.index(str(tmp_path)) - 1 : comando.index(str(tmp_path)) + 2
    ]


def _git(pasta: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-C", str(pasta), "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S607
        check=True,
        capture_output=True,
    )


def test_a_copia_isolada_leva_junto_o_git_de_verdade(tmp_path: Path) -> None:
    """Numa cópia isolada (worktree), o `.git` mora fora da pasta: sem ele, nem commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "inicio")
    assert git_comum(repo) == []  # o .git está dentro da pasta
    copia = tmp_path / "copia"
    _git(repo, "worktree", "add", "-q", "-b", "ze/x", str(copia))
    assert git_comum(copia) == [repo / ".git"]


def test_sem_bubblewrap_nao_cria_sessao_protegida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raiz = tmp_path / "casa"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,))
    monkeypatch.setattr(isolamento, "disponivel", lambda: False)
    with pytest.raises(SessaoErro, match="bubblewrap"):
        sessoes.criar("Loja", str(raiz / "loja"), protegida=True)
    monkeypatch.setattr(isolamento, "disponivel", lambda: True)
    s = sessoes.criar("Loja", str(raiz / "loja"), protegida=True)
    assert s.protegida and sessoes.ler(s.id).protegida  # fica gravado
    assert "protegida" in sessoes.mensagens(s.id)[0]["texto"]


@precisa_do_bwrap
def test_links_do_sistema_e_da_casa_nao_quebram_o_isolamento(tmp_path: Path) -> None:
    """09/11/2026: no Arch, /usr/sbin é um link para bin, e o bwrap recusava montar ali ("Can't
    mount on symlink destination"). O que só se lê fora da casa já está visível; um link dentro
    da casa (o ~/.gitconfig que aponta para outro lugar) chega lá dentro como link."""
    casa, projeto = _casa(tmp_path)
    (casa / "dotfiles").mkdir()
    (casa / "dotfiles" / "gitconfig").write_text("[user]\n")
    (casa / ".gitconfig").symlink_to(casa / "dotfiles" / "gitconfig")
    comando = isolamento.envolver(
        ["sh", "-c", f"cat {casa / '.gitconfig'}"],
        [projeto],
        [Path("/usr/sbin"), Path("/usr/bin")],
        casa=casa,
        pasta=projeto,
    )
    assert "/usr/sbin" not in comando and "/usr/bin" not in comando  # o sistema já está visível
    feito = subprocess.run(comando, capture_output=True, text=True, timeout=30)  # noqa: S603
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == "[user]\n"


@precisa_do_bwrap
def test_os_outros_processos_da_maquina_ficam_fora(tmp_path: Path) -> None:
    """Nem a lista nem a linha de comando dos outros processos (a do Zé, a de outra sessão)."""
    casa, projeto = _casa(tmp_path)
    feito = _rodar(casa, projeto, "ls /proc | grep -c '^[0-9]'; cat /proc/1/cmdline")
    assert feito.returncode == 0, feito.stderr
    linhas = feito.stdout.splitlines()
    assert int(linhas[0]) < 10  # o próprio shell e o bwrap, não as centenas da máquina
    assert "systemd" not in feito.stdout and "init" not in feito.stdout
