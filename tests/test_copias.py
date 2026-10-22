"""Aplicação e descarte em repositórios Git reais, sem tocar em projetos do usuário."""

from pathlib import Path

import pytest

from zervis.oficina.sessoes import Sessao, SessaoErro, Sessoes, _git


def git(pasta: Path, *args: str) -> str:
    r = _git(pasta, *args)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def copia(tmp_path: Path) -> tuple[Sessoes, Sessao, Path, Path]:
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    (projeto / "a.txt").write_text("base\n")
    (projeto / ".gitignore").write_text("*.local\n")
    git(projeto, "init", "-q")
    git(projeto, "config", "user.email", "teste@example.invalid")
    git(projeto, "config", "user.name", "Teste")
    git(projeto, "add", ".")
    git(projeto, "commit", "-qm", "base")
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *a: None)
    sessao = sessoes.criar("Teste", str(projeto), isolada=True)
    return sessoes, sessao, projeto, Path(sessao.worktree)


def mudar(onde: Path, nome: str = "a.txt", texto: str = "novo\n") -> None:
    (onde / nome).write_text(texto)
    git(onde, "add", nome)
    git(onde, "commit", "-qm", "mudança")


def test_aplicar_so_muda_projeto_depois_da_aprovacao(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    assert (projeto / "a.txt").read_text() == "base\n"
    assert sessoes.copia(s.id)["arquivos"] == ["a.txt"]
    assert sessoes.aplicar_copia(s.id) == "Mudanças juntadas ao projeto."
    assert (projeto / "a.txt").read_text() == "novo\n"
    assert sessoes.ler(s.id).base == git(projeto, "rev-parse", "HEAD")
    assert sessoes.copia(s.id)["commits"] == []


def test_conflito_preserva_projeto_e_copia(copia: tuple[Sessoes, Sessao, Path, Path]) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    mudar(projeto, texto="outro\n")
    antes = git(projeto, "rev-parse", "HEAD")
    with pytest.raises(SessaoErro, match="conflito"):
        sessoes.aplicar_copia(s.id)
    assert git(projeto, "rev-parse", "HEAD") == antes
    assert git(projeto, "status", "--porcelain") == ""
    assert (projeto / "a.txt").read_text() == "outro\n"
    assert (onde / "a.txt").read_text() == "novo\n"
    assert sessoes.ler(s.id).base == s.base


def test_historias_divergentes_sem_conflito_se_juntam(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    mudar(projeto, nome="b.txt", texto="do projeto\n")
    sessoes.aplicar_copia(s.id)
    assert (projeto / "b.txt").read_text() == "do projeto\n"
    assert (onde / "b.txt").read_text() == "do projeto\n"
    assert git(projeto, "rev-parse", "HEAD") == git(onde, "rev-parse", "HEAD")


def test_descartar_preserva_ignorados_e_remove_alteracoes_da_copia(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    (onde / "novo.txt").write_text("não commitado")
    (onde / "config.local").write_text("configuração local")
    assert sessoes.descartar_copia(s.id) == "Mudanças descartadas."
    assert (onde / "a.txt").read_text() == "base\n"
    assert not (onde / "novo.txt").exists()
    assert (onde / "config.local").read_text() == "configuração local"
    assert git(onde, "rev-parse", "HEAD") == git(projeto, "rev-parse", "HEAD")


def test_git_invalido_nao_informa_descarte_nem_muda_base(
    copia: tuple[Sessoes, Sessao, Path, Path],
    tmp_path: Path,
) -> None:
    sessoes, s, _, onde = copia
    (onde / "a.txt").write_text("pendente")
    (onde / ".git").write_text(f"gitdir: {tmp_path / 'ausente'}\n")
    with pytest.raises(SessaoErro, match="Git"):
        sessoes.descartar_copia(s.id)
    assert (onde / "a.txt").read_text() == "pendente"
    assert sessoes.ler(s.id).base == s.base


def test_falha_no_reset_nao_limpa_arquivos_nem_informa_sucesso(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, _, onde = copia
    (onde / "novo.txt").write_text("preservar")
    index = Path(git(onde, "rev-parse", "--git-path", "index"))
    trava = Path(f"{index}.lock")
    trava.write_text("bloqueio sintético")
    with pytest.raises(SessaoErro, match="Git"):
        sessoes.descartar_copia(s.id)
    assert (onde / "novo.txt").read_text() == "preservar"
    assert sessoes.ler(s.id).base == s.base


@pytest.mark.parametrize("metodo", ["aplicar_copia", "descartar_copia"])
def test_sessao_trabalhando_bloqueia_operacao(
    copia: tuple[Sessoes, Sessao, Path, Path],
    metodo: str,
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    sessoes._mudar(s.id, estado="trabalhando")
    # Sessão sem terminal: a consulta de estado não deve depender de um processo real.
    sessoes.trabalhando = lambda: [s.id]  # type: ignore[method-assign]
    with pytest.raises(SessaoErro, match="trabalhando"):
        getattr(sessoes, metodo)(s.id)
    assert (projeto / "a.txt").read_text() == "base\n"
    assert (onde / "a.txt").read_text() == "novo\n"


@pytest.mark.parametrize("metodo", ["aplicar_copia", "descartar_copia"])
def test_manutencao_nao_pode_contornar_a_zona_protegida(
    copia: tuple[Sessoes, Sessao, Path, Path],
    metodo: str,
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    sessoes._mudar(s.id, origem="manutencao")
    with pytest.raises(SessaoErro, match="Autodesenvolvimento"):
        getattr(sessoes, metodo)(s.id)
    assert (projeto / "a.txt").read_text() == "base\n"
    assert (onde / "a.txt").read_text() == "novo\n"


def test_aplicar_preserva_ignorado_no_projeto(copia: tuple[Sessoes, Sessao, Path, Path]) -> None:
    sessoes, s, projeto, onde = copia
    (projeto / "config.local").write_text("preservar")
    (onde / "config.local").write_text("outro")
    git(onde, "add", "-f", "config.local")
    git(onde, "commit", "-qm", "arquivo agora versionado")
    with pytest.raises(SessaoErro, match="ignorado"):
        sessoes.aplicar_copia(s.id)
    assert (projeto / "config.local").read_text() == "preservar"


def test_descartar_preserva_ignorado_que_colide_com_novo_commit(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    (onde / "config.local").write_text("preservar")
    (projeto / "config.local").write_text("do projeto")
    git(projeto, "add", "-f", "config.local")
    git(projeto, "commit", "-qm", "arquivo agora versionado")
    with pytest.raises(SessaoErro, match="ignorado"):
        sessoes.descartar_copia(s.id)
    assert (onde / "config.local").read_text() == "preservar"
    assert sessoes.ler(s.id).base == s.base


def test_projeto_com_arquivo_novo_bloqueia_aplicacao(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    (projeto / "nota.txt").write_text("preservar")
    with pytest.raises(SessaoErro, match="alterações locais"):
        sessoes.aplicar_copia(s.id)
    assert (projeto / "nota.txt").read_text() == "preservar"
    assert (projeto / "a.txt").read_text() == "base\n"


def test_api_exige_confirmacao_antes_de_alterar_copia(
    copia: tuple[Sessoes, Sessao, Path, Path],
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    from zervis.portal.acoes import Acoes
    from zervis.portal.servidor import PedidoInvalido

    sessoes, s, projeto, onde = copia
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path / "latencias", tmp_path / "teste")
    mudar(onde)
    for acao in (acoes.aplicar_copia, acoes.descartar_copia):
        with pytest.raises(PedidoInvalido, match="Confirme"):
            acao({"id": s.id})
    assert (projeto / "a.txt").read_text() == "base\n"
    assert acoes.aplicar_copia({"id": s.id, "confirmado": True})["commits"] == []


def test_copia_sem_commit_bloqueia_aplicacao(copia: tuple[Sessoes, Sessao, Path, Path]) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    (onde / "a.txt").write_text("sem commit")
    with pytest.raises(SessaoErro, match="sem commit"):
        sessoes.aplicar_copia(s.id)
    assert (projeto / "a.txt").read_text() == "base\n"
    assert (onde / "a.txt").read_text() == "sem commit"


def test_falha_na_limpeza_nao_registra_descarte_concluido(
    copia: tuple[Sessoes, Sessao, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from zervis.oficina import sessoes as modulo

    sessoes, s, projeto, onde = copia
    mudar(projeto, nome="b.txt")
    (onde / "novo.txt").write_text("preservar")
    executar = modulo._git

    def falhar(pasta: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[0] == "clean":
            return subprocess.CompletedProcess(args, 1, "", "falha sintética")
        return executar(pasta, *args)

    monkeypatch.setattr(modulo, "_git", falhar)
    with pytest.raises(SessaoErro, match="Git"):
        sessoes.descartar_copia(s.id)
    assert (onde / "novo.txt").read_text() == "preservar"
    assert sessoes.ler(s.id).base == s.base
    assert not any("Descartei" in m["texto"] for m in sessoes.mensagens(s.id))


def test_ignorado_na_copia_bloqueia_antes_de_modificar_projeto(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    sessoes, s, projeto, onde = copia
    mudar(onde)
    (onde / "config.local").write_text("preservar")
    (projeto / "config.local").write_text("do projeto")
    git(projeto, "add", "-f", "config.local")
    git(projeto, "commit", "-qm", "arquivo agora versionado")
    antes = git(projeto, "rev-parse", "HEAD")
    with pytest.raises(SessaoErro, match="ignorado"):
        sessoes.aplicar_copia(s.id)
    assert git(projeto, "rev-parse", "HEAD") == antes
    assert (projeto / "a.txt").read_text() == "base\n"
    assert (onde / "config.local").read_text() == "preservar"


def test_aplicar_encerra_terminal_ocioso_antes_de_mudar_arquivos(
    copia: tuple[Sessoes, Sessao, Path, Path],
) -> None:
    import sys

    from zervis.oficina.terminal import Terminal

    sessoes, s, _, onde = copia
    mudar(onde)
    t = Terminal([sys.executable, "-c", "import time; time.sleep(60)"], onde, {})
    sessoes.terminais[s.id] = t
    try:
        sessoes.aplicar_copia(s.id)
        assert not t.vivo
        assert t.leitor is not None and not t.leitor.is_alive()
    finally:
        t.encerrar()
