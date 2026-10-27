"""As contas dos agentes (ADR 0016): cada conta é uma pasta de login do próprio agente.

O Claude Code guarda o login em `CLAUDE_CONFIG_DIR` (padrão `~/.claude`) e o Codex em `CODEX_HOME`
(padrão `~/.codex`). Uma conta nova é só outra pasta, criada pelo Zé em `<dados>/contas/`; o login
quem faz é a pessoa, no próprio agente (o Zé abre o terminal com o comando certo). A pasta padrão
é sempre a primeira conta de cada agente, sem cadastro.

O Zé lê de cada pasta só o que a tela mostra: se há login, o e-mail (mascarado) e o plano.

Uma conta do Claude Code também pode ser de outro provedor com API no formato da Anthropic (a
DeepSeek, provada em 27/10/2026): o próprio Claude Code, com voz, painel e aprovação iguais, mas
o modelo do provedor, pago por uso com a chave da pessoa. A chave fica em `chaves/contas`, 0600,
nunca no `contas.json`; ao guardar, o Zé testa a chave pedindo ao provedor a lista de modelos. Essa
conta vale só nas sessões: o cérebro do Zé segue na conta do Claude em uso.
"""

import base64
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from zervis import lugares

ARQUIVO = lugares.CONFIG / "contas.json"
PASTA = lugares.DADOS / "contas"
NOMES = {"claude": "Claude", "codex": "Codex"}
VARIAVEIS = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME"}
ORIGINAL = {v: os.environ.get(v, "") for v in VARIAVEIS.values()}
PADRAO = "padrao"
CHAVES = lugares.CONFIG / "chaves/contas"  # <conta>, 0600: a chave das contas de provedor


@dataclass(frozen=True)
class Provedor:
    nome: str
    endereco: str  # a API no formato da Anthropic, que o Claude Code usa (ANTHROPIC_BASE_URL)
    lista: str  # a lista de modelos do provedor: testa a chave e diz o que ela oferece
    principal: str  # o modelo das tarefas grandes (o lugar do Opus e do Sonnet)
    rapido: str  # o das tarefas leves do Claude Code (o lugar do Haiku)
    criar_chave: str  # onde a pessoa cria a chave


PROVEDORES = {
    "deepseek": Provedor(
        "DeepSeek",
        "https://api.deepseek.com/anthropic",
        "https://api.deepseek.com/models",
        "deepseek-v4-pro",
        "deepseek-flash",
        "https://platform.deepseek.com/api_keys",
    ),
}


class ContaErro(ValueError):
    pass


@dataclass(frozen=True)
class Conta:
    id: str
    agente: str
    nome: str
    pasta: str = ""  # vazio: a pasta padrão do agente
    provedor: str = ""  # vazio: a conta do próprio agente; senão, uma chave de PROVEDORES
    modelos: tuple[tuple[str, str], ...] = ()  # do provedor: (id, nome), lidos ao guardar a chave

    @property
    def onde(self) -> Path:
        if self.pasta:
            return Path(self.pasta)
        if self.agente == "claude":
            return Path(ORIGINAL["CLAUDE_CONFIG_DIR"] or "~/.claude").expanduser()
        return Path(ORIGINAL["CODEX_HOME"] or "~/.codex").expanduser()

    @property
    def login(self) -> Path:
        if self.provedor:
            return CHAVES / self.id.replace(":", "-")
        return self.onde / (".credentials.json" if self.agente == "claude" else "auth.json")

    def ambiente_do_provedor(self) -> dict[str, str]:
        """O Claude Code apontado para o provedor, com a chave e os modelos dele (vazio se a conta
        não é de provedor ou a chave sumiu). Vai no ambiente do agente, nunca no comando."""
        provedor = PROVEDORES.get(self.provedor)
        try:
            chave = self.login.read_text().strip() if provedor else ""
        except OSError:
            chave = ""
        if provedor is None or not chave:
            return {}
        ids = [m[0] for m in self.modelos]
        principal = provedor.principal if provedor.principal in ids or not ids else ids[0]
        rapido = provedor.rapido if provedor.rapido in ids or not ids else principal
        return {
            "ANTHROPIC_BASE_URL": provedor.endereco,
            "ANTHROPIC_AUTH_TOKEN": chave,
            "ANTHROPIC_MODEL": principal,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": principal,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": principal,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": rapido,
            "CLAUDE_CODE_SUBAGENT_MODEL": rapido,
            # Sem as chamadas à Anthropic que não são do trabalho (atualização, telemetria).
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }

    def ambiente(self) -> dict[str, str]:
        """A variável que aponta o agente para esta conta (vazio na pasta padrão)."""
        return {VARIAVEIS[self.agente]: self.pasta} if self.pasta else {}

    def comando_login(self) -> list[str]:
        variavel = [f"{VARIAVEIS[self.agente]}={self.pasta}"] if self.pasta else []
        agente = (
            ["claude", "auth", "login"]
            if self.agente == "claude"
            else ["codex", "login", "--device-auth"]
        )
        return ["env", *variavel, *agente]


