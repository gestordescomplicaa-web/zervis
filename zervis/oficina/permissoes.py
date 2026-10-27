"""Os pedidos de permissão das sessões do Claude, decididos de fora do terminal (ADR 0039).

O Claude Code chama o gancho `PermissionRequest` quando abriria a janela de permissão; o gancho é
um POST para uma rota local do painel, com a chave da sessão no cabeçalho. O pedido entra aqui e
o POST espera a decisão: do painel (também pelo celular), depois da voz, ou de ninguém. A janela
do terminal aparece ao mesmo tempo (prova E0, 27/10/2026), e o primeiro que responde decide:
quando a pessoa responde no terminal, o gancho não é avisado, e o Zé retira o pedido pelos outros
eventos da sessão (a ferramenta rodou, o turno parou, outro pedido chegou). O pedido de permissão
não traz o `tool_use_id` (conferido em 27/10/2026, ao contrário do exemplo da documentação): a
ferramenta que rodou se reconhece pela assinatura (o nome e o resumo dos argumentos).

A frase é do Zé, montada da ferramenta e dos argumentos de verdade: a `description` que o modelo
escreve num comando pode dizer uma coisa e o comando fazer outra.
"""

import hashlib
import json
import re
import secrets
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

PRAZO_S = 300.0  # quanto o gancho espera; depois, a janela do terminal segue sozinha
FALAVEL = 160  # um comando maior que isto não se aprova de ouvido: "está na tela"
DETALHE = 400

# O que acontece se a pessoa aprovar, por ferramenta do MCP do n8n (as que pedem aprovação).
# `{obj}` vira "o fluxo "Nome"" quando o pedido traz o nome, ou "um fluxo no n8n-loja": um ID
# como "QkERvuSCj7yNj5rW" não diz nada a quem ouve (ele fica no detalhe, na tela).
CONSEQUENCIAS = {
    "publish_workflow": ("fluxo", "publicar {obj}: ele passa a rodar de verdade"),
    "unpublish_workflow": ("fluxo", "despublicar {obj}: ele para de rodar"),
    "execute_workflow": ("fluxo", "rodar de verdade {obj}: envia, cria ou cobra o que ele fizer"),
    "archive_workflow": ("fluxo", "arquivar {obj}"),
    "restore_workflow_version": ("fluxo", "voltar {obj} para uma versão anterior"),
    "move_workflows_to_folder": ("fluxo", "mover fluxos de pasta"),
    "update_folder": ("pasta", "renomear ou mover {obj}"),
    "add_data_table_rows": ("tabela", "gravar linhas {em_obj}"),
    "add_data_table_column": ("tabela", "criar uma coluna {em_obj}"),
    "rename_data_table_column": ("tabela", "renomear uma coluna {de_obj}"),
    "rename_data_table": ("tabela", "renomear {obj}"),
    "delete_data_table_column": ("tabela", "apagar uma coluna {de_obj}, com os dados dela"),
}
ARTIGOS = {"fluxo": ("o", "um"), "pasta": ("a", "uma"), "tabela": ("a", "uma")}
CONTRACOES = {
    ("em", "o"): "no",
    ("em", "a"): "na",
    ("em", "um"): "num",
    ("em", "uma"): "numa",
    ("de", "o"): "do",
    ("de", "a"): "da",
    ("de", "um"): "de um",
    ("de", "uma"): "de uma",
}
NOMES = ("workflowName", "name", "nome", "title", "dataTableName", "folderName")
# Um comando só se aprova de ouvido se a fala não o muda: a voz tira caminhos, links e
# símbolos, e "cat > /etc/hosts" seria ouvido como "cat".
COMANDO_FALAVEL = re.compile(r"[\w .,:=@+-]+")


@dataclass
class Pedido:
    id: str
    sessao: str
    ferramenta: str
    frase: str  # "publicar o fluxo X: ele passa a rodar de verdade"
    detalhe: str  # os argumentos, para a tela
    falavel: bool  # cabe numa frase curta (a voz só aprova o que cabe)
    assinatura: str  # a ferramenta e o resumo dos argumentos: acha o PostToolUse dela
    turno: str  # o `prompt_id` do pedido da conversa em que a permissão foi pedida
    criado: float
    decisao: str = ""  # aprovado, negado, retirado, expirou
    por: str = ""  # painel, voz, terminal


