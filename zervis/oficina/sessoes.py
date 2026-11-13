"""As sessões da oficina própria do Zé (docs/plano-oficina.md, fase 1; 09/10/2026).

Cada sessão é um agente de código com nome, uma pasta (o projeto), um motor e a sua conversa,
como os "bots" do Hermes. O motor Claude é o próprio Claude Code (o Agent SDK que o Zé já usa
no cérebro), com as ferramentas de código, a pasta como diretório de trabalho e o CLAUDE.md do
projeto. Funciona pela assinatura ou pela chave, sem o Orca.

Regras herdadas do Hermes e do Orca: no máximo três trabalhando ao mesmo tempo, edição só dentro
da pasta (`acceptEdits`), comandos por uma lista de proibidos, parar a qualquer momento,
continuar depois (`resume`) e, opcionalmente, uma cópia isolada (git worktree, branch
`ze/<id>`) para não mexer no projeto até o usuário aprovar.
"""

import asyncio
import contextlib
import json
import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import fuso
from zervis.cerebro import contas, mcp_externo, modelos
from zervis.dados.documentos import Documentos, linhas_json, objeto_json
from zervis.memoria import aimemory
from zervis.oficina import (
    continuidade,
    fallback,
    isolamento,
    sessoes_copia,
    sessoes_envio,
    sessoes_eventos,
    sessoes_leitura,
)
from zervis.oficina.agentes import ACOES_DO_CLAUDE as ACOES_DO_CLAUDE
from zervis.oficina.agentes import ANSI as ANSI
from zervis.oficina.agentes import COMANDOS_LIVRES as COMANDOS_LIVRES
from zervis.oficina.agentes import CONECTORES as CONECTORES
from zervis.oficina.agentes import ESPERA_RETOMAR as ESPERA_RETOMAR
from zervis.oficina.agentes import FOCO_S as FOCO_S
from zervis.oficina.agentes import GANCHO_CODEX as GANCHO_CODEX
from zervis.oficina.agentes import GANCHOS_DO_CODEX as GANCHOS_DO_CODEX
from zervis.oficina.agentes import HOOKS_DO_ZE as HOOKS_DO_ZE
from zervis.oficina.agentes import INTERNET_LIVRE as INTERNET_LIVRE
from zervis.oficina.agentes import LIMITE as LIMITE
from zervis.oficina.agentes import LIMITE_CODEX as LIMITE_CODEX
from zervis.oficina.agentes import LIMITE_TERMINAL as LIMITE_TERMINAL
from zervis.oficina.agentes import NOME_DE_FERRAMENTA as NOME_DE_FERRAMENTA
from zervis.oficina.agentes import NOMES_MOTORES as NOMES_MOTORES
from zervis.oficina.agentes import OUTRAS_COM_PERMISSAO as OUTRAS_COM_PERMISSAO
from zervis.oficina.agentes import PASTAS_DE_SKILLS as PASTAS_DE_SKILLS
from zervis.oficina.agentes import PRAZO_PERMISSAO_S as PRAZO_PERMISSAO_S
from zervis.oficina.agentes import PREFIXO_SKILL as PREFIXO_SKILL
from zervis.oficina.agentes import REGRAS as REGRAS
from zervis.oficina.agentes import RESUMO_DO_EVENTO as RESUMO_DO_EVENTO
from zervis.oficina.agentes import RETOMAR_CONVERSA as RETOMAR_CONVERSA
from zervis.oficina.agentes import SEM_APROVACAO as SEM_APROVACAO
from zervis.oficina.agentes import TELA_RETOMAR as TELA_RETOMAR
from zervis.oficina.agentes import VARIAVEL_PERMISSAO as VARIAVEL_PERMISSAO
from zervis.oficina.agentes import _acao_do_claude as _acao_do_claude
from zervis.oficina.agentes import _arquivo_da_conversa as _arquivo_da_conversa
from zervis.oficina.agentes import _comando_codex as _comando_codex
from zervis.oficina.agentes import _descrever_ferramenta as _descrever_ferramenta
from zervis.oficina.agentes import _fora_do_git as _fora_do_git
from zervis.oficina.agentes import _ligar_em as _ligar_em
from zervis.oficina.agentes import _nome_da_conta as _nome_da_conta
from zervis.oficina.agentes import _resumo_de as _resumo_de
from zervis.oficina.agentes import _simples as _simples
from zervis.oficina.agentes import _tabela_toml as _tabela_toml
from zervis.oficina.agentes import _turno_auxiliar_do_codex as _turno_auxiliar_do_codex
from zervis.oficina.agentes import _ultima_resposta_claude as _ultima_resposta_claude
from zervis.oficina.agentes import ambiente_da_conta as ambiente_da_conta
from zervis.oficina.agentes import ambiente_do_agente as ambiente_do_agente
from zervis.oficina.agentes import ambiente_para_sdk as ambiente_para_sdk
from zervis.oficina.agentes import arquivo_de_conectores as arquivo_de_conectores
from zervis.oficina.agentes import comando_terminal as comando_terminal
from zervis.oficina.agentes import conectores_codex as conectores_codex
from zervis.oficina.agentes import conectores_do_projeto as conectores_do_projeto
from zervis.oficina.agentes import confiar_pasta_claude as confiar_pasta_claude
from zervis.oficina.agentes import confiar_pasta_codex as confiar_pasta_codex
from zervis.oficina.agentes import conversa_claude_existe as conversa_claude_existe
from zervis.oficina.agentes import copiar_conversa as copiar_conversa
from zervis.oficina.agentes import ganchos_codex as ganchos_codex
from zervis.oficina.agentes import git_comum as git_comum
from zervis.oficina.agentes import isolar as isolar
from zervis.oficina.agentes import ligar_skills_no_projeto as ligar_skills_no_projeto
from zervis.oficina.agentes import pastas_da_conta as pastas_da_conta
from zervis.oficina.agentes import pede_aprovacao as pede_aprovacao
from zervis.oficina.agentes import regras_de_skills as regras_de_skills
from zervis.oficina.permissoes import Permissoes
from zervis.oficina.ponte import Ponte
from zervis.oficina.supervisor import Oficina, TerminalRemoto
from zervis.oficina.terminal import Terminal

