"""Uma identidade de autodesenvolvimento por projeto, com unificação recuperável.

As origens ficam intactas. Índices temporários fotografam rascunhos; merge-tree verifica
conflitos antes de tocar a central. O histórico só é arquivado depois da publicação Git.
"""

import os
import re
import subprocess
import tempfile
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from zervis import atividade
from zervis.oficina.sessoes import (
    Sessao,
    SessaoErro,
    Sessoes,
    _git_preservar_ignorados,
    _git_sem_operacao,
)

COLECAO = "autodesenvolvimento"


class Central:
    def __init__(self, sessoes: Sessoes, repo: Path, pasta: Path) -> None:
        self.sessoes = sessoes
        self.repo = repo.resolve()
        self.pasta = pasta / "centralizacao"
        self.chave = str(self.repo)

    def registro(self) -> dict[str, Any]:
        return self.sessoes._dados.ler(COLECAO, self.chave) or {}

    def _gravar(self, **campos: Any) -> None:
        with self.sessoes._dados.banco.transacao():
            self.sessoes._dados.guardar(COLECAO, {**self.registro(), **campos}, self.chave)

    def candidatas(self) -> list[Sessao]:
        return [
            s
            for s in self.sessoes.listar()
            if s.origem == "manutencao"
            and Path(s.pasta).resolve() == self.repo
            and not self.sessoes.arquivada_em(s.id)
        ]

    def _validar(self, s: Sessao) -> None:
        if (
            s.origem != "manutencao"
            or Path(s.pasta).resolve() != self.repo
            or self.sessoes.arquivada_em(s.id)
            or not s.worktree
            or not s.onde.is_dir()
        ):
            raise SessaoErro("A cópia central está indisponível. Restaure-a antes de continuar.")

    def _exigir_repositorio(self) -> None:
        """O autodesenvolvimento vive numa cópia Git do código. Um Zé instalado de um pacote, sem o
        `.git`, dava "não foi possível unificar pelo Git" sem dizer o que fazer (VPS, 16/10)."""
        try:
            feito = subprocess.run(  # noqa: S603 (Git local, sem shell; argumentos internos)
                ["/usr/bin/git", "-C", str(self.repo), "rev-parse", "--verify", "-q", "HEAD"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise SessaoErro("Não foi possível verificar o Git.") from None
        if feito.returncode:
            raise SessaoErro(
                "Esta instalação não tem histórico Git. "
                "Rode deploy/instalar-servidor.sh de novo para ativar o autodesenvolvimento."
            )

    def resolver(self, preferida: str, agente: str) -> str:
        # O vínculo fica no mesmo banco das sessões, além do estado volátil da manutenção.
        # A transação impede dois painéis de escolherem/criarem centrais diferentes.
        with self.sessoes._operacoes, self.sessoes._dados.banco.transacao():
            registro = self.registro()
            id_ = str(registro.get("sessao") or preferida)
            if id_:
                try:
                    atual = self.sessoes.ler(id_)
                except SessaoErro:
                    if registro.get("sessao"):
                        raise SessaoErro(
                            "A sessão central está ausente. Restaure seu registro."
                        ) from None
                else:
                    self._validar(atual)
                    if registro.get("sessao") != atual.id:
                        self._gravar(sessao=atual.id)
                    return atual.id
            candidatas = self.candidatas()
            if not candidatas:
                self._exigir_repositorio()
            if len(candidatas) > 1:
                raise SessaoErro(
                    "Escolha a sessão central em Autodesenvolvimento e unifique as cópias."
                )
            if candidatas:
                atual = candidatas[0]
                self._validar(atual)
            elif preferida:
                raise SessaoErro("A sessão anterior está ausente. Restaure-a antes de continuar.")
            else:
                comuns = {
                    Path(s.worktree).resolve()
                    for s in self.sessoes.listar()
                    if s.origem != "manutencao" and s.worktree
                }
                for linha in self._git(self.repo, "worktree", "list", "--porcelain").splitlines():
                    if not linha.startswith("worktree "):
                        continue
                    pasta = Path(linha.removeprefix("worktree ")).resolve()
                    if (
                        pasta.name == "copia"
                        and pasta not in comuns
                        and pasta.parent.parent == self.sessoes.pasta.resolve()
                        and re.fullmatch(r"[0-9a-f]{8}", pasta.parent.name)
                    ):
                        raise SessaoErro(
                            "Há uma cópia anterior sem registro. Restaure-a antes de continuar."
                        )
                atual = self.sessoes.criar(
                    "Zé · autodesenvolvimento",
                    str(self.repo),
                    motor=agente,
                    origem="manutencao",
                    isolada=True,
                )
            self._gravar(sessao=atual.id)
            return atual.id

    def situacao(self, preferida: str = "") -> dict[str, Any]:
        registro = self.registro()
        candidatas = self.candidatas()
        id_ = str(registro.get("sessao") or preferida)
        if not id_ and len(candidatas) == 1:
            id_ = candidatas[0].id
        estado = registro.get("estado", "disponivel")
        aviso = registro.get("aviso", "")
        if self.em_andamento():
            estado = "em_andamento"
        elif estado == "em_andamento":
            estado, aviso = "interrompida", "Unificação interrompida. Tente novamente."
        return {
            "sessao": id_,
            "estado": estado,
            "aviso": aviso,
            "candidatas": [
                {"id": s.id, "motor": s.motor, "conta": s.conta, "branch": s.branch}
                for s in candidatas
            ],
            "arquivadas": list(registro.get("arquivadas", [])),
        }

    def iniciar(self, principal: str, preferida: str, agente: str) -> str:
        with self.sessoes._operacoes:
            if self.em_andamento():
                raise SessaoErro("A unificação já está em andamento.")
            self.sessoes._exigir_disponivel()
            registro = self.registro()
            vinculada = str(registro.get("sessao") or preferida)
            if vinculada and principal and vinculada != principal:
                raise SessaoErro("A sessão central já está definida.")
            id_ = self.resolver(vinculada or principal, agente)
            candidatas = self.candidatas()
            if len(candidatas) < 2:
                return "As sessões já estão centralizadas."
            for s in candidatas:
                self.sessoes._consumir_eventos(s.id)
            if any(s.id in self.sessoes.trabalhando() for s in candidatas):
                raise SessaoErro("Aguarde os trabalhos terminarem antes de unificar.")
            central = self.sessoes.ler(id_)
            self._validar_git(central)
            if self._git(central.onde, "status", "--porcelain", "--untracked-files=all"):
                raise SessaoErro(
                    "Conclua as alterações sem commit da sessão central antes de unificar."
                )
            ids = {s.id for s in candidatas}
            self.sessoes._centralizando.update(ids)
            try:
                self._gravar(estado="em_andamento", aviso="Unificando sessões.")
                atividade.PADRAO.registrar(
                    "execucao",
                    "Iniciou a unificação de autodesenvolvimento",
                    origem="painel",
                    autorizacao="confirmada",
                    sessao=id_,
                )
                threading.Thread(
                    target=self._executar,
                    args=(id_, ids),
                    name="unificar-sessoes",
                    daemon=True,
                ).start()
            except Exception:
                self.sessoes._centralizando.difference_update(ids)
                raise
            return "Unificação iniciada. Acompanhe no painel."

    def em_andamento(self) -> bool:
        # O registro em disco pode ter ficado em andamento após uma queda; o conjunto é do
        # processo dono. Nesse caso, a operação pode ser refeita com as origens preservadas.
        return any(s.id in self.sessoes._centralizando for s in self.candidatas())

    def _git(
        self,
        pasta: Path,
        *args: str,
        entrada: str | None = None,
        ambiente: dict[str, str] | None = None,
    ) -> str:
        try:
            feito = subprocess.run(  # noqa: S603 (Git local, sem shell; argumentos internos)
                ["/usr/bin/git", "-C", str(pasta), *args],
                input=entrada,
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise SessaoErro(
                "Não foi possível verificar o Git. As cópias foram preservadas."
            ) from None
        if feito.returncode:
            if args[0] == "merge-tree":
                raise SessaoErro(
                    "Há conflitos entre as cópias. Resolva-os na sessão central e tente novamente."
                )
            raise SessaoErro("Não foi possível unificar pelo Git. As cópias foram preservadas.")
        return feito.stdout.strip()

    def _validar_git(self, s: Sessao) -> None:
        if not s.onde.is_dir():
            raise SessaoErro("Uma cópia está ausente. Restaure-a antes de unificar.")
        raiz = self._git(s.onde, "rev-parse", "--show-toplevel")
        comum = self._git(s.onde, "rev-parse", "--path-format=absolute", "--git-common-dir")
        esperado = self._git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if (
            Path(raiz).resolve() != s.onde.resolve()
            or comum != esperado
            or (s.branch and self._git(s.onde, "branch", "--show-current") != s.branch)
        ):
            raise SessaoErro("Uma cópia não corresponde ao projeto e à branch registrados.")
        _git_sem_operacao(s.onde)

    def _fotografar(self, s: Sessao, indice: Path) -> tuple[str, str]:
        self._validar_git(s)
        ambiente = {**os.environ, "GIT_INDEX_FILE": str(indice)}
        head = self._git(s.onde, "rev-parse", "HEAD")
        self._git(s.onde, "read-tree", head, ambiente=ambiente)
        self._git(s.onde, "add", "-A", ambiente=ambiente)
        arvore = self._git(s.onde, "write-tree", ambiente=ambiente)
        if arvore == self._git(s.onde, "rev-parse", f"{head}^{{tree}}"):
            return head, arvore
        # Uma nova data de commit não torna o rascunho diferente. Reutiliza a fotografia,
        # preferindo aquela já reconciliada no histórico da central. Caso contrário, uma
        # resolução manual voltava como conflito a cada tentativa de unificar.
        referencias = self._git(
            self.repo,
            "for-each-ref",
            "--format=%(objectname) %(tree) %(parent)",
            f"refs/zervis/arquivo/*/{s.id}",
        )
        fotos = [
            campos[0]
            for linha in referencias.splitlines()
            if len(campos := linha.split()) == 3 and campos[1:] == [arvore, head]
        ]
        central = str(self.registro().get("sessao", ""))
        if fotos and central:
            destino = self._git(self.sessoes.ler(central).onde, "rev-parse", "HEAD")
            for foto in fotos:
                if not self._git(self.repo, "rev-list", "-1", foto, "--not", destino):
                    return foto, arvore
        if fotos:
            return fotos[0], arvore
        commit = self._commit(arvore, [head], f"Preserva rascunhos da sessão {s.id}")
        return commit, arvore

    def _commit(self, arvore: str, pais: list[str], mensagem: str) -> str:
        argumentos = [
            "-c",
            "user.name=Zérvis",
            "-c",
            "user.email=zervis@localhost",
            "commit-tree",
            arvore,
        ]
        for pai in pais:
            argumentos.extend(("-p", pai))
        return self._git(self.repo, *argumentos, entrada=mensagem + "\n")

    def _executar(self, id_: str, ids: set[str]) -> None:
        try:
            self._unificar(id_, ids)
        except Exception as erro:
            aviso = (
                str(erro)
                if isinstance(erro, SessaoErro)
                else "A unificação foi interrompida. As cópias foram preservadas."
            )
            self._gravar(estado="erro", aviso=aviso)
            atividade.PADRAO.registrar(
                "falha",
                "Unificação de autodesenvolvimento interrompida",
                origem="painel",
            )
        finally:
            self.sessoes._centralizando.difference_update(ids)

    def _unificar(self, id_: str, ids: set[str]) -> None:
        for origem in ids:
            terminal = self.sessoes.terminais.pop(origem, None)
            if terminal is not None:
                terminal.encerrar()
            self.sessoes._consumir_eventos(origem)
        central = self.sessoes.ler(id_)
        origens = [self.sessoes.ler(i) for i in sorted(ids - {id_})]
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        rodada = uuid.uuid4().hex
        self.sessoes._dados.banco.backup(self.pasta / f"{rodada}.db")
        antes = self._git(central.onde, "rev-parse", "HEAD")
        resultado = antes
        arvores: dict[str, str] = {}
        preservadas: dict[str, dict[str, str]] = {}
        with tempfile.TemporaryDirectory(dir=self.pasta) as temporaria:
            for s in origens:
                foto, arvore = self._fotografar(s, Path(temporaria) / s.id)
                arvores[s.id] = arvore
                referencia = f"refs/zervis/arquivo/{rodada}/{s.id}"
                self._git(self.repo, "update-ref", referencia, foto)
                preservadas[s.id] = {"referencia": referencia, "commit": foto}
                self._gravar(origens=preservadas)
                # merge-tree só escreve objetos. Conflito não altera nenhuma pasta ou índice.
                arvore_final = self._git(
                    self.repo, "merge-tree", "--write-tree", resultado, foto
                ).splitlines()[0]
                if arvore_final != self._git(self.repo, "rev-parse", f"{resultado}^{{tree}}"):
                    resultado = self._commit(
                        arvore_final,
                        [resultado, foto],
                        f"Unifica a sessão {s.id} no autodesenvolvimento",
                    )
            for s in origens:
                _, arvore_atual = self._fotografar(s, Path(temporaria) / f"conferir-{s.id}")
                if arvore_atual != arvores[s.id]:
                    raise SessaoErro("Uma cópia mudou durante a unificação. Tente novamente.")
        self._validar_git(central)
        if self._git(central.onde, "rev-parse", "HEAD") != antes or self._git(
            central.onde, "status", "--porcelain", "--untracked-files=all"
        ):
            raise SessaoErro("A sessão central mudou durante a unificação. Tente novamente.")
        _git_preservar_ignorados(central.onde, resultado)
        self._gravar(preparado=resultado, anterior=antes)
        self._git(central.onde, "merge", "--ff-only", "--no-edit", resultado)
        # A importação é transacional e tem chaves estáveis. Repetir após queda não duplica
        # mensagens nem confunde as conversas nativas de contas e agentes diferentes.
        with self.sessoes._dados.banco.transacao():
            for s in origens:
                for numero, mensagem in enumerate(self.sessoes.mensagens(s.id)):
                    self.sessoes._dados.guardar(
                        "mensagens-" + id_,
                        {**mensagem, "origem_sessao": s.id},
                        f"unificada:{s.id}:{numero}",
                    )
                self.sessoes._dados.guardar(
                    "contexto-central-" + id_,
                    {
                        "sessao": s.id,
                        "motor": s.motor,
                        "pedido": s.ultimo_pedido,
                        "resumo": s.resumo,
                        "interrompida": s.interrompida,
                    },
                    s.id,
                )
                self.sessoes._dados.guardar("autodesenvolvimento-arquivos", {"central": id_}, s.id)
            atual = self.sessoes.ler(id_)
            self.sessoes._gravar(replace(atual, passagem=self.sessoes.passagem(atual, atual.motor)))
            arquivadas = sorted(set(self.registro().get("arquivadas", [])) | (ids - {id_}))
            self._gravar(
                estado="concluida",
                aviso="Sessões unificadas. Histórico preservado.",
                arquivadas=arquivadas,
            )
        atividade.PADRAO.registrar(
            "execucao",
            "Unificou as sessões de autodesenvolvimento",
            autorizacao="painel",
            origem="painel",
            sessao=id_,
        )
