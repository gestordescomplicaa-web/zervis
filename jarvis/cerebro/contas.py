"""As contas dos agentes (ADR 0016): cada conta é uma pasta de login do próprio agente.

O Claude Code guarda o login em `CLAUDE_CONFIG_DIR` (padrão `~/.claude`) e o Codex em `CODEX_HOME`
(padrão `~/.codex`). Uma conta nova é só outra pasta, criada pelo Zé em `<dados>/contas/`; o login
quem faz é a pessoa, no próprio agente (o Zé abre o terminal com o comando certo). A pasta padrão
é sempre a primeira conta de cada agente, sem cadastro.

O Zé lê de cada pasta só o que a tela mostra: se há login, o e-mail (mascarado) e o plano.
"""

import base64
import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "contas.json"
PASTA = lugares.DADOS / "contas"
NOMES = {"claude": "Claude", "codex": "Codex"}
VARIAVEIS = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME"}
ORIGINAL = {v: os.environ.get(v, "") for v in VARIAVEIS.values()}
PADRAO = "padrao"


class ContaErro(ValueError):
    pass


@dataclass(frozen=True)
class Conta:
    id: str
    agente: str
    nome: str
    pasta: str = ""  # vazio: a pasta padrão do agente

    @property
    def onde(self) -> Path:
        if self.pasta:
            return Path(self.pasta)
        if self.agente == "claude":
            return Path(ORIGINAL["CLAUDE_CONFIG_DIR"] or "~/.claude").expanduser()
        return Path(ORIGINAL["CODEX_HOME"] or "~/.codex").expanduser()

    @property
    def login(self) -> Path:
        return self.onde / (".credentials.json" if self.agente == "claude" else "auth.json")

    def ambiente(self) -> dict[str, str]:
        """A variável que aponta o agente para esta conta (vazio na pasta padrão)."""
        return {VARIAVEIS[self.agente]: self.pasta} if self.pasta else {}

    def comando_login(self) -> list[str]:
        variavel = [f"{VARIAVEIS[self.agente]}={self.pasta}"] if self.pasta else []
        agente = ["claude"] if self.agente == "claude" else ["codex", "login", "--device-auth"]
        return ["env", *variavel, *agente]


def _mascarar(email: str) -> str:
    if "@" not in email:
        return ""
    nome, dominio = email.split("@", 1)
    return f"{nome[:3]}…@{dominio}"


def quem(conta: Conta) -> dict[str, Any]:
    """Se há login e de quem (e-mail mascarado, plano), lido dos arquivos do próprio agente."""
    if not conta.login.is_file():
        return {"logado": False, "email": "", "plano": ""}
    email = plano = ""
    try:
        if conta.agente == "claude":
            # O perfil fica na pasta da conta; na padrão (~/.claude), ao lado: ~/.claude.json.
            perfis = (conta.onde / ".claude.json", conta.onde.parent / ".claude.json")
            perfil = next(p for p in perfis if p.is_file())
            dados = json.loads(perfil.read_text())
            email = str((dados.get("oauthAccount") or {}).get("emailAddress", ""))
        else:
            tokens = json.loads(conta.login.read_text()).get("tokens") or {}
            carga = str(tokens.get("id_token", "")).split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
            email = str(claims.get("email", ""))
            plano = str(claims.get("https://api.openai.com/auth", {}).get("chatgpt_plan_type", ""))
    except (OSError, ValueError, IndexError, AttributeError, StopIteration):
        pass
    return {"logado": True, "email": _mascarar(email), "plano": plano}


class Contas:
    def __init__(self, arquivo: Path = ARQUIVO, pasta: Path = PASTA) -> None:
        self.arquivo = arquivo
        self.pasta = pasta

    def _ler(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.arquivo.read_text())
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self, dados: dict[str, Any]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1))
        temporario.replace(self.arquivo)

    def listar(self, agente: str | None = None) -> list[Conta]:
        contas = [Conta(f"{a}:{PADRAO}", a, "Padrão") for a in NOMES]
        for c in self._ler().get("contas", []):
            campos = {k: str(c.get(k, "")) for k in ("id", "agente", "nome", "pasta")}
            if campos["agente"] in NOMES and campos["id"] and campos["pasta"]:
                contas.append(Conta(**campos))
        return [c for c in contas if agente is None or c.agente == agente]

    def achar(self, id_: str) -> Conta:
        conta = next((c for c in self.listar() if c.id == id_), None)
        if conta is None:
            raise ContaErro("conta desconhecida")
        return conta

    def adicionar(self, agente: str, nome: str) -> Conta:
        nome = " ".join(nome.split())[:40]
        if agente not in NOMES:
            raise ContaErro("agente desconhecido")
        if not nome:
            raise ContaErro("dê um nome à conta")
        if any(c.nome.casefold() == nome.casefold() for c in self.listar(agente)):
            raise ContaErro("já existe uma conta com esse nome")
        id_ = f"{agente}:{uuid.uuid4().hex[:8]}"
        apelido = re.sub(r"[^\w-]+", "-", nome.casefold()).strip("-")[:24] or "conta"
        pasta = self.pasta / f"{agente}-{apelido}-{id_.split(':')[1]}"
        pasta.mkdir(parents=True, exist_ok=False, mode=0o700)
        conta = Conta(id_, agente, nome, str(pasta))
        dados = self._ler()
        dados["contas"] = [*dados.get("contas", []), asdict(conta)]
        self._gravar(dados)
        return conta

    def remover(self, id_: str) -> None:
        conta = self.achar(id_)
        if not conta.pasta:
            raise ContaErro("a conta padrão do agente não sai daqui")
        dados = self._ler()
        dados["contas"] = [c for c in dados.get("contas", []) if c.get("id") != id_]
        if dados.get("usar", {}).get(conta.agente) == id_:
            dados["usar"].pop(conta.agente)
        self._gravar(dados)
        if self.pasta in Path(conta.pasta).parents:  # só apaga pasta que o Zé criou
            shutil.rmtree(conta.pasta, ignore_errors=True)

    def em_uso(self, agente: str) -> Conta:
        """A conta que o Zé usa para aquele agente (a padrão, se nada foi escolhido)."""
        escolhida = self._ler().get("usar", {}).get(agente, "")
        conta = next((c for c in self.listar(agente) if c.id == escolhida), None)
        return conta or self.listar(agente)[0]

    def usar(self, id_: str) -> Conta:
        conta = self.achar(id_)
        dados = self._ler()
        dados["usar"] = {**dados.get("usar", {}), conta.agente: conta.id}
        self._gravar(dados)
        return conta


# Terminais que abrem um comando (o primeiro que existir); `xdg-terminal-exec` é o padrão do
# freedesktop e respeita o terminal escolhido por quem usa.
TERMINAIS = (
    ("xdg-terminal-exec",),
    ("ghostty", "-e"),
    ("kitty",),
    ("alacritty", "-e"),
    ("foot",),
    ("gnome-terminal", "--"),
    ("konsole", "-e"),
    ("xterm", "-e"),
)


def abrir_login(conta: Conta) -> bool:
    """Abre um terminal com o login do próprio agente nesta conta; False se não houver terminal
    (a tela mostra o comando para copiar)."""
    import subprocess

    for terminal in TERMINAIS:
        if shutil.which(terminal[0]):
            subprocess.Popen(  # noqa: S603 (terminal da lista acima; comando montado aqui)
                [*terminal, *conta.comando_login()],
                cwd=Path.home(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
    return False
