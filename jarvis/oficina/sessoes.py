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
import os
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
from jarvis.cerebro import contas, modelos
from jarvis.memoria import aimemory

log = logging.getLogger(__name__)
FUSO = fuso.local()
MAXIMO_TRABALHANDO = 3
MOTORES = ("claude", "codex")
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
    conta: str = ""  # a conta do agente (jarvis.cerebro.contas); vazio: a que o Zé usa agora
    modelo: str = ""  # vazio: o padrão da conta
    esforco: str = ""  # esforço de raciocínio (Codex); vazio: o padrão do modelo
    isolada: bool = False
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
        self.rodar = rodar or rodar_agente
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
            conta=contas.Contas().em_uso(motor).id,
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
        if quem == "continuacao":  # o mesmo pedido de novo, noutra conta: anotado como do Zé
            self.anotar(id_, "sistema", f"Continuando o pedido: {texto[:300]}")
        else:
            self.anotar(id_, quem, texto or "(anexos)", anexos)
        if quem == "usuario":
            self._mudar(id_, ultimo_pedido=texto)
        if caminhos:  # o agente recebe os caminhos; imagens e PDFs ele lê com o Read
            lista = "\n".join(f"- {c}" for c in caminhos)
            texto = f"{texto}\n\nAnexos do usuário (leia antes de responder):\n{lista}".strip()
        if s.passagem:  # depois de uma troca: o agente novo recebe o que perdeu
            texto = f"{s.passagem}\n\nPedido agora:\n{texto}"
        s = self._mudar(id_, estado="trabalhando", passagem="", limite=False)
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
        except LimiteErro:
            conta = _nome_da_conta(s)
            estado, resumo = "erro", f"a conta {conta} do {NOMES_MOTORES[s.motor]} bateu o limite"
            self._mudar(s.id, limite=True)
            self.anotar(
                s.id,
                "sistema",
                f"A conta {conta} atingiu o limite de uso. Troque de conta ou de agente para "
                "continuar: a conversa segue.",
            )
        except Exception as erro:
            log.exception("sessão %s falhou", s.id)
            estado, resumo = "erro", f"falhou: {type(erro).__name__}"
            self.anotar(s.id, "sistema", f"O agente falhou ({type(erro).__name__}).")
        if s.worktree and estado != "erro" and (mudou := self.mudancas(s)):
            self.anotar(s.id, "sistema", f"Mudanças na branch {s.branch}:\n{mudou}")
        atual = self.ler(s.id)
        final = self._mudar(
            s.id,
            estado=estado,
            resumo=resumo[:300],
            fios={**atual.fios, atual.motor: atual.sdk_sessao} if atual.sdk_sessao else atual.fios,
            vistos={**atual.vistos, atual.motor: len(self.mensagens(s.id))},
        )
        if self.ao_terminar is not None:
            try:
                self.ao_terminar(final, resumo)
            except Exception:
                log.exception("aviso do fim da sessão falhou")

    def trocar(self, id_: str, motor: str, conta_id: str = "") -> tuple[Sessao, str]:
        """Troca o agente ou a conta de uma sessão parada, sem perder a conversa (ADR 0016).

        Mesmo agente, outra conta: a conversa nativa é copiada para a pasta da conta nova e o
        agente a retoma inteira. Outro agente: ele retoma a conversa dele nesta sessão, se houver,
        e o próximo pedido leva a passagem do que aconteceu desde a última vez dele."""
        s = self.ler(id_)
        if id_ in self.trabalhando():
            raise SessaoErro("essa sessão está trabalhando; pare antes de trocar")
        if motor not in MOTORES:
            raise SessaoErro(f"agente desconhecido: {motor}")
        cs = contas.Contas()
        try:
            nova = cs.achar(conta_id) if conta_id else cs.em_uso(motor)
        except contas.ContaErro as erro:
            raise SessaoErro(str(erro)) from None
        if nova.agente != motor:
            raise SessaoErro("essa conta é de outro agente")
        fios = {**s.fios, **({s.motor: s.sdk_sessao} if s.sdk_sessao else {})}
        fio = fios.get(motor, "")
        if fio and not copiar_conversa(motor, fio, cs.listar(motor), nova):
            fio = ""  # a conversa nativa sumiu: segue pela passagem
        passagem = ""
        if motor != s.motor or not fio:
            passagem = self.passagem(s, motor)
        # O modelo escolhido só segue se a conta nova também o oferece.
        mantem = motor == s.motor and any(m["id"] == s.modelo for m in modelos.da_conta(nova))
        s = self._mudar(
            id_,
            motor=motor,
            conta=nova.id,
            sdk_sessao=fio,
            fios=fios,
            passagem=passagem,
            modelo=s.modelo if mantem else "",
            esforco=s.esforco if mantem else "",
        )
        como = (
            "continua a mesma conversa"
            if fio and not passagem
            else "retoma a conversa dele e recebe o que mudou"
            if fio
            else "recebe a passagem do que já foi feito"
        )
        aviso = f"Agora com o {NOMES_MOTORES[motor]} · {nova.nome}: {como}."
        self.anotar(id_, "sistema", aviso)
        return s, aviso

    def ajustar_modelo(self, id_: str, modelo: str, esforco: str = "") -> Sessao:
        """O modelo (e o esforço, no Codex) dos próximos pedidos; a conversa continua."""
        s = self.ler(id_)
        if id_ in self.trabalhando():
            raise SessaoErro("essa sessão está trabalhando; espere para trocar o modelo")
        try:
            conta = contas.Contas().achar(s.conta) if s.conta else contas.Contas().em_uso(s.motor)
        except contas.ContaErro:
            conta = contas.Contas().em_uso(s.motor)
        opcoes = {m["id"]: m for m in modelos.da_conta(conta)}
        if modelo and modelo not in opcoes:
            raise SessaoErro("esse modelo não está disponível nesta conta")
        if esforco and esforco not in (opcoes.get(modelo, {}).get("esforcos") or modelos.ESFORCOS):
            raise SessaoErro("esse esforço não vale para este modelo")
        s = self._mudar(id_, modelo=modelo, esforco=esforco if s.motor == "codex" else "")
        nome = opcoes[modelo]["nome"] if modelo else "o padrão da conta"
        extra = f", esforço {modelos.ESFORCOS[esforco].lower()}" if s.esforco else ""
        self.anotar(id_, "sistema", f"Modelo: {nome}{extra}.")
        return s

    def continuar(self, id_: str) -> Sessao:
        """Manda de novo o pedido que bateu no limite (depois de trocar de conta ou de agente)."""
        s = self.ler(id_)
        if not s.ultimo_pedido:
            raise SessaoErro("não há pedido para continuar")
        return self.enviar(id_, s.ultimo_pedido, quem="continuacao")

    def passagem(self, s: Sessao, motor: str) -> str:
        """O que o agente que assume precisa saber: o objetivo, o que aconteceu desde a última vez
        dele (as mensagens visíveis, com tamanho limitado) e o estado do git agora."""
        todas = self.mensagens(s.id)
        objetivo = next((m["texto"] for m in todas if m["quem"] == "usuario"), "")[:600]
        rotulos = {"usuario": "usuário", "agente": "agente", "ferramenta": "ação", "sistema": "Zé"}
        linhas = [
            f"- {rotulos.get(m['quem'], m['quem'])}: {' '.join(m['texto'].split())[:700]}"
            for m in todas[s.vistos.get(motor, 0) :]
        ]
        recente: list[str] = []
        total = 0
        for linha in reversed(linhas):  # do fim para o começo, até ~8 mil caracteres
            if total + len(linha) > 8000:
                break
            recente.insert(0, linha)
            total += len(linha)
        git = "\n".join(
            p
            for p in (
                _git(s.onde, "log", "--oneline", "-5").stdout.strip(),
                _git(s.onde, "status", "--short").stdout.strip(),
            )
            if p
        )
        anterior = NOMES_MOTORES.get(s.motor, s.motor)
        return (
            f"[Passagem do Zé] Você assume esta sessão de código, que estava com o {anterior}. "
            f"Objetivo da sessão (o primeiro pedido): {objetivo}\n"
            f"O que aconteceu desde a sua última vez aqui:\n{chr(10).join(recente) or '- nada'}\n"
            f"Estado do git agora:\n{git or 'sem git ou sem mudanças'}\n"
            "Use isso para continuar sem refazer o que já foi feito."
        )

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


