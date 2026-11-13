"""Os agentes das sessões (Claude e Codex) por fora da classe `Sessoes`: o ambiente da conta,
o comando do terminal e o do Codex, os ganchos, a confiança na pasta, a conversa salva, os
conectores e as skills do projeto. Tirado de `sessoes.py`, que continua exportando os nomes."""

import contextlib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zervis import caminhos
from zervis.cerebro import contas, mcp_externo
from zervis.memoria import aimemory
from zervis.oficina import isolamento
from zervis.oficina.permissoes import PRAZO_CODEX_S, PRAZO_S

if TYPE_CHECKING:
    from zervis.oficina.sessoes import Sessao

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.oficina.sessoes")
REGRAS = """
Você é um agente de código de uma sessão da oficina do Zé, o assistente pessoal do usuário.
O pedido vem dele (às vezes repassado pelo Zé). Trabalhe só dentro desta pasta. Não delegue a
outros agentes, não faça push e não mexa em nada fora do projeto. Rode os testes do projeto
quando mudar código. Ao terminar, a sua última mensagem começa com uma frase curta, em
português, dizendo o que foi feito (o Zé a lê em voz alta), e depois os detalhes.
"""


def _resumo_de(texto: str) -> str:
    primeira = re.split(r"(?<=[.!?])\s|\n", texto.strip(), maxsplit=1)[0]
    return primeira[:240]


def _descrever_ferramenta(nome: str, entrada: dict[str, Any]) -> str:
    if nome == "Bash":
        return f"$ {str(entrada.get('command', ''))[:160]}"
    alvo = entrada.get("file_path") or entrada.get("path") or entrada.get("pattern") or ""
    return f"{nome} {alvo}".strip()[:200]


def ambiente_da_conta(s: "Sessao") -> dict[str, str]:
    """A pasta de login da conta desta sessão; sem conta, a que o processo já usa."""
    if not s.conta:
        return {}
    try:
        conta = contas.Contas().achar(s.conta)
    except contas.ContaErro:
        return {}
    variavel = contas.VARIAVEIS[conta.agente]
    if conta.pasta:
        return {variavel: conta.pasta, **conta.ambiente_do_provedor()}
    # A conta padrão quando o processo aponta para outra: de volta para a padrão.
    return {variavel: str(conta.onde)} if os.environ.get(variavel) else {}


