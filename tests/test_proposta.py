"""Propor como PR: as melhorias da cópia vão para o GitHub só com os testes verdes e sem dados de
quem usa (06/11/2026). O GitHub aqui é um repositório local e um `gh` de mentira."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

from zervis.oficina import proposta, vazamento

GIT = "/usr/bin/git"
ASSINA = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false")


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 (git em repositórios temporários do teste)
        [GIT, "-C", str(pasta), *ASSINA, *args], check=True, capture_output=True, text=True
    ).stdout


def _commit(pasta: Path, arquivo: str, texto: str, mensagem: str) -> None:
    (pasta / arquivo).parent.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(texto)
    _git(pasta, "add", "-A")
    _git(pasta, "commit", "-qm", mensagem)


@pytest.fixture
def mundo(tmp_path: Path) -> dict[str, Path]:
    origem = tmp_path / "origem.git"
    subprocess.run([GIT, "init", "-q", "--bare", "-b", "master", str(origem)], check=True)  # noqa: S603
    ze = tmp_path / "ze"
    subprocess.run([GIT, "clone", "-q", str(origem), str(ze)], check=True, capture_output=True)  # noqa: S603
    _commit(ze, "README.md", "zé\n", "início")
    _git(ze, "push", "-q", "origin", "master")
    _git(ze, "remote", "set-head", "origin", "master")
    copia = tmp_path / "copia"
    _git(ze, "worktree", "add", "-q", "-b", "ze/abc", str(copia))
    chamadas = tmp_path / "gh.txt"
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" >> "{chamadas}"\n'
        f'test "$2" = list && {{ cat "{tmp_path / "gh-abertos"}" 2>/dev/null || echo "[]"; '
        "exit 0; }\n"
        'test "$1" = pr && echo "https://github.com/dono/zervis/pull/7"\n'
        f'exit "$(cat "{tmp_path / "gh-sai"}" 2>/dev/null || echo 0)"\n'
    )
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    return {"origem": origem, "ze": ze, "copia": copia, "gh": gh, "chamadas": chamadas}


def _propor(
    m: dict[str, Path], testes: bool = True, s: vazamento.Sensiveis | None = None
) -> proposta.Resultado:
    return proposta.propor(
        m["copia"],
        "ze/abc",
        lambda pasta: testes,
        ("zervis/config.py",),
        sensiveis=lambda: s or vazamento.Sensiveis(),
        gh=str(m["gh"]),
        agora=lambda: 1_793_900_000.0,
    )


def _branches(origem: Path) -> str:
    return _git(origem, "branch", "--list")


def test_publica_a_branch_e_abre_o_pr_com_o_que_foi_conferido(mundo: dict[str, Path]) -> None:
    _commit(mundo["copia"], "zervis/config.py", "x = 1\n", "Ajusta a configuração")
    r = _propor(mundo)
    assert r.ok and r.endereco.endswith("/pull/7") and "PR 7" in r.texto
    assert "ze/melhoria-" in _branches(mundo["origem"])
    args = mundo["chamadas"].read_text().splitlines()
    args = args[args.index("create") - 1 :]  # antes, a consulta dos PRs já abertos
    assert args[:2] == ["pr", "create"] and args[args.index("--base") + 1] == "master"
    assert args[args.index("--title") + 1] == "Ajusta a configuração"
    corpo = args[args.index("--body") + 1 :]
    assert any("Zona protegida" in linha for linha in corpo)
    assert any("`zervis/config.py`" in linha for linha in corpo)


def test_dado_pessoal_nao_sai_da_maquina(mundo: dict[str, Path]) -> None:
    _commit(mundo["copia"], "tests/test_x.py", 'TEL = "5571988887777"\n', "Teste novo")
    s = vazamento.Sensiveis(telefones={vazamento._chave_telefone("5571988887777")})
    r = _propor(mundo, s=s)
    assert not r.ok and "número de telefone da sua agenda em tests/test_x.py:1" in r.texto
    assert "88887777" not in r.texto
    assert "melhoria" not in _branches(mundo["origem"])
    assert "create" not in mundo["chamadas"].read_text()


def test_testes_vermelhos_ou_nada_novo_nao_publicam(mundo: dict[str, Path]) -> None:
    assert "nada novo" in _propor(mundo).texto
    _commit(mundo["copia"], "docs/a.md", "a\n", "Doc")
    r = _propor(mundo, testes=False)
    assert not r.ok and "testes falharam" in r.texto
    (mundo["copia"] / "solto.txt").write_text("sem commit")
    assert "sem commit" in _propor(mundo).texto
    assert "melhoria" not in _branches(mundo["origem"])


def test_sem_pr_a_branch_enviada_e_apagada(mundo: dict[str, Path], tmp_path: Path) -> None:
    _commit(mundo["copia"], "docs/a.md", "a\n", "Doc")
    (tmp_path / "gh-sai").write_text("1")
    r = _propor(mundo)
    assert not r.ok and "não abriu o PR" in r.texto
    assert "melhoria" not in _branches(mundo["origem"])


def test_acha_o_gh_fora_do_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", "/nada")
    falso = tmp_path / "gh"
    falso.write_text("#!/bin/sh\n")
    falso.chmod(0o755)
    monkeypatch.setattr(proposta, "CANDIDATOS_GH", ("/nao/existe/gh", str(falso)))
    assert proposta.achar_gh() == str(falso)
    monkeypatch.setattr(proposta, "CANDIDATOS_GH", ())
    assert proposta.achar_gh() == ""
    assert os.environ["PATH"] == "/nada"


def test_pela_voz_pergunta_antes_e_pelo_painel_so_confirmado() -> None:
    from types import SimpleNamespace

    from zervis.nucleo.servicos.oficina import ServicoOficina
    from zervis.portal.acoes.melhorias import AcoesMelhorias
    from zervis.portal.servidor import PedidoInvalido

    frase = ServicoOficina._descrever_manutencao("mcp__jarvis__modo_manutencao", {"acao": "propor"})
    assert frase and "GitHub" in frase and "público" in frase and frase.endswith("?")
    chamado: list[bool] = []
    a = AcoesMelhorias.__new__(AcoesMelhorias)
    resultado = proposta.Resultado(True, "Abri o PR 7 no GitHub.", "https://x/pull/7")

    def propor() -> proposta.Resultado:
        chamado.append(True)
        return resultado

    a.n = SimpleNamespace(manutencao=SimpleNamespace(propor=propor))  # type: ignore[assignment]
    with pytest.raises(PedidoInvalido):
        a.propor_melhorias({})
    assert not chamado
    assert a.propor_melhorias({"confirmado": True}) == {
        "aviso": "Abri o PR 7 no GitHub.",
        "endereco": "https://x/pull/7",
    }


def test_pr_aberto_com_os_mesmos_commits_nao_abre_outro(
    mundo: dict[str, Path], tmp_path: Path
) -> None:
    """09/11/2026: quatro cliques no "Sim" abriram quatro PRs do mesmo commit."""
    import json

    _commit(mundo["copia"], "docs/x.md", "x\n", "Documenta x")
    ponta = _git(mundo["copia"], "rev-parse", "HEAD").strip()
    url = "https://github.com/dono/zervis/pull/5"
    (tmp_path / "gh-abertos").write_text(json.dumps([{"url": url, "headRefOid": ponta}]))
    testados: list[Path] = []

    def testar(pasta: Path) -> bool:
        testados.append(pasta)
        return True

    r = proposta.propor(
        mundo["copia"], "ze/abc", testar, (),
        sensiveis=vazamento.Sensiveis, gh=str(mundo["gh"]), agora=lambda: 1_793_900_000.0,
    )  # fmt: skip
    assert r.ok and r.endereco == url and "PR 5 já tem" in r.texto
    assert not testados and "melhoria" not in _branches(mundo["origem"])
    assert "create" not in mundo["chamadas"].read_text()


def test_um_segundo_sim_enquanto_testa_nao_abre_outro_pr(mundo: dict[str, Path]) -> None:
    import threading

    _commit(mundo["copia"], "docs/y.md", "y\n", "Documenta y")
    testando, solta = threading.Event(), threading.Event()

    def testar(_pasta: Path) -> bool:
        testando.set()
        return solta.wait(10)

    resultados: list[proposta.Resultado] = []

    def primeira() -> None:
        resultados.append(
            proposta.propor(
                mundo["copia"],
                "ze/abc",
                testar,
                (),
                sensiveis=vazamento.Sensiveis,
                gh=str(mundo["gh"]),
                agora=lambda: 1_793_900_000.0,
            )
        )

    t = threading.Thread(target=primeira)
    t.start()
    assert testando.wait(10)
    segunda = _propor(mundo)
    solta.set()
    t.join(10)
    assert not segunda.ok and "Já estou propondo" in segunda.texto
    assert resultados[0].ok
    assert mundo["chamadas"].read_text().count("create") == 1
