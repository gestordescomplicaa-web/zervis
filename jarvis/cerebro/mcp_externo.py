"""MCPs externos ligados pelo usuário (como o `mcp_servers` do Hermes; ADR 0011).

Arquivo próprio, `~/.config/zervis/mcp.toml`, um bloco por servidor:

    [servidores.github]
    tipo = "stdio"                       # ou "http"
    comando = "npx"
    argumentos = ["-y", "@modelcontextprotocol/server-github"]
    ambiente = ["GITHUB_PERSONAL_ACCESS_TOKEN"]   # só nomes: o valor vem do ambiente do serviço
    livres = ["search_repositories"]     # ferramentas só de leitura, sem pergunta falada
    bloqueadas = ["delete_repository"]   # nem aparecem para o cérebro (e não custam tokens)
    projetos = ["loja-do-cliente"]       # também nas sessões de código destes projetos ("*": todos)
    ligado = true

    [servidores.agenda]
    tipo = "http"
    url = "https://exemplo/mcp"
    cabecalhos = { Authorization = "AGENDA_AUTH" }  # nome da variável com o valor do cabeçalho

Segredos nunca ficam no arquivo (docs/06-qualidade.md). Toda ferramenta externa pede aprovação
falada, menos as `livres`. Cada servidor ligado põe a descrição das ferramentas dele em todo turno:
o custo aparece no consumo do dia; ligue só o que usar.
"""

import contextlib
import json
import logging
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jarvis import lugares

log = logging.getLogger(__name__)
CAMINHO = lugares.CONFIG / "mcp.toml"
PAINEL = lugares.CONFIG / "mcp-painel.json"  # os conectores criados pelo painel
SEGREDOS = lugares.CONFIG / "chaves/mcp"  # <conector>/<VARIAVEL>, 0600
NOME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
RESERVADOS = {"jarvis"}
CHAVES = {
    "tipo",
    "comando",
    "argumentos",
    "ambiente",
    "url",
    "cabecalhos",
    "livres",
    "bloqueadas",
    "projetos",
    "ligado",
}
TODOS = "*"


class McpInvalido(ValueError):
    pass


@dataclass
class Externos:
    servidores: dict[str, dict[str, Any]] = field(default_factory=dict)
    livres: list[str] = field(default_factory=list)
    bloqueadas: list[str] = field(default_factory=list)  # fora da lista do cérebro
    nomes: dict[str, str] = field(default_factory=dict)  # mcp__servidor -> servidor (falas)


def _lista_de_textos(valor: Any, onde: str) -> list[str]:
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise McpInvalido(f"{onde} precisa ser lista de textos")
    return list(valor)


def _servidor(
    nome: str, bloco: dict[str, Any], env: dict[str, str], avisar: bool = True
) -> dict[str, Any] | None:
    desconhecidas = set(bloco) - CHAVES
    if desconhecidas:
        raise McpInvalido(f"{nome}: chave desconhecida {sorted(desconhecidas)[0]}")
    faltando = [
        v for v in _lista_de_textos(bloco.get("ambiente", []), f"{nome}.ambiente") if v not in env
    ]
    cabecalhos = bloco.get("cabecalhos", {})
    if not isinstance(cabecalhos, dict):
        raise McpInvalido(f"{nome}.cabecalhos precisa ser uma tabela")
    faltando += [v for v in cabecalhos.values() if v not in env]
    if faltando:
        if avisar:
            log.warning("MCP %s desligado: falta a variável %s no ambiente", nome, faltando[0])
        return None
    tipo = bloco.get("tipo", "stdio")
    if tipo == "stdio":
        if not isinstance(bloco.get("comando"), str):
            raise McpInvalido(f"{nome}: stdio precisa de comando")
        config: dict[str, Any] = {
            "type": "stdio",
            "command": bloco["comando"],
            "args": _lista_de_textos(bloco.get("argumentos", []), f"{nome}.argumentos"),
        }
        if bloco.get("ambiente"):
            config["env"] = {v: env[v] for v in bloco["ambiente"]}
        return config
    if tipo == "http":
        url = str(bloco.get("url", ""))
        partes = urlsplit(url)
        local = partes.hostname in ("127.0.0.1", "localhost", "::1")
        if partes.scheme != "https" and not (partes.scheme == "http" and local):
            raise McpInvalido(f"{nome}: http precisa de https (ou http em loopback)")
        config = {"type": "http", "url": url}
        if cabecalhos:
            config["headers"] = {k: env[v] for k, v in cabecalhos.items()}
        return config
    raise McpInvalido(f"{nome}: tipo deve ser stdio ou http")