# O ambiente do Zé vem do perfil de quem usa, que costuma exportar tokens de outros serviços
# (visto em 10/11/2026: um token do n8n chegava a todas as sessões). Variáveis com nome de segredo
# não passam para o agente; passam só as que a conta dele usa para entrar e as que a sessão
# entrega de propósito (a conta, os conectores do projeto, a chave do gancho de permissão).
SEGREDO = re.compile(
    r"(?:^|_)(?:API_?KEY|KEY|KEYS|TOKEN|SECRET|PASSWORD|PASSWD|PASS|CREDENTIALS?|AUTH|COOKIE"
    r"|PRIVATE|DSN|PAT)(?:_|$)",
    re.IGNORECASE,
)
LIVRES = frozenset({"SSH_AUTH_SOCK"})  # um endereço, não um segredo (na protegida, fica fora)
PROPRIOS = {
    "claude": frozenset({"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}),
    "codex": frozenset({"OPENAI_API_KEY", "CODEX_API_KEY"}),
}
# O Claude Code pela Bedrock ou pela Vertex entra com as credenciais da nuvem.
NUVEM = {"CLAUDE_CODE_USE_BEDROCK": "AWS_", "CLAUDE_CODE_USE_VERTEX": "GOOGLE_"}


def sem_segredos(ambiente: dict[str, str], motor: str) -> dict[str, str]:
    """O ambiente sem as variáveis de segredo que não são do login deste agente."""
    proprios = PROPRIOS.get(motor, frozenset())
    nuvens = tuple(p for v, p in NUVEM.items() if motor == "claude" and ambiente.get(v))

    def passa(nome: str) -> bool:
        if nome in proprios or nome in LIVRES or (nuvens and nome.startswith(nuvens)):
            return True
        return not SEGREDO.search(nome)

    return {k: v for k, v in ambiente.items() if passa(k)}


def ambiente_do_agente(s: "Sessao", extra: dict[str, str] | None = None) -> dict[str, str]:
    """O ambiente inteiro do processo do agente: o do Zé sem os segredos, a conta e o `extra`."""
    return {**sem_segredos(dict(os.environ), s.motor), **ambiente_da_conta(s), **(extra or {})}


def ambiente_para_sdk(s: "Sessao") -> dict[str, str]:
    """O SDK do Claude junta o ambiente do Zé por baixo do que recebe: os segredos vão vazios."""
    limpo = sem_segredos(dict(os.environ), s.motor)
    return {**{k: "" for k in os.environ if k not in limpo}, **ambiente_da_conta(s)}


# Como os agentes avisam que a conta acabou: o Codex ("You've hit your usage limit", "rate limit
# reached", "insufficient_quota") e o Claude ("Claude AI usage limit reached", "credit balance is
# too low", "out of extra usage").
LIMITE = re.compile(
    r"usage limit|rate limit|quota|credit balance|out of (extra )?usage|limite de uso",
    re.IGNORECASE,
)


LIMITE_CODEX = LIMITE


def _comando_codex(s: "Sessao", texto: str, conectores: list[str] | None = None) -> list[str]:
    """`codex exec` na primeira vez, `codex exec resume <id>` depois. Escreve só na pasta da
    sessão (os anexos ele lê de onde estão; liberar escrita numa pasta que ainda não existe
    derruba o isolamento inteiro do Codex, visto em 12/10/2026)."""
    comum = ["--json", "--skip-git-repo-check", "-c", 'sandbox_mode="workspace-write"']
    if s.modelo:
        comum += ["-m", s.modelo]
    if s.esforco:
        comum += ["-c", f'model_reasoning_effort="{s.esforco}"']
    if memoria := aimemory.orientacao(Path(s.pasta)):
        comum += ["-c", f"developer_instructions={json.dumps(memoria)}"]
    comum += conectores or []
    if s.sdk_sessao:
        return ["codex", "exec", "resume", *comum, s.sdk_sessao, texto]
    return ["codex", "exec", *comum, texto]


NOMES_MOTORES = {"claude": "Claude", "codex": "Codex"}


def _nome_da_conta(s: "Sessao") -> str:
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


ANSI = re.compile(r"\x1b(\[[0-?]*[ -/]*[@-~]|\][^\x07]*(\x07|\x1b\\)|[@-Z\\-_])")


# Como os dois agentes dizem na tela que a conta acabou (mais estrito que LIMITE: o texto do
# próprio trabalho também passa por aqui).
LIMITE_TERMINAL = re.compile(
    r"usage limit reached|hit your usage limit|credit balance is too low|out of extra usage"
    r"|hit your (?:weekly|daily|monthly|session) limit"
    r"|limit will reset|upgrade to pro|purchase more credits",
    re.IGNORECASE,
)


HOOKS_DO_ZE = ("SessionStart", "UserPromptSubmit", "Stop", "Notification", "PostToolUse")


# Do que o agente faz, o Zé guarda o que conta o andamento: comandos e arquivos mexidos.
ACOES_DO_CLAUDE = "Bash|Edit|MultiEdit|Write|NotebookEdit"


# As outras ferramentas que podem pedir permissão: delas, o Zé só precisa saber que rodaram. O
# formulário de perguntas e o plano também: respondidos no terminal, saem do painel e da voz.
OUTRAS_COM_PERMISSAO = "mcp__.*|AskUserQuestion|ExitPlanMode"


# O mesmo cálculo de `permissoes.assinatura`, sem a resposta da ferramenta.
RESUMO_DO_EVENTO = (
    "import hashlib,json,sys;e=json.load(sys.stdin);n=str(e.get('tool_name',''));"
    "a=e.get('tool_input');a=a if isinstance(a,dict) else {};"
    "a={} if n in ('AskUserQuestion','ExitPlanMode') else a;"
    "h=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()[:16];"
    "print(json.dumps({'hook_event_name':e.get('hook_event_name'),'assinatura':n+':'+h}))"
)


VARIAVEL_PERMISSAO = "ZE_PERMISSAO"  # a chave do gancho de permissão, no ambiente do terminal


# O gancho de permissão do Codex (só comando, não HTTP): repassa o pedido à rota do painel e
# devolve a resposta; sem o Zé, nada (a pergunta do Codex aparece). Só a biblioteca padrão.
GANCHO_CODEX = (
    "import os,sys,urllib.request as u\n"
    "try:\n"
    " p=u.Request(os.environ['ZE_PERMISSAO_URL'],data=sys.stdin.buffer.read(),"
    "headers={'Authorization':'Bearer '+os.environ['ZE_PERMISSAO'],"
    "'Content-Type':'application/json'})\n"
    " t=float(os.environ.get('ZE_PERMISSAO_PRAZO','125'))\n"
    " r=u.build_opener(u.ProxyHandler({})).open(p,timeout=t)\n"
    " sys.stdout.write(r.read().decode())\n"
    "except Exception:\n"
    " pass\n"
)


GANCHOS_DO_CODEX = "hooks need review"  # a mensagem do aviso, para quem avisa saber o que é


# O Claude Code pergunta antes de retomar uma conversa longa parada (o cache esfriou): retomar
# gasta uma parte do limite de 5 horas, e a escolha é da pessoa (visto em 06/11/2026). A
# pergunta aparece ao abrir o terminal com a conversa e também no Enter de um pedido novo.
TELA_RETOMAR = b"Resume this conversation?"


RETOMAR_CONVERSA = "resume this conversation"  # a mensagem do aviso


ESPERA_RETOMAR = (
    "A sessão espera a escolha entre retomar a conversa ou começar outra. "
    "Responda no terminal da sessão."
)


NOME_DE_FERRAMENTA = re.compile(r"[A-Za-z0-9_-]{1,64}")


PRAZO_PERMISSAO_S = PRAZO_S


# Os comandos de teste e verificação rodam sem pergunta, para a sessão iterar sozinha até o
# resultado (ADR 0039). O Claude não deixa um prefixo destes cobrir `cmd && outro`.
# Pesquisar e ler páginas só leem a internet: uma sessão de pesquisa pedia aprovação a cada
# busca e a cada site, nove pedidos numa só (caso real de 27/10/2026).
INTERNET_LIVRE = ["WebSearch", "WebFetch"]


COMANDOS_LIVRES = [
    "Bash(make check)",
    "Bash(make test)",
    "Bash(npm test)",
    "Bash(npm test:*)",
    "Bash(npm run test)",
    "Bash(npm run test:*)",
    "Bash(npm run lint)",
    "Bash(npm run lint:*)",
    "Bash(uv run pytest)",
    "Bash(uv run pytest:*)",
    "Bash(pytest)",
    "Bash(pytest:*)",
]


FOCO_S = 30 * 60  # depois disso, "a sessão" sem nome não aponta mais para a última


def _simples(texto: str) -> str:
    """Sem acento, maiúscula nem pontuação: "Universo - Teste" e "universo teste" são iguais."""
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    letras = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w]+", " ", letras).split())


def _acao_do_claude(e: dict[str, Any]) -> str:
    """Uma linha para a ação do Claude: "$ npm test", "editou login.ts"."""
    entrada = e.get("tool_input")
    if not isinstance(entrada, dict):
        entrada = {}
    ferramenta = str(e.get("tool_name", ""))
    if ferramenta not in ACOES_DO_CLAUDE.split("|"):
        return ""
    if ferramenta == "Bash":
        comando = " ".join(str(entrada.get("command", "")).split())
        return f"$ {comando[:160]}" if comando else ""
    arquivo = str(entrada.get("file_path") or entrada.get("notebook_path") or "")
    if not arquivo:
        return ""
    verbo = "criou" if ferramenta == "Write" else "editou"
    return f"{verbo} {Path(arquivo).name}"


def _turno_auxiliar_do_codex(e: dict[str, Any]) -> bool:
    """O Codex avisa também os turnos auxiliares dele (o título da conversa, num fio à parte)."""
    entradas = e.get("input-messages") or []
    primeira = str(entradas[0]) if isinstance(entradas, list) and entradas else ""
    resposta = str(e.get("last-assistant-message") or "")
    return primeira.startswith("Generate a concise") or resposta.startswith('{"title"')


def _ultima_resposta_claude(transcricao: str) -> str:
    """O texto da última resposta do Claude, lido da transcrição que o próprio agente grava."""
    try:
        linhas = Path(transcricao).read_text().splitlines()[-200:]
    except OSError:
        return ""
    for linha in reversed(linhas):
        with contextlib.suppress(ValueError, AttributeError, TypeError):
            d = json.loads(linha)
            if d.get("type") != "assistant":
                continue
            textos = [b.get("text", "") for b in d["message"]["content"] if b.get("type") == "text"]
            if texto := "\n".join(t for t in textos if t).strip():
                return texto
    return ""


def confiar_pasta_claude(s: "Sessao") -> None:
    """Marca a pasta da sessão como confiável no perfil da conta do Claude (o mesmo registro que o
    "Sim, confio nesta pasta" do próprio Claude grava): a pessoa escolheu essa pasta ao criar a
    sessão, e um pedido feito por voz não pode ficar parado na pergunta."""
    try:
        conta = contas.Contas().achar(s.conta) if s.conta else contas.Contas().em_uso("claude")
    except contas.ContaErro:
        return
    perfil = conta.onde / ".claude.json" if conta.pasta else conta.onde.parent / ".claude.json"
    try:
        dados = json.loads(perfil.read_text()) if perfil.is_file() else {}
    except (OSError, ValueError):
        return  # perfil ilegível: melhor a pergunta na tela que estragar o arquivo
    projeto = dados.setdefault("projects", {}).setdefault(str(s.onde), {})
    if projeto.get("hasTrustDialogAccepted"):
        return
    projeto["hasTrustDialogAccepted"] = True
    temporario = perfil.with_name(perfil.name + ".ze")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2))
    temporario.replace(perfil)


