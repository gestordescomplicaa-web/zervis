"""Servidor MCP `jarvis` dentro do processo (docs/04-arquitetura.md): sessões, memória e histórico.

Cada grupo de ferramentas mora no seu módulo (sessões, aprendizado, automacoes, sistema, tela,
manutencao, navegador, conectores);
aqui ficam a montagem, a lista do que passa sem perguntar e os ganchos do ClaudeBrain.

Leitura (projetos, situação, saída) passa sem perguntar; delegar, responder a um agente, criar
projeto, abrir frente, mudar status e renomear passam pela aprovação falada do `can_use_tool`.
Apagar não existe aqui de propósito: excluir uma sessão é no painel (decisão de 06/10/2026).
"""

import dataclasses
import time
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server

from jarvis import atividade
from jarvis.automacoes.jobs import Jobs
from jarvis.cerebro.ferramentas import aprendizado as g_aprendizado
from jarvis.cerebro.ferramentas import automacoes as g_automacoes
from jarvis.cerebro.ferramentas import conectores as g_conectores
from jarvis.cerebro.ferramentas import manutencao as g_manutencao
from jarvis.cerebro.ferramentas import navegador as g_navegador
from jarvis.cerebro.ferramentas import sessoes as g_sessoes
from jarvis.cerebro.ferramentas import sistema as g_sistema
from jarvis.cerebro.ferramentas import tela as g_tela
from jarvis.cerebro.ferramentas.comum import _mudanca, _skill_nova
from jarvis.habilidades import revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import SkillErro, Skills
from jarvis.memoria.curta import Memoria, MemoriaErro
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.sessoes import Sessoes
from jarvis.rosto.tela import Tela
from jarvis.sistema.politica import Sistema

SERVIDOR = "jarvis"
LEITURA = [
    "sessoes_listar",
    "sessao_ler",
    "historico_buscar",
    "historico_ler",
    "skills_ver",
    "sugestoes_listar",
    "sugestao_descartar",
    "automacoes_listar",
    "sistema_buscar",
    "sistema_estado",
    "automacao_lembrete",  # o usuário pediu o lembrete; perguntar "posso?" de novo seria ruído
    "tela_ver",
    "tela_agir",  # só a própria tela do JARVIS: abrir, mostrar, zoom, tema; tudo reversível
    "janela_fechar",  # fechar a própria janela apaga a câmera; abrir (acende) pede confirmação
    "navegador_continuar",  # o resto de uma página que o JARVIS já leu (só leitura)
    "conectores_listar",
    "conector_testar",  # sobe só o que a pessoa aprovou ao cadastrar
]
LIVRES = [f"mcp__{SERVIDOR}__{nome}" for nome in LEITURA]


SKILL_ESCRITA = {f"mcp__{SERVIDOR}__skill_criar", f"mcp__{SERVIDOR}__skill_corrigir"}


def prechecagem(memoria: Memoria, skills: Skills | None = None) -> Any:
    """Para o ClaudeBrain: recusa sem perguntar ao usuário o que já não seria aceito."""

    def prechecar(nome: str, entrada: dict[str, Any]) -> str | None:
        try:
            if nome == f"mcp__{SERVIDOR}__memoria":
                memoria.resultado(_mudanca(entrada))
            elif nome in SKILL_ESCRITA and skills is not None:
                _skill_nova(skills, entrada)
        except MemoriaErro as erro:
            return f"A memória não aceitou: {erro}"
        except SkillErro as erro:
            return f"A skill não foi aceita: {erro}"
        return None

    return prechecar


APROVAR_SUGESTAO = f"mcp__{SERVIDOR}__sugestao_aprovar"


def mostrador(skills: Skills, apresentar: Any, pendencias: revisao.Pendencias | None = None) -> Any:
    """Para o ClaudeBrain: o diff de uma skill vai para o Barehands enquanto a fala pergunta."""

    def mostrar(nome: str, entrada: dict[str, Any]) -> None:
        if nome in SKILL_ESCRITA:
            alvo = str(entrada.get("nome", ""))
            apresentar(f"Skill {alvo}", skills.diff(alvo, _skill_nova(skills, entrada)))
        elif nome == APROVAR_SUGESTAO and pendencias is not None:
            p = pendencias.achar(str(entrada.get("id", "")))
            if p is not None and p.tipo == "skill":
                alvo = p.dados["nome"]
                apresentar(f"Skill {alvo}", skills.diff(alvo, p.dados.get("final", "")))

    return mostrar


def descritor(pendencias: revisao.Pendencias) -> Any:
    """Para o ClaudeBrain: a frase da aprovação de uma sugestão diz o que ela é."""

    def descrever_extra(nome: str, entrada: dict[str, Any]) -> str | None:
        if nome != APROVAR_SUGESTAO:
            return None
        p = pendencias.achar(str(entrada.get("id", "")))
        if p is None:
            return None
        tela = " O texto está no Barehands." if p.tipo == "skill" else ""
        return f"Vou {p.resumo}.{tela}"

    return descrever_extra


def servidor(ferramentas: list[SdkMcpTool[Any]]) -> McpSdkServerConfig:
    return create_sdk_mcp_server(SERVIDOR, tools=ferramentas)


def montar(
    sessoes: Sessoes | None,
    memoria: Memoria,
    skills: Skills,
    pendencias: revisao.Pendencias | None = None,
    jobs: Jobs | None = None,
    sistema: Sistema | None = None,
    diario: Diario | None = None,
    tela: Tela | None = None,
    manutencao: Manutencao | None = None,
) -> list[SdkMcpTool[Any]]:
    """As ferramentas do servidor `jarvis` (a pasta do JARVIS lista os nomes como conexões),
    cada uma registrada na atividade ao rodar (ADR 0025)."""
    return [
        auditada(f)
        for f in [
            *g_sessoes.ferramentas(sessoes),
            *g_tela.ferramentas(tela),
            *g_sistema.ferramentas(sistema),
            *g_automacoes.ferramentas(jobs),
            *g_aprendizado.ferramentas(memoria, skills, pendencias, diario),
            *g_manutencao.ferramentas(manutencao),
            *g_navegador.ferramentas(),
            *g_conectores.ferramentas(),
        ]
    ]


def auditada(ferramenta: SdkMcpTool[Any]) -> SdkMcpTool[Any]:
    """A mesma ferramenta, registrando na atividade o que fez, como foi autorizada e o resultado."""
    original = ferramenta.handler

    async def registrar(entrada: dict[str, Any]) -> dict[str, Any]:
        inicio = time.monotonic()
        titulo = atividade.titulo_da_ferramenta(ferramenta.name, entrada)
        como = atividade.PADRAO.autorizacao(ferramenta.name)
        try:
            resposta = await original(entrada)
        except Exception as erro:
            atividade.PADRAO.registrar(
                "falha", titulo, ferramenta=ferramenta.name, entrada=entrada, autorizacao=como,
                erro=f"{type(erro).__name__}: {erro}",
            )  # fmt: skip
            raise
        textos = [c.get("text", "") for c in resposta.get("content", []) if isinstance(c, dict)]
        atividade.PADRAO.registrar(
            "falha" if resposta.get("is_error") else "execucao",
            titulo,
            ferramenta=ferramenta.name,
            entrada=entrada,
            autorizacao=como,
            resultado=" ".join(textos).strip(),
            duracao_ms=round((time.monotonic() - inicio) * 1000),
        )
        return resposta

    return dataclasses.replace(ferramenta, handler=registrar)
