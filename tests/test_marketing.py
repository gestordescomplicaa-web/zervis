"""Marketing (ADR 0091): o site e o blog por Pull Request. O GitHub aqui é um repositório local e
um `gh` de mentira; o site, um repositório inventado que se declara no `zervis.json`."""

import json
import stat
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import marketing
from zervis.marketing import Marketing, MarketingErro
from zervis.oficina.agentes import livres_da_sessao
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
        "instalar": "npm ci",
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
    # A identidade fica no repositório, como num site de verdade (a CI não tem uma global).
    _git(site, "config", "user.name", "Autora do Site")
    _git(site, "config", "user.email", "autora@exemplo.com")
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
        'test "$1 $2" = "repo view" && { echo "dono/site"; exit 0; }\n'
        'case "$1 $2" in "api "*statuses) '
        f'cat "{tmp_path / "deploy"}" 2>/dev/null || echo \'["success", "", "https://site"]\'; '
        'exit 0;; "api "*) echo "[11]"; exit 0;; esac\n'
        'test "$2" = list && { echo "[]"; exit 0; }\n'
        'test "$1" = pr && echo "https://github.com/dono/site/pull/3"\n'
        "exit 0\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)

    async def rodar(_s: Sessoes, sessao: Sessao, texto: str) -> str:
        # O "aprovado": a sessão tira o rascunho e os marcadores e faz o commit, como pedido.
        if "aprovou o artigo" in texto:
            copia = Path(sessao.worktree)
            for arquivo in (copia / "posts").glob("*.md"):
                corpo = arquivo.read_text()
                if "rascunho: true" in corpo and not arquivo.name.startswith("_"):
                    corpo = corpo.replace("rascunho: true", "rascunho: false")
                    corpo = corpo.replace("\n[[AUTOR: conte um caso]]\n", "")
                    _commit(copia, {f"posts/{arquivo.name}": corpo}, "blog: publica")
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


def _artigo_pronto(m: Marketing, sessoes: Sessoes) -> Sessao:
    """Um pedido de artigo que terminou com o rascunho e um marcador, e o PR aberto sozinho."""
    s = _parada(sessoes, m.pedir(sessoes, "artigo", "", "claude").id)
    texto = _artigo("Um artigo novo", "ia", "2026-11-20", True) + "\n[[AUTOR: conte um caso]]\n"
    _commit(Path(s.worktree), {"posts/novo.md": texto}, "blog: Um artigo novo")
    assert "Abri o PR 3" in m.ao_terminar(sessoes, s.id)
    return s