def confiar_pasta_codex(s: "Sessao") -> None:
    """O mesmo para o Codex: `[projects."<pasta>"] trust_level = "trusted"` no config.toml da conta
    (o que o "Trust and continue" dele grava; pela linha de comando ele não aceita)."""
    try:
        conta = contas.Contas().achar(s.conta) if s.conta else contas.Contas().em_uso("codex")
    except contas.ContaErro:
        return
    arquivo = conta.onde / "config.toml"
    try:
        texto = arquivo.read_text() if arquivo.is_file() else ""
        projetos = tomllib.loads(texto).get("projects", {})
    except (OSError, tomllib.TOMLDecodeError):
        return
    if projetos.get(str(s.onde), {}).get("trust_level") == "trusted":
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with arquivo.open("a") as f:
        f.write(f'\n[projects.{json.dumps(str(s.onde))}]\ntrust_level = "trusted"\n')


def conversa_claude_existe(s: "Sessao") -> bool:
    """A conversa do Claude que a sessão retomaria está salva na pasta da conta?"""
    try:
        onde = contas.Contas().achar(s.conta).onde
    except contas.ContaErro:
        onde = contas.Contas().em_uso("claude").onde
    return any((onde / "projects").glob(f"*/{s.sdk_sessao}.jsonl"))