log = logging.getLogger(__name__)
FUSO = fuso.local()
MAXIMO_TRABALHANDO = 3
LIDOS = "eventos-lidos"  # até onde o arquivo de eventos de cada sessão já foi consumido
MOTORES = ("claude", "codex")
PASSAGEM = continuidade.PASSAGEM
PEDIDO_AGORA = continuidade.PEDIDO_AGORA
SAIDAS_NORMAIS = (0, 130, 143, -2, -15)  # saiu, Ctrl+C, ou o Zé fechou o terminal (SIGTERM)
ESTADOS = ("parada", "trabalhando", "erro")
LIMITE_PASSAGEM = 8000
LIMITE_ANEXO = 20 * 1024 * 1024
LIMITE_ARQUIVO = 512 * 1024
# O que dá para arrastar ou colar numa sessão (o Claude Code lê imagens e PDFs).
TIPOS_ANEXO = {
    *(".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"),
    *(".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".toml", ".log", ".html", ".css", ".xml"),
    *(".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".sh", ".sql", ".java", ".kt", ".swift"),
}
TIPOS_ARQUIVO = (".md", ".txt")
# Comandos que o agente nunca roda sozinho, mesmo dentro da pasta.
PROIBIDOS = re.compile(
    r"(^|[;&|`(]\s*)(sudo|su|doas|pkexec)\b"
    r"|\bgit\s+push\b|\bgit\s+.*--force\b"
    r"|\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME|\.\.)(\s|$)"
    r"|\b(mkfs|fdisk|parted|dd\s+if=|shutdown|reboot|poweroff|systemctl\s+(stop|disable|mask))"
    r"|curl[^|]*\|\s*(ba|z)?sh\b|wget[^|]*\|\s*(ba|z)?sh\b"
    r"|\bchmod\s+-R\s+777\b|\b(crontab|passwd|chsh|useradd|usermod)\b"
    r"|>\s*/(etc|usr|boot|dev)/",
    re.IGNORECASE,
)


class LimiteErro(RuntimeError):
    """A conta do agente bateu o limite de uso (dá para trocar de conta ou de agente)."""


class SessaoErro(ValueError):
    """Mensagem curta, para a tela e para a voz."""


def agora() -> str:
    return datetime.now(FUSO).isoformat(timespec="seconds")


def comando_proibido(comando: str) -> bool:
    return bool(PROIBIDOS.search(comando))


@dataclass
class Sessao:
    id: str
    nome: str
    pasta: str
    motor: str = "claude"
    conta: str = ""  # a conta do agente (zervis.cerebro.contas); vazio: a que o Zé usa agora
    modelo: str = ""  # vazio: o padrão da conta
    esforco: str = ""  # esforço de raciocínio (Codex); vazio: o padrão do modelo
    isolada: bool = False
    # Protegida (ADR 0074): o agente roda no isolamento e só enxerga a pasta do projeto.
    protegida: bool = False
    # Fora do projeto, onde a sessão protegida também escreve (a manutenção grava ali a resposta).
    escrita: list[str] = field(default_factory=list)
    worktree: str = ""
    branch: str = ""
    base: str = ""  # o commit de onde a cópia isolada saiu
    estado: str = "parada"
    criada: str = field(default_factory=agora)
    atualizada: str = field(default_factory=agora)
    resumo: str = ""  # o último recado do agente, curto (a lista e a voz)
    sdk_sessao: str = ""  # a conversa nativa do agente em uso (resume)
    origem: str = "painel"
    # Troca de agente (ADR 0016): a conversa nativa de cada agente nesta sessão, quantas mensagens
    # cada um já viu, e a passagem que vai junto do próximo pedido.
    fios: dict[str, str] = field(default_factory=dict)
    vistos: dict[str, int] = field(default_factory=dict)
    passagem: str = ""
    # O último pedido de quem usa e se ele bateu no limite da conta: trocando de conta, o Zé
    # o manda de novo e o trabalho continua de onde parou.
    ultimo_pedido: str = ""
    limite: bool = False
    limite_conta: str = ""  # só a conta em que o limite foi confirmado
    # O pedido que estava em andamento quando o agente parou sem terminar (o Zé reiniciou, o
    # terminal fechou no meio): fica até a pessoa continuar ou dispensar.
    interrompida: str = ""

    @property
    def onde(self) -> Path:
        return Path(self.worktree or self.pasta)


def _git(pasta: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (git fixo, argumentos em lista)
        ["git", "-C", str(pasta), *args],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _git_verificado(pasta: Path, *args: str) -> str:
    feito = _git_resultado(pasta, *args)
    if feito.returncode:
        raise SessaoErro("Não foi possível concluir a operação com o Git.")
    return feito.stdout


def _git_resultado(pasta: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return _git(pasta, *args)
    except (OSError, subprocess.SubprocessError):
        raise SessaoErro("Não foi possível concluir a operação com o Git.") from None


def _git_sem_operacao(pasta: Path) -> None:
    for nome in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        relativo = _git_verificado(pasta, "rev-parse", "--git-path", nome).strip()
        if (pasta / relativo).exists():
            raise SessaoErro("Há uma operação Git em andamento. Conclua-a antes de continuar.")


def _git_preservar_ignorados(pasta: Path, alvo: str) -> None:
    ignorados = _git_verificado(
        pasta, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"
    )
    arquivos = _git_verificado(pasta, "ls-tree", "-r", "--name-only", "-z", alvo)
    ocupados = set(filter(None, ignorados.split("\0")))
    pastas = {
        "/".join(partes[:i])
        for nome in ocupados
        if (partes := nome.split("/"))
        for i in range(1, len(partes))
    }
    for arquivo in filter(None, arquivos.split("\0")):
        partes = arquivo.split("/")
        if (
            arquivo in ocupados
            or arquivo in pastas
            or any("/".join(partes[:i]) in ocupados for i in range(1, len(partes)))
        ):
            raise SessaoErro(
                "A operação substituiria um arquivo ignorado. Preserve-o antes de continuar."
            )


class Sessoes:
    def __init__(
        self,
        pasta: Path,
        raizes: tuple[Path, ...],
        ao_terminar: Callable[[Sessao, str], None] | None = None,
        rodar: Callable[["Sessoes", Sessao, str], Any] | None = None,
        projetos_novos: Path | None = None,
        skills: Any = None,
        oficina: Oficina | None = None,
        protegida_padrao: bool = False,
    ) -> None:
        self.protegida_padrao = protegida_padrao  # sem escolha, nasce protegida (ADR 0074)
        self.skills = (
            skills  # as skills do usuário (habilidades.skills.Skills): sessões também leem
        )
        self._dados = Documentos(pasta / "sessoes.db")
        for antigo in sorted(pasta.glob("*/sessao.json")):
            self._dados.importar(antigo, objeto_json, "sessoes", campo_chave="id")
        for antigo in sorted(pasta.glob("*/mensagens.jsonl")):
            self._dados.importar(antigo, linhas_json, "mensagens-" + antigo.parent.name)
        self.pasta = pasta  # ~/.local/share/zervis/sessoes
        self.projetos_novos = projetos_novos  # onde nasce um projeto criado com a sessão
        self.raizes = tuple(r.expanduser().resolve() for r in raizes)
        self.ao_terminar = ao_terminar
        self.ao_avisar: Callable[[Sessao, str], None] | None = None  # aprovação pedida no terminal
        # Os pedidos de permissão do Claude, decididos também fora do terminal (ADR 0039).
        self.permissoes = Permissoes()
        # Os conectores com segredo passam pelo Zé (ADR 0076): o agente só leva a chave da sessão.
        self.ponte = Ponte(
            self.permissoes.sessao_da_chave, self._conectores, self.permissoes.tem_chave
        )
        # Motivo para não aceitar trabalho agora (o Zé vai se atualizar, ADR 0028), ou None.
        self.reservada: Callable[[], str | None] = lambda: None
        # Sem `rodar`, cada sessão é um terminal real (o agente com todos os comandos dele);
        # com `rodar` (testes, ou trabalho sem tela), roda sem terminal.
        self.legado = rodar is not None
        self.rodar = rodar or rodar_agente
        self.terminais: dict[str, Terminal | TerminalRemoto] = {}
        self._lidos: dict[str, int] = {}  # quanto do arquivo de eventos de cada sessão já foi lido
        self._limite_visto: set[str] = set()
        self._ganchos_avisados: set[str] = set()  # o Codex pediu para confiar nos ganchos
        # O Claude pergunta se retoma a conversa parada: nada é colado até a pessoa responder.
        self.retomada_pendente: set[str] = set()
        self._cauda: dict[str, bytes] = {}  # o fim da tela, para um texto partido em dois
        self._saida_limite: dict[str, bytes] = {}  # avisos de limite podem vir em vários quadros
        self.em_foco: tuple[str, float] = ("", 0.0)  # a sessão de que se fala agora, e quando
        self.trava = threading.Lock()
        # Não abre ou envia para um agente enquanto a exclusão espera ele encerrar.
        self._operacoes = threading.RLock()
        self.fallback = fallback.Fallback(self)
        self._centralizando: set[str] = set()
        self.tarefas: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task[None]]] = {}
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.legado:
            threading.Thread(
                target=self._vigiar_eventos, name="sessoes-eventos", daemon=True
            ).start()
        # Com o supervisor (ADR 0068), os terminais vivem fora do Zé: os que continuaram abertos
        # enquanto ele reiniciava são reencontrados aqui. Sem ele, cada terminal é um filho do Zé.
        self.oficina = oficina if oficina is not None and not self.legado else None
        if self.oficina is not None and not self.oficina.conectar():
            log.warning("supervisor das sessões indisponível: os terminais ficam no Zé")
            self.oficina = None
        continuam = self._retomar_terminais()
        # Uma sessão que estava trabalhando quando o Zé caiu, e cujo agente não continuou, não
        # está mais: o pedido fica guardado como interrompido, para o Zé avisar e oferecer
        # continuar.
        self.interrompidas_ao_subir: list[Sessao] = []
        for s in self.listar():
            if s.estado == "trabalhando" and s.id not in continuam:
                s.estado = "parada"
                s.interrompida = s.ultimo_pedido or s.interrompida or "(pedido sem registro)"
                self._gravar(s)
                self.anotar(s.id, "sistema", "O Zé reiniciou no meio do trabalho.")
                self.interrompidas_ao_subir.append(s)

    def _retomar_terminais(self) -> set[str]:
        return sessoes_eventos._retomar_terminais(self)

    def _avisos_do_terminal(
        self, id_: str, resumo_chave: str
    ) -> tuple[Callable[[int], None], Callable[[bytes], None]]:
        return sessoes_eventos._avisos_do_terminal(self, id_, resumo_chave)

    def _novo_terminal(
        self,
        id_: str,
        comando: list[str],
        pasta: Path,
        ambiente: dict[str, str],
        chave: str,
        prazo: float | None,
        colunas: int,
        linhas: int,
    ) -> Terminal | TerminalRemoto:
        return sessoes_eventos._novo_terminal(
            self, id_, comando, pasta, ambiente, chave, prazo, colunas, linhas
        )

    def soltar_terminais(self) -> None:
        """O Zé está fechando: os agentes no supervisor continuam (ADR 0068)."""
        if self.oficina is not None:
            self.oficina.soltar()
            self.terminais.clear()

    # --- disco ---------------------------------------------------------------------------

    def _conectores(self, id_: str) -> tuple[mcp_externo.Externos, Path]:
        s = self.ler(id_)
        return conectores_do_projeto(s), Path(s.onde)

    def _dir(self, id_: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{8}", id_):
            raise SessaoErro("sessão desconhecida")
        return self.pasta / id_

    def _gravar(self, s: Sessao) -> None:
        self._dir(s.id).mkdir(exist_ok=True, mode=0o700)
        self._dados.guardar("sessoes", asdict(s), s.id)

    def ler(self, id_: str) -> Sessao:
        return sessoes_leitura.ler(self, id_)

    def focar(self, id_: str) -> None:
        """Esta sessão é a de que se fala agora (aviso, tela, pedido): "diz pra ela..." é ela."""
        self.em_foco = (id_, time.time())

    def achar(self, ref: str) -> Sessao:
        return sessoes_leitura.achar(self, ref)

    def listar(self, incluir_arquivadas: bool = False) -> list[Sessao]:
        return sessoes_leitura.listar(self, incluir_arquivadas)

    def mensagens(self, id_: str, desde: int = 0) -> list[dict[str, Any]]:
        self._dir(id_)
        return self._dados.listar("mensagens-" + id_, desde=desde)

    def buscar(self, id_: str, texto: str, limite: int = 50) -> list[dict[str, Any]]:
        self._dir(id_)
        return self._dados.buscar(texto, "mensagens-" + id_, limite)

    def anotar(self, id_: str, quem: str, texto: str, anexos: list[str] | None = None) -> None:
        # O limite é da passagem enviada ao modelo. O registro local conserva as ressalvas
        # e restrições de mensagens longas para recuperação sob demanda.
        texto = texto.strip()
        if not texto:
            return
        linha: dict[str, Any] = {"em": agora(), "quem": quem, "texto": texto}
        if anexos:
            linha["anexos"] = anexos
        self._dir(id_)
        self._dados.guardar("mensagens-" + id_, linha)

    def pasta_de_anexos(self, id_: str) -> Path:
        return self._dir(id_) / "anexos"

    def anexar(self, id_: str, nome: str, dados: bytes) -> str:
        return sessoes_envio.anexar(self, id_, nome, dados)

    def criar_arquivo(self, id_: str, nome: str, conteudo: str, sobrescrever: bool = False) -> str:
        return sessoes_envio.criar_arquivo(self, id_, nome, conteudo, sobrescrever)

    def _mudar(self, id_: str, **campos: Any) -> Sessao:
        return sessoes_leitura._mudar(self, id_, **campos)

    # --- criar, conversar, parar ---------------------------------------------------------

    def _pasta_permitida(self, pasta: str) -> Path:
        return sessoes_leitura._pasta_permitida(self, pasta)

    def criar(
        self,
        nome: str,
        pasta: str,
        motor: str = "claude",
        modelo: str = "",
        isolada: bool = False,
        origem: str = "painel",
        protegida: bool | None = None,
        escrita: tuple[str, ...] = (),
    ) -> Sessao:
        """`protegida`: None é o padrão (protegida quando dá); True ou False, a escolha feita."""
        with self._operacoes:
            return self._criar(nome, pasta, motor, modelo, isolada, origem, protegida, escrita)

    def _criar(
        self,
        nome: str,
        pasta: str,
        motor: str,
        modelo: str,
        isolada: bool,
        origem: str,
        protegida: bool | None = None,
        escrita: tuple[str, ...] = (),
    ) -> Sessao:
        criar = sessoes_envio._criar
        return criar(self, nome, pasta, motor, modelo, isolada, origem, protegida, escrita)

    def protegida_disponivel(self) -> bool:
        """Dá para criar sessão protegida aqui: o bubblewrap funciona e há terminal."""
        return not self.legado and isolamento.disponivel()

    def criar_projeto(self, nome: str) -> Path:
        return sessoes_envio.criar_projeto(self, nome)

    def trabalhando(self) -> list[str]:
        ids = [id_ for id_, (_, t) in self.tarefas.items() if not t.done()]
        for id_, terminal in list(self.terminais.items()):
            if terminal.vivo and id_ not in ids:
                with contextlib.suppress(SessaoErro):
                    if self.ler(id_).estado == "trabalhando":
                        ids.append(id_)
        return ids

    def enviar(
        self, id_: str, texto: str, quem: str = "usuario", anexos: list[str] | None = None
    ) -> Sessao:
        with self._operacoes:
            self.fallback.cancelar(id_)
            if quem == "usuario":
                self._dados.remover("fallback-tentativas", id_)
            return self._enviar(id_, texto, quem, anexos)

    def _enviar(self, id_: str, texto: str, quem: str, anexos: list[str] | None) -> Sessao:
        return sessoes_envio._enviar(self, id_, texto, quem, anexos)

    async def _trabalhar(self, s: Sessao, texto: str) -> None:
        await sessoes_envio._trabalhar(self, s, texto)

    def trocar(self, id_: str, motor: str, conta_id: str = "") -> tuple[Sessao, str]:
        with self._operacoes:
            self.fallback.cancelar(id_)
            self._consumir_eventos(id_)
            return self._trocar(id_, motor, conta_id)

    def _trocar(self, id_: str, motor: str, conta_id: str) -> tuple[Sessao, str]:
        return sessoes_envio._trocar(self, id_, motor, conta_id)

    def modelos_da_sessao(self, s: Sessao) -> list[dict[str, Any]]:
        """Os modelos que a conta da sessão oferece (com a versão), para a escolha no painel."""
        try:
            conta = contas.Contas().achar(s.conta) if s.conta else contas.Contas().em_uso(s.motor)
        except contas.ContaErro:
            return []
        return modelos.da_conta(conta)

    def ajustar_modelo(self, id_: str, modelo: str, esforco: str = "") -> Sessao:
        return sessoes_envio.ajustar_modelo(self, id_, modelo, esforco)

    def recarregar_conectores(self, id_: str, nomes: list[str]) -> Sessao:
        """Os conectores do projeto mudaram: o agente reabre com eles, retomando a conversa (os
        agentes só leem os MCPs ao iniciar)."""
        with self._operacoes:
            if id_ in self.trabalhando():
                raise SessaoErro("essa sessão está trabalhando; espere para trocar os conectores")
            if (terminal := self.terminais.pop(id_, None)) is not None:
                terminal.encerrar()  # reabre com os conectores novos, com resume
            self.anotar(id_, "sistema", f"Conectores: {', '.join(nomes) or 'nenhum'}.")
            return self.ler(id_)

    def continuar_interrompida(self, id_: str) -> Sessao:
        return sessoes_envio.continuar_interrompida(self, id_)

    def dispensar_interrompida(self, id_: str) -> Sessao:
        with self._operacoes:
            self.exigir_editavel(id_)
            return self._mudar(id_, interrompida="")

    def continuar(self, id_: str) -> Sessao:
        """Manda de novo o pedido que bateu no limite (depois de trocar de conta ou de agente)."""
        s = self.ler(id_)
        if not s.ultimo_pedido:
            raise SessaoErro("não há pedido para continuar")
        return self.enviar(id_, s.ultimo_pedido, quem="continuacao")

    def passagem(self, s: Sessao, motor: str) -> str:
        return sessoes_envio.passagem(self, s, motor)

    # --- o terminal real (ADR 0017) ---------------------------------------------------------

    def eventos(self, id_: str) -> Path:
        return self._dir(id_) / "eventos.jsonl"

    def _exigir_disponivel(self) -> None:
        if motivo := self.reservada():
            raise SessaoErro(motivo)

    def arquivada_em(self, id_: str) -> str:
        registro = self._dados.ler("autodesenvolvimento-arquivos", id_) or {}
        return str(registro.get("central", ""))

    def exigir_editavel(self, id_: str) -> None:
        sessoes_copia.exigir_editavel(self, id_)

    def escrever_terminal(self, id_: str, dados: bytes) -> None:
        with self._operacoes:
            self.fallback.cancelar(id_)
            self.exigir_editavel(id_)
            self._exigir_disponivel()
            terminal = self.terminais.get(id_)
            if terminal is None or not terminal.vivo:
                raise SessaoErro("O terminal desta sessão está fechado.")
            self.retomada_pendente.discard(id_)  # a pessoa está respondendo no terminal
            terminal.escrever(dados)

    def abrir_terminal(
        self, id_: str, pedido: str = "", colunas: int = 120, linhas: int = 32
    ) -> Terminal | TerminalRemoto:
        """O agente da sessão num terminal: o mesmo se já estiver aberto; senão, abre retomando a
        conversa nativa. Depois de uma troca de agente, a passagem chega sem gastar um turno:
        como contexto (hook do Claude; instruções do Codex numa conversa nova) ou, no Codex que
        retoma a própria conversa, colada no campo, sem Enter, e vai com o próximo pedido."""
        with self._operacoes:
            return self._abrir_terminal(id_, pedido, colunas, linhas)

    def _abrir_terminal(
        self, id_: str, pedido: str, colunas: int, linhas: int
    ) -> Terminal | TerminalRemoto:
        return sessoes_eventos._abrir_terminal(self, id_, pedido, colunas, linhas)

    def _contexto(self, id_: str, texto: str) -> Path | None:
        return sessoes_eventos._contexto(self, id_, texto)

    def _terminal_saiu(self, id_: str, codigo: int, *, resumo_chave: str = "") -> None:
        sessoes_eventos._terminal_saiu(self, id_, codigo, resumo_chave=resumo_chave)

    def _olhar_saida(self, id_: str, dados: bytes) -> None:
        sessoes_eventos._olhar_saida(self, id_, dados)

    def _vigiar_eventos(self) -> None:
        sessoes_eventos._vigiar_eventos(self)

    def _ler_eventos(self, id_: str) -> None:
        with self._operacoes:
            self._consumir_eventos(id_)

    def _consumir_eventos(self, id_: str) -> None:
        sessoes_eventos._consumir_eventos(self, id_)

    def _evento(self, id_: str, e: dict[str, Any]) -> None:
        sessoes_eventos._evento(self, id_, e)

    def _pedido(self, id_: str, texto: str) -> str:
        return sessoes_eventos._pedido(self, id_, texto)

    def _fim_do_turno(self, id_: str, resposta: str, conversa: str = "") -> None:
        sessoes_eventos._fim_do_turno(self, id_, resposta, conversa)

    def _registrar_custo(self, s: "Sessao", conversa: str) -> None:
        sessoes_eventos._registrar_custo(self, s, conversa)

    def excluir(self, id_: str) -> str:
        """Encerra o agente e exclui a sessão; alterações na cópia bloqueiam a exclusão.

        Uma branch conserva commits, não arquivos locais. Inclui os ignorados na checagem:
        uma configuração ou um resultado local também não pode desaparecer por engano.
        """
        with self._operacoes:
            return self._excluir(id_)

    def _encerrar_agente(self, id_: str, espera_s: float = 5.0) -> None:
        sessoes_copia._encerrar_agente(self, id_, espera_s)

    def _excluir(self, id_: str) -> str:
        return sessoes_copia._excluir(self, id_)

    def parar(self, id_: str) -> Sessao:
        with self._operacoes:
            self.fallback.cancelar(id_)
            if id_ in self._centralizando:
                raise SessaoErro("Unificação em andamento. Aguarde a conclusão.")
            terminal = self.terminais.get(id_)
            if terminal is not None and terminal.vivo:
                terminal.escrever(b"\x1b")  # Esc: os dois agentes interrompem o turno
                return self._mudar(id_, estado="parada")
            laco_tarefa = self.tarefas.get(id_)
            if laco_tarefa is None or laco_tarefa[1].done():
                raise SessaoErro("essa sessão não está trabalhando")
            laco, tarefa = laco_tarefa
            laco.call_soon_threadsafe(tarefa.cancel)
            return self.ler(id_)

    def copia(self, id_: str) -> dict[str, Any]:
        """Mudanças da cópia; uma consulta Git que falhou nunca significa cópia limpa."""
        with self._operacoes:
            return self._copia(self.ler(id_))

    def _copia(self, s: Sessao) -> dict[str, Any]:
        return sessoes_copia._copia(self, s)

    def _copia_parada(self, id_: str) -> Sessao:
        return sessoes_copia._copia_parada(self, id_)

    def aplicar_copia(self, id_: str) -> str:
        return sessoes_copia.aplicar_copia(self, id_)

    def descartar_copia(self, id_: str) -> str:
        return sessoes_copia.descartar_copia(self, id_)

    def mudancas(self, s: Sessao) -> str:
        """O que a sessão mudou na pasta dela (commits novos e o que ainda não foi commitado)."""
        onde = s.onde
        partes = []
        if s.base:
            partes.append(_git(onde, "diff", "--stat", f"{s.base}..HEAD").stdout.strip())
        partes.append(_git(onde, "status", "--short").stdout.strip())
        return "\n".join(p for p in partes if p)[:2000]


# --- motor Claude ---------------------------------------------------------------------------


async def rodar_claude(sessoes: Sessoes, s: Sessao, texto: str) -> str:
    """Uma rodada do Claude Code na pasta da sessão; devolve o resumo falável."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        PermissionResultAllow,
        PermissionResultDeny,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
    from claude_agent_sdk.types import ToolPermissionContext

    externos = conectores_do_projeto(s)
    arquivo_mcp = arquivo_de_conectores(sessoes._dir(s.id) / CONECTORES, externos)

    async def pode(
        nome: str, entrada: dict[str, Any], _ctx: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        if pede_aprovacao(nome, externos):
            return PermissionResultDeny(message=SEM_APROVACAO)
        if nome == "Bash" and comando_proibido(str(entrada.get("command", ""))):
            sessoes.anotar(s.id, "sistema", f"Recusei: {str(entrada.get('command'))[:160]}")
            return PermissionResultDeny(
                message="Comando proibido nesta oficina; não tente outro jeito."
            )
        if nome in ("Task", "Agent"):
            return PermissionResultDeny(message="Nesta oficina o agente não delega.")
        return PermissionResultAllow()

    extra, pasta_skills = regras_de_skills(sessoes.skills)
    regras = REGRAS + extra + aimemory.orientacao(Path(s.pasta))
    pastas_extras: list[str | Path] = [sessoes.pasta_de_anexos(s.id)]
    if pasta_skills is not None:
        pastas_extras.append(pasta_skills)
    opcoes = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": regras},
        cwd=str(s.onde),
        add_dirs=pastas_extras,
        permission_mode="acceptEdits",
        can_use_tool=pode,
        setting_sources=["project"],
        strict_mcp_config=True,
        mcp_servers=str(arquivo_mcp) if arquivo_mcp else {},
        allowed_tools=list(externos.livres),
        resume=s.sdk_sessao or None,
        model=s.modelo or None,
        disallowed_tools=["Task", "Agent", *externos.bloqueadas],
        # O ai-memory recebe o que a sessão faz (ADR 0016): os hooks dele só nesta sessão.
        settings=json.dumps(hooks) if (hooks := aimemory.hooks_claude()) else None,
        env=ambiente_para_sdk(s),
    )
    ultimo = ""
    async with ClaudeSDKClient(options=opcoes) as cliente:
        await cliente.query(texto)
        async for msg in cliente.receive_response():
            if isinstance(msg, AssistantMessage):
                if msg.error in ("rate_limit", "billing_error"):
                    raise LimiteErro(msg.error)
                for bloco in msg.content:
                    if isinstance(bloco, TextBlock) and bloco.text.strip():
                        ultimo = bloco.text
                        sessoes.anotar(s.id, "agente", bloco.text)
                    elif isinstance(bloco, ToolUseBlock):
                        sessoes.anotar(
                            s.id, "ferramenta", _descrever_ferramenta(bloco.name, bloco.input)
                        )
            elif isinstance(msg, ResultMessage):
                sessoes._mudar(s.id, sdk_sessao=msg.session_id)
                if msg.is_error and LIMITE.search(f"{msg.result or ''} {msg.subtype or ''}"):
                    raise LimiteErro(msg.result or msg.subtype or "limite")
                if msg.is_error:
                    raise RuntimeError(msg.subtype or "erro")
                if LIMITE.search(ultimo) and len(ultimo) < 300:  # "usage limit reached|…"
                    raise LimiteErro(ultimo)
    return _resumo_de(ultimo) if ultimo else "terminou sem dizer nada"


# --- motor Codex ----------------------------------------------------------------------------


async def rodar_codex(sessoes: Sessoes, s: Sessao, texto: str) -> str:
    """Uma rodada do Codex na pasta da sessão, pelo `codex exec --json`; devolve o resumo falável.
    A conta é a pasta de login da sessão (CODEX_HOME); as regras vão na primeira mensagem."""
    if not s.sdk_sessao:
        texto = f"{REGRAS.strip()}\n\nPedido:\n{texto}"
    conectores, segredos = conectores_codex(conectores_do_projeto(s))
    processo = await asyncio.create_subprocess_exec(
        *_comando_codex(s, texto, conectores),
        cwd=s.onde,
        env=ambiente_do_agente(s, segredos),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=16 * 1024 * 1024,  # uma linha de evento pode trazer a saída inteira de um comando
    )
    ultimo, erro = "", ""
    try:
        assert processo.stdout is not None  # noqa: S101 (criado com PIPE acima)
        async for linha in processo.stdout:
            try:
                evento = json.loads(linha)
            except ValueError:
                continue
            tipo, item = evento.get("type"), evento.get("item") or {}
            if tipo == "thread.started" and evento.get("thread_id"):
                sessoes._mudar(s.id, sdk_sessao=str(evento["thread_id"]))
            elif tipo == "item.completed" and item.get("type") == "agent_message":
                if texto_agente := str(item.get("text", "")).strip():
                    ultimo = texto_agente
                    sessoes.anotar(s.id, "agente", texto_agente)
            elif tipo == "item.started" and item.get("type") == "command_execution":
                sessoes.anotar(s.id, "ferramenta", f"$ {str(item.get('command', ''))[:160]}")
            elif tipo == "item.completed" and item.get("type") == "file_change":
                arquivos = [str(m.get("path", "")) for m in item.get("changes", [])]
                sessoes.anotar(s.id, "ferramenta", "Editou " + ", ".join(arquivos)[:200])
            elif tipo in ("turn.failed", "error"):
                erro = str((evento.get("error") or {}).get("message") or evento.get("message"))
        await processo.wait()
    except asyncio.CancelledError:
        processo.terminate()
        raise
    if erro and LIMITE_CODEX.search(erro):
        raise LimiteErro(erro[:200])
    if erro and not ultimo:
        raise RuntimeError(erro[:200])
    if processo.returncode and not ultimo:
        raise RuntimeError(f"codex saiu com {processo.returncode}")
    return _resumo_de(ultimo) if ultimo else "terminou sem dizer nada"


async def rodar_agente(sessoes: Sessoes, s: Sessao, texto: str) -> str:
    """O motor da sessão: Claude (Agent SDK) ou Codex (`codex exec`)."""
    if s.motor == "codex":
        return await rodar_codex(sessoes, s, texto)
    return await rodar_claude(sessoes, s, texto)


# --- terminal real (ADR 0017) ---------------------------------------------------------------