def _mascarar(email: str) -> str:
    if "@" not in email:
        return ""
    nome, dominio = email.split("@", 1)
    return f"{nome[:3]}…@{dominio}"


def quem(conta: Conta) -> dict[str, Any]:
    """Se há login e de quem (e-mail mascarado, plano), lido dos arquivos do próprio agente."""
    if conta.provedor:
        nome = PROVEDORES[conta.provedor].nome if conta.provedor in PROVEDORES else conta.provedor
        return {"logado": conta.login.is_file(), "email": "", "plano": f"{nome} · chave de API"}
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
            campos = {k: str(c.get(k, "")) for k in ("id", "agente", "nome", "pasta", "provedor")}
            modelos = tuple(
                (str(m[0]), str(m[1]))
                for m in c.get("modelos", [])
                if isinstance(m, list | tuple) and len(m) == 2
            )
            if campos["agente"] in NOMES and campos["id"] and campos["pasta"]:
                contas.append(Conta(**campos, modelos=modelos))
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

    def adicionar_provedor(
        self,
        provedor: str,
        chave: str,
        consultar: "Callable[[Provedor, str], list[tuple[str, str]]] | None" = None,
    ) -> Conta:
        """Uma conta do Claude Code no provedor, com a chave colada; só fica se a chave vale."""
        dados_provedor = PROVEDORES.get(provedor)
        if dados_provedor is None:
            raise ContaErro("provedor desconhecido")
        chave = chave.strip()
        if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
            raise ContaErro("cole só a chave de API, sem espaços")
        modelos = (consultar or modelos_do_provedor)(dados_provedor, chave)
        if not modelos:
            raise ContaErro(f"a {dados_provedor.nome} não listou nenhum modelo para essa chave")
        existentes = {c.nome.casefold() for c in self.listar("claude")}
        nome = next(
            n
            for n in (dados_provedor.nome, *(f"{dados_provedor.nome} {i}" for i in range(2, 99)))
            if n.casefold() not in existentes
        )
        id_ = f"claude:{uuid.uuid4().hex[:8]}"
        pasta = self.pasta / f"claude-{provedor}-{id_.split(':')[1]}"
        pasta.mkdir(parents=True, exist_ok=False, mode=0o700)
        # Sem login nesta pasta: a apresentação do Claude Code (tema, login) não aparece.
        (pasta / ".claude.json").write_text(json.dumps({"hasCompletedOnboarding": True}))
        conta = Conta(id_, "claude", nome, str(pasta), provedor, tuple(modelos))
        guardar_chave(conta, chave)
        dados = self._ler()
        dados["contas"] = [*dados.get("contas", []), asdict(conta)]
        self._gravar(dados)
        return conta

    def remover(self, id_: str) -> None:
        conta = self.achar(id_)
        if not conta.pasta:
            raise ContaErro("a conta padrão do agente não sai daqui")
        if conta.provedor:
            conta.login.unlink(missing_ok=True)
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
        if conta.provedor:
            # O cérebro do Zé e o teste do acesso usam a conta em uso com os modelos do Claude.
            raise ContaErro("a conta de provedor vale só nas sessões: escolha-a na própria sessão")
        dados = self._ler()
        dados["usar"] = {**dados.get("usar", {}), conta.agente: conta.id}
        self._gravar(dados)
        return conta


def guardar_chave(conta: Conta, chave: str) -> None:
    CHAVES.mkdir(parents=True, exist_ok=True, mode=0o700)
    CHAVES.chmod(0o700)
    temporario = conta.login.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(chave + "\n")
    temporario.replace(conta.login)


def modelos_do_provedor(provedor: Provedor, chave: str) -> list[tuple[str, str]]:
    """A lista de modelos que a chave usa: o teste da chave e a escolha na sessão."""
    pedido = urllib.request.Request(  # noqa: S310 (endereço fixo do provedor, https)
        provedor.lista, headers={"Authorization": f"Bearer {chave}"}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15) as resposta:  # noqa: S310
            dados = json.load(resposta)
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            raise ContaErro(f"a {provedor.nome} recusou a chave") from None
        raise ContaErro(f"a {provedor.nome} respondeu {erro.code}; tente de novo") from None
    except (OSError, ValueError):
        raise ContaErro(f"não consegui falar com a {provedor.nome}; tente de novo") from None
    lista = dados.get("data", []) if isinstance(dados, dict) else []
    return [
        (str(m["id"]), str(m.get("name") or m["id"]))
        for m in lista
        if isinstance(m, dict) and m.get("id")
    ]
