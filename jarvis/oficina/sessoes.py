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
import shutil
import subprocess
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis import fuso
from jarvis.memoria import aimemory

log = logging.getLogger(__name__)
FUSO = fuso.local()
MAXIMO_TRABALHANDO = 3
MOTORES = ("claude",)  # o Codex entra na fase 4
ESTADOS = ("parada", "trabalhando", "erro")
LIMITE_MENSAGEM = 8000
LIMITE_ANEXO = 20 * 1024 * 1024
LIMITE_ARQUIVO = 512 * 1024
# O que dá para arrastar ou colar numa sessão (o Claude Code lê imagens e PDFs).
TIPOS_ANEXO = {
    *(".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"),
    *(".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".toml", ".log", ".html", ".css", ".xml"),
    *(".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".sh", ".sql", ".java", ".kt", ".swift"),
}
TIPOS_ARQUIVO = (".md", ".txt")
REGRAS = """
Você é um agente de código de uma sessão da oficina do Zé, o assistente pessoal do usuário.
O pedido vem dele (às vezes repassado pelo Zé). Trabalhe só dentro desta pasta. Não delegue a
outros agentes, não faça push e não mexa em nada fora do projeto. Rode os testes do projeto
quando mudar código. Ao terminar, a sua última mensagem começa com uma frase curta, em
português, dizendo o que foi feito (o Zé a lê em voz alta), e depois os detalhes.
"""
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
    modelo: str = ""
    isolada: bool = False
    worktree: str = ""
    branch: str = ""
    base: str = ""  # o commit de onde a cópia isolada saiu
    estado: str = "parada"
    criada: str = field(default_factory=agora)
    atualizada: str = field(default_factory=agora)
    resumo: str = ""  # o último recado do agente, curto (a lista e a voz)
    sdk_sessao: str = ""  # para continuar a conversa do Claude Code (resume)
    origem: str = "painel"

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


class Sessoes:
    def __init__(
        self,
        pasta: Path,
        raizes: tuple[Path, ...],
        ao_terminar: Callable[[Sessao, str], None] | None = None,
        rodar: Callable[["Sessoes", Sessao, str], Any] | None = None,
        projetos_novos: Path | None = None,
        skills: Any = None,
    ) -> None:
        self.skills = (
            skills  # as skills do usuário (habilidades.skills.Skills): sessões também leem
        )
        self.pasta = pasta  # ~/.local/share/zervis/sessoes
        self.projetos_novos = projetos_novos  # onde nasce um projeto criado com a sessão
        self.raizes = tuple(r.expanduser().resolve() for r in raizes)
        self.ao_terminar = ao_terminar
        self.rodar = rodar or rodar_claude
        self.trava = threading.Lock()
        self.tarefas: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task[None]]] = {}
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Uma sessão que estava trabalhando quando o Zé caiu não está mais.
        for s in self.listar():
            if s.estado == "trabalhando":
                s.estado = "parada"
                self._gravar(s)
                self.anotar(s.id, "sistema", "O Zé reiniciou no meio do trabalho; peça de novo.")

    # --- disco ---------------------------------------------------------------------------

    def _dir(self, id_: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{8}", id_):
            raise SessaoErro("sessão desconhecida")
        return self.pasta / id_

    def _gravar(self, s: Sessao) -> None:
        d = self._dir(s.id)
        d.mkdir(exist_ok=True, mode=0o700)
        temporario = d / "sessao.next"
        temporario.write_text(json.dumps(asdict(s), ensure_ascii=False, indent=1))
        temporario.replace(d / "sessao.json")

    def ler(self, id_: str) -> Sessao:
        try:
            return Sessao(**json.loads((self._dir(id_) / "sessao.json").read_text()))
        except (OSError, ValueError, TypeError):
            raise SessaoErro("sessão desconhecida") from None

    def listar(self) -> list[Sessao]:
        sessoes = []
        for arquivo in self.pasta.glob("*/sessao.json"):
            with contextlib.suppress(OSError, ValueError, TypeError):
                sessoes.append(Sessao(**json.loads(arquivo.read_text())))
        return sorted(sessoes, key=lambda s: s.atualizada, reverse=True)

    def mensagens(self, id_: str, desde: int = 0) -> list[dict[str, Any]]:
        try:
            linhas = (self._dir(id_) / "mensagens.jsonl").read_text().splitlines()
        except OSError:
            return []
        saida = []
        for linha in linhas[desde:]:
            with contextlib.suppress(ValueError):
                saida.append(json.loads(linha))
        return saida

    def anotar(self, id_: str, quem: str, texto: str, anexos: list[str] | None = None) -> None:
        texto = texto.strip()[:LIMITE_MENSAGEM]
        if not texto:
            return
        linha: dict[str, Any] = {"em": agora(), "quem": quem, "texto": texto}
        if anexos:
            linha["anexos"] = anexos
        with self.trava, (self._dir(id_) / "mensagens.jsonl").open("a") as f:
            f.write(json.dumps(linha, ensure_ascii=False))
            f.write("\n")

    def pasta_de_anexos(self, id_: str) -> Path:
        return self._dir(id_) / "anexos"

    def anexar(self, id_: str, nome: str, dados: bytes) -> str:
        """Guarda um arquivo arrastado ou uma imagem colada; devolve o nome guardado."""
        self.ler(id_)
        base = Path(nome).name.strip() or "colado.png"
        sufixo = Path(base).suffix.lower()
        if sufixo not in TIPOS_ANEXO:
            raise SessaoErro(f"tipo de arquivo não aceito: {sufixo or 'sem extensão'}")
        if not dados or len(dados) > LIMITE_ANEXO:
            raise SessaoErro("arquivo vazio ou maior que 20 MB")
        limpo = re.sub(r"[^\w.-]+", "_", Path(base).stem)[:60].strip("._") or "anexo"
        pasta = self.pasta_de_anexos(id_)
        pasta.mkdir(exist_ok=True, mode=0o700)
        guardado = f"{datetime.now(FUSO):%H%M%S}-{uuid.uuid4().hex[:4]}-{limpo}{sufixo}"
        (pasta / guardado).write_bytes(dados)
        return guardado

    def criar_arquivo(self, id_: str, nome: str, conteudo: str, sobrescrever: bool = False) -> str:
        """Um .md (ou .txt) escrito pelo usuário direto na pasta da sessão."""
        s = self.ler(id_)
        relativo = Path(nome.strip().lstrip("/"))
        if not relativo.parts or any(p in ("..", "") or p.startswith(".") for p in relativo.parts):
            raise SessaoErro("nome inválido: use algo como NOTAS.md ou docs/ideia.md")
        if relativo.suffix.lower() not in TIPOS_ARQUIVO:
            relativo = relativo.with_name(relativo.name + ".md")
        if len(conteudo.encode()) > LIMITE_ARQUIVO:
            raise SessaoErro("conteúdo grande demais (máximo 512 KB)")
        destino = (s.onde / relativo).resolve()
        if s.onde.resolve() not in destino.parents:
            raise SessaoErro("o arquivo precisa ficar dentro da pasta da sessão")
        if destino.exists() and not sobrescrever:
            raise SessaoErro(f"{relativo} já existe; marque substituir para trocar")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo if conteudo.endswith("\n") else conteudo + "\n")
        self.anotar(id_, "sistema", f"Você criou {relativo} na pasta da sessão.")
        return str(relativo)

    def _mudar(self, id_: str, **campos: Any) -> Sessao:
        with self.trava:
            s = self.ler(id_)
            for chave, valor in campos.items():
                setattr(s, chave, valor)
            s.atualizada = agora()
            self._gravar(s)
            return s

    # --- criar, conversar, parar ---------------------------------------------------------

    def _pasta_permitida(self, pasta: str) -> Path:
        caminho = Path(pasta).expanduser().resolve()
        if not caminho.is_dir():
            raise SessaoErro("essa pasta não existe")
        raiz = next((r for r in self.raizes if caminho == r or r in caminho.parents), None)
        if raiz is None:
            raise SessaoErro("essa pasta está fora das pastas permitidas")
        if any(parte.startswith(".") for parte in caminho.relative_to(raiz).parts):
            raise SessaoErro("pastas ocultas (configurações, chaves) não viram sessão")
        return caminho

    def criar(
        self,
        nome: str,
        pasta: str,
        motor: str = "claude",
        modelo: str = "",
        isolada: bool = False,
        origem: str = "painel",
    ) -> Sessao:
        nome = " ".join(nome.split())[:60]
        caminho = self._pasta_permitida(pasta)
        if motor not in MOTORES:
            raise SessaoErro(f"motor desconhecido: {motor}")
        s = Sessao(
            id=uuid.uuid4().hex[:8],
            nome=nome or caminho.name,
            pasta=str(caminho),
            motor=motor,
            modelo=modelo.strip(),
            isolada=isolada,
            origem=origem,
        )
        if isolada:
            if _git(caminho, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
                raise SessaoErro("a cópia isolada precisa de um projeto com git")
            destino = self.pasta / s.id / "copia"
            s.branch = f"ze/{s.id}"
            feito = _git(caminho, "worktree", "add", "-b", s.branch, str(destino), "HEAD")
            if feito.returncode != 0:
                raise SessaoErro(
                    "não consegui criar a cópia isolada: " + feito.stderr.strip()[:120]
                )
            s.worktree = str(destino)
            s.base = _git(caminho, "rev-parse", "HEAD").stdout.strip()
        self._gravar(s)
        onde = f"numa cópia isolada (branch {s.branch})" if isolada else "direto na pasta"
        self.anotar(s.id, "sistema", f"Sessão criada em {caminho}, {onde}, com o {motor}.")
        return s

    def criar_projeto(self, nome: str) -> Path:
        """Uma pasta nova para a sessão trabalhar: com git, README e o primeiro commit."""
        if self.projetos_novos is None:
            raise SessaoErro("sem pasta para projetos novos")
        nome = " ".join(nome.split())
        pasta_nome = re.sub(r"[^\w.-]+", "-", nome).strip("-.")[:60]
        if not pasta_nome:
            raise SessaoErro("dê um nome ao projeto")
        destino = self.projetos_novos.expanduser() / pasta_nome
        if destino.exists():
            raise SessaoErro(f"já existe uma pasta {pasta_nome}; escolha como pasta existente")
        destino.mkdir(parents=True)
        (destino / "README.md").write_text(f"# {nome}\n")
        for args in (["init", "-q"], ["add", "README.md"], ["commit", "-qm", "Início do projeto"]):
            _git(destino, *args)
        return destino

    def trabalhando(self) -> list[str]:
        return [id_ for id_, (_, t) in self.tarefas.items() if not t.done()]

    def enviar(
        self, id_: str, texto: str, quem: str = "usuario", anexos: list[str] | None = None
    ) -> Sessao:
        texto = texto.strip()
        anexos = list(anexos or [])
        if not texto and not anexos:
            raise SessaoErro("mensagem vazia")
        s = self.ler(id_)
        pasta = self.pasta_de_anexos(id_)
        caminhos = []
        for nome in anexos:
            caminho = pasta / Path(nome).name
            if Path(nome).name != nome or not caminho.is_file():
                raise SessaoErro(f"anexo não encontrado: {nome}")
            caminhos.append(str(caminho))
        if id_ in self.trabalhando():
            raise SessaoErro("essa sessão ainda está trabalhando; espere ou pare")
        if len(self.trabalhando()) >= MAXIMO_TRABALHANDO:
            raise SessaoErro(f"já há {MAXIMO_TRABALHANDO} sessões trabalhando")
        self.anotar(id_, quem, texto or "(anexos)", anexos)
        if caminhos:  # o agente recebe os caminhos; imagens e PDFs ele lê com o Read
            lista = "\n".join(f"- {c}" for c in caminhos)
            texto = f"{texto}\n\nAnexos do usuário (leia antes de responder):\n{lista}".strip()
        s = self._mudar(id_, estado="trabalhando")
        laco = asyncio.new_event_loop()
        pronto = threading.Event()

        def rodar() -> None:
            asyncio.set_event_loop(laco)
            tarefa = laco.create_task(self._trabalhar(s, texto))
            self.tarefas[id_] = (laco, tarefa)
            pronto.set()
            with contextlib.suppress(asyncio.CancelledError):
                laco.run_until_complete(tarefa)
            laco.close()

        threading.Thread(target=rodar, name=f"sessao-{id_}", daemon=True).start()
        pronto.wait(5)
        return s

    async def _trabalhar(self, s: Sessao, texto: str) -> None:
        resumo, estado = "", "parada"
        try:
            resumo = str(await self.rodar(self, s, texto) or "")
        except asyncio.CancelledError:
            self.anotar(s.id, "sistema", "Parada a pedido.")
            self._mudar(s.id, estado="parada")
            raise
        except Exception as erro:
            log.exception("sessão %s falhou", s.id)
            estado, resumo = "erro", f"falhou: {type(erro).__name__}"
            self.anotar(s.id, "sistema", f"O agente falhou ({type(erro).__name__}).")
        if s.worktree and estado != "erro" and (mudou := self.mudancas(s)):
            self.anotar(s.id, "sistema", f"Mudanças na branch {s.branch}:\n{mudou}")
        final = self._mudar(s.id, estado=estado, resumo=resumo[:300])
        if self.ao_terminar is not None:
            try:
                self.ao_terminar(final, resumo)
            except Exception:
                log.exception("aviso do fim da sessão falhou")

    def excluir(self, id_: str) -> str:
        """Apaga a sessão (conversa e anexos). A pasta do projeto fica; a cópia isolada sai,
        mas a branch dela fica no projeto, para nada do trabalho se perder."""
        s = self.ler(id_)
        if id_ in self.trabalhando():
            raise SessaoErro("pare a sessão antes de excluir")
        aviso = ""
        if s.worktree:
            _git(Path(s.pasta), "worktree", "remove", "--force", s.worktree)
            _git(Path(s.pasta), "worktree", "prune")
            aviso = f"A branch {s.branch} continua no projeto."
        shutil.rmtree(self._dir(id_), ignore_errors=True)
        self.tarefas.pop(id_, None)
        return aviso

    def parar(self, id_: str) -> Sessao:
        laco_tarefa = self.tarefas.get(id_)
        if laco_tarefa is None or laco_tarefa[1].done():
            raise SessaoErro("essa sessão não está trabalhando")
        laco, tarefa = laco_tarefa
        laco.call_soon_threadsafe(tarefa.cancel)
        return self.ler(id_)

    def mudancas(self, s: Sessao) -> str:
        """O que a sessão mudou na pasta dela (commits novos e o que ainda não foi commitado)."""
        onde = s.onde
        partes = []
        if s.base:
            partes.append(_git(onde, "diff", "--stat", f"{s.base}..HEAD").stdout.strip())
        partes.append(_git(onde, "status", "--short").stdout.strip())
        return "\n".join(p for p in partes if p)[:2000]


# --- motor Claude ---------------------------------------------------------------------------


def _resumo_de(texto: str) -> str:
    primeira = re.split(r"(?<=[.!?])\s|\n", texto.strip(), maxsplit=1)[0]
    return primeira[:240]


def _descrever_ferramenta(nome: str, entrada: dict[str, Any]) -> str:
    if nome == "Bash":
        return f"$ {str(entrada.get('command', ''))[:160]}"
    alvo = entrada.get("file_path") or entrada.get("path") or entrada.get("pattern") or ""
    return f"{nome} {alvo}".strip()[:200]


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

    async def pode(
        nome: str, entrada: dict[str, Any], _ctx: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        if nome == "Bash" and comando_proibido(str(entrada.get("command", ""))):
            sessoes.anotar(s.id, "sistema", f"Recusei: {str(entrada.get('command'))[:160]}")
            return PermissionResultDeny(
                message="Comando proibido nesta oficina; não tente outro jeito."
            )
        if nome in ("Task", "Agent"):
            return PermissionResultDeny(message="Nesta oficina o agente não delega.")
        return PermissionResultAllow()

    regras = REGRAS
    pastas_extras: list[str | Path] = [sessoes.pasta_de_anexos(s.id)]
    if sessoes.skills is not None and sessoes.skills.listar():
        regras += (
            "\nO usuário tem skills: procedimentos do jeito dele. Antes de uma tarefa que uma "
            f"delas cobre, leia {sessoes.skills.pasta}/<nome>/SKILL.md e siga.\n"
            + sessoes.skills.catalogo()
        )
        pastas_extras.append(sessoes.skills.pasta)
    opcoes = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": regras},
        cwd=str(s.onde),
        add_dirs=pastas_extras,
        permission_mode="acceptEdits",
        can_use_tool=pode,
        setting_sources=["project"],
        strict_mcp_config=True,
        resume=s.sdk_sessao or None,
        model=s.modelo or None,
        disallowed_tools=["Task", "Agent", "WebSearch"],
        # O ai-memory recebe o que a sessão faz (ADR 0016): os hooks dele só nesta sessão.
        settings=json.dumps(hooks) if (hooks := aimemory.hooks_claude()) else None,
    )
    ultimo = ""
    async with ClaudeSDKClient(options=opcoes) as cliente:
        await cliente.query(texto)
        async for msg in cliente.receive_response():
            if isinstance(msg, AssistantMessage):
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
                if msg.is_error:
                    raise RuntimeError(msg.subtype or "erro")
    return _resumo_de(ultimo) if ultimo else "terminou sem dizer nada"
