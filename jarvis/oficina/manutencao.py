"""O modo manutenção: o Zé encaminha os pedidos do usuário a uma sessão de código nele mesmo.

"Entra no modo manutenção" liga; daí em diante, o que não for comando local vai como texto para
uma sessão própria do Zé (`jarvis/oficina/sessoes.py`, ADR 0015) aberta no repositório dele, com o
contexto do momento. O Zé cria essa sessão na primeira vez e a reaproveita depois (a conversa do
agente continua). O agente trabalha como sempre (testes, janela real, commit) e, ao terminar,
grava o Resumo falado num arquivo combinado; se precisar perguntar, grava a pergunta em outro e
encerra a vez. O Zé olha esses arquivos e fala o que chegar. Aperto de mão por arquivo: funciona
igual com qualquer agente.

Supervisionado de propósito (docs/05-roadmap.md, fase de manutenção):
- a zona protegida (regras de aprovação, política do sistema, configuração, este módulo, o
  reinício) pode mudar só com o usuário aprovando na sessão; se mudar, o JARVIS avisa e não se
  reinicia sem um "eu revisei";
- reiniciar para a mudança valer passa pelos testes e por `deploy/reinicio-seguro.sh`, que volta
  sozinho para a última versão boa se a nova não subir.
"""

import json
import logging
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jarvis import atividade, lugares
from jarvis.oficina.sessoes import MOTORES, Sessao, SessaoErro, Sessoes

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]  # o repositório do próprio Zé
AGENTES = {"claude": "Claude", "codex": "Codex"}
NOME_DA_SESSAO = "Zé · autodesenvolvimento"
NOMES_ANTIGOS = ("Zé · melhorias",)
ORIGEM = "manutencao"
# Mudam só com o usuário aprovando: o que decide o que o JARVIS faz sem perguntar.
PROTEGIDOS = (
    "jarvis/cerebro/ferramentas/__init__.py",  # LEITURA: o que passa sem aprovação
    "jarvis/cerebro/claude.py",  # can_use_tool: a aprovação falada
    "jarvis/sistema/politica.py",
    "jarvis/sistema/catalogo.py",  # níveis de risco do Omarchy
    "jarvis/imersivo/servidor.py",  # fronteira HTTP dos pedidos do usuário
    "jarvis/imersivo/http.py",  # autorização dos clientes locais
    "jarvis/config.py",
    "jarvis/oficina/manutencao.py",
    "deploy/reinicio-seguro.sh",
    "systemd/",
    "CLAUDE.md",
    "AGENTS.md",
    # A essência e quem o Zé é (ADR 0026).
    "docs/essencia.md",
    "jarvis/persona/",
    # A segurança do acesso de outro aparelho e o registro do que ele executa.
    "jarvis/portal/senha.py",
    "jarvis/portal/servidor.py",
    "jarvis/portal/remoto.py",
    "jarvis/portal/tunel.py",
    "jarvis/transporte/websocket.py",
    "jarvis/atividade.py",
    "jarvis/cerebro/codex_rpc.py",  # o que o cérebro Codex pode fazer (sem shell)
    "jarvis/cerebro/codex_mcp.py",  # a aprovação das ferramentas no Codex
)
CONFIG_DO_USUARIO = lugares.CONFIG / "config.toml"
# Precisam de reinício para valer (o resto é página, documento ou teste).
CODIGO = ("jarvis/", "persona/")
SEM_RESPOSTA_S = 45 * 60.0


@dataclass
class Pedido:
    id: str
    texto: str
    em: float
    inicio: str  # o commit de quando foi encaminhado: a guarda compara a partir dele
    avisado: bool = False  # já avisou que está demorando


@dataclass
class Estado:
    ligado: bool = False
    agente: str = "claude"
    sessao: str = ""  # a sessão de código do Zé (id), criada na primeira entrada
    pendentes: list[Pedido] = field(default_factory=list)


@dataclass(frozen=True)
class Chegada:
    tipo: str  # resposta | pergunta | demora
    pedido: str
    texto: str
    mudou_codigo: bool = False
    protegidos: tuple[str, ...] = ()


