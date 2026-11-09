"""A cópia isolada de uma sessão (ADR 0026) e o fim dela: aplicar, descartar, encerrar o agente
e excluir a sessão sem perder trabalho.
Funções da classe `Sessoes`, tiradas de `sessoes.py`; a classe repassa a chamada."""

import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zervis.oficina import sessoes as ses

if TYPE_CHECKING:
    from zervis.oficina.sessoes import Sessoes


def exigir_editavel(n: "Sessoes", id_: str) -> None:
    s = n.ler(id_)
    if id_ in n._centralizando:
        raise ses.SessaoErro("Unificação em andamento. Aguarde a conclusão.")
    central = n.arquivada_em(id_)
    if s.origem == "manutencao":
        registro = n._dados.ler("autodesenvolvimento", str(Path(s.pasta).resolve())) or {}
        central = central or str(registro.get("sessao", ""))
        if (
            not central
            and sum(
                outra.origem == "manutencao"
                and Path(outra.pasta).resolve() == Path(s.pasta).resolve()
                and not n.arquivada_em(outra.id)
                for outra in n.listar()
            )
            > 1
        ):
            raise ses.SessaoErro("Escolha a sessão central em Autodesenvolvimento antes de enviar.")
    if central and central != id_:
        raise ses.SessaoErro(
            "Esta sessão foi substituída. Abra a sessão central em Autodesenvolvimento."
        )


def _encerrar_agente(n: "Sessoes", id_: str, espera_s: float = 5.0) -> None:
    if (terminal := n.terminais.get(id_)) is not None:
        try:
            terminal.encerrar(espera_s)
        except (OSError, TimeoutError):
            raise ses.SessaoErro(
                "Não foi possível encerrar o agente. A sessão foi preservada."
            ) from None
    laco_tarefa = n.tarefas.get(id_)
    if laco_tarefa is None or laco_tarefa[1].done():
        return
    laco, tarefa = laco_tarefa
    encerrada = threading.Event()

    def cancelar() -> None:
        tarefa.add_done_callback(lambda _: encerrada.set())
        tarefa.cancel()

    try:
        laco.call_soon_threadsafe(cancelar)
    except RuntimeError:
        if tarefa.done():
            return
        raise ses.SessaoErro(
            "Não foi possível encerrar o agente. A sessão foi preservada."
        ) from None
    if not encerrada.wait(espera_s):
        raise ses.SessaoErro("O agente ainda está encerrando. Tente excluir novamente.")


def _excluir(n: "Sessoes", id_: str) -> str:
    n.fallback.cancelar(id_)
    s = n.ler(id_)
    n.exigir_editavel(id_)
    if s.origem == "manutencao":
        registro = n._dados.ler("autodesenvolvimento", str(Path(s.pasta).resolve())) or {}
        if registro.get("sessao") == id_:
            raise ses.SessaoErro("A sessão central de autodesenvolvimento deve ser preservada.")
    # Espera o cancelamento e os callbacks antes de conferir o Git e remover os arquivos.
    n._encerrar_agente(id_)
    if s.worktree and Path(s.worktree).exists():
        # Os atalhos `zervis-*` das skills são do próprio Zé, não trabalho: saem antes da
        # conferência (26/10/2026: só eles, ignorados pelo Git, travavam a exclusão).
        ses.ligar_skills_no_projeto(Path(s.worktree), None)
        estado = ses._git(
            Path(s.worktree), "status", "--porcelain", "--untracked-files=all", "--ignored"
        )
        if estado.returncode != 0:
            raise ses.SessaoErro("Não foi possível verificar a cópia isolada.")
        if estado.stdout.strip():
            raise ses.SessaoErro(
                "A cópia isolada tem alterações. Preserve o trabalho antes de excluir."
            )
    aviso = ""
    if s.worktree:
        if Path(s.worktree).exists():
            # O próprio git verifica novamente alterações feitas depois da consulta acima.
            feito = ses._git(Path(s.pasta), "worktree", "remove", s.worktree)
            if feito.returncode != 0:
                raise ses.SessaoErro(
                    "Não foi possível remover a cópia isolada. A sessão foi preservada."
                )
        aviso = f"A branch {s.branch} continua no projeto."
    try:
        with n.trava:
            shutil.rmtree(n._dir(id_))
    except OSError:
        raise ses.SessaoErro("Não foi possível excluir os arquivos da sessão.") from None
    with n._dados.banco.transacao():
        n._dados.remover("sessoes", id_)
        n._dados.remover("mensagens-" + id_)
        n._dados.remover(ses.LIDOS, id_)
    n.terminais.pop(id_, None)
    n.tarefas.pop(id_, None)
    n._lidos.pop(id_, None)
    n._limite_visto.discard(id_)
    n._saida_limite.pop(id_, None)
    if n.em_foco[0] == id_:
        n.em_foco = ("", 0.0)
    return aviso


def _copia(n: "Sessoes", s: ses.Sessao) -> dict[str, Any]:
    if not s.worktree:
        return {"copia": False}
    onde = Path(s.worktree)
    if not onde.is_dir() or not s.base:
        raise ses.SessaoErro("A cópia isolada está indisponível.")
    raiz = ses._git_verificado(onde, "rev-parse", "--show-toplevel").strip()
    if Path(raiz).resolve() != onde.resolve():
        raise ses.SessaoErro("A pasta da cópia não corresponde ao repositório Git.")
    if ses._git_verificado(onde, "branch", "--show-current").strip() != s.branch:
        raise ses.SessaoErro("A cópia está em outra branch. Volte à branch da sessão.")
    commits = ses._git_verificado(onde, "log", "--oneline", f"{s.base}..HEAD").splitlines()
    arquivos = ses._git_verificado(onde, "diff", "--name-only", "-z", s.base).split("\0")
    novos = ses._git_verificado(onde, "ls-files", "--others", "--exclude-standard", "-z")
    return {
        "copia": True,
        "branch": s.branch,
        "commits": commits,
        "arquivos": sorted({a for a in [*arquivos, *novos.split("\0")] if a}),
        "sem_commit": bool(
            ses._git_verificado(onde, "status", "--porcelain", "--untracked-files=all").strip()
        ),
        "ignorados_preservados": bool(
            ses._git_verificado(onde, "ls-files", "--others", "--ignored", "--exclude-standard")
        ),
        "resumo": ses._git_verificado(onde, "diff", "--stat", s.base).strip()[:2000],
    }