PREFIXO_SKILL = "zervis-"  # os atalhos que o Zé põe no projeto, para reconhecer e limpar


CONECTORES = "conectores.json"  # na pasta da sessão, 0600: os conectores do projeto (Claude)


SEM_APROVACAO = (
    "Sem o terminal aberto, só as ferramentas livres do conector. Para esta, a pessoa abre o "
    "terminal da sessão (o Claude pergunta ali) ou a libera em Conectores."
)


def conectores_do_projeto(s: "Sessao") -> mcp_externo.Externos:
    """Os conectores do Zé marcados para o projeto desta sessão (ADR 0037)."""
    try:
        return mcp_externo.para_projeto(Path(s.pasta))
    except mcp_externo.McpInvalido as erro:
        log.warning("sessão %s sem conectores: %s", s.id, erro)
        return mcp_externo.Externos()


def pede_aprovacao(nome: str, externos: mcp_externo.Externos) -> bool:
    """Uma ferramenta de conector que não é livre (sem terminal, não há a quem perguntar)."""
    partes = nome.split("__")
    return (
        len(partes) == 3
        and partes[0] == "mcp"
        and partes[1] in externos.servidores
        and nome not in externos.livres
    )


def arquivo_de_conectores(destino: Path, externos: mcp_externo.Externos) -> Path | None:
    """Claude: os conectores num arquivo 0600 (`--mcp-config`), com os segredos fora da linha de
    comando, que outros processos leem. Sem conectores, o arquivo sai."""
    if not externos.servidores:
        destino.unlink(missing_ok=True)
        return None
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = destino.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(json.dumps({"mcpServers": externos.servidores}))
    temporario.replace(destino)
    return destino


