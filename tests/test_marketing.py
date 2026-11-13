"""Marketing (ADR 0091): o site e o blog por Pull Request. O GitHub aqui é um repositório local e
um `gh` de mentira; o site, um repositório inventado que se declara no `zervis.json`."""

import json
import stat
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from zervis import marketing
from zervis.marketing import Marketing, MarketingErro
from zervis.oficina.sessoes import Sessao, Sessoes

GIT = "/usr/bin/git"
ASSINA = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false")


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 (git em repositórios temporários do teste)
        [GIT, "-C", str(pasta), *ASSINA, *args], check=True, capture_output=True, text=True
    ).stdout


MANIFESTO = {
    "zervis": 1,
    "blog": {
        "manual": "docs/manual-do-blog.md",
        "artigos": "posts",
        "modelo": "posts/_modelo.md",
        "validar": "npm run checar -- {slug}",
        "campos": {"data": "publicado", "rascunho": "rascunho"},
        "marcador": "[[AUTOR:",
    },
}


def _artigo(titulo: str, categoria: str, data: str, rascunho: bool) -> str:
    return (
        f'---\ntitle: "{titulo}"   # comentário\ncategory: "{categoria}"\n'
        f'publicado: "{data}"\ntags: ["a", "b"]\nrascunho: {str(rascunho).lower()}\n---\n\n'
        "## Seção\n\nTexto.\n"
    )


def _commit(pasta: Path, arquivos: dict[str, str], mensagem: str) -> None:
    for nome, texto in arquivos.items():
        (pasta / nome).parent.mkdir(parents=True, exist_ok=True)
        (pasta / nome).write_text(texto)
    _git(pasta, "add", "-A")
    _git(pasta, "commit", "-qm", mensagem)


@pytest.fixture
def mundo(tmp_path: Path) -> dict[str, Any]:
    origem = tmp_path / "origem.git"
    subprocess.run([GIT, "init", "-q", "--bare", "-b", "main", str(origem)], check=True)  # noqa: S603
    site = tmp_path / "casa" / "site"
    site.parent.mkdir()
    subprocess.run([GIT, "clone", "-q", str(origem), str(site)], check=True, capture_output=True)  # noqa: S603
    _commit(
        site,
        {
            "zervis.json": json.dumps(MANIFESTO),
            "docs/manual-do-blog.md": "# Manual\n",
            "posts/_modelo.md": _artigo("Modelo do blog", "x", "2026-01-01", True),
            "posts/antigo.md": _artigo("Artigo publicado", "dores", "2026-10-01", False),
            "posts/futuro.md": _artigo("Artigo agendado", "dores", "2026-12-24", False),
            "posts/rascunho.md": _artigo("Artigo rascunho", "ia", "2026-11-01", True),
        },
        "início",
    )
    _git(site, "push", "-q", "origin", "main")
    _git(site, "remote", "set-head", "origin", "main")
    # A pasta do site está noutra branch, com um commit que a base não tem.
    _git(site, "checkout", "-q", "-b", "trabalho")
    _commit(site, {"local.txt": "só aqui\n"}, "local")
    chamadas = tmp_path / "gh.txt"
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" >> "{chamadas}"\n'
        'test "$2" = list && { echo "[]"; exit 0; }\n'
        'test "$1" = pr && echo "https://github.com/dono/site/pull/3"\n'
        "exit 0\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)

    async def rodar(_s: Sessoes, _sessao: Sessao, _texto: str) -> str:
        return "Feito."

    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), rodar=rodar)
    m = Marketing(tmp_path / "config" / "marketing.json", gh=str(gh))
    return {"site": site, "origem": origem, "m": m, "sessoes": sessoes, "chamadas": chamadas}


def _parada(sessoes: Sessoes, id_: str) -> Sessao:
    fim = time.monotonic() + 5
    while sessoes.ler(id_).estado == "trabalhando" and time.monotonic() < fim:
        time.sleep(0.02)
    return sessoes.ler(id_)


def test_sem_configuracao_e_pastas_invalidas(mundo: dict[str, Any], tmp_path: Path) -> None:
    m: Marketing = mundo["m"]
    assert m.situacao()["estado"] == "Não configurado" and m.artigos() == []
    with pytest.raises(MarketingErro, match="git"):
        m.guardar(str(tmp_path), "main")
    with pytest.raises(MarketingErro, match="não existe"):
        m.guardar(str(mundo["site"]), "outra")
    with pytest.raises(MarketingErro, match="Configure"):
        m.pedir(mundo["sessoes"], "artigo", "", "claude")