def test_o_pedido_libera_so_os_comandos_do_site(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = m.pedir(mundo["sessoes"], "artigo", "", "claude")
    livres = livres_da_sessao(mundo["sessoes"].pasta / s.id)
    assert "Bash(npm ci)" in livres and "Bash(npm run checar:*)" in livres
    assert "Bash(git commit:*)" in livres and not any("push" in r for r in livres)


def test_regras_com_shell_sao_ignoradas(tmp_path: Path) -> None:
    (tmp_path / "livres.json").write_text(
        json.dumps(["Bash(npm ci)", "Bash(npm ci; rm -rf ~)", "Bash(a && b)", "Write", 3])
    )
    assert livres_da_sessao(tmp_path) == ["Bash(npm ci)"]
    with pytest.raises(MarketingErro, match="comando"):
        marketing.ler_manifesto(
            '{"zervis": 1, "blog": {"manual": "m.md", "artigos": "a", "validar": "x && y"}}'
        )


def test_ao_terminar_abre_o_pr_uma_vez(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _artigo_pronto(m, mundo["sessoes"])
    assert m.pedidos(mundo["sessoes"])[0]["pr"].endswith("/pull/3")
    assert m.ao_terminar(mundo["sessoes"], s.id) == ""  # já tem PR: não abre outro


def test_aprovado_publica_direto_na_base_e_vigia_o_deploy(mundo: dict[str, Any]) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _artigo_pronto(m, mundo["sessoes"])
    avisos: list[str] = []
    m.avisar = avisos.append
    assert not m.finalizar(mundo["sessoes"], s.id).ok  # ainda é rascunho: não publica
    r = m.publicar(mundo["sessoes"], s.id)
    assert r.ok and m.pedidos(mundo["sessoes"])[0]["publicando"]
    tarefa = mundo["sessoes"].mensagens(s.id)
    assert any("aprovou o artigo posts/novo.md" in x["texto"] for x in tarefa)
    _parada(mundo["sessoes"], s.id)
    assert "Enviei à main" in m.ao_terminar(mundo["sessoes"], s.id)
    publicado = _git(mundo["origem"], "show", "main:posts/novo.md")
    assert "rascunho: false" in publicado and "[[AUTOR:" not in publicado
    assert _git(mundo["origem"], "rev-parse", "main") == _git(
        mundo["origem"], "rev-parse", "blog/novo"
    )
    fim = time.monotonic() + 5
    while not avisos and time.monotonic() < fim:
        time.sleep(0.02)
    assert avisos == [f"{s.nome}: está no ar."]
    assert not m.pedidos(mundo["sessoes"])[0]["publicando"]


def test_deploy_bloqueado_e_avisado(mundo: dict[str, Any], tmp_path: Path) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    (tmp_path / "deploy").write_text('["failure", "Deployment was blocked", ""]')
    assert m.implantacao("abc") == ("falhou", "Deployment was blocked")


def test_mudanca_no_site_publica_na_hora_e_junta_a_base_que_andou(
    mundo: dict[str, Any],
) -> None:
    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _parada(mundo["sessoes"], m.pedir(mundo["sessoes"], "site", "Botão maior", "claude").id)
    _commit(Path(s.worktree), {"app/page.tsx": "botão\n"}, "Botão maior na home")
    # Enquanto isso, a base andou no GitHub.
    _git(mundo["site"], "checkout", "-q", "-b", "outra", "origin/main")
    _commit(mundo["site"], {"README.md": "novo\n"}, "readme")
    _git(mundo["site"], "push", "-q", "origin", "outra:main")
    r = m.publicar(mundo["sessoes"], s.id)
    assert r.ok, r.texto
    arquivos = _git(mundo["origem"], "ls-tree", "--name-only", "-r", "main").split()
    assert {"app/page.tsx", "README.md"} <= set(arquivos)
    # Depois do rebase, o commit continua com o autor de quem fez: é o que o deploy confere.
    assert _git(mundo["origem"], "log", "-1", "--format=%an", "main").strip() == "t"


def test_a_automacao_de_artigo_pede_o_artigo_na_hora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis import fuso
    from zervis.automacoes.jobs import Jobs
    from zervis.nucleo.servicos.automacoes import ServicoAutomacoes

    agora = datetime(2099, 1, 5, 8, 0, tzinfo=fuso.local())  # uma segunda
    jobs = Jobs(tmp_path / "jobs.json")
    jobs.criar("Artigo do blog", "cron 0 9 * * 1,4", "artigo", json.dumps({"tema": ""}), agora)
    pedidos: list[tuple[str, str]] = []

    def pedir(_sessoes: Any, tipo: str, texto: str, _motor: str) -> Any:
        pedidos.append((tipo, texto))
        return SimpleNamespace(nome="Blog · próximo artigo")

    monkeypatch.setattr(marketing.PADRAO, "pedir", pedir)
    linha: list[str] = []
    n = SimpleNamespace(
        jobs=jobs, sessoes=object(), _rodando=set(), fila=SimpleNamespace(guardar=print),
        _na_linha=lambda _tipo, texto: linha.append(texto),
    )  # fmt: skip
    momento = datetime(2099, 1, 5, 9, 0, 30, tzinfo=fuso.local())
    jobs.disparar(momento)
    (x,) = jobs.pendentes()
    ServicoAutomacoes(n)._executar(x, momento)
    fim = time.monotonic() + 3
    while jobs.listar()[0].ultimo_status != "ok" and time.monotonic() < fim:
        time.sleep(0.02)
    assert pedidos == [("artigo", "")] and jobs.listar()[0].ultimo_status == "ok"
    assert linha == ["Comecei o artigo do blog: Blog · próximo artigo."]


def test_renomear_depois_do_pr_nao_muda_a_branch(mundo: dict[str, Any]) -> None:
    from zervis.oficina import sessoes_leitura

    m: Marketing = mundo["m"]
    m.guardar(str(mundo["site"]), "main")
    s = _parada(mundo["sessoes"], m.pedir(mundo["sessoes"], "site", "Botão maior", "claude").id)
    _commit(Path(s.worktree), {"app/page.tsx": "botão\n"}, "Botão maior na home")
    assert m.abrir_pr(mundo["sessoes"], s.id).ok
    sessoes_leitura.renomear(mundo["sessoes"], s.id, "Site · Outro nome")
    assert m.publicar(mundo["sessoes"], s.id).ok
    assert _git(mundo["origem"], "branch", "--list", "site/*").split() == [
        f"site/botao-maior-{s.id}"
    ]