def _tabela_toml(valores: dict[str, str]) -> str:
    return "{" + ", ".join(f"{json.dumps(k)} = {json.dumps(v)}" for k, v in valores.items()) + "}"


def conectores_codex(
    externos: mcp_externo.Externos, perguntar: bool = False
) -> tuple[list[str], dict[str, str]]:
    """Codex: os conectores do projeto em `-c mcp_servers.*` e os segredos no ambiente do
    processo (`env_vars`, `env_http_headers`), nunca na linha de comando. Sem como perguntar ao
    Zé (`codex exec`), só as ferramentas livres (`enabled_tools`). No terminal, com o gancho de
    permissão (`perguntar`, ADR 0039): todas pedem aprovação (`prompt`, que passa pelo gancho),
    as livres já vão aprovadas (`approve`) e as bloqueadas nem aparecem (`disabled_tools`).
    Conferido no Codex 0.159 em 27/10/2026: `auto` não libera, deixa o Codex decidir."""
    argumentos: list[str] = []
    segredos: dict[str, str] = {}
    for nome, config in externos.servidores.items():
        prefixo = f"mcp__{nome}__"
        livres = [f.removeprefix(prefixo) for f in externos.livres if f.startswith(prefixo)]
        bloqueadas = [f.removeprefix(prefixo) for f in externos.bloqueadas if f.startswith(prefixo)]
        if not livres and not perguntar:
            continue
        base = f"mcp_servers.{nome}"
        if config["type"] == "stdio":
            argumentos += ["-c", f"{base}.command={json.dumps(config['command'])}"]
            argumentos += ["-c", f"{base}.args={json.dumps(config.get('args', []))}"]
            if variaveis := config.get("env"):
                segredos.update(variaveis)
                argumentos += ["-c", f"{base}.env_vars={json.dumps(sorted(variaveis))}"]
        else:
            argumentos += ["-c", f"{base}.url={json.dumps(config['url'])}"]
            cabecalhos = {}
            for i, (cabecalho, valor) in enumerate(sorted(config.get("headers", {}).items())):
                variavel = f"ZE_MCP_{nome.upper().replace('-', '_')}_{i}"
                segredos[variavel] = valor
                cabecalhos[cabecalho] = variavel
            if cabecalhos:
                argumentos += ["-c", f"{base}.env_http_headers={_tabela_toml(cabecalhos)}"]
        if not perguntar:
            argumentos += ["-c", f"{base}.enabled_tools={json.dumps(livres)}"]
            continue
        argumentos += ["-c", f'{base}.default_tools_approval_mode="prompt"']
        if bloqueadas:
            argumentos += ["-c", f"{base}.disabled_tools={json.dumps(bloqueadas)}"]
        for ferramenta in livres:
            if NOME_DE_FERRAMENTA.fullmatch(ferramenta):  # outra forma de nome segue pedindo
                argumentos += ["-c", f'{base}.tools.{ferramenta}.approval_mode="approve"']
    return argumentos, segredos