def test_artigos_da_base_com_estado_e_categoria(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    site = m.guardar(str(mundo["site"]), "")  # vazia: a branch padrão do GitHub
    assert site.base == "main"
    assert m.situacao()["estado"] == "Configurado"
    artigos = m.artigos(hoje=date(2026, 11, 13))
    assert [(a["slug"], a["estado"]) for a in artigos] == [
        ("futuro", "Agendado"),
        ("rascunho", "Rascunho"),
        ("antigo", "Publicado"),
    ]
    assert artigos[0]["titulo"] == "Artigo agendado"  # aspas e comentário fora
    assert m.por_categoria(artigos) == {"dores": 2, "ia": 1}


def test_pedido_de_artigo_parte_da_base_e_segue_o_manual(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = m.pedir(mundo["sessoes"], "artigo", "quando automatizar", "claude")
    assert s.origem == "marketing" and s.nome == "Blog · quando automatizar" and s.worktree
    copia = Path(s.worktree)
    assert not (copia / "local.txt").exists()  # partiu da base do GitHub, não da pasta
    assert s.base == _git(mundo["site"], "rev-parse", "origin/main").strip()
    tarefa = next(x["texto"] for x in mundo["sessoes"].mensagens(s.id) if x["quem"] == "usuario")
    assert "docs/manual-do-blog.md" in tarefa and "posts/_modelo.md" in tarefa
    assert "`rascunho: true`" in tarefa and "npm run checar -- {slug}" in tarefa
    assert marketing.CORPO_PR in tarefa
    assert [p["nome"] for p in m.pedidos(mundo["sessoes"])] == ["Blog · quando automatizar"]


def test_site_sem_integracao_so_aceita_mudanca(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    _git(mundo["site"], "rm", "-q", "zervis.json")
    _git(mundo["site"], "commit", "-qm", "sem integração")
    _git(mundo["site"], "push", "-q", "origin", "trabalho:sem-blog")
    m.guardar(str(mundo["site"]), "sem-blog")
    assert m.situacao()["estado"] == "Sem integração" and m.artigos() == []
    with pytest.raises(MarketingErro, match=r"zervis\.json"):
        m.pedir(mundo["sessoes"], "artigo", "", "claude")
    with pytest.raises(MarketingErro, match="Diga"):
        m.pedir(mundo["sessoes"], "site", " ", "claude")


def test_o_pr_do_artigo_vai_como_rascunho(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _parada(mundo["sessoes"], m.pedir(mundo["sessoes"], "artigo", "", "claude").id)
    copia = Path(s.worktree)
    assert not m.abrir_pr(mundo["sessoes"], s.id).ok  # nada novo ainda
    _commit(
        copia,
        {"posts/novo.md": _artigo("Um artigo novo", "ia", "2026-11-20", False)},
        "blog: Um artigo novo",
    )
    r = m.abrir_pr(mundo["sessoes"], s.id)
    assert not r.ok and "rascunho" in r.texto  # draft: false não sai da sessão
    _commit(
        copia,
        {"posts/novo.md": _artigo("Um artigo novo", "ia", "2026-11-20", True)
         + "\n[[AUTOR: conte um caso]]\n"},
        "blog: rascunho",
    )  # fmt: skip
    (copia / marketing.CORPO_PR).write_text("## Um artigo novo\n")
    r = m.abrir_pr(mundo["sessoes"], s.id)
    assert r.ok and r.endereco.endswith("/pull/3") and "marcadores" in r.texto
    assert _git(mundo["origem"], "branch", "--list", "blog/novo").strip()
    gh = mundo["chamadas"].read_text().splitlines()
    criar = gh[gh.index("create") - 1 :]
    assert criar[:8] == ["pr", "create", "--base", "main", "--head", "blog/novo", "--title",
                         "blog: Um artigo novo"]  # fmt: skip
    assert criar[criar.index("--body") + 1] == "## Um artigo novo"


def test_mudanca_no_site_vira_branch_propria(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _parada(mundo["sessoes"], m.pedir(mundo["sessoes"], "site", "Botão maior", "claude").id)
    _commit(Path(s.worktree), {"app/page.tsx": "botão\n"}, "Botão maior na home")
    r = m.abrir_pr(mundo["sessoes"], s.id)
    assert r.ok
    branches = _git(mundo["origem"], "branch", "--list", "site/*").split()
    assert branches == [f"site/botao-maior-{s.id}"]


def test_so_sessao_de_marketing_abre_pr(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    outra = mundo["sessoes"].criar("Outra", str(mundo["site"]))
    assert not m.abrir_pr(mundo["sessoes"], outra.id).ok


def test_configuracao_sobrevive(mundo: dict[str, Any], tmp_path: Path) -> None:
    mundo["m"].guardar(str(mundo["site"]), "main")
    dados = json.loads((tmp_path / "config" / "marketing.json").read_text())
    assert dados["site"]["base"] == "main"
    assert Marketing(tmp_path / "config" / "marketing.json").site().base == "main"


@pytest.mark.parametrize(
    ("texto", "erro"),
    [
        ("{nao é json", "JSON"),
        ('{"zervis": 2}', "zervis"),
        ('{"zervis": 1, "blog": {"manual": "../fora.md", "artigos": "posts"}}', "caminho"),
        ('{"zervis": 1, "blog": {"manual": "/etc/x", "artigos": "posts"}}', "caminho"),
        ('{"zervis": 1, "blog": {"manual": "m.md"}}', "caminho"),
    ],
)
def test_manifesto_invalido_e_recusado(texto: str, erro: str) -> None:
    with pytest.raises(MarketingErro, match=erro):
        marketing.ler_manifesto(texto)


def test_manifesto_sem_blog_e_campos_padrao() -> None:
    assert marketing.ler_manifesto('{"zervis": 1}') is None
    blog = marketing.ler_manifesto('{"zervis": 1, "blog": {"manual": "m.md", "artigos": "a"}}')
    assert blog is not None and blog.campo("rascunho") == "draft" and blog.campo("data") == "date"


def test_manifesto_invalido_aparece_na_situacao(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    _commit(mundo["site"], {"zervis.json": '{"zervis": 7}'}, "manifesto errado")
    _git(mundo["site"], "push", "-q", "origin", "trabalho:errado")
    m.guardar(str(mundo["site"]), "errado")
    assert m.situacao()["estado"] == "Integração inválida" and m.artigos() == []
