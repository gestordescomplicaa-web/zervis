"""Propor como PR: as melhorias do autodesenvolvimento vão para o GitHub (06/11/2026).

Sem isto, o que o Zé melhora em si fica só nesta máquina: junta na pasta em uso e nunca chega ao
repositório. Propor publica a cópia de melhorias numa branch nova e abre o PR, para a CI conferir
e quem mantém mesclar; depois, o `update` traz de volta como qualquer versão.

Publicar é para fora e o repositório é público, então, nesta ordem, e parando no primeiro não:
1. há o que propor: commits da cópia que a origem ainda não tem, nada sem commit;
2. os testes passam na cópia;
3. a mudança não leva dados de quem usa (`vazamento.py`): diz o tipo e o lugar, nunca o valor;
4. envia a branch e abre o PR pelo `gh` desta máquina, com o login dela no GitHub.
A aprovação ("sim" falado ou a confirmação no painel) vem antes, de quem chama.
"""

import contextlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from zervis.oficina import vazamento

ESPERA_GIT_S = 120
# Uma proposta por vez: os testes levam minutos, e um segundo "sim" no meio abria outro PR igual
# (09/11/2026: quatro PRs do mesmo commit, um por clique).
_PROPONDO = threading.Lock()
CANDIDATOS_GH = (
    "~/.local/share/mise/shims/gh",
    "~/.local/bin/gh",
    "/usr/local/bin/gh",
    "/usr/bin/gh",
)


@dataclass(frozen=True)
class Resultado:
    ok: bool
    texto: str  # o que dizer, falado e no painel
    endereco: str = ""  # o PR aberto


def achar_gh() -> str:
    """O `gh` desta máquina: o serviço não tem o PATH do terminal (o do mise, por exemplo)."""
    if achado := shutil.which("gh"):
        return achado
    for candidato in CANDIDATOS_GH:
        caminho = Path(candidato).expanduser()
        if caminho.is_file() and os.access(caminho, os.X_OK):
            return str(caminho)
    return ""


def _rodar(
    args: list[str], cwd: Path, espera: float = ESPERA_GIT_S
) -> subprocess.CompletedProcess[str]:
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"}
    return subprocess.run(  # noqa: S603 (git e gh, com argumentos montados aqui)
        args, cwd=cwd, capture_output=True, text=True, timeout=espera, check=False, env=ambiente
    )


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _rodar(["/usr/bin/git", *args], cwd)


def titulo(commits: list[str], quando: float) -> str:
    """O assunto do commit, se for um só; senão, quantas melhorias e o dia."""
    if len(commits) == 1:
        return commits[0].split(" ", 1)[-1][:100]
    dia = time.strftime("%d/%m", time.localtime(quando))
    return f"Melhorias do autodesenvolvimento: {len(commits)} mudanças ({dia})"


def corpo(commits: list[str], resumo: str, protegidos: list[str]) -> str:
    linhas = [
        "Proposto pelo **autodesenvolvimento do Zé**: as melhorias feitas numa cópia isolada, por "
        "pedido de quem usa.",
        "",
        "## Commits",
        *(f"- {c}" for c in commits),
        "",
        "## Arquivos",
        "```",
        resumo.strip()[-3000:],
        "```",
        "",
        "## Antes de publicar, o Zé conferiu",
        "- `make check` na cópia: passou.",
        "- Dados pessoais: nenhum número ou nome da agenda do WhatsApp, chave, token ou caminho "
        "da máquina nas linhas novas nem nas mensagens dos commits.",
    ]
    if protegidos:
        linhas += [
            "",
            "## Zona protegida",
            "Estas mudanças mexem no que decide o que o Zé faz sem perguntar. Revise com atenção:",
            *(f"- `{p}`" for p in protegidos),
        ]
    return "\n".join(linhas)


def propor(
    copia: Path,
    branch: str,
    testar: Callable[[Path], bool],
    protegidos: tuple[str, ...],
    sensiveis: Callable[[], vazamento.Sensiveis] = vazamento.coletar,
    gh: str | None = None,
    agora: Callable[[], float] = time.time,
) -> Resultado:
    """Publica a cópia de melhorias (`branch`, na pasta `copia`) e abre o PR."""
    if not _PROPONDO.acquire(blocking=False):
        return Resultado(False, "Já estou propondo estas melhorias. Aguarde o resultado.")
    try:
        return _propor(copia, branch, testar, protegidos, sensiveis, gh, agora)
    finally:
        _PROPONDO.release()