def ganchos_codex() -> list[str]:
    """Os ganchos do Zé no Codex: a permissão repassada à rota do painel e a interrupção nos
    eventos da sessão. Os comandos são sempre os mesmos (o resto vem do ambiente), então a
    pessoa confia neles uma vez por conta do Codex ("Hooks need review")."""
    permissao = f"{shlex.quote(sys.executable)} -c {shlex.quote(GANCHO_CODEX)}"
    interrupcao = 'cat >> "$ZE_EVENTOS"; echo >> "$ZE_EVENTOS"'
    prazo = int(PRAZO_CODEX_S) + 10
    return [
        "-c",
        f'hooks.PermissionRequest=[{{matcher="", hooks=[{{type="command", '
        f"command={json.dumps(permissao)}, timeout={prazo}}}]}}]",
        "-c",
        f'hooks.Interrupt=[{{matcher="", hooks=[{{type="command", '
        f"command={json.dumps(interrupcao)}}}]}}]",
    ]


PASTAS_DE_SKILLS = (".claude/skills", ".agents/skills")  # onde o Claude Code e o Codex procuram


def ligar_skills_no_projeto(pasta: Path, skills: Any) -> None:
    """Atalhos `zervis-<nome>` para as skills do Zé marcadas para as sessões, nas pastas onde o
    Claude Code e o Codex procuram skills do projeto; tira os que sobraram. Os atalhos ficam fora
    do Git do projeto pela exclusão local (`info/exclude`), nunca num commit."""
    for relativa in PASTAS_DE_SKILLS:
        _ligar_em(pasta, relativa, skills)


def _ligar_em(pasta: Path, relativa: str, skills: Any) -> None:
    marcadas = {nome for nome, _ in skills.para_sessoes()} if skills is not None else set()
    destino = pasta / relativa
    existentes = (
        {p.name for p in destino.iterdir() if p.name.startswith(PREFIXO_SKILL) and p.is_symlink()}
        if destino.is_dir()
        else set()
    )
    if not marcadas and not existentes:
        return
    destino.mkdir(parents=True, exist_ok=True)
    for nome in marcadas:
        atalho, alvo = destino / f"{PREFIXO_SKILL}{nome}", Path(skills.pasta) / nome
        if atalho.is_symlink() and atalho.resolve() == alvo.resolve():
            continue
        atalho.unlink(missing_ok=True)
        atalho.symlink_to(alvo, target_is_directory=True)
    for nome in existentes - {f"{PREFIXO_SKILL}{n}" for n in marcadas}:
        (destino / nome).unlink(missing_ok=True)
    for vazia in (destino, destino.parent):
        with contextlib.suppress(OSError):
            vazia.rmdir()  # só sai se ficou vazia
    _fora_do_git(pasta, f"/{relativa}/{PREFIXO_SKILL}*")