def ambiente_da_conta(s: Sessao) -> dict[str, str]:
    """A pasta de login da conta desta sessão; sem conta, a que o processo já usa."""
    if not s.conta:
        return {}
    try:
        conta = contas.Contas().achar(s.conta)
    except contas.ContaErro:
        return {}
    variavel = contas.VARIAVEIS[conta.agente]
    if conta.pasta:
        return {variavel: conta.pasta}
    # A conta padrão quando o processo aponta para outra: de volta para a padrão.
    return {variavel: str(conta.onde)} if os.environ.get(variavel) else {}


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
        env=ambiente_da_conta(s),
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


# Como os agentes avisam que a conta acabou: o Codex ("You've hit your usage limit", "rate limit
# reached", "insufficient_quota") e o Claude ("Claude AI usage limit reached", "credit balance is
# too low", "out of extra usage").
LIMITE = re.compile(
    r"usage limit|rate limit|quota|credit balance|out of (extra )?usage|limite de uso",
    re.IGNORECASE,
)
LIMITE_CODEX = LIMITE


def _comando_codex(s: Sessao, texto: str) -> list[str]:
    """`codex exec` na primeira vez, `codex exec resume <id>` depois. Escreve só na pasta da
    sessão (os anexos ele lê de onde estão; liberar escrita numa pasta que ainda não existe
    derruba o isolamento inteiro do Codex, visto em 12/10/2026)."""
    comum = ["--json", "--skip-git-repo-check", "-c", 'sandbox_mode="workspace-write"']
    if s.modelo:
        comum += ["-m", s.modelo]
    if s.esforco:
        comum += ["-c", f'model_reasoning_effort="{s.esforco}"']
    if s.sdk_sessao:
        return ["codex", "exec", "resume", *comum, s.sdk_sessao, texto]
    return ["codex", "exec", *comum, texto]


