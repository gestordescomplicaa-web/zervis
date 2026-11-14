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

Duas ferramentas não se aprovam com um "sim" sozinho (visto em 09 e 10/11/2026: o Zé aprovava, o
Claude Code descartava e o formulário ficava no terminal): o formulário de perguntas
(`AskUserQuestion`) precisa das respostas, e a aprovação do plano (`ExitPlanMode`), do plano de
volta, os dois no `updatedInput`. A pergunta (`tipo` "pergunta") se responde por opção, uma
pergunta por vez; o plano (`tipo` "plano") se aprova como os outros pedidos.
"""

import hashlib
import json
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PRAZO_S = 300.0  # quanto o gancho espera; depois, a janela do terminal segue sozinha
# O Codex só mostra a pergunta dele depois que o gancho volta (prova de 27/10/2026): no
# terminal, nada aparece enquanto o Zé espera, então a pergunta volta para lá mais cedo.
PRAZO_CODEX_S = 120.0
FALAVEL = 160  # um comando maior que isto é dito pelo resumo, não por extenso
# O que só se aprova na tela, olhando o comando inteiro (ADR 0039, revisto em 13/11/2026): apagar
# em massa, virar administrador, rodar o que vem da internet, reescrever o GitHub, formatar disco.
PERIGOSO = re.compile(
    r"\brm\s+-\w*[rf]|\bsudo\b|\b(curl|wget)\b[^\n]*\|\s*(ba|z)?sh\b"
    r"|\bgit\s+push\b[^\n]*(--force|\s-f\b)|\bgit\s+reset\s+--hard|\bmkfs|\bdd\s+if="
    r"|\bchmod\s+-R|\bchown\s+-R|>\s*/(etc|dev|usr|boot)/"
)
# O que cada programa faz, para a voz resumir um comando que não cabe numa frase.
ACOES = {
    "lê arquivos": {
        "cat",
        "ls",
        "head",
        "tail",
        "grep",
        "rg",
        "find",
        "wc",
        "sed",
        "awk",
        "echo",
        "pwd",
        "test",
        "stat",
        "file",
        "tree",
        "diff",
        "sort",
        "uniq",
        "cut",
        "jq",
        "less",
        "printf",
        "basename",
        "dirname",
        "realpath",
    },
    "usa o git": {"git", "gh"},
    "cria ou move arquivos": {"mkdir", "cp", "mv", "touch", "ln", "tee"},
    "apaga arquivos": {"rm", "rmdir"},
    "roda um script": {"python", "python3", "node", "bash", "sh", "deno", "bun", "ruby"},
}
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

PERGUNTA = "AskUserQuestion"  # o formulário de perguntas do Claude Code
# O que o Zé aprova sozinho numa sessão protegida: o que só mexe na cópia do projeto (e ler a web).
SOZINHO = frozenset(
    {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch", "WebFetch"}
)
PLANO = "ExitPlanMode"  # a aprovação do plano, no fim do modo plano
# As duas se reconhecem pelo nome, sem os argumentos: o que roda leva as respostas junto.
SO_PELO_NOME = (PERGUNTA, PLANO)


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
    decisao: str = ""  # aprovado, negado, retirado, devolvido (ao terminal), expirou
    por: str = ""  # painel, voz, terminal
    tipo: str = "permissao"  # permissao | pergunta (AskUserQuestion) | plano (ExitPlanMode)
    # Do formulário: {"pergunta", "titulo", "opcoes": [rótulos], "multipla"}, na ordem dele.
    perguntas: list[dict[str, Any]] = field(default_factory=list)
    respostas: dict[str, str] = field(default_factory=dict)  # pergunta -> rótulo(s) ou texto

    def a_responder(self) -> dict[str, Any] | None:
        """A próxima pergunta do formulário sem resposta (None: todas respondidas)."""
        return next((q for q in self.perguntas if q["pergunta"] not in self.respostas), None)


class ChaveInvalida(PermissionError):
    """O gancho chegou com uma chave que não é de nenhuma sessão aberta."""


def _objeto(tipo: str, entrada: dict[str, Any], conector: str) -> str:
    definido, indefinido = ARTIGOS[tipo]
    for campo in NOMES:
        if nome := str(entrada.get(campo) or "").strip():
            return f'{definido} {tipo} "{nome[:80]}"'
    return f"{indefinido} {tipo} no {conector}"


def perguntas_do_formulario(entrada: dict[str, Any]) -> list[dict[str, Any]]:
    """As perguntas do `AskUserQuestion`, só com o que o Zé fala e mostra."""
    saida = []
    for q in entrada.get("questions") or []:
        if not isinstance(q, dict) or not str(q.get("question", "")).strip():
            continue
        opcoes = [
            str(o.get("label", "")).strip()
            for o in q.get("options") or []
            if isinstance(o, dict) and str(o.get("label", "")).strip()
        ]
        saida.append(
            {
                "pergunta": str(q["question"]).strip(),
                "titulo": str(q.get("header", "")).strip(),
                "opcoes": opcoes,
                "multipla": bool(q.get("multiSelect")),
            }
        )
    return saida


def _normal(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", sem_acento)


ORDINAIS = {
    "primeira": 0, "primeiro": 0, "segunda": 1, "segundo": 1, "terceira": 2, "terceiro": 2,
    "quarta": 3, "quarto": 3, "ultima": -1, "ultimo": -1,
}  # fmt: skip
NUMEROS = {"um": 0, "uma": 0, "1": 0, "dois": 1, "duas": 1, "2": 1, "tres": 2, "3": 2,
           "quatro": 3, "4": 3}  # fmt: skip
# "Outra resposta: ..." ou "responde ...": o resto da fala vai como texto livre.
LIVRE = ("outra", "outro", "resposta", "responde", "responda")
# Deixar a pergunta para o terminal, sem responder pelo Zé.
NO_TERMINAL = {
    ("cancela",), ("deixa",), ("deixa", "pra", "la"), ("deixa", "para", "la"), ("no", "terminal"),
    ("responde", "no", "terminal"), ("eu", "respondo", "no", "terminal"), ("nenhuma",),
    ("respondo", "no", "terminal"), ("deixa", "no", "terminal"),
}  # fmt: skip


def escolher(opcoes: list[str], multipla: bool, texto: str) -> tuple[str, str]:
    """A resposta falada a uma pergunta do formulário: ("opcao", rótulos), ("livre", texto),
    ("terminal", "") ou ("nenhuma", "") quando não dá para saber qual (o Zé pergunta de novo).
    Nada se adivinha: uma fala que não bate com uma opção, uma posição ("a segunda") ou o texto
    livre anunciado ("outra resposta: ...") não vira resposta."""
    p = _normal(texto)
    if not p:
        return "nenhuma", ""
    if tuple(p) in NO_TERMINAL:
        return "terminal", ""
    contidas = [o for o in opcoes if (r := _normal(o)) and _contem(p, r)]
    if multipla and contidas:
        return "opcao", ", ".join(contidas)
    if len(contidas) == 1:
        return "opcao", contidas[0]
    if len(contidas) > 1:  # "a de cima" dentro de "a de cima e a de baixo": a mais comprida
        maior = max(contidas, key=lambda o: len(_normal(o)))
        if all(_contem(_normal(maior), _normal(o)) for o in contidas):
            return "opcao", maior
        return "nenhuma", ""  # duas opções ditas para uma pergunta de uma só
    if len(p) <= 4 and opcoes:
        posicao = next((ORDINAIS[w] for w in p if w in ORDINAIS), None)
        if posicao is None and (p[0] in ("opcao", "numero", "a", "o") or len(p) == 1):
            posicao = next((NUMEROS[w] for w in p if w in NUMEROS), None)
        if posicao is not None and -len(opcoes) <= posicao < len(opcoes):
            return "opcao", opcoes[posicao]
    if p[0] in LIVRE and len(p) > 1:
        bruto = texto.strip()
        resto = re.sub(r"^\W*\w+(\s+resposta)?[\s,:.-]*", "", bruto, flags=re.IGNORECASE)
        if resto.strip():
            return "livre", resto.strip()
    return "nenhuma", ""


def _contem(fala: list[str], rotulo: list[str]) -> bool:
    n = len(rotulo)
    return any(fala[i : i + n] == rotulo for i in range(len(fala) - n + 1))


def _programas(comando: str) -> list[str]:
    """Os programas de um comando composto, na ordem, sem repetir."""
    vistos: list[str] = []
    for parte in re.split(r"&&|\|\||[;|\n()]", comando):
        palavras = [p for p in parte.split() if "=" not in p.split("/")[0]]  # tira VAR=valor
        if palavras and palavras[0] not in ("then", "do", "else", "fi", "done", "!"):
            nome = palavras[0].rsplit("/", 1)[-1]
            if nome and nome not in vistos:
                vistos.append(nome)
    return vistos


def resumo_do_comando(comando: str) -> str:
    """'rodar um comando que lê arquivos e roda o npm': o que a voz consegue dizer e a pessoa
    consegue julgar de ouvido."""
    acoes: list[str] = []
    for nome in _programas(comando):
        acao = next((a for a, nomes in ACOES.items() if nome in nomes), f"roda o {nome}")
        if acao not in acoes:
            acoes.append(acao)
    if not acoes:
        return "rodar um comando"
    lista = acoes[0] if len(acoes) == 1 else ", ".join(acoes[:-1]) + " e " + acoes[-1]
    return f"rodar um comando que {lista}"


def frase(ferramenta: str, entrada: dict[str, Any], protegida: bool = False) -> tuple[str, bool]:
    """O que a sessão quer fazer, dito pelo Zé, e se cabe ser aprovado de ouvido. A voz aprova
    quase tudo: o comando curto por extenso, o longo pelo resumo do que ele faz. Só o perigoso
    fica para a tela. Numa sessão protegida (ADR 0074), mudar arquivos também vai pela voz: o
    agente só enxerga a cópia do projeto."""
    if ferramenta == PERGUNTA:
        perguntas = perguntas_do_formulario(entrada)
        primeira = perguntas[0]["pergunta"] if perguntas else "uma pergunta"
        mais = f" (e mais {len(perguntas) - 1})" if len(perguntas) > 1 else ""
        return f"perguntar: {primeira}{mais}", True
    if ferramenta == PLANO:
        return "começar a executar o plano que preparou (veja na tela)", True
    if ferramenta == "Bash":
        bruto = str(entrada.get("command", ""))
        comando = " ".join(bruto.split())
        if PERIGOSO.search(bruto):
            return f"{resumo_do_comando(bruto)}, com risco (veja na tela)", False
        if (
            len(comando) <= FALAVEL
            and "\n" not in bruto.strip()
            and COMANDO_FALAVEL.fullmatch(comando)
        ):
            return f"rodar o comando: {comando}", True
        return resumo_do_comando(bruto), True
    if ferramenta == "apply_patch":  # o Codex mudando arquivos do projeto
        patch = str(entrada.get("patch") or entrada.get("input") or "")
        n = len(re.findall(r"^\*\*\* (?:Update|Add|Delete) File:", patch, re.M))
        return (f"mudar {n} arquivos do projeto" if n > 1 else "mudar um arquivo do projeto"), True
    if ferramenta in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        caminho = str(entrada.get("file_path") or entrada.get("notebook_path") or "")
        if protegida:
            return f"mudar o arquivo {Path(caminho).name or caminho}", True
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
    """A ferramenta e os argumentos, resumidos: o mesmo cálculo do gancho enxuto das sessões.
    O formulário e o plano, só pelo nome: quando rodam, os argumentos já trazem as respostas."""
    if ferramenta in SO_PELO_NOME:
        entrada = {}
    texto = json.dumps(entrada if isinstance(entrada, dict) else {}, sort_keys=True)
    return f"{ferramenta}:{hashlib.sha256(texto.encode()).hexdigest()[:16]}"


def resposta(decisao: str, por: str, entrada: dict[str, Any] | None = None) -> dict[str, Any]:
    """O que o gancho devolve ao Claude: permitir, negar ou nada (a janela do terminal segue).
    `entrada`: os argumentos com que a ferramenta roda (o formulário com as respostas, o plano);
    sem eles, o Claude Code descarta o "permitir" dessas duas."""
    if decisao == "aprovado":
        comportamento: dict[str, Any] = {"behavior": "allow"}
        if entrada is not None:
            comportamento["updatedInput"] = entrada
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
        # Se a sessão é protegida (ADR 0074): lá dentro, mudar arquivos também vai pela voz.
        self.protegida: Callable[[str], bool] | None = None
        # Se o Zé aprova sozinho os pedidos desta sessão (as protegidas, salvo ajuste em contrário).
        self.automatico: Callable[[str], bool] | None = None
        self.endereco = ""  # a rota do painel; vazio = sem painel, sem gancho
        self._relogio = relogio
        self._chaves: dict[str, str] = {}  # resumo da chave → sessão
        self._prazos: dict[str, float] = {}  # sessão → prazo próprio (o do Codex é menor)
        self._pedidos: dict[str, Pedido] = {}
        self._mudou = threading.Condition()

    # --- chaves ------------------------------------------------------------------------------

    def chave(self, sessao: str, prazo_s: float | None = None) -> str:
        """Uma chave nova a cada vez que o terminal da sessão abre; a anterior deixa de valer."""
        nova = secrets.token_urlsafe(32)
        with self._mudou:
            self._chaves = {r: s for r, s in self._chaves.items() if s != sessao}
            self._chaves[_resumo(nova)] = sessao
            self._prazos[sessao] = self.prazo_s if prazo_s is None else prazo_s
        return nova

    def adotar(self, sessao: str, resumo: str, prazo_s: float | None = None) -> None:
        """A chave de um terminal que continuou aberto no supervisor enquanto o Zé reiniciava
        (ADR 0068): só o resumo fica guardado, e o gancho do agente segue com a chave dele."""
        with self._mudou:
            self._chaves = {r: s for r, s in self._chaves.items() if s != sessao}
            self._chaves[resumo] = sessao
            self._prazos[sessao] = self.prazo_s if prazo_s is None else prazo_s

    def esquecer(self, sessao: str, chave: str = "", *, resumo: str = "") -> None:
        """O terminal dessa chave (ou desse resumo) fechou: ela some e, se a sessão não abriu
        outro, os pedidos dela saem."""
        resumo = resumo or _resumo(chave)
        with self._mudou:
            if self._chaves.get(resumo) == sessao:
                del self._chaves[resumo]
            outro = sessao in self._chaves.values()
        if not outro:
            self.retirar(sessao)

    def tem_chave(self, sessao: str) -> bool:
        with self._mudou:
            return sessao in self._chaves.values()

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
        protegida = self.protegida is not None and self.protegida(sessao)
        texto, falavel = frase(ferramenta, argumentos, protegida)
        tipo = {PERGUNTA: "pergunta", PLANO: "plano"}.get(ferramenta, "permissao")
        perguntas = perguntas_do_formulario(argumentos) if tipo == "pergunta" else []
        if tipo == "pergunta" and not perguntas:
            return resposta("", "")  # um formulário sem pergunta: fica com o terminal
        if tipo == "pergunta":
            detalhe = " · ".join(q["pergunta"] for q in perguntas)
        elif tipo == "plano":
            detalhe = str(argumentos.get("plan", ""))
        else:
            detalhe = json.dumps(argumentos, ensure_ascii=False)
        p = Pedido(
            id=uuid.uuid4().hex[:12],
            sessao=sessao,
            ferramenta=ferramenta,
            frase=texto,
            detalhe=detalhe[:DETALHE],
            falavel=falavel,
            assinatura=assinatura(ferramenta, argumentos),
            turno=str(entrada.get("prompt_id") or entrada.get("turn_id") or ""),  # Claude, Codex
            criado=self._relogio(),
            tipo=tipo,
            perguntas=perguntas,
        )
        if self._sozinho(p):
            p.decisao, p.por = "aprovado", "automatico"
            self._avisar(p)  # na Atividade, sem perguntar
            return resposta(p.decisao, p.por)
        with self._mudou:
            self._pedidos[p.id] = p
            self._mudou.notify_all()
        if self.ao_pedir is not None:
            self.ao_pedir(p)
        with self._mudou:
            limite = time.monotonic() + self._prazos.get(sessao, self.prazo_s)
            while not p.decisao and (falta := limite - time.monotonic()) > 0:
                self._mudou.wait(falta)
            if not p.decisao:
                p.decisao = "expirou"
            self._pedidos.pop(p.id, None)
        self._avisar(p)
        final: dict[str, Any] | None = None
        if p.decisao == "aprovado" and p.tipo == "pergunta":
            final = {**argumentos, "answers": dict(p.respostas)}
        elif p.decisao == "aprovado" and p.tipo == "plano":
            final = dict(argumentos)
        return resposta(p.decisao, p.por, final)

    def decidir(self, sessao: str, pedido: str, aprovado: bool, por: str) -> Pedido:
        """Aprovar ou negar. Uma pergunta não se aprova (responde-se com `responder`): negar a
        devolve ao terminal, onde o formulário segue aberto."""
        with self._mudou:
            p = self._pedidos.get(pedido)
            if p is None or p.sessao != sessao or p.decisao:
                raise KeyError("esse pedido já foi respondido")
            if p.tipo == "pergunta" and aprovado:
                raise ValueError("a sessão fez uma pergunta: responda com uma das opções")
            if p.tipo == "pergunta":
                p.decisao, p.por = "devolvido", por
            else:
                p.decisao, p.por = ("aprovado" if aprovado else "negado"), por
            self._mudou.notify_all()
            return p

    def responder(self, sessao: str, pedido: str, pergunta: str, valor: str, por: str) -> Pedido:
        """A resposta a uma pergunta do formulário. Com todas respondidas, o pedido sai
        aprovado com as respostas (o gancho as devolve ao Claude)."""
        valor = " ".join(str(valor).split())[:500]
        with self._mudou:
            p = self._pedidos.get(pedido)
            if p is None or p.sessao != sessao or p.decisao:
                raise KeyError("esse pedido já foi respondido")
            if p.tipo != "pergunta" or pergunta not in {q["pergunta"] for q in p.perguntas}:
                raise KeyError("essa pergunta não é deste pedido")
            if not valor:
                raise ValueError("resposta vazia")
            p.respostas[pergunta] = valor
            if p.a_responder() is None:
                p.decisao, p.por = "aprovado", por
                self._mudou.notify_all()
            return Pedido(**{**asdict(p), "respostas": dict(p.respostas)})

    def ver(self, pedido: str) -> Pedido | None:
        """Uma cópia do pedido que ainda espera (None se já foi respondido)."""
        with self._mudou:
            p = self._pedidos.get(pedido)
            if p is None or p.decisao:
                return None
            return Pedido(**{**asdict(p), "respostas": dict(p.respostas)})

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

    def _sozinho(self, p: Pedido) -> bool:
        """Aprovar sem perguntar: numa sessão protegida, só comando e edição (que ficam presos na
        cópia do projeto) e só o que não é perigoso. Conector (age fora: publica um fluxo, cobra
        um cliente), pergunta e plano continuam com a pessoa."""
        return (
            self.automatico is not None
            and p.tipo == "permissao"
            and p.falavel
            and p.ferramenta in SOZINHO
            and self.automatico(p.sessao)
        )

    def _avisar(self, p: Pedido) -> None:
        if self.ao_decidir is not None:
            self.ao_decidir(p)


def _resumo(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


resumo = _resumo  # o que se guarda de uma chave: com ele, o Zé a reconhece sem conhecê-la