def enviar(copia: Path, gh: str, *args: str) -> subprocess.CompletedProcess[str]:
    """`git push origin` com o login do GitHub pelo `gh` desta máquina, mesmo que a
    configuração do git aponte outro. Sem os hooks do repositório: eles rodariam aqui, fora do
    isolamento da sessão."""
    ajudante = f"!{gh} auth git-credential"
    return _git(
        copia,
        "-c", "core.hooksPath=/dev/null",
        "-c", "credential.https://github.com.helper=",
        "-c", f"credential.https://github.com.helper={ajudante}",
        "push", "--quiet", "origin", *args,
    )  # fmt: skip


def _pr_aberto(copia: Path, gh: str, branch: str) -> str:
    """O endereço de um PR aberto que já leva exatamente estes commits, ou vazio."""
    ponta = _git(copia, "rev-parse", branch).stdout.strip()
    lista = _rodar([gh, "pr", "list", "--state", "open", "--json", "url,headRefOid"], copia)
    try:
        abertos = json.loads(lista.stdout) if lista.returncode == 0 else []
    except ValueError:
        return ""
    return next((p["url"] for p in abertos if ponta and p.get("headRefOid") == ponta), "")


def _propor(
    copia: Path,
    branch: str,
    testar: Callable[[Path], bool],
    protegidos: tuple[str, ...],
    sensiveis: Callable[[], vazamento.Sensiveis],
    gh: str | None,
    agora: Callable[[], float],
) -> Resultado:
    if _git(copia, "status", "--porcelain").stdout.strip():
        return Resultado(False, "A cópia tem alterações sem commit. Peça para a sessão concluir.")
    if _git(copia, "fetch", "--quiet", "origin").returncode != 0:
        return Resultado(False, "Sem conexão com o GitHub agora. Tente de novo daqui a pouco.")
    base = _git(copia, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").stdout.strip()
    base = base or "origin/master"
    commits = _git(copia, "log", "--reverse", "--format=%h %s", f"{base}..{branch}").stdout
    lista = [c for c in commits.splitlines() if c.strip()]
    if not lista:
        return Resultado(False, "Não há nada novo para propor: o GitHub já tem tudo da cópia.")
    gh = gh if gh is not None else achar_gh()
    if not gh:
        return Resultado(False, "O GitHub não está conectado nesta máquina (falta o gh).")
    if aberto := _pr_aberto(copia, gh, branch):
        numero = aberto.rsplit("/", 1)[-1]
        return Resultado(True, f"O PR {numero} já tem estas melhorias.", aberto)
    if not testar(copia):
        return Resultado(
            False, "Não publiquei: os testes falharam na cópia. Peça para a sessão corrigir."
        )
    diff = _git(copia, "diff", "--unified=0", "--no-color", f"{base}...{branch}").stdout
    mensagens = _git(copia, "log", "--format=%B", f"{base}..{branch}").stdout
    achados = vazamento.conferir(diff, mensagens, sensiveis())
    if achados:
        lugares = "; ".join(str(a) for a in achados[:5])
        mais = f" e mais {len(achados) - 5}" if len(achados) > 5 else ""
        return Resultado(
            False,
            f"Não publiquei: a mudança leva dados seus ({lugares}{mais}). Peça para a sessão "
            "trocar por dados de exemplo.",
        )
    nome = f"ze/melhoria-{time.strftime('%Y%m%d-%H%M%S', time.localtime(agora()))}"
    envio = enviar(copia, gh, f"{branch}:refs/heads/{nome}")
    if envio.returncode != 0:
        return Resultado(
            False, "Não consegui enviar a branch ao GitHub. Confira o login do GitHub."
        )
    arquivos = list(vazamento.arquivos_novos(diff))
    tocados = [p for p in protegidos if any(a.startswith(p) for a in arquivos)]
    resumo = _git(copia, "diff", "--stat", f"{base}...{branch}").stdout
    pr = _rodar(
        [
            gh, "pr", "create",
            "--base", base.removeprefix("origin/"),
            "--head", nome,
            "--title", titulo(lista, agora()),
            "--body", corpo(lista, resumo, tocados),
        ],
        copia,
    )  # fmt: skip
    endereco = next(iter(re.findall(r"https://\S+/pull/\d+", pr.stdout)), "")
    if pr.returncode != 0 or not endereco:
        with contextlib.suppress(Exception):  # a branch sem PR não fica para trás
            enviar(copia, gh, "--delete", nome)
        return Resultado(False, "Enviei a branch, mas o GitHub não abriu o PR. Tente de novo.")
    numero = endereco.rsplit("/", 1)[-1]
    return Resultado(True, f"Abri o PR {numero} no GitHub, com {len(lista)} melhoria(s).", endereco)