def _make_check(pasta: Path) -> bool:
    """Os testes do projeto na pasta (a cópia isolada cria o ambiente dela na primeira vez)."""
    try:
        feito = subprocess.run(
            ["/usr/bin/make", "-s", "check"],
            cwd=pasta,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return feito.returncode == 0


def _git_ok(*args: str, repo: Path = REPO) -> int:
    try:
        return subprocess.run(  # noqa: S603 (git com argumentos montados aqui)
            ["/usr/bin/git", "-C", str(repo), *args], capture_output=True, timeout=60, check=False
        ).returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def _git(*args: str, repo: Path = REPO) -> str:
    try:
        return subprocess.run(  # noqa: S603 (git com argumentos em lista)
            ["/usr/bin/git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class Manutencao:
    def __init__(self, sessoes: Sessoes, pasta: Path, repo: Path = REPO) -> None:
        self.sessoes = sessoes
        self.pasta = pasta
        self.repo = repo
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.estado = self._carregar()
        self._config_mtime = self._mtime_config()
        # A versão que este processo carregou: a guarda e o reinício comparam a partir dela, e é
        # para ela que o reinício volta se a nova não subir (commits fora de um pedido contam).
        self.rodando = _git("rev-parse", "HEAD", repo=self.repo).strip()
        self.testar = _make_check  # os testes da cópia antes de aplicar (os testes trocam)

    # --- estado (sobrevive ao reinício, que faz parte da manutenção) -----------------------

    def _carregar(self) -> Estado:
        try:
            d = json.loads((self.pasta / "estado.json").read_text())
            return Estado(
                ligado=bool(d.get("ligado")),
                agente=str(d.get("agente") or "claude"),
                sessao=str(d.get("sessao") or ""),
                pendentes=[Pedido(**p) for p in d.get("pendentes", [])],
            )
        except (OSError, ValueError, TypeError):
            return Estado()

    def _gravar(self) -> None:
        arquivo = self.pasta / "estado.json"
        temporario = arquivo.with_suffix(".next")
        temporario.write_text(json.dumps(asdict(self.estado), ensure_ascii=False))
        temporario.replace(arquivo)

    @property
    def ligado(self) -> bool:
        return self.estado.ligado

    @property
    def nome_do_agente(self) -> str:
        return AGENTES.get(self.estado.agente, self.estado.agente)

    # --- ligar, desligar, encaminhar -------------------------------------------------------

    def abrir_sessao(self, agente: str = "") -> str:
        """A sessão de melhorias (a mesma de antes, ou nova, na cópia isolada), sem ligar o modo
        manutenção: a voz continua indo ao Zé; o painel abre a sessão para trabalhar nela."""
        agente = agente if agente in AGENTES else self.estado.agente
        self.estado.sessao, self.estado.agente = self._sessao(agente), agente
        self._gravar()
        return self.estado.sessao

    def entrar(self, agente: str = "") -> str:
        agente = agente if agente in AGENTES else self.estado.agente
        try:
            self.estado.sessao = self._sessao(agente)
        except SessaoErro as erro:
            return f"Não entrei no modo manutenção: {erro}."
        self.estado.ligado, self.estado.agente = True, agente
        self._gravar()
        log.info("manutenção ligada com %s (sessão %s)", agente, self.estado.sessao)
        return (
            f"Modo manutenção ligado, com o {AGENTES[agente]}. O que você pedir vai para a "
            "sessão de manutenção. Para voltar, diga: sai do modo manutenção."
        )

    def sair(self) -> str:
        self.estado.ligado = False
        self._gravar()
        pendentes = len(self.estado.pendentes)
        if pendentes:
            return "Saí do modo manutenção. Ainda aviso quando o pedido em andamento terminar."
        return "Saí do modo manutenção."

    def situacao(self, agora: float) -> str:
        if not self.estado.ligado and not self.estado.pendentes:
            return "O modo manutenção está desligado."
        partes = [
            f"Modo manutenção {'ligado' if self.estado.ligado else 'desligado'}, com o "
            f"{self.nome_do_agente}."
        ]
        if self.estado.pendentes:
            minutos = round((agora - self.estado.pendentes[0].em) / 60)
            partes.append(
                f"Um pedido em andamento há {minutos} minutos."
                if len(self.estado.pendentes) == 1
                else f"{len(self.estado.pendentes)} pedidos em andamento."
            )
        else:
            partes.append("Nenhum pedido em andamento.")
        return " ".join(partes)

    def _sessao(self, agente: str) -> str:
        """A sessão de manutenção daquele agente no repositório do Zé: a mesma de antes, ou nova."""
        if agente not in MOTORES:
            raise SessaoErro(
                f"o {AGENTES.get(agente, agente)} ainda não está disponível nas sessões"
            )
        # Só a cópia isolada (ADR 0026): sessões antigas, direto no repositório, ficam como estão.
        minhas = [
            s
            for s in self.sessoes.listar()
            if s.origem == ORIGEM
            and s.motor == agente
            and Path(s.pasta) == self.repo.resolve()
            and s.worktree
        ]
        escolhida = next((s for s in minhas if s.id == self.estado.sessao), None)
        if escolhida or minhas:
            return (escolhida or minhas[0]).id
        nova = self.sessoes.criar(
            NOME_DA_SESSAO, str(self.repo), motor=agente, origem=ORIGEM, isolada=True
        )
        return nova.id

    def encaminhar(self, texto: str, contexto: str, agora: float, rodada: str = "") -> str:
        """Manda o pedido à sessão e devolve a frase para falar já. Com uma pergunta do agente
        em aberto, o que o usuário disser é a resposta dela, no mesmo pedido."""
        perguntou = next((p for p in self.estado.pendentes if self._pergunta_aberta(p.id)), None)
        if perguntou and not rodada:
            pedido, novo = perguntou, False
            corpo = f'Resposta do usuário à sua pergunta: "{texto}".'
        else:
            inicio = _git("rev-parse", "HEAD", repo=self.repo).strip()
            pedido, novo = Pedido(uuid.uuid4().hex[:8], texto, agora, inicio), True
            corpo = rodada or f'O usuário pediu por voz: "{texto}".'
        resposta, pergunta = self._arquivos(pedido.id)
        mensagem = (
            f"[JARVIS · modo manutenção · pedido {pedido.id}] {corpo} Contexto agora: {contexto} "
            "Trabalhe como sempre neste projeto (CLAUDE.md, testes, conferir na janela real, "
            "commit). Leia docs/essencia.md: nenhuma mudança pode contrariá-la. Escopo: só "
            "trabalho sobre o próprio Zérvis; pedido fora disso (outro projeto, um site, um "
            "script qualquer) você recusa e grava como resposta que ele deve abrir uma sessão "
            "comum. Zona protegida: não altere sem o usuário aprovar explicitamente nesta "
            f"sessão: {', '.join(PROTEGIDOS)} e {CONFIG_DO_USUARIO}. Ao terminar, grave só o seu "
            f"Resumo falado (um parágrafo, sem símbolos nem caminhos, números por extenso) em "
            f"{resposta}. Se precisar perguntar algo ao usuário antes, grave só a pergunta em "
            f"{pergunta} e encerre a sua vez: a resposta chega como nova mensagem nesta sessão."
        )
        try:
            if not self.estado.sessao:
                self.estado.sessao = self._sessao(self.estado.agente)
            self.sessoes.enviar(self.estado.sessao, mensagem, quem="usuario")
        except SessaoErro as erro:
            return f"Não consegui mandar para o {self.nome_do_agente}: {erro}."
        if not novo:
            (self.pasta / f".perguntou-{pedido.id}").unlink(missing_ok=True)
            return f"Respondi ao {self.nome_do_agente}."
        self.estado.pendentes.append(pedido)
        self._gravar()
        log.info("manutenção: pedido %s encaminhado ao %s", pedido.id, self.estado.agente)
        return f"Mandei para o {self.nome_do_agente}. Aviso quando terminar."

    def _arquivos(self, pedido: str) -> tuple[Path, Path]:
        return self.pasta / f"resposta-{pedido}.md", self.pasta / f"pergunta-{pedido}.md"

    def _pergunta_aberta(self, pedido: str) -> bool:
        return (self.pasta / f".perguntou-{pedido}").exists()

    # --- o que chega da sessão -------------------------------------------------------------

    def verificar(self, agora: float) -> list[Chegada]:
        """Respostas e perguntas gravadas pelo agente (uma vez cada) e pedidos demorados."""
        chegadas: list[Chegada] = []
        for p in list(self.estado.pendentes):
            resposta, pergunta = self._arquivos(p.id)
            if (texto := _ler(pergunta)) is not None:
                pergunta.unlink(missing_ok=True)
                (self.pasta / f".perguntou-{p.id}").touch()
                chegadas.append(Chegada("pergunta", p.id, texto))
            if (texto := _ler(resposta)) is not None:
                resposta.unlink(missing_ok=True)
                (self.pasta / f".perguntou-{p.id}").unlink(missing_ok=True)
                self.estado.pendentes.remove(p)
                mudou, protegidos = self.guarda(p.inicio)
                chegadas.append(Chegada("resposta", p.id, texto, mudou, protegidos))
            elif not p.avisado and agora - p.em > SEM_RESPOSTA_S:
                p.avisado = True
                chegadas.append(Chegada("demora", p.id, p.texto))
        if chegadas:
            self._gravar()
        return chegadas

    def guarda(self, inicio: str) -> tuple[bool, tuple[str, ...]]:
        """Desde `inicio`: mudou código que pede reinício? Mexeu na zona protegida? Vale o que
        a cópia isolada mudou e o que mudou direto no repositório."""
        mudados = (
            set(_git("diff", "--name-only", inicio, repo=self.repo).split()) if inicio else set()
        )
        for linha in _git("status", "--porcelain", repo=self.repo).splitlines():
            mudados.add(linha[3:].strip().strip('"'))
        mudados |= set(self.mudancas().get("arquivos", []))
        mudados.discard("")
        protegidos = sorted(m for m in mudados if any(m.startswith(p) for p in PROTEGIDOS))
        if self._mtime_config() != self._config_mtime:
            protegidos.append(str(CONFIG_DO_USUARIO))
        mudou = any(m.startswith(CODIGO) for m in mudados)
        return mudou, tuple(protegidos)

    def _mtime_config(self) -> float:
        try:
            return CONFIG_DO_USUARIO.stat().st_mtime
        except OSError:
            return 0.0

    # --- a cópia isolada: o que mudou, aplicar, descartar (ADR 0026) ---------------------------

    def copia(self) -> Sessao | None:
        """A sessão de autodesenvolvimento com a cópia isolada dela, se existir."""
        if not self.estado.sessao:
            return None
        try:
            s = self.sessoes.ler(self.estado.sessao)
        except SessaoErro:
            return None
        if not (s.worktree and Path(s.worktree).is_dir()):
            return None
        if s.nome in NOMES_ANTIGOS:  # a sessão criada antes do nome atual
            s.nome = NOME_DA_SESSAO
            self.sessoes._gravar(s)
        return s

    def mudancas(self) -> dict[str, Any]:
        """O que a cópia tem a mais que o Zé em uso: commits, arquivos e a zona protegida."""
        s = self.copia()
        if s is None:
            return {"copia": False}
        onde = Path(s.worktree)
        commits = _git("log", "--oneline", f"HEAD..{s.branch}", repo=self.repo).splitlines()
        arquivos = set(_git("diff", "--name-only", f"HEAD...{s.branch}", repo=self.repo).split())
        sem_commit = [
            linha[3:].strip().strip('"')
            for linha in _git("status", "--porcelain", repo=onde).splitlines()
            if linha.strip()
        ]
        arquivos |= set(sem_commit)
        arquivos.discard("")
        return {
            "copia": True,
            "sessao": s.id,
            "branch": s.branch,
            "commits": commits[:30],
            "arquivos": sorted(arquivos)[:200],
            "protegidos": sorted(a for a in arquivos if a.startswith(PROTEGIDOS)),
            "sem_commit": bool(sem_commit),
            "resumo": _git("diff", "--stat", f"HEAD...{s.branch}", repo=self.repo)[-1500:],
        }

    def aplicar(self, revisado: bool = False) -> tuple[bool, str]:
        """Junta as melhorias da cópia ao Zé em uso, com os testes da cópia verdes, e reinicia."""
        s = self.copia()
        m = self.mudancas()
        if s is None or not m.get("commits"):
            return False, "Não há melhorias para aplicar."
        if s.estado == "trabalhando":
            return False, "A sessão de melhorias ainda está trabalhando."
        if m["sem_commit"]:
            return False, "A cópia tem alterações sem commit. Peça para a sessão concluir."
        if m["protegidos"] and not revisado:
            return False, (
                "As melhorias mexem na zona protegida (essência, segurança ou o que eu faço sem "
                "perguntar). Revise no painel e confirme a revisão para aplicar."
            )
        if not self.testar(Path(s.worktree)):
            return False, "Os testes falharam na cópia. Peça para a sessão corrigir antes."
        if _git("status", "--porcelain", "--untracked-files=no", repo=self.repo).strip():
            return False, "O repositório do Zé tem alterações sem commit. Resolva antes de aplicar."
        if _git_ok("merge", "--ff-only", s.branch, repo=self.repo) != 0:
            mensagem = f"Autodesenvolvimento do Zé ({s.branch})"
            if _git_ok("merge", "--no-ff", "-m", mensagem, s.branch, repo=self.repo) != 0:
                _git_ok("merge", "--abort", repo=self.repo)
                return (
                    False,
                    "Conflito ao juntar as melhorias. Peça para a sessão atualizar a cópia.",
                )
        atual = _git("rev-parse", "HEAD", repo=self.repo).strip()
        _git_ok("merge", "--ff-only", atual, repo=Path(s.worktree))  # a cópia acompanha
        atividade.PADRAO.registrar(
            "execucao",
            f"Aplicou {len(m['commits'])} melhoria(s) do Zé",
            commits=m["commits"],
            protegidos=m["protegidos"],
            autorizacao="revisada" if m["protegidos"] else "aprovada",
        )
        return self.reiniciar(revisado=True)

    def descartar(self) -> str:
        """Joga fora o que a cópia tem a mais: ela volta a ser igual ao Zé em uso."""
        s = self.copia()
        if s is None:
            return "Não há cópia de melhorias."
        m = self.mudancas()
        atual = _git("rev-parse", "HEAD", repo=self.repo).strip()
        onde = Path(s.worktree)
        _git_ok("reset", "--hard", atual, repo=onde)
        _git_ok("clean", "-fd", repo=onde)
        atividade.PADRAO.registrar(
            "execucao", "Descartou as melhorias da cópia", commits=m.get("commits", [])
        )
        return "Mudanças descartadas."

    # --- reiniciar para valer ----------------------------------------------------------------

    def reiniciar(self, revisado: bool = False) -> tuple[bool, str]:
        """Confere a guarda e os testes e entrega o reinício ao script (fora deste processo)."""
        _, protegidos = self.guarda(self.rodando)
        if protegidos and not revisado:
            return False, (
                "Não reiniciei: a mudança mexeu na zona protegida, nas regras do que eu faço sem "
                "perguntar. Revise na sessão de manutenção, no painel; para valer mesmo assim, "
                "diga: reinicia o Zé, eu revisei."
            )
        testes = subprocess.run(
            ["/usr/bin/make", "-s", "check"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if testes.returncode != 0:
            return False, "Não reiniciei: os testes falharam. Peça para a sessão corrigir antes."
        subprocess.run(  # noqa: S603 (script nosso, fora do cgroup do jarvisd)
            [
                "/usr/bin/systemd-run",
                "--user",
                "--collect",
                f"--unit=jarvis-reinicio-{int(time.time())}",
                str(self.repo / "deploy/reinicio-seguro.sh"),
                str(self.repo),
                self.rodando,
                str(self.pasta),
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        return True, "Testes passaram. Vou me reiniciar; volto em alguns segundos."

    def resultado_do_reinicio(self) -> str | None:
        """O que o script deixou dito sobre o último reinício (uma vez só)."""
        arquivo = self.pasta / "reinicio.json"
        try:
            d: dict[str, Any] = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            return None
        arquivo.unlink(missing_ok=True)
        if d.get("resultado") == "ok":
            return "Voltei com a versão nova."
        if d.get("resultado") == "voltou":
            return (
                "A versão nova não subiu, então voltei sozinho para a anterior. O que mudou está "
                "guardado; peça para a sessão ver o que quebrou."
            )
        return None


def _ler(arquivo: Path) -> str | None:
    try:
        texto = " ".join(arquivo.read_text().split())
    except OSError:
        return None
    return texto[:1500] or None
