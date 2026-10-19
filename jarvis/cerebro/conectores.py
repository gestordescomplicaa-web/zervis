"""Os conectores MCP pelo painel (09/10/2026): a janela do Zé para outros sistemas.

Hoje a maior parte da conversa entre sistemas é MCP. O `mcp.toml` (mcp_externo.py) continua
valendo e intocado; o painel grava os conectores dele em `mcp-painel.json`, guarda os segredos
como as chaves de API (um arquivo 0600 por variável, nunca devolvido) e pode ligar e desligar
qualquer um. "Testar" sobe o servidor de verdade e lista as ferramentas, para o usuário escolher
o que é livre, o que pede aprovação falada e o que fica bloqueado.
"""

import contextlib
import itertools
import json
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from jarvis.cerebro import mcp_externo, mcp_oauth
from jarvis.cerebro.mcp_externo import McpInvalido

VARIAVEL = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
# O valor de um segredo fora do lugar dele (argumentos ou url): chaves com formato conhecido e
# `nome=valor` ou `--nome valor` com nome de segredo. Caminho de arquivo com a chave não conta.
_NOME_SEGREDO = r"(?:token|secret|password|passwd|senha|api[-_]?key|apikey|access[-_]?key)"
CHAVE_CONHECIDA = re.compile(
    r"\b(?:sk-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}"
    r"|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{30,})"
)
NOME_E_VALOR = re.compile(rf"[\w-]*{_NOME_SEGREDO}[\w-]*=(?!\$)[^&\s]{{6,}}", re.IGNORECASE)
OPCAO_DE_SEGREDO = re.compile(rf"--?[\w-]*{_NOME_SEGREDO}[\w-]*", re.IGNORECASE)
CAMINHO = re.compile(r"(file|path|dir)", re.IGNORECASE)
PROJETO = re.compile(r"[^/\\\x00*]{1,128}")  # o nome da pasta, sem caminho
PROTOCOLO = "2025-06-18"
LIMITE_TESTE_S = 25.0


def _ler_painel(painel: Path) -> dict[str, Any]:
    try:
        dados: dict[str, Any] = json.loads(painel.read_text())
    except (OSError, ValueError):
        return {"servidores": {}, "desligados": []}
    dados.setdefault("servidores", {})
    dados.setdefault("desligados", [])
    return dados


def _gravar_painel(painel: Path, dados: dict[str, Any]) -> None:
    painel.parent.mkdir(parents=True, exist_ok=True)
    temporario = painel.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1))
    temporario.replace(painel)


