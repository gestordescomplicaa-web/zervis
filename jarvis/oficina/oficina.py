"""A oficina (ADR 0006): o JARVIS delega trabalho de código ao Orca pela orquestração nativa.

O `jarvisd` é o coordenador de um Run só ("JARVIS por voz"), guardado no estado e recriado se o
Orca o perder. Cada delegação é um `worker-start` num projeto que já existe no Orca, com um
terminal novo. Os agentes rodam como o usuário usa no Orca (modo livre, decisão de 06/10/2026):
a aprovação falada acontece antes, na hora de delegar.

A caixa do Run é lida pelo monitor (`jarvis/oficina/monitor.py`); aqui ficam só as operações.

**Posto:** o Orca identifica o remetente de um comando de orquestração pelo terminal de onde ele
vem, e o `jarvisd` (systemd) não tem terminal: sem isso, `no_active_sender_terminal`. Então o
JARVIS mantém um terminal próprio no Orca, neste projeto, mostrando o log dele, e usa o handle
como `--from`/`--terminal`. Se o posto sumir (Orca reiniciado), nasce outro com um Run novo.
"""

import json
import logging
import re
import subprocess
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.oficina.orca import Orca, OrcaErro

log = logging.getLogger(__name__)
AGENTES = {"claude": "Claude", "codex": "Codex"}
PROJETO_JARVIS = Path(__file__).resolve().parents[2]
COMANDO_POSTO = "journalctl --user -fu zervis -o cat"
OBJETIVO = "JARVIS por voz: tarefas delegadas pelo usuário"
# Teste de 06/10/2026: a tarefa dizia "não execute comandos" e o agente não mandou o worker_done
# (que é um comando); o usuário nunca soube que terminou. Vai em toda tarefa, depois do texto.
RODAPE = (
    "\n\nAo terminar, envie o worker_done como o preâmbulo do Orca manda, com outcome "
    "succeeded ou failed e um resumo curto em português. Isso é obrigatório e nunca conta como "
    "um comando proibido por esta tarefa."
)
STATUS = {
    "a fazer": "todo",
    "em andamento": "in-progress",
    "em revisão": "in-review",
    "concluído": "completed",
}
NOME_VALIDO = re.compile(r"[\w][\w \-]{0,59}")


# Telas de aprovação do Codex 0.159 e do Claude Code (portado de VIBE-CODING/jarvis/agents.py):
# com uma delas aberta, texto + Enter responderia à pergunta em vez de chegar ao agente.
MARCAS_APROVACAO = (
    "would you like to run the following command",
    "would you like to make the following edits",
    "would you like to grant these permissions",
    "do you want to proceed",
    "do you want to make this edit",
    "do you want to create",
    "don't ask again",
    "hooks need review",
    "bypass permissions mode",
)


def pasta_de(nome: str) -> str:
    """Nome falado -> nome de pasta: "Loja Virtual" -> "loja-virtual"."""
    sem_acento = unicodedata.normalize("NFKD", nome.casefold())
    simples = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", simples).strip("-")


def _chave(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in sem_acento if c.isalnum())


@dataclass(frozen=True)
class Projeto:
    nome: str
    caminho: str
    agentes: tuple[str, ...]  # "codex: working", ...


@dataclass(frozen=True)
class Mensagem:
    id: str
    tipo: str  # worker_done, question, escalation, ...
    assunto: str
    corpo: str
    dados: dict[str, Any]