def _copia_parada(n: "Sessoes", id_: str) -> ses.Sessao:
    n._consumir_eventos(id_)  # o pedido no terminal pode ter chegado antes do próximo tick
    s = n.ler(id_)
    if s.origem == "manutencao":
        raise ses.SessaoErro("Use Autodesenvolvimento para alterar esta cópia.")
    if id_ in n.trabalhando():
        raise ses.SessaoErro("Essa sessão está trabalhando. Espere ela terminar.")
    if not n._copia(s)["copia"]:
        raise ses.SessaoErro("Esta sessão não tem cópia isolada.")
    ses._git_sem_operacao(Path(s.pasta))
    ses._git_sem_operacao(Path(s.worktree))
    projeto = Path(s.pasta).resolve()
    for trabalhando in n.trabalhando():
        if trabalhando != id_ and n.ler(trabalhando).onde.resolve() == projeto:
            raise ses.SessaoErro("Há uma sessão trabalhando no projeto. Espere ela terminar.")
    return s


def aplicar_copia(n: "Sessoes", id_: str) -> str:
    """A aprovação junta commits; fecha o agente ocioso antes de mudar as duas pastas."""
    with n._operacoes:
        s = n._copia_parada(id_)
        n._encerrar_agente(id_)
        c = n._copia(s)
        if not c["commits"]:
            raise ses.SessaoErro("Não há commits na cópia para aplicar.")
        if c["sem_commit"]:
            raise ses.SessaoErro(
                "A cópia tem alterações sem commit. Faça o commit antes de aplicar."
            )
        projeto, onde = Path(s.pasta), Path(s.worktree)
        if ses._git_verificado(projeto, "status", "--porcelain", "--untracked-files=all").strip():
            raise ses.SessaoErro("O projeto tem alterações locais. Preserve-as antes de aplicar.")
        alvo = ses._git_verificado(onde, "rev-parse", "--verify", "HEAD").strip()
        atual = ses._git_verificado(projeto, "rev-parse", "--verify", "HEAD").strip()
        ses._git_preservar_ignorados(projeto, alvo)
        ses._git_preservar_ignorados(onde, atual)
        if ses._git_resultado(
            projeto, "merge", "--ff-only", "--no-overwrite-ignore", alvo
        ).returncode:
            junta = ses._git_resultado(
                projeto,
                "merge",
                "--no-ff",
                "--no-overwrite-ignore",
                "-m",
                f"Sessão {s.nome} ({s.branch})",
                alvo,
            )
            if junta.returncode:
                merge_head = ses._git_verificado(
                    projeto, "rev-parse", "--git-path", "MERGE_HEAD"
                ).strip()
                if (projeto / merge_head).exists():
                    ses._git_verificado(projeto, "merge", "--abort")
                    raise ses.SessaoErro(
                        "Há conflito ao aplicar. Atualize a cópia antes de tentar novamente."
                    )
                raise ses.SessaoErro("Não foi possível aplicar as mudanças pelo Git.")
        novo = ses._git_verificado(projeto, "rev-parse", "--verify", "HEAD").strip()
        try:
            ses._git_preservar_ignorados(onde, novo)
            ses._git_verificado(onde, "merge", "--ff-only", "--no-overwrite-ignore", novo)
        except ses.SessaoErro:
            n.anotar(
                id_,
                "sistema",
                "Mudanças aplicadas no projeto; sincronização da cópia pendente.",
            )
            raise ses.SessaoErro(
                "Mudanças aplicadas no projeto. Falhou a atualização da cópia."
            ) from None
        n._mudar(id_, base=novo)
        n.anotar(id_, "sistema", f"Juntei ao projeto {len(c['commits'])} commit(s).")
        return "Mudanças juntadas ao projeto."


def descartar_copia(n: "Sessoes", id_: str) -> str:
    """Descarta só na cópia; arquivos ignorados são preservados, inclusive em colisões."""
    with n._operacoes:
        s = n._copia_parada(id_)
        n._encerrar_agente(id_)
        onde = Path(s.worktree)
        atual = ses._git_verificado(Path(s.pasta), "rev-parse", "--verify", "HEAD").strip()
        ses._git_preservar_ignorados(onde, atual)
        ses._git_verificado(onde, "reset", "--hard", atual)
        ses._git_verificado(onde, "clean", "-fd")  # sem -x: arquivos ignorados não são apagados
        if ses._git_verificado(onde, "status", "--porcelain", "--untracked-files=all").strip():
            raise ses.SessaoErro("O descarte não foi concluído. Confira as alterações da cópia.")
        if ses._git_verificado(onde, "rev-parse", "--verify", "HEAD").strip() != atual:
            raise ses.SessaoErro("O descarte não foi concluído. Confira a versão da cópia.")
        n._mudar(id_, base=atual)
        n.anotar(id_, "sistema", "Descartei as mudanças da cópia; arquivos ignorados preservados.")
        return "Mudanças descartadas."