def _fora_do_git(pasta: Path, padrao: str) -> None:
    """Acrescenta o padrão à exclusão local do Git do projeto, se for um repositório."""
    r = subprocess.run(  # noqa: S603 (git com argumentos fixos)
        ["git", "-C", str(pasta), "rev-parse", "--git-path", "info/exclude"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return
    exclude = Path(r.stdout.strip())
    if not exclude.is_absolute():
        exclude = pasta / exclude
    atual = exclude.read_text() if exclude.exists() else ""
    if padrao not in atual.splitlines():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(
            atual + ("" if atual.endswith("\n") or not atual else "\n") + padrao + "\n"
        )


def regras_de_skills(skills: Any) -> tuple[str, Path | None]:
    """O que as sessões recebem das skills do usuário: o aviso com o catálogo e a pasta para ler
    (vazio sem skills). O mesmo para o terminal e para o agente sem tela."""
    marcadas = skills.para_sessoes() if skills is not None else []
    if not marcadas:
        return "", None
    texto = (
        "\nO usuário tem skills: procedimentos do jeito dele. Antes de uma tarefa que uma "
        f"delas cobre, leia {skills.pasta}/<nome>/SKILL.md e siga.\n" + skills.catalogo(marcadas)
    )
    return texto, Path(skills.pasta)


def comando_terminal(
    s: "Sessao",
    pedido: str,
    eventos: Path,
    contexto: Path | None = None,
    externos: mcp_externo.Externos | None = None,
    arquivo_mcp: Path | None = None,
    permissao: str = "",
) -> list[str]:
    """O agente interativo da sessão: retoma a conversa nativa e conta ao Zé o que acontece.
    `contexto` (a passagem) entra sem virar pedido. As skills do Zé chegam pela pasta do projeto
    (`ligar_skills_no_projeto`); os conectores do projeto, pelo `arquivo_mcp` (Claude) ou pela
    configuração do Codex, com os segredos no ambiente (`conectores_codex`). Com `permissao` (a
    rota do painel), os pedidos de permissão do Claude vão também ao Zé (ADR 0039)."""
    externos = externos or mcp_externo.Externos()
    if s.motor == "codex":
        avisar = ["sh", "-c", 'printf "%s\\n" "$1" >> "$0"', str(eventos)]  # + o JSON do Codex
        cmd = [
            "codex",
            "--no-alt-screen",  # conserva a saída na barra de rolagem do xterm
            "-c",
            f"notify={json.dumps(avisar)}",
            "--sandbox",
            "workspace-write",
        ]
        texto = aimemory.orientacao(Path(s.pasta))
        if contexto is not None:  # conversa nova: instruções do desenvolvedor (TOML aceita JSON)
            passagem = json.loads(contexto.read_text())["hookSpecificOutput"]["additionalContext"]
            texto = f"{passagem}\n{texto}".strip()
        if texto:
            cmd += ["-c", f"developer_instructions={json.dumps(texto)}"]
        if s.modelo:
            cmd += ["-m", s.modelo]
        if s.esforco:
            cmd += ["-c", f'model_reasoning_effort="{s.esforco}"']
        cmd += conectores_codex(externos, bool(permissao))[0]
        if permissao:
            cmd += ganchos_codex()
        if s.sdk_sessao:
            cmd += ["resume", s.sdk_sessao]
        return [*cmd, *([pedido] if pedido else [])]
    gravar = f"cat >> {shlex.quote(str(eventos))}; echo >> {shlex.quote(str(eventos))}"
    hooks: dict[str, list[dict[str, Any]]] = dict(aimemory.hooks_claude().get("hooks", {}))
    for evento in HOOKS_DO_ZE:
        filtro = ACOES_DO_CLAUDE if evento == "PostToolUse" else ""
        hooks[evento] = [
            *hooks.get(evento, []),
            {"matcher": filtro, "hooks": [{"type": "command", "command": gravar}]},
        ]
    if contexto is not None:  # entregue uma vez só: o arquivo sai depois de lido
        c = shlex.quote(str(contexto))
        entregar = {"type": "command", "command": f"cat {c} 2>/dev/null && rm -f {c}"}
        hooks["SessionStart"] = [
            *hooks.get("SessionStart", []),
            {"matcher": "", "hooks": [entregar]},
        ]
    if permissao:
        # A ferramenta que pediu permissão rodou: só a assinatura dela, para o Zé saber que a
        # pessoa aprovou no terminal (a resposta inteira de um MCP pode ter dados de clientes).
        resumo = f"{shlex.quote(sys.executable)} -c {shlex.quote(RESUMO_DO_EVENTO)} >> "
        hooks["PostToolUse"] = [
            *hooks.get("PostToolUse", []),
            {
                "matcher": OUTRAS_COM_PERMISSAO,
                "hooks": [{"type": "command", "command": resumo + shlex.quote(str(eventos))}],
            },
        ]
        hooks["PermissionRequest"] = [
            *hooks.get("PermissionRequest", []),
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "http",
                        "url": permissao,
                        "headers": {"Authorization": f"Bearer ${{{VARIAVEL_PERMISSAO}}}"},
                        "allowedEnvVars": [VARIAVEL_PERMISSAO],
                        "timeout": int(PRAZO_PERMISSAO_S) + 10,
                    }
                ],
            },
        ]
    ajustes: dict[str, Any] = {"hooks": hooks}
    # Livres sem pergunta (as do conector e os comandos de teste, para a sessão iterar sozinha
    # até o resultado); bloqueadas nunca; o resto o Claude pergunta.
    ajustes["permissions"] = {
        "allow": [*INTERNET_LIVRE, *COMANDOS_LIVRES, *externos.livres],
        "deny": externos.bloqueadas,
    }
    cmd = [caminhos.claude()]
    if arquivo_mcp is not None:  # logo depois do comando: a opção aceita vários arquivos
        cmd += ["--mcp-config", str(arquivo_mcp)]
    cmd += [
        "--permission-mode",
        "acceptEdits",
        "--append-system-prompt",
        REGRAS.strip() + "\n" + aimemory.orientacao(Path(s.pasta)),
        "--settings",
        json.dumps(ajustes),
    ]
    if s.sdk_sessao:
        cmd += ["--resume", s.sdk_sessao]
    if s.modelo:
        cmd += ["--model", s.modelo]
    if s.esforco:
        cmd += ["--effort", s.esforco]
    return [*cmd, *([pedido] if pedido else [])]