class ChaveInvalida(PermissionError):
    """O gancho chegou com uma chave que não é de nenhuma sessão aberta."""


def _objeto(tipo: str, entrada: dict[str, Any], conector: str) -> str:
    definido, indefinido = ARTIGOS[tipo]
    for campo in NOMES:
        if nome := str(entrada.get(campo) or "").strip():
            return f'{definido} {tipo} "{nome[:80]}"'
    return f"{indefinido} {tipo} no {conector}"


def frase(ferramenta: str, entrada: dict[str, Any]) -> tuple[str, bool]:
    """O que a sessão quer fazer, dito pelo Zé, e se cabe ser aprovado de ouvido."""
    if ferramenta == "Bash":
        bruto = str(entrada.get("command", ""))
        comando = " ".join(bruto.split())
        if len(comando) > FALAVEL or "\n" in bruto.strip():
            return "rodar um comando longo (veja na tela)", False
        if not COMANDO_FALAVEL.fullmatch(comando):
            return f"rodar o comando {comando.split()[0] if comando else ''} (veja na tela)", False
        return f"rodar o comando: {comando}", True
    if ferramenta in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        caminho = str(entrada.get("file_path") or entrada.get("notebook_path") or "")
        return f"mudar o arquivo {caminho} (veja na tela)", False
    if ferramenta == "WebFetch":
        site = urlsplit(str(entrada.get("url", ""))).hostname or "um endereço"
        return f"abrir uma página de {site}", True
    if ferramenta.startswith("mcp__"):
        _, conector, nome = [*ferramenta.split("__", 2), "", ""][:3]
        if nome in CONSEQUENCIAS:
            tipo, modelo = CONSEQUENCIAS[nome]
            obj = _objeto(tipo, entrada, conector)
            artigo, _, resto = obj.partition(" ")
            em, de = (f"{CONTRACOES[(p, artigo)]} {resto}" for p in ("em", "de"))
            return modelo.format(obj=obj, em_obj=em, de_obj=de), True
        return f"usar {nome} no {conector}", True
    return f"usar a ferramenta {ferramenta}", True


def assinatura(ferramenta: str, entrada: Any) -> str:
    """A ferramenta e os argumentos, resumidos: o mesmo cálculo do gancho enxuto das sessões."""
    texto = json.dumps(entrada if isinstance(entrada, dict) else {}, sort_keys=True)
    return f"{ferramenta}:{hashlib.sha256(texto.encode()).hexdigest()[:16]}"


def resposta(decisao: str, por: str) -> dict[str, Any]:
    """O que o gancho devolve ao Claude: permitir, negar ou nada (a janela do terminal segue)."""
    if decisao == "aprovado":
        comportamento: dict[str, Any] = {"behavior": "allow"}
    elif decisao == "negado":
        comportamento = {"behavior": "deny", "message": f"A pessoa negou pelo {por or 'Zé'}."}
    else:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": comportamento}}