async def rodar_codex(sessoes: Sessoes, s: Sessao, texto: str) -> str:
    """Uma rodada do Codex na pasta da sessão, pelo `codex exec --json`; devolve o resumo falável.
    A conta é a pasta de login da sessão (CODEX_HOME); as regras vão na primeira mensagem."""
    if not s.sdk_sessao:
        texto = f"{REGRAS.strip()}\n\nPedido:\n{texto}"
    processo = await asyncio.create_subprocess_exec(
        *_comando_codex(s, texto),
        cwd=s.onde,
        env={**os.environ, **ambiente_da_conta(s)},
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


NOMES_MOTORES = {"claude": "Claude", "codex": "Codex"}


def _nome_da_conta(s: Sessao) -> str:
    try:
        return contas.Contas().achar(s.conta).nome if s.conta else "em uso"
    except contas.ContaErro:
        return "em uso"


def _arquivo_da_conversa(motor: str, fio: str, onde: Path) -> Path | None:
    """Onde o próprio agente guarda a conversa: o Claude em `projects/<pasta>/<id>.jsonl`, o
    Codex em `sessions/AAAA/MM/DD/rollout-...-<id>.jsonl`."""
    padrao = f"projects/*/{fio}.jsonl" if motor == "claude" else f"sessions/**/*{fio}.jsonl"
    return next(iter(sorted(onde.glob(padrao))), None)


def copiar_conversa(motor: str, fio: str, todas: list[contas.Conta], nova: contas.Conta) -> bool:
    """Põe a conversa nativa `fio` na pasta da conta nova, copiando de onde ela estiver (testado em
    10/10/2026: o agente retoma a conversa em outra conta). True se ela está lá."""
    if _arquivo_da_conversa(motor, fio, nova.onde) is not None:
        return True
    for conta in todas:
        origem = _arquivo_da_conversa(motor, fio, conta.onde)
        if origem is None:
            continue
        destino = nova.onde / origem.relative_to(conta.onde)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        return True
    return False
