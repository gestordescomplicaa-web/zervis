"""As empresas que quem usa gere, cada uma com o seu grupo de WhatsApp (ADR 0105).

Uma empresa é o nome, o grupo ligado (um grupo por empresa, e um grupo nunca em duas), a pasta do
projeto dela nesta máquina (opcional) e a **vitrine**: a pasta, nos dados do Zé, com o que foi
publicado para ela (relatórios, métricas, perguntas frequentes). O grupo só vai ver a vitrine
(docs/plano-empresas.md, regra 2): nunca a sessão, os conectores nem a memória do Zé.

Nesta etapa nada é enviado nem lido no grupo: só o cadastro. O cadastro fica na configuração; a
vitrine, nos dados, fora de qualquer projeto (dado de cliente não vai para repositório).
"""

import json
import logging
import re
import threading
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import fuso, lugares

log = logging.getLogger(__name__)
ARQUIVO = lugares.CONFIG / "empresas.json"
PASTA = lugares.DADOS / "empresas"
NOME_MAXIMO = 60
GRUPO = re.compile(r"\d{6,40}(-\d{6,20})?@g\.us")


class EmpresaErro(ValueError):
    """Um cadastro que não pode ser salvo; a mensagem vai para a tela."""


@dataclass(frozen=True)
class Empresa:
    id: str
    nome: str
    grupo: str = ""  # o chat do grupo ("...@g.us"); vazio = sem grupo ligado
    grupo_nome: str = ""
    pasta: str = ""  # a pasta do projeto nesta máquina, como o painel mostra (~/...)
    ligada: bool = False
    criada: str = field(default_factory=lambda: _agora())

    def para_tela(self, vitrine: Path) -> dict[str, Any]:
        arquivos = [p for p in vitrine.rglob("*") if p.is_file()] if vitrine.is_dir() else []
        return {
            **asdict(self),
            "vitrine": str(vitrine).replace(str(Path.home()), "~", 1),
            "publicados": len(arquivos),
        }


def _agora() -> str:
    return datetime.now(fuso.local()).isoformat(timespec="seconds")


def identificador(nome: str) -> str:
    """O nome sem acento, em minúsculas e com hífens: "Padaria São João" → "padaria-sao-joao"."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40] or "empresa"


class Empresas:
    def __init__(self, arquivo: Path | None = None, pasta: Path | None = None) -> None:
        self.arquivo = arquivo or ARQUIVO
        self.pasta = pasta or PASTA
        self._trava = threading.Lock()

    def listar(self) -> list[Empresa]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as erro:
            log.warning("empresas: cadastro ilegível (%s)", erro)
            return []
        lista = dados.get("empresas") if isinstance(dados, dict) else None
        empresas: list[Empresa] = []
        for d in lista if isinstance(lista, list) else []:
            if not isinstance(d, dict) or not d.get("id") or not d.get("nome"):
                continue
            conhecidos = {k: d[k] for k in Empresa.__dataclass_fields__ if k in d}
            empresas.append(Empresa(**conhecidos))
        return sorted(empresas, key=lambda e: e.nome.lower())

    def achar(self, ident: str) -> Empresa | None:
        return next((e for e in self.listar() if e.id == ident), None)

    def do_grupo(self, chat: str) -> Empresa | None:
        """A empresa ligada a este grupo (só se ela está ligada)."""
        return next((e for e in self.listar() if e.grupo == chat and e.ligada), None)

    def vitrine(self, ident: str) -> Path:
        return self.pasta / ident / "vitrine"

    def salvar(
        self,
        nome: str,
        grupo: str = "",
        grupo_nome: str = "",
        pasta: str = "",
        ligada: bool = False,
        ident: str = "",
    ) -> Empresa:
        """Cria (sem `ident`) ou altera uma empresa. Ligar exige um grupo."""
        nome = " ".join(nome.split())
        grupo, pasta = grupo.strip(), pasta.strip()
        if not nome:
            raise EmpresaErro("Informe o nome da empresa.")
        if len(nome) > NOME_MAXIMO:
            raise EmpresaErro(f"Nome longo demais (até {NOME_MAXIMO} caracteres).")
        if grupo and not GRUPO.fullmatch(grupo):
            raise EmpresaErro("Grupo inválido.")
        if ligada and not grupo:
            raise EmpresaErro("Escolha o grupo antes de ligar.")
        with self._trava:
            empresas = {e.id: e for e in self.listar()}
            antes = empresas.get(ident) if ident else None
            if ident and antes is None:
                raise EmpresaErro("Empresa não encontrada.")
            outros = [e for e in empresas.values() if e.id != ident]
            if any(e.nome.lower() == nome.lower() for e in outros):
                raise EmpresaErro("Já existe uma empresa com esse nome.")
            if grupo and (dona := next((e for e in outros if e.grupo == grupo), None)):
                raise EmpresaErro(f"Esse grupo já está ligado a {dona.nome}.")
            if antes is None:
                ident = identificador(nome)
                base, n = ident, 2
                while ident in empresas:
                    ident, n = f"{base}-{n}", n + 1
            empresa = Empresa(
                ident,
                nome,
                grupo,
                " ".join(grupo_nome.split())[:120] if grupo else "",
                pasta,
                ligada,
                antes.criada if antes else _agora(),
            )
            empresas[ident] = empresa
            self._gravar(list(empresas.values()))
        self.vitrine(ident).mkdir(parents=True, exist_ok=True)
        return empresa

    def remover(self, ident: str) -> Empresa:
        """Tira a empresa do cadastro; a vitrine fica nos dados, para não perder o publicado."""
        with self._trava:
            empresas = self.listar()
            alvo = next((e for e in empresas if e.id == ident), None)
            if alvo is None:
                raise EmpresaErro("Empresa não encontrada.")
            self._gravar([e for e in empresas if e.id != ident])
        return alvo

    def _gravar(self, empresas: list[Empresa]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".next")
        dados = {"empresas": [asdict(e) for e in empresas]}
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1))
        temporario.chmod(0o600)
        temporario.replace(self.arquivo)


PADRAO = Empresas()