class Permissoes:
    def __init__(
        self,
        prazo_s: float = PRAZO_S,
        ao_decidir: Callable[[Pedido], None] | None = None,
        relogio: Callable[[], float] = time.time,
    ) -> None:
        self.prazo_s = prazo_s
        self.ao_decidir = ao_decidir  # a Atividade, e a voz retira a pergunta
        self.ao_pedir: Callable[[Pedido], None] | None = None  # a voz pergunta (E2)
        self.endereco = ""  # a rota do painel; vazio = sem painel, sem gancho
        self._relogio = relogio
        self._chaves: dict[str, str] = {}  # resumo da chave → sessão
        self._pedidos: dict[str, Pedido] = {}
        self._mudou = threading.Condition()

    # --- chaves ------------------------------------------------------------------------------

    def chave(self, sessao: str) -> str:
        """Uma chave nova a cada vez que o terminal da sessão abre; a anterior deixa de valer."""
        nova = secrets.token_urlsafe(32)
        with self._mudou:
            self._chaves = {r: s for r, s in self._chaves.items() if s != sessao}
            self._chaves[_resumo(nova)] = sessao
        return nova

    def esquecer(self, sessao: str, chave: str) -> None:
        """O terminal dessa chave fechou: ela some e, se a sessão não abriu outro, os pedidos
        dela saem."""
        with self._mudou:
            if self._chaves.get(_resumo(chave)) == sessao:
                del self._chaves[_resumo(chave)]
            outro = sessao in self._chaves.values()
        if not outro:
            self.retirar(sessao)

    def sessao_da_chave(self, chave: str) -> str | None:
        with self._mudou:
            return self._chaves.get(_resumo(chave)) if chave else None

    # --- pedidos -----------------------------------------------------------------------------

    def pedir(self, chave: str, entrada: dict[str, Any]) -> dict[str, Any]:
        """Chamado pelo gancho: espera a decisão até o prazo e devolve a resposta do gancho."""
        sessao = self.sessao_da_chave(chave)
        if sessao is None:
            raise ChaveInvalida("chave de sessão inválida")
        ferramenta = str(entrada.get("tool_name", ""))
        bruto = entrada.get("tool_input")
        argumentos: dict[str, Any] = bruto if isinstance(bruto, dict) else {}
        texto, falavel = frase(ferramenta, argumentos)
        p = Pedido(
            id=uuid.uuid4().hex[:12],
            sessao=sessao,
            ferramenta=ferramenta,
            frase=texto,
            detalhe=json.dumps(argumentos, ensure_ascii=False)[:DETALHE],
            falavel=falavel,
            assinatura=assinatura(ferramenta, argumentos),
            turno=str(entrada.get("prompt_id", "")),
            criado=self._relogio(),
        )
        with self._mudou:
            self._pedidos[p.id] = p
            self._mudou.notify_all()
        if self.ao_pedir is not None:
            self.ao_pedir(p)
        with self._mudou:
            limite = time.monotonic() + self.prazo_s
            while not p.decisao and (falta := limite - time.monotonic()) > 0:
                self._mudou.wait(falta)
            if not p.decisao:
                p.decisao = "expirou"
            self._pedidos.pop(p.id, None)
        self._avisar(p)
        return resposta(p.decisao, p.por)

    def decidir(self, sessao: str, pedido: str, aprovado: bool, por: str) -> Pedido:
        with self._mudou:
            p = self._pedidos.get(pedido)
            if p is None or p.sessao != sessao or p.decisao:
                raise KeyError("esse pedido já foi respondido")
            p.decisao, p.por = ("aprovado" if aprovado else "negado"), por
            self._mudou.notify_all()
            return p

    def retirar(
        self, sessao: str, *, rodou: str = "", do_turno: str = "", fora_do_turno: str = ""
    ) -> None:
        """A pessoa respondeu no terminal: o pedido sai do painel e o gancho volta sem decisão.
        Os eventos chegam com atraso (o arquivo é lido a cada 0,7 s), então cada um retira só o
        que é seu: a ferramenta que rodou (`rodou`, a assinatura), o turno que parou
        (`do_turno`) ou o que não é do turno que começou (`fora_do_turno`). Sem nada, todos (o
        terminal fechou)."""
        with self._mudou:
            for p in self._pedidos.values():
                if p.sessao != sessao or p.decisao:
                    continue
                if rodou and p.assinatura != rodou:
                    continue
                if do_turno and p.turno not in (do_turno, ""):
                    continue
                if fora_do_turno and p.turno == fora_do_turno:
                    continue
                p.decisao, p.por = "retirado", "terminal"
            self._mudou.notify_all()

    def pendente(self, pedido: str) -> bool:
        with self._mudou:
            p = self._pedidos.get(pedido)
            return p is not None and not p.decisao

    def pendentes(self, sessao: str | None = None) -> list[dict[str, Any]]:
        with self._mudou:
            return [
                asdict(p)
                for p in sorted(self._pedidos.values(), key=lambda p: p.criado)
                if not p.decisao and (sessao is None or p.sessao == sessao)
            ]

    def _avisar(self, p: Pedido) -> None:
        if self.ao_decidir is not None:
            self.ao_decidir(p)


def _resumo(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()
