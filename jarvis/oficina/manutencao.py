"""O modo manutenção: o JARVIS encaminha os pedidos do usuário à sessão de código dele mesmo.

"Entra no modo manutenção" liga; daí em diante, o que não for comando local vai como texto para
a sessão de agente (Claude ou Codex) aberta no projeto do JARVIS no Orca, com o contexto do
momento. O agente trabalha como sempre (testes, janela real, commit) e, ao terminar, grava o
Resumo falado num arquivo combinado; se precisar perguntar, grava a pergunta em outro. O JARVIS
olha esses arquivos e fala o que chegar. Aperto de mão por arquivo: funciona igual com qualquer
agente e não depende de ler a tela.

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

from jarvis import lugares
from jarvis.oficina.oficina import PROJETO_JARVIS, Oficina
from jarvis.oficina.orca import OrcaErro

log = logging.getLogger(__name__)

AGENTES = {"claude": "Claude", "codex": "Codex"}
# Mudam só com o usuário aprovando: o que decide o que o JARVIS faz sem perguntar.
PROTEGIDOS = (
    "jarvis/cerebro/ferramentas/__init__.py",  # LEITURA: o que passa sem aprovação
    "jarvis/cerebro/claude.py",  # can_use_tool: a aprovação falada
    "jarvis/sistema/politica.py",
    "jarvis/sistema/catalogo.py",  # níveis de risco do Omarchy
    "jarvis/config.py",
    "jarvis/oficina/manutencao.py",
    "deploy/reinicio-seguro.sh",
    "systemd/",
    "CLAUDE.md",
    "AGENTS.md",
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
    pendentes: list[Pedido] = field(default_factory=list)


@dataclass(frozen=True)
class Chegada:
    tipo: str  # resposta | pergunta | demora
    pedido: str
    texto: str
    mudou_codigo: bool = False
    protegidos: tuple[str, ...] = ()


def _git(*args: str, repo: Path = PROJETO_JARVIS) -> str:
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
    def __init__(
        self,
        oficina: Oficina,
        pasta: Path,
        repo: Path = PROJETO_JARVIS,
        projeto: str = str(PROJETO_JARVIS),
    ) -> None:
        self.oficina = oficina
        self.pasta = pasta
        self.repo = repo
        self.projeto = projeto
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.estado = self._carregar()
        self._config_mtime = self._mtime_config()
        # A versão que este processo carregou: a guarda e o reinício comparam a partir dela, e é
        # para ela que o reinício volta se a nova não subir (commits fora de um pedido contam).
        self.rodando = _git("rev-parse", "HEAD", repo=self.repo).strip()

    # --- estado (sobrevive ao reinício, que faz parte da manutenção) -----------------------

    def _carregar(self) -> Estado:
        try:
            d = json.loads((self.pasta / "estado.json").read_text())
            return Estado(
                ligado=bool(d.get("ligado")),
                agente=str(d.get("agente") or "claude"),
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

    def entrar(self, agente: str = "") -> str:
        agente = agente if agente in AGENTES else self.estado.agente
        try:
            self._sessao(agente)
        except OrcaErro as erro:
            return f"Não entrei no modo manutenção: {erro}."
        self.estado.ligado, self.estado.agente = True, agente
        self._gravar()
        log.info("manutenção ligada com %s", agente)
        return (
            f"Modo manutenção ligado, com o {AGENTES[agente]}. O que você pedir vai para a "
            "sessão do JARVIS no Orca. Para voltar, diga: sai do modo manutenção."
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

    def _sessao(self, agente: str) -> None:
        """Confere que há uma sessão daquele agente aberta no projeto do JARVIS."""
        projeto = self.oficina.achar_projeto(self.projeto)
        if not any(s["agente"] == agente for s in self.oficina.sessoes(projeto)):
            raise OrcaErro(
                f"não há sessão do {AGENTES.get(agente, agente)} aberta no projeto do JARVIS no "
                "Orca; abra uma e peça de novo"
            )

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
            "commit). Zona protegida: não altere sem o usuário aprovar explicitamente nesta "
            f"sessão: {', '.join(PROTEGIDOS)} e {CONFIG_DO_USUARIO}. Ao terminar, grave só o seu "
            f"Resumo falado (um parágrafo, sem símbolos nem caminhos, números por extenso) em "
            f"{resposta}. Se precisar perguntar algo ao usuário antes, grave só a pergunta em "
            f"{pergunta} e espere: a resposta chega nesta sessão."
        )
        try:
            self.oficina.mandar_texto(self.projeto, mensagem, agente=self.estado.agente)
        except OrcaErro as erro:
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
        """Desde `inicio`: mudou código que pede reinício? Mexeu na zona protegida?"""
        mudados = (
            set(_git("diff", "--name-only", inicio, repo=self.repo).split()) if inicio else set()
        )
        for linha in _git("status", "--porcelain", repo=self.repo).splitlines():
            mudados.add(linha[3:].strip().strip('"'))
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

    # --- reiniciar para valer ----------------------------------------------------------------

    def reiniciar(self, revisado: bool = False) -> tuple[bool, str]:
        """Confere a guarda e os testes e entrega o reinício ao script (fora deste processo)."""
        _, protegidos = self.guarda(self.rodando)
        if protegidos and not revisado:
            return False, (
                "Não reiniciei: a mudança mexeu na zona protegida, nas regras do que eu faço sem "
                "perguntar. Revise no Orca; para valer mesmo assim, diga: reinicia o JARVIS, eu "
                "revisei."
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