def pastas_da_conta(s: "Sessao") -> list[Path]:
    """Onde a conta do agente guarda o login e as conversas (e o `~/.claude.json` da conta
    padrão do Claude, que fica fora da pasta)."""
    try:
        cs = contas.Contas()
        conta = cs.achar(s.conta) if s.conta else cs.em_uso(s.motor)
    except contas.ContaErro:
        return []
    pastas = [conta.onde]
    if s.motor == "claude" and conta.onde == Path.home() / ".claude":
        pastas.append(Path.home() / ".claude.json")
    return pastas


def git_comum(pasta: Path) -> list[Path]:
    """O `.git` de verdade de uma cópia isolada (worktree): fica fora da pasta, e o agente precisa
    dele para ler e fazer commit."""
    feito = subprocess.run(  # noqa: S603 (git com argumentos fixos)
        ["git", "-C", str(pasta), "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        capture_output=True,
        text=True,
    )
    comum = Path(feito.stdout.strip()) if feito.returncode == 0 and feito.stdout.strip() else None
    if comum is None or comum.is_relative_to(pasta):
        return []
    return [comum]


def isolar(s: "Sessao", comando: list[str], pasta_da_sessao: Path) -> list[str]:
    """O comando do agente, dentro do isolamento quando a sessão é protegida (ADR 0074)."""
    if not s.protegida:
        return comando
    onde = Path(s.worktree or s.pasta)
    escrita = [onde, pasta_da_sessao, *pastas_da_conta(s), *git_comum(onde)]
    escrita += [Path(p) for p in s.escrita]
    leitura = [b.parent for b in (aimemory.binario(),) if b is not None]
    # Onde o agente está instalado de verdade (o executável costuma ser um link para lá).
    if executavel := shutil.which(comando[0]):
        leitura.append(Path(executavel).resolve().parent.parent)
    return isolamento.envolver(comando, escrita, leitura, pasta=onde)