def listar(
    caminho: Path = mcp_externo.CAMINHO,
    painel: Path = mcp_externo.PAINEL,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Todos os conectores, com o que falta (segredo sem valor) e de onde vieram."""
    base = os.environ.copy() if env is None else env
    saida = []
    for nome, (bloco, origem) in mcp_externo._blocos(caminho, painel).items():
        env_com = mcp_externo.com_segredos(nome, bloco, base)
        segredos = [v for v in mcp_externo._nomes_de_segredo(bloco) if isinstance(v, str)]
        saida.append(
            {
                "nome": nome,
                "origem": origem,
                "tipo": bloco.get("tipo", "stdio"),
                "comando": bloco.get("comando", ""),
                "argumentos": bloco.get("argumentos", []),
                "url": bloco.get("url", ""),
                "ambiente": bloco.get("ambiente", []),
                "cabecalhos": bloco.get("cabecalhos", {}),
                "livres": bloco.get("livres", []),
                "bloqueadas": bloco.get("bloqueadas", []),
                "projetos": bloco.get("projetos", []),
                "oauth": bloco.get("oauth") is True,
                "conectado": bloco.get("oauth") is True and mcp_oauth.PADRAO.conectado(nome),
                "app_proprio": mcp_oauth.PADRAO.cliente_proprio(nome) is not None,
                "ligado": bloco.get("ligado", True) is not False,
                "segredos": {v: v in env_com for v in segredos},
            }
        )
    return sorted(saida, key=lambda c: (c["origem"] != "painel", c["nome"]))


def _tem_segredo(argumentos: list[str], url: str) -> bool:
    """Um valor de segredo escrito nos argumentos ou na url, que iriam para o arquivo do painel
    e para a linha de comando (visível a outros processos)."""
    textos = [*argumentos, url]
    if any(CHAVE_CONHECIDA.search(t) or NOME_E_VALOR.search(t) for t in textos):
        return True
    for opcao, valor in itertools.pairwise(argumentos):
        if (
            OPCAO_DE_SEGREDO.fullmatch(opcao)
            and not CAMINHO.search(opcao)
            and not valor.startswith(("-", "$"))
        ):
            return True
    return False


def _bloco_valido(nome: str, dados: dict[str, Any]) -> dict[str, Any]:
    if not mcp_externo.NOME.fullmatch(nome) or nome in mcp_externo.RESERVADOS:
        raise McpInvalido("nome: minúsculas, números, hífen ou sublinhado (até 32)")
    bloco: dict[str, Any] = {"tipo": dados.get("tipo", "stdio")}
    if bloco["tipo"] == "stdio":
        bloco["comando"] = str(dados.get("comando", "")).strip()
        bloco["argumentos"] = [str(a) for a in dados.get("argumentos") or [] if str(a).strip()]
    else:
        bloco["url"] = str(dados.get("url", "")).strip()
        if dados.get("oauth") is True:
            bloco["oauth"] = True
    ambiente = [str(v).strip() for v in dados.get("ambiente") or [] if str(v).strip()]
    cabecalhos = {
        str(k).strip(): str(v).strip() for k, v in (dados.get("cabecalhos") or {}).items()
    }
    for nome_cab, variavel in cabecalhos.items():
        if not VARIAVEL.fullmatch(variavel):
            # Sem repetir o que veio: quase sempre é o próprio token colado no lugar do nome.
            raise McpInvalido(
                f"cabeçalho {nome_cab[:40]}: use o nome de uma variável, como N8N_AUTH; "
                "o valor se guarda no cartão do conector"
            )
    for variavel in ambiente:
        if not VARIAVEL.fullmatch(variavel):
            raise McpInvalido(f"variável {variavel[:40]!r}: use MAIÚSCULAS_COM_SUBLINHADO")
    if bloco.get("oauth") and (ambiente or cabecalhos):
        raise McpInvalido("com login (OAuth), o conector não leva segredos próprios")
    if ambiente:
        bloco["ambiente"] = ambiente
    if cabecalhos:
        bloco["cabecalhos"] = cabecalhos
    for chave in ("livres", "bloqueadas"):
        if valores := [str(v) for v in dados.get(chave) or []]:
            bloco[chave] = valores
    projetos = list(dict.fromkeys(str(p).strip() for p in dados.get("projetos") or []))
    if projetos := [p for p in projetos if p]:
        if not all(p == mcp_externo.TODOS or PROJETO.fullmatch(p) for p in projetos):
            raise McpInvalido("projeto: o nome da pasta do projeto, ou * para todos")
        bloco["projetos"] = projetos
    if set(bloco.get("livres", [])) & set(bloco.get("bloqueadas", [])):
        raise McpInvalido("uma ferramenta não pode ser livre e bloqueada")
    if _tem_segredo(bloco.get("argumentos", []), bloco.get("url", "")):
        raise McpInvalido(
            "segredo nos argumentos ou no endereço: use o nome de uma variável e guarde o valor "
            "no cartão do conector"
        )
    # A mesma validação do carregador, com segredos fictícios (só a forma importa aqui).
    ficticio = {v: "x" for v in [*ambiente, *cabecalhos.values()]}
    mcp_externo._servidor(nome, bloco, ficticio)
    return bloco


def salvar(
    nome: str,
    dados: dict[str, Any],
    painel: Path = mcp_externo.PAINEL,
    caminho: Path = mcp_externo.CAMINHO,
) -> dict[str, Any]:
    """Cria ou troca um conector do painel (os do mcp.toml se editam no arquivo)."""
    todos = mcp_externo._blocos(caminho, painel)
    atual = _ler_painel(painel)
    if nome in todos and todos[nome][1] == "arquivo":
        raise McpInvalido(f"{nome} vem do mcp.toml: edite lá (aqui dá para ligar e desligar)")
    bloco = _bloco_valido(nome, dados)
    atual["servidores"][nome] = bloco
    _gravar_painel(painel, atual)
    return bloco


def remover(nome: str, painel: Path = mcp_externo.PAINEL) -> None:
    atual = _ler_painel(painel)
    if nome not in atual["servidores"]:
        raise McpInvalido("só dá para remover conectores criados pelo painel")
    del atual["servidores"][nome]
    atual["desligados"] = [d for d in atual["desligados"] if d != nome]
    _gravar_painel(painel, atual)
    with contextlib.suppress(OSError):
        for arquivo in (mcp_externo.SEGREDOS / nome).iterdir():
            arquivo.unlink()


def ligar(nome: str, ligado: bool, painel: Path = mcp_externo.PAINEL) -> None:
    atual = _ler_painel(painel)
    desligados = [d for d in atual["desligados"] if d != nome]
    if not ligado:
        desligados.append(nome)
    atual["desligados"] = desligados
    _gravar_painel(painel, atual)


def gravar_segredo(nome: str, variavel: str, valor: str) -> None:
    if not mcp_externo.NOME.fullmatch(nome) or not VARIAVEL.fullmatch(variavel):
        raise McpInvalido("conector ou variável inválida")
    valor = valor.strip()
    if not valor or len(valor) > 4000:
        raise McpInvalido("segredo vazio ou grande demais")
    pasta = mcp_externo.SEGREDOS / nome
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    for p in (mcp_externo.SEGREDOS, pasta):
        p.chmod(0o700)
    destino = pasta / variavel
    temporario = destino.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(valor + "\n")
    temporario.replace(destino)


# --- importar: a configuração que o serviço fornece, colada como veio ------------------------

NAO_RECONHECIDA = "Configuração não reconhecida. Cole o JSON do MCP ou o comando curl."
# Valor de exemplo, não segredo: "<token>", "YOUR_API_KEY", "${TOKEN}", "SEU_TOKEN".
EXEMPLO = re.compile(r"^$|<.*>|\$\{|(^|\s)(your|seu|sua)[_-]", re.IGNORECASE)


def _nome_de(texto: str) -> str:
    nome = re.sub(r"[^a-z0-9_-]+", "-", texto.lower()).strip("-_")[:32].strip("-_")
    return nome or "conector"


def _variavel_de(*partes: str) -> str:
    variavel = re.sub(r"[^A-Z0-9]+", "_", "_".join(partes).upper()).strip("_")
    if not variavel[:1].isalpha():
        variavel = "MCP_" + variavel
    return variavel[:64]


def _de_curl(texto: str) -> list[tuple[str, dict[str, Any]]]:
    import shlex

    try:
        partes = shlex.split(texto.replace("\\\n", " "))
    except ValueError:
        raise McpInvalido(NAO_RECONHECIDA) from None
    url, cabecalhos = "", {}
    for anterior, parte in itertools.pairwise(["", *partes]):
        if anterior in ("-H", "--header") and ":" in parte:
            chave, valor = parte.split(":", 1)
            cabecalhos[chave.strip()] = valor.strip()
        elif not url and parte.startswith(("https://", "http://")):
            url = parte
    if not url:
        raise McpInvalido(NAO_RECONHECIDA)
    # Os de protocolo vêm do próprio Zé; só os de acesso viram segredo.
    for comum in ("Content-Type", "Accept", "User-Agent"):
        for chave in [c for c in cabecalhos if c.lower() == comum.lower()]:
            del cabecalhos[chave]
    host = re.sub(r"^www\.", "", url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0])
    return [(host.split(".")[0], {"url": url, "headers": cabecalhos})]


def _de_json(texto: str) -> list[tuple[str, dict[str, Any]]]:
    dados: Any = None
    for tentativa in (texto, "{" + texto.strip().rstrip(",") + "}"):  # aceita o trecho sem chaves
        with contextlib.suppress(ValueError):
            dados = json.loads(tentativa)
            break
    if not isinstance(dados, dict):
        raise McpInvalido(NAO_RECONHECIDA)
    for chave in ("mcpServers", "servers", "mcp_servers"):
        if isinstance(dados.get(chave), dict):
            dados = dados[chave]
            break
    if "url" in dados or "command" in dados:  # um servidor só, sem nome
        dados = {"conector": dados}
    servidores = [(k, v) for k, v in dados.items() if isinstance(v, dict)]
    if not servidores:
        raise McpInvalido(NAO_RECONHECIDA)
    return servidores


def _tabela(valor: Any, alvo: str, campo: str) -> dict[str, Any]:
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        raise McpInvalido(f"{alvo}: {campo} precisa ser um objeto")
    return {str(k): v for k, v in valor.items()}


def ler_configuracao(texto: str) -> list[tuple[str, dict[str, Any]]]:
    """(nome sugerido, servidor) no formato `mcpServers` (Claude, Cursor, n8n) ou de um curl."""
    texto = texto.strip()
    return _de_curl(texto) if texto.startswith("curl") else _de_json(texto)


def importar(
    texto: str,
    nome: str = "",
    projetos: list[str] | None = None,
    painel: Path = mcp_externo.PAINEL,
    caminho: Path = mcp_externo.CAMINHO,
) -> list[str]:
    """Cria (ou troca) os conectores da configuração colada. Os valores dos cabeçalhos e do
    `env` vão para os segredos 0600 e nunca para o arquivo; as permissões já escolhidas
    continuam. Nenhuma mensagem de erro repete o que foi colado."""
    servidores = ler_configuracao(texto)
    if nome and len(servidores) > 1:
        raise McpInvalido("a configuração tem mais de um servidor: deixe o nome em branco")
    atuais = _ler_painel(painel)["servidores"]
    feitos = []
    for chave, servidor in servidores:
        alvo = nome or _nome_de(chave)
        tipo = str(servidor.get("type") or servidor.get("transport") or "")
        if tipo.lower() == "sse":
            raise McpInvalido(f"{alvo}: servidor SSE; o Zé usa MCP por HTTP (streamable)")
        segredos: dict[str, str] = {}
        dados: dict[str, Any]
        if servidor.get("command"):
            ambiente = []
            for variavel, valor in _tabela(servidor.get("env"), alvo, "env").items():
                variavel = variavel if VARIAVEL.fullmatch(variavel) else _variavel_de(variavel)
                ambiente.append(variavel)
                segredos[variavel] = str(valor)
            dados = {
                "tipo": "stdio",
                "comando": str(servidor["command"]),
                "argumentos": [str(a) for a in servidor.get("args") or [] if isinstance(a, str)],
                "ambiente": ambiente,
            }
        elif servidor.get("url"):
            cabecalhos = {}
            for cabecalho, valor in _tabela(servidor.get("headers"), alvo, "headers").items():
                variavel = _variavel_de(alvo, cabecalho)
                cabecalhos[str(cabecalho)] = variavel
                segredos[variavel] = str(valor)
            dados = {"tipo": "http", "url": str(servidor["url"]), "cabecalhos": cabecalhos}
        else:
            raise McpInvalido(f"{alvo}: sem url nem command")
        anterior = atuais.get(alvo, {})
        dados.update(
            livres=anterior.get("livres", []),
            bloqueadas=anterior.get("bloqueadas", []),
            projetos=projetos if projetos is not None else anterior.get("projetos", []),
        )
        salvar(alvo, dados, painel, caminho)
        for variavel, valor in segredos.items():
            if not EXEMPLO.search(valor.strip()):
                gravar_segredo(alvo, variavel, valor)
        feitos.append(alvo)
    return feitos


# --- testar: sobe o servidor e lista as ferramentas -----------------------------------------


def _pedido(id_: int | None, metodo: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": metodo, "params": params or {}}
    if id_ is not None:
        msg["id"] = id_
    return msg


INICIAR = {
    "protocolVersion": PROTOCOLO,
    "capabilities": {},
    "clientInfo": {"name": "ze", "version": "1"},
}


def _ferramentas(resposta: dict[str, Any]) -> list[dict[str, str]]:
    if "error" in resposta:
        raise McpInvalido(str(resposta["error"].get("message", resposta["error"]))[:200])
    return [
        {"nome": str(t.get("name", "")), "descricao": str(t.get("description", ""))[:240]}
        for t in (resposta.get("result") or {}).get("tools", [])
    ]


def _testar_stdio(config: dict[str, Any], env: dict[str, str]) -> list[dict[str, str]]:
    processo = subprocess.Popen(  # noqa: S603 (o comando que o próprio usuário cadastrou)
        [config["command"], *config.get("args", [])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={**env, **config.get("env", {})},
        text=True,
    )
    linhas: queue.Queue[str] = queue.Queue()

    def ler() -> None:
        assert processo.stdout is not None  # noqa: S101
        for linha in processo.stdout:
            linhas.put(linha)

    threading.Thread(target=ler, daemon=True).start()
    try:
        assert processo.stdin is not None  # noqa: S101
        for msg in (
            _pedido(1, "initialize", INICIAR),
            _pedido(None, "notifications/initialized"),
            _pedido(2, "tools/list"),
        ):
            processo.stdin.write(json.dumps(msg) + "\n")
        processo.stdin.flush()
        fim = time.monotonic() + LIMITE_TESTE_S
        while time.monotonic() < fim:
            try:
                linha = linhas.get(timeout=0.5)
            except queue.Empty:
                if processo.poll() is not None:
                    raise McpInvalido("o servidor fechou sem responder") from None
                continue
            with contextlib.suppress(ValueError):
                dados = json.loads(linha)
                if dados.get("id") == 2:
                    return _ferramentas(dados)
        raise McpInvalido(f"sem resposta em {LIMITE_TESTE_S:.0f} s")
    finally:
        processo.kill()


def _post(url: str, msg: dict[str, Any], cab: dict[str, str]) -> tuple[dict[str, Any], str]:
    pedido = urllib.request.Request(  # noqa: S310 (http(s) já validado pelo carregador)
        url,
        data=json.dumps(msg).encode(),
        headers={
            **cab,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": mcp_oauth.AGENTE,
        },
    )
    with urllib.request.urlopen(pedido, timeout=LIMITE_TESTE_S) as resp:  # noqa: S310
        sessao = resp.headers.get("Mcp-Session-Id", "")
        corpo = resp.read().decode("utf-8", "replace")
    if not corpo.strip():
        return {}, sessao
    if corpo.lstrip().startswith("{"):
        return json.loads(corpo), sessao
    for linha in corpo.splitlines():  # SSE: a resposta vem numa linha "data:"
        if linha.startswith("data:"):
            with contextlib.suppress(ValueError):
                return json.loads(linha[5:]), sessao
    return {}, sessao


def _acesso_negado(codigo: int, cabecalhos: dict[str, str]) -> str:
    """401/403 com a causa mais comum quando dá para ver sem mostrar o segredo: o token sem o
    tipo no Authorization (o n8n e a maioria dos MCPs pedem `Bearer <token>`)."""
    sem_tipo = any(
        nome.lower() == "authorization" and " " not in valor.strip()
        for nome, valor in cabecalhos.items()
    )
    if sem_tipo:
        return f"Acesso negado (HTTP {codigo}). O Authorization está sem o tipo, como Bearer."
    return f"Acesso negado (HTTP {codigo}). Confira o segredo."


def _testar_http(config: dict[str, Any]) -> list[dict[str, str]]:
    cab = dict(config.get("headers", {}))
    try:
        _, sessao = _post(config["url"], _pedido(1, "initialize", INICIAR), cab)
        if sessao:
            cab["Mcp-Session-Id"] = sessao
        _post(config["url"], _pedido(None, "notifications/initialized"), cab)
        resposta, _ = _post(config["url"], _pedido(2, "tools/list"), cab)
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            raise McpInvalido(_acesso_negado(erro.code, config.get("headers", {}))) from None
        raise McpInvalido(f"HTTP {erro.code}") from None
    except (urllib.error.URLError, OSError) as erro:
        raise McpInvalido(f"não conectou ({type(erro).__name__})") from None
    return _ferramentas(resposta)


def testar(
    nome: str,
    caminho: Path = mcp_externo.CAMINHO,
    painel: Path = mcp_externo.PAINEL,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    blocos = mcp_externo._blocos(caminho, painel)
    if nome not in blocos:
        raise McpInvalido("conector desconhecido")
    bloco = blocos[nome][0]
    base = mcp_externo.com_segredos(nome, bloco, os.environ.copy() if env is None else env)
    config = mcp_externo._servidor(nome, bloco, base, avisar=False)
    if config is None and bloco.get("oauth") is True:
        return {"ok": False, "erro": "falta entrar"}
    if config is None:
        faltam = [v for v in mcp_externo._nomes_de_segredo(bloco) if v not in base]
        return {"ok": False, "erro": "falta o segredo " + ", ".join(faltam)}
    inicio = time.monotonic()
    try:
        ferramentas = (
            _testar_stdio(config, base) if config["type"] == "stdio" else _testar_http(config)
        )
    except (McpInvalido, OSError) as erro:
        return {"ok": False, "erro": str(erro)[:200] or type(erro).__name__}
    return {
        "ok": True,
        "ms": round((time.monotonic() - inicio) * 1000),
        "ferramentas": ferramentas,
    }