class Oficina:
    def __init__(self, estado: Path, orca: Orca | None = None, raiz: Path | None = None) -> None:
        self.estado = estado
        self.raiz = raiz or Path.home() / "projetos"
        self.orca = orca or Orca()
        self.tarefas: dict[str, dict[str, str]] = {}  # dispatch -> agente, projeto, tarefa
        # Quem quer saber do que muda (o Foco anota as frentes): (o que houve, detalhes).
        self.ao_mudar: Callable[[str, dict[str, str]], None] | None = None
        self._carregar()

    # --- estado (Run e tarefas em curso sobrevivem a reinícios) -----------------------------

    def _carregar(self) -> None:
        try:
            dados = json.loads(self.estado.read_text())
        except (OSError, ValueError):
            dados = {}
        self.run: str | None = dados.get("run")
        self.posto: str | None = dados.get("posto")
        self.tarefas = dados.get("tarefas") or {}

    def _gravar(self) -> None:
        temporario = self.estado.with_suffix(".next")
        temporario.write_text(
            json.dumps({"run": self.run, "posto": self.posto, "tarefas": self.tarefas})
        )
        temporario.chmod(0o600)
        temporario.replace(self.estado)

    def garantir_posto(self) -> str:
        vivos = self.orca.chamar("terminal", "list", "--worktree", f"path:{PROJETO_JARVIS}")
        handles = {t.get("handle") for t in vivos.get("terminals", [])}
        if self.posto is None or self.posto not in handles:
            criado = self.orca.chamar(
                "terminal", "create",
                "--worktree", f"path:{PROJETO_JARVIS}",
                "--title", "JARVIS · oficina",
                "--command", COMANDO_POSTO,
            )  # fmt: skip
            terminal = criado.get("terminal") or {}
            self.posto = str(terminal.get("handle") or criado.get("handle") or "")
            if not self.posto:
                raise OrcaErro("não consegui abrir o terminal do JARVIS no Orca")
            log.info("oficina: posto %s criado; Run novo", self.posto)
            self.run = None  # o Run pertence à caixa do posto antigo
            self._gravar()
        return self.posto

    def garantir_run(self) -> str:
        posto = self.garantir_posto()
        if self.run is None:
            criado = self.orca.chamar(
                "orchestration", "run-create", "--objective", OBJETIVO, "--from", posto
            )
            self.run = str(criado["run"]["id"])
            log.info("oficina: Run %s criado", self.run)
            self._gravar()
        return self.run

    # --- operações do cérebro -----------------------------------------------------------------

    def projetos(self) -> list[Projeto]:
        resultado = self.orca.chamar("worktree", "ps", "--limit", "200", limite_s=25)
        projetos = []
        for w in resultado.get("worktrees", []):
            if w.get("isArchived") or not w.get("path"):
                continue
            agentes = tuple(
                f"{a.get('agentType', '?')}: {a.get('state') or a.get('status') or '?'}"
                for a in w.get("agents", [])
            )
            projetos.append(
                Projeto(str(w.get("displayName") or w["path"]), str(w["path"]), agentes)
            )
        return projetos

    def achar_projeto(self, nome: str) -> Projeto:
        projetos = self.projetos()
        alvo = _chave(nome)
        exatos = [p for p in projetos if _chave(p.nome) == alvo or p.caminho == nome]
        if len(exatos) == 1:
            return exatos[0]
        parecidos = exatos or [p for p in projetos if alvo and alvo in _chave(p.nome + p.caminho)]
        caminhos = {p.caminho for p in parecidos}
        if len(caminhos) == 1:
            return parecidos[0]
        if not parecidos:
            raise OrcaErro(f"não achei o projeto {nome} no Orca")
        nomes = ", ".join(sorted({p.nome for p in parecidos}))
        raise OrcaErro(f"mais de um projeto parece com {nome}: {nomes}")

    def delegar(self, tarefa: str, projeto: str, agente: str) -> dict[str, str]:
        if agente not in AGENTES:
            raise OrcaErro(f"agente desconhecido: {agente}; use claude ou codex")
        alvo = self.achar_projeto(projeto)
        run = self.garantir_run()
        resultado = self.orca.chamar(
            "orchestration", "worker-start",
            "--run", run,
            "--spec", tarefa + RODAPE,
            "--task-title", tarefa[:80],
            "--worktree", "path:" + alvo.caminho,
            "--agent", agente,
            "--from", str(self.posto),
            limite_s=180,
        )  # fmt: skip
        dispatch = str(resultado.get("dispatchId") or "")
        if resultado.get("state") != "ready" or not dispatch:
            etapa = resultado.get("failedStage") or resultado.get("stage") or "?"
            motivo = resultado.get("lastError") or f"etapa {etapa}"
            if dispatch:
                motivo = self._motivo_na_tela(dispatch) or motivo
                self.liberar(dispatch)
            raise OrcaErro(f"o {AGENTES[agente]} não ficou pronto: {motivo}")
        self.tarefas[dispatch] = {"agente": agente, "projeto": alvo.nome, "tarefa": tarefa}
        self._gravar()
        log.info("oficina: %s delegado ao %s em %s", dispatch, agente, alvo.nome)
        self._mudou("delegado", {"projeto": alvo.nome, "tarefa": tarefa, "agente": AGENTES[agente]})
        return {"dispatch": dispatch, "agente": AGENTES[agente], "projeto": alvo.nome}

    # --- projetos: criar e organizar; apagar nunca (decisão de 06/10/2026) -------------------

    def criar_projeto(self, nome: str) -> dict[str, str]:
        nome = nome.strip()
        pasta = pasta_de(nome)
        if not NOME_VALIDO.fullmatch(nome) or not pasta:
            raise OrcaErro("nome de projeto inválido; use letras, números, espaço ou hífen")
        caminho = self.raiz / pasta
        if caminho.exists():
            raise OrcaErro(f"a pasta {pasta} já existe; use o projeto existente")
        caminho.mkdir(parents=True)
        (caminho / "README.md").write_text(f"# {nome}\n")
        for comando in (
            ["git", "init", "-q", "-b", "main"],
            ["git", "add", "README.md"],
            ["git", "commit", "-q", "-m", "Início do projeto"],
        ):
            feito = subprocess.run(  # noqa: S603 (git com argumentos fixos)
                comando, cwd=caminho, capture_output=True, text=True, check=False
            )
            if feito.returncode:
                raise OrcaErro(f"o git falhou ao preparar a pasta {pasta}")
        self.orca.chamar("repo", "add", "--path", str(caminho))
        self.orca.chamar("worktree", "set", "--worktree", f"path:{caminho}", "--display-name", nome)
        log.info("oficina: projeto %s criado em %s", nome, caminho)
        self._mudou("projeto", {"projeto": nome})
        return {"nome": nome, "pasta": str(caminho)}

    def nova_frente(self, projeto: str, nome: str) -> dict[str, str]:
        alvo = self.achar_projeto(projeto)
        ramo = pasta_de(nome)
        if not ramo:
            raise OrcaErro("nome de frente inválido")
        criado = self.orca.chamar(
            "worktree", "create",
            "--repo", f"path:{alvo.caminho}",
            "--name", ramo,
            "--no-parent",
            limite_s=120,
        )  # fmt: skip
        caminho = str((criado.get("worktree") or {}).get("path") or "")
        log.info("oficina: frente %s criada em %s", ramo, alvo.nome)
        return {"projeto": alvo.nome, "frente": ramo, "pasta": caminho}

    def marcar(self, projeto: str, status: str) -> dict[str, str]:
        if status not in STATUS:
            raise OrcaErro(f"status desconhecido: {status}; use {', '.join(STATUS)}")
        alvo = self.achar_projeto(projeto)
        self.orca.chamar(
            "worktree", "set", "--worktree", f"path:{alvo.caminho}",
            "--workspace-status", STATUS[status],
        )  # fmt: skip
        return {"projeto": alvo.nome, "status": status}

    def renomear(self, projeto: str, novo: str) -> dict[str, str]:
        if not NOME_VALIDO.fullmatch(novo.strip()):
            raise OrcaErro("nome inválido; use letras, números, espaço ou hífen")
        alvo = self.achar_projeto(projeto)
        self.orca.chamar(
            "worktree", "set", "--worktree", f"path:{alvo.caminho}", "--display-name", novo.strip()
        )
        return {"antes": alvo.nome, "agora": novo.strip()}

    # --- sessões que já estão abertas -----------------------------------------------------------

    def sessoes(self, projeto: Projeto) -> list[dict[str, str]]:
        vivos = self.orca.chamar("terminal", "list", "--worktree", f"path:{projeto.caminho}")
        return [
            {"handle": str(t["handle"]), "titulo": str(t.get("title") or ""), "agente": str(a)}
            for t in vivos.get("terminals", [])
            if (a := t.get("agentIdentity")) and t.get("handle") != self.posto
        ]

    def mandar_texto(
        self, projeto: str, texto: str, sessao: str = "", agente: str = ""
    ) -> dict[str, str]:
        """Escreve numa sessão de agente já aberta no projeto (não cria agente novo). `agente`
        escolhe pelo tipo exato (claude, codex): um título pode citar o outro agente."""
        alvo = self.achar_projeto(projeto)
        abertas = self.sessoes(alvo)
        if agente:
            abertas = [s for s in abertas if s["agente"] == agente]
        if sessao:
            abertas = [s for s in abertas if _chave(sessao) in _chave(s["titulo"] + s["agente"])]
        if not abertas:
            raise OrcaErro(f"não há sessão de agente aberta no projeto {alvo.nome}")
        if len(abertas) > 1:
            titulos = "; ".join(f"{s['agente']}: {s['titulo']}" for s in abertas)
            raise OrcaErro(f"há mais de uma sessão no projeto {alvo.nome}: {titulos}")
        escolhida = abertas[0]
        tela = self.orca.chamar("terminal", "read", "--terminal", escolhida["handle"], "--screen")
        linhas = " ".join(str(x) for x in (tela.get("terminal") or {}).get("tail", [])).casefold()
        if any(m in linhas for m in MARCAS_APROVACAO):
            raise OrcaErro("a sessão está esperando uma resposta na tela; resolva lá antes")
        linha = " ".join(texto.split())
        # Texto e Enter separados: com --enter o Orca espera ~8 s pela confirmação do agente.
        self.orca.chamar("terminal", "send", "--terminal", escolhida["handle"], "--text", linha)
        self.orca.chamar("terminal", "send", "--terminal", escolhida["handle"], "--text", "\r")
        log.info("oficina: texto enviado à sessão %s em %s", escolhida["agente"], alvo.nome)
        return {"projeto": alvo.nome, "sessao": escolhida["titulo"], "agente": escolhida["agente"]}

    def _motivo_na_tela(self, dispatch: str) -> str | None:
        """O que travou o agente ao abrir, dito de um jeito que o usuário saiba resolver."""
        try:
            tela = " ".join(self.ler_saida(dispatch)).casefold()
        except OrcaErro:
            return None
        if "bypass permissions mode" in tela:
            return (
                "ele está parado no aviso do modo livre do Claude; "
                "aceite esse aviso uma vez no Orca e peça de novo"
            )
        if "hooks need review" in tela:
            return (
                "o Codex está pedindo para revisar os hooks do Orca e da memória; "
                "abra um Codex no Orca, escolha confiar em todos e peça de novo"
            )
        if "sign in" in tela or "log in" in tela or "login" in tela:
            return "o agente está pedindo login; entre na conta dele no Orca e peça de novo"
        return None

    def situacao(self) -> list[dict[str, Any]]:
        if self.run is None:
            return []
        resultado = self.orca.chamar("orchestration", "worker-list", "--run", self.run)
        linhas = []
        for w in resultado.get("workers", []):
            p = w.get("projection") or {}
            dispatch = str(p.get("dispatchId") or "")
            tarefa = self.tarefas.get(dispatch, {})
            linhas.append(
                {
                    "dispatch": dispatch,
                    "agente": AGENTES.get(tarefa.get("agente", ""), "agente"),
                    "projeto": tarefa.get("projeto", ""),
                    "tarefa": tarefa.get("tarefa", ""),
                    "etapa": (p.get("stage") or {}).get("worker"),
                    "resultado": p.get("outcome"),
                    "vivo": (p.get("liveness") or {}).get("verdict"),
                }
            )
        return linhas

    def responder(self, mensagem: str, texto: str) -> None:
        run = self.garantir_run()
        self.orca.chamar(
            "orchestration", "reply", "--id", mensagem, "--body", texto,
            "--run", run, "--from", str(self.posto),
        )  # fmt: skip

    def ler_saida(self, dispatch: str, linhas: int = 40) -> list[str]:
        resultado = self.orca.chamar(
            "orchestration", "worker-read", "--dispatch", dispatch, "--limit", str(linhas)
        )
        return [str(x) for x in (resultado.get("terminal") or {}).get("tail", [])]

    # --- caixa do Run (monitor) ---------------------------------------------------------------

    def caixa(self, espera_ms: int) -> tuple[str | None, list[Mensagem]]:
        """Lote mais antigo ainda não confirmado da caixa do Run (espera até chegar algo)."""
        if self.run is None or self.posto is None:
            return None, []
        resultado = self.orca.chamar(
            "orchestration", "check", "--run", self.run, "--terminal", self.posto,
            "--wait", "--types", "worker_done,escalation,question",
            "--timeout-ms", str(espera_ms),
            limite_s=espera_ms / 1000 + 30,
        )  # fmt: skip
        mensagens = []
        for m in resultado.get("messages") or []:
            try:
                dados = m.get("payload") or {}
                if isinstance(dados, str):
                    dados = json.loads(dados or "{}")
            except ValueError:
                dados = {}
            mensagens.append(
                Mensagem(
                    str(m.get("id")),
                    str(m.get("type")),
                    str(m.get("subject") or ""),
                    str(m.get("body") or ""),
                    dados if isinstance(dados, dict) else {},
                )
            )
        return resultado.get("deliveryId"), mensagens

    def confirmar(self, entrega: str) -> None:
        if self.run is not None and self.posto is not None:
            self.orca.chamar(
                "orchestration", "check", "--run", self.run,
                "--terminal", self.posto, "--ack", entrega,
            )  # fmt: skip

    def liberar(self, dispatch: str) -> None:
        try:
            self.orca.chamar("orchestration", "worker-release", "--dispatch", dispatch)
        except OrcaErro as erro:
            log.warning("oficina: não liberei %s: %s", dispatch, erro)

    def concluir(self, dispatch: str) -> dict[str, str]:
        tarefa = self.tarefas.pop(dispatch, {})
        self._gravar()
        if tarefa:
            self._mudou("concluido", tarefa)
        return tarefa

    def _mudou(self, o_que: str, detalhes: dict[str, str]) -> None:
        if self.ao_mudar is None:
            return
        try:
            self.ao_mudar(o_que, detalhes)
        except Exception:  # quem escuta nunca derruba a oficina
            log.exception("oficina: aviso de mudança falhou")