def _blocos(caminho: Path, painel: Path | None) -> dict[str, tuple[dict[str, Any], str]]:
    """Os servidores do `mcp.toml` (origem "arquivo") e os do painel (origem "painel").

    O painel grava os dele num JSON à parte (o TOML, com os comentários do usuário, fica
    intocado) e pode desligar qualquer um pela lista `desligados`.
    """
    blocos: dict[str, tuple[dict[str, Any], str]] = {}
    if caminho.exists():
        try:
            dados = tomllib.loads(caminho.read_text())
        except tomllib.TOMLDecodeError as erro:
            raise McpInvalido(f"{caminho}: TOML inválido: {erro}") from None
        if set(dados) - {"servidores"}:
            raise McpInvalido(f"{caminho}: só a seção [servidores.<nome>] é aceita")
        for nome, bloco in (dados.get("servidores") or {}).items():
            blocos[nome] = (bloco, "arquivo")
    desligados: set[str] = set()
    if painel is not None and painel.exists():
        try:
            dados_painel = json.loads(painel.read_text())
        except ValueError:
            raise McpInvalido(f"{painel}: JSON inválido") from None
        desligados = set(dados_painel.get("desligados") or [])
        for nome, bloco in (dados_painel.get("servidores") or {}).items():
            if nome in blocos:
                raise McpInvalido(f"o conector {nome} já existe no mcp.toml")
            blocos[nome] = (bloco, "painel")
    for nome, (bloco, origem) in blocos.items():
        if not NOME.fullmatch(nome) or nome in RESERVADOS:
            raise McpInvalido(f"nome de servidor inválido ou reservado: {nome}")
        if not isinstance(bloco, dict):
            raise McpInvalido(f"[servidores.{nome}] precisa ser uma seção")
        if nome in desligados:
            blocos[nome] = ({**bloco, "ligado": False}, origem)
    return blocos


def _nomes_de_segredo(bloco: dict[str, Any]) -> list[str]:
    cabecalhos = bloco.get("cabecalhos") or {}
    valores = list(cabecalhos.values()) if isinstance(cabecalhos, dict) else []
    return [*(bloco.get("ambiente") or []), *valores]


def com_segredos(nome: str, bloco: dict[str, Any], env: dict[str, str]) -> dict[str, str]:
    """O ambiente com os segredos que o painel guardou para este conector (se faltarem no env)."""
    env = dict(env)
    for variavel in _nomes_de_segredo(bloco):
        if variavel in env or not isinstance(variavel, str):
            continue
        with contextlib.suppress(OSError):
            if valor := (SEGREDOS / nome / variavel).read_text().strip():
                env[variavel] = valor
    return env


def carregar(
    caminho: Path = CAMINHO,
    env: dict[str, str] | None = None,
    painel: Path | None = None,
    avisar: bool = True,
) -> Externos:
    """Os conectores ligados, prontos para o cérebro. `avisar=False` só confere (o painel
    compara com os que estão valendo, sem encher o registro)."""
    externos = Externos()
    base = os.environ.copy() if env is None else env
    for nome, (bloco, _origem) in _blocos(caminho, painel).items():
        if bloco.get("ligado", True) is False:
            continue
        config = _servidor(nome, bloco, com_segredos(nome, bloco, base), avisar)
        if config is None:
            continue
        externos.servidores[nome] = config
        externos.nomes[f"mcp__{nome}"] = nome
        livres = _lista_de_textos(bloco.get("livres", []), f"{nome}.livres")
        bloqueadas = _lista_de_textos(bloco.get("bloqueadas", []), f"{nome}.bloqueadas")
        if set(livres) & set(bloqueadas):
            raise McpInvalido(
                f"{nome}: {sorted(set(livres) & set(bloqueadas))[0]} livre e bloqueada"
            )
        externos.livres += [f"mcp__{nome}__{f}" for f in livres]
        externos.bloqueadas += [f"mcp__{nome}__{f}" for f in bloqueadas]
    if externos.servidores and avisar:
        log.info("MCPs externos ligados: %s", ", ".join(externos.servidores))
    return externos


def para_projeto(
    pasta: Path,
    caminho: Path | None = None,
    painel: Path | None = None,
    env: dict[str, str] | None = None,
) -> Externos:
    """Os conectores ligados que valem nas sessões de código de um projeto: os que citam o nome
    da pasta (ou `*`) em `projetos`. Sem `projetos`, o conector fica só na conversa com o Zé: o
    sistema de um cliente não aparece no projeto de outro (ADR 0037)."""
    caminho = CAMINHO if caminho is None else caminho
    painel = PAINEL if painel is None else painel
    blocos = _blocos(caminho, painel)
    escolhidos = []
    for nome, (bloco, _origem) in blocos.items():
        projetos = _lista_de_textos(bloco.get("projetos", []), f"{nome}.projetos")
        if TODOS in projetos or pasta.name in projetos:
            escolhidos.append(nome)
    todos = carregar(caminho, env, painel, avisar=False)
    prefixos = tuple(f"mcp__{nome}__" for nome in escolhidos)
    return Externos(
        servidores={n: c for n, c in todos.servidores.items() if n in escolhidos},
        livres=[f for f in todos.livres if f.startswith(prefixos)],
        bloqueadas=[f for f in todos.bloqueadas if f.startswith(prefixos)],
        nomes={k: v for k, v in todos.nomes.items() if v in escolhidos},
    )
