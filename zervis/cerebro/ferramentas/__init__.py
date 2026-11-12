"""Servidor MCP `jarvis` dentro do processo (docs/04-arquitetura.md): sessões, memória e histórico.

Cada grupo de ferramentas mora no seu módulo (sessões, aprendizado, automacoes, sistema, tela,
manutencao, navegador, conectores, atualizacoes, pesquisa, profunda, modelos, imagens, whatsapp,
instagram); aqui ficam a montagem, a lista do que passa sem perguntar e os ganchos do ClaudeBrain.

Leitura (projetos, situação, saída) passa sem perguntar; delegar, responder a um agente, criar
projeto, abrir frente, mudar status e renomear passam pela aprovação falada do `can_use_tool`.
Apagar não existe aqui de propósito: excluir uma sessão é no painel (decisão de 06/10/2026).
"""

import dataclasses
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server

from zervis import atividade
from zervis.automacoes.jobs import Jobs
from zervis.cerebro.ferramentas import aprendizado as g_aprendizado
from zervis.cerebro.ferramentas import atualizacoes as g_atualizacoes
from zervis.cerebro.ferramentas import automacoes as g_automacoes
from zervis.cerebro.ferramentas import conectores as g_conectores
from zervis.cerebro.ferramentas import imagens as g_imagens
from zervis.cerebro.ferramentas import instagram as g_instagram
from zervis.cerebro.ferramentas import manutencao as g_manutencao
from zervis.cerebro.ferramentas import modelos as g_modelos
from zervis.cerebro.ferramentas import navegador as g_navegador
from zervis.cerebro.ferramentas import pesquisa as g_pesquisa
from zervis.cerebro.ferramentas import profunda as g_profunda
from zervis.cerebro.ferramentas import projetos3d as g_projetos3d
from zervis.cerebro.ferramentas import sessoes as g_sessoes
from zervis.cerebro.ferramentas import sistema as g_sistema
from zervis.cerebro.ferramentas import sobre as g_sobre
from zervis.cerebro.ferramentas import tela as g_tela
from zervis.cerebro.ferramentas import tela_tv as g_tela_tv
from zervis.cerebro.ferramentas import whatsapp as g_whatsapp
from zervis.cerebro.ferramentas.comum import _mudanca, _skill_nova
from zervis.habilidades import revisao
from zervis.habilidades.diario import Diario
from zervis.habilidades.skills import SkillErro, Skills
from zervis.impressora3d import Impressora3D
from zervis.memoria.curta import Memoria, MemoriaErro
from zervis.oficina.manutencao import Manutencao
from zervis.oficina.sessoes import Sessoes
from zervis.pesquisa.buscador import Buscador
from zervis.pesquisa.guardadas import Guardadas
from zervis.pesquisa.saude import Vigia
from zervis.projetos3d import Projetos3D
from zervis.redes.instagram import Instagram
from zervis.rosto import andamento
from zervis.rosto.tela import Tela
from zervis.sistema.politica import Sistema
from zervis.tv import TelaTV

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
    "tela_agir",  # só a própria tela do Zé: abrir, mostrar, zoom, tema; tudo reversível
    "tela_explicar",  # uma cena animada na própria tela; some com a tecla A ou outra cena
    "janela_fechar",  # fechar a própria janela apaga a câmera; abrir (acende) pede confirmação
    "navegador_continuar",  # o resto de uma página que o Zé já leu (só leitura)
    "conectores_listar",
    "conector_testar",  # sobe só o que a pessoa aprovou ao cadastrar
    "atualizacoes_ver",  # só lê; atualizar é no painel
    "ze_sobre",  # o retrato do próprio Zé, sem segredos (ADR 0043)
    "internet_pesquisar",  # só lê a internet, numa consulta à parte (ADR 0044)
    "modelo3d_buscar",  # só lê um acervo livre de modelos (ADR 0049)
    "modelo3d_baixar",  # só grava no próprio Acervo, de uma fonte permitida, e mostra na tela
    "imagem_buscar",  # só lê a Wikimedia (ADR 0058)
    "imagem_baixar",  # só grava no próprio Acervo, da Wikimedia, com o crédito
    "pagina_capturar",  # o print de uma página pública, atrás da trava de rede
    "whatsapp_conversas",  # só lê a caixa de entrada (ADR 0054); responder pede o sim
    "whatsapp_ler",
    "whatsapp_buscar",  # só lê o arquivo do WhatsApp (ADR 0056); esquecer pede o sim
    "whatsapp_contatos",  # só lê a agenda do celular que o WhatsApp sincroniza
    "whatsapp_ligacoes",  # só lê as ligações que o agente atendeu
    "whatsapp_ligacao",  # a resposta a "pode atender?": o sim (ou o não) já é a decisão dele
    "whatsapp_leads",  # só lê os leads esperando resposta (ADR 0053)
    "whatsapp_ja_vi",  # só para um lembrete
    "whatsapp_prioridade",  # só muda quem o Zé vigia (ADR 0055); nada sai para ninguém
    "instagram_perfil",  # o Instagram é só leitura (ADR 0057)
    "instagram_posts",
    "pesquisa_profunda",  # só lê a internet pelo buscador próprio e a trava (ADR 0059)
    "pagina_ler",
    "empresa_cnpj",  # só lê o cadastro público da Receita
    "pesquisas_guardadas",  # só lê as pesquisas já feitas (ADR 0060)
    "pesquisa_guardada",
    "fontes_saude",  # só testa as fontes com pedidos pequenos
    "projetos3d_listar",  # só lê a pasta dos projetos 3D (ADR 0082)
    "projeto3d_mostrar",  # só a prévia no próprio Acervo e a própria tela; criar pede o sim
    "projeto3d_fatiar",  # só prepara o arquivo na pasta do projeto (ADR 0083); imprimir pede o sim
    "impressora_status",  # só lê a impressora; os comandos e imprimir pedem o sim
    "impressora_foto",  # só a câmera da impressora (ADR 0085)
    "tela_tv_mostrar",  # o Modo TV (ADR 0084): o navegador da TV de quem usa; fechar volta atrás
    "tela_tv_fechar",
]
LIVRES = [f"mcp__{SERVIDOR}__{nome}" for nome in LEITURA]

# Entrada de fora (plano de maturidade, Frente 2): as ferramentas cuja resposta traz texto de
# terceiros, e de onde. Depois de uma delas, o turno é "de fora": nada se executa sem a
# aprovação falada (`ClaudeBrain.viu`). Conectores de outros servidores (n8n, o navegador)
# também contam.
DE_FORA = {
    "whatsapp_conversas": "as conversas do WhatsApp",
    "whatsapp_ler": "uma conversa do WhatsApp",
    "whatsapp_buscar": "o arquivo do WhatsApp",
    "whatsapp_leads": "os leads do WhatsApp",
    "whatsapp_ligacoes": "o que foi falado nas ligações",
    "internet_pesquisar": "a internet",
    "pesquisa_profunda": "a internet",
    "pagina_ler": "uma página da internet",
    "pagina_capturar": "uma página da internet",
    "navegador_continuar": "uma página da internet",
    "pesquisa_guardada": "uma pesquisa guardada",
    "instagram_perfil": "o Instagram",
    "instagram_posts": "o Instagram",
    "historico_buscar": "o histórico",
    "historico_ler": "o histórico",
    "sessao_ler": "a resposta de uma sessão de código",
}
EMBUTIDAS_DE_FORA = {"WebSearch": "a internet", "WebFetch": "uma página da internet"}
# As livres que mudam alguma coisa (as outras só leem): num turno de fora, pedem a aprovação.
COM_EFEITO = frozenset(
    f"mcp__{SERVIDOR}__{nome}"
    for nome in (
        "automacao_lembrete",
        "sugestao_descartar",
        "conector_testar",
        "modelo3d_baixar",
        "imagem_baixar",
        "projeto3d_mostrar",
        "projeto3d_fatiar",
        "tela_tv_mostrar",
        "whatsapp_ja_vi",
        "whatsapp_prioridade",
    )
)


def de_fora(nome: str) -> str:
    """De onde vem o texto de terceiros que a ferramenta devolve ("" se não traz nenhum)."""
    if nome.startswith(f"mcp__{SERVIDOR}__"):
        return DE_FORA.get(nome.removeprefix(f"mcp__{SERVIDOR}__"), "")
    if nome.startswith("mcp__"):
        return f"o conector {nome.split('__')[1]}"
    return EMBUTIDAS_DE_FORA.get(nome, "")


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
    sobre: Callable[[], str] | None = None,
    pesquisar: Callable[[str], Awaitable[str]] | None = None,
    acervo: Path | None = None,
    leads: g_whatsapp.Nucleo | None = None,
    instagram: Instagram | None = None,
    buscador: Buscador | None = None,
    vigia: Vigia | None = None,
    pesquisas: Guardadas | None = None,
    projetos: Projetos3D | None = None,
    impressora: Impressora3D | None = None,
    tela_tv: TelaTV | None = None,
) -> list[SdkMcpTool[Any]]:
    """As ferramentas do servidor `jarvis` (a pasta do Zé lista os nomes como conexões),
    cada uma registrada na atividade ao rodar (ADR 0025)."""
    grupos = por_grupo(
        sessoes, memoria, skills, pendencias, jobs, sistema, diario, tela, manutencao, sobre,
        pesquisar, acervo, leads, instagram, buscador, vigia, pesquisas, projetos, impressora,
        tela_tv,
    )  # fmt: skip
    return [f for fs in grupos.values() for f in fs]


def por_grupo(
    sessoes: Sessoes | None,
    memoria: Memoria,
    skills: Skills,
    pendencias: revisao.Pendencias | None = None,
    jobs: Jobs | None = None,
    sistema: Sistema | None = None,
    diario: Diario | None = None,
    tela: Tela | None = None,
    manutencao: Manutencao | None = None,
    sobre: Callable[[], str] | None = None,
    pesquisar: Callable[[str], Awaitable[str]] | None = None,
    acervo: Path | None = None,
    leads: g_whatsapp.Nucleo | None = None,
    instagram: Instagram | None = None,
    buscador: Buscador | None = None,
    vigia: Vigia | None = None,
    pesquisas: Guardadas | None = None,
    projetos: Projetos3D | None = None,
    impressora: Impressora3D | None = None,
    tela_tv: TelaTV | None = None,
) -> dict[str, list[SdkMcpTool[Any]]]:
    """As mesmas ferramentas, por grupo (o módulo de cada uma): o Zé diz o que sabe fazer por
    área (ADR 0045). Grupo sem ferramenta (o serviço não existe aqui) fica de fora."""
    grupos = {
        "sessoes": g_sessoes.ferramentas(sessoes),
        "tela": g_tela.ferramentas(tela),
        "sistema": g_sistema.ferramentas(sistema),
        "automacoes": g_automacoes.ferramentas(jobs),
        "aprendizado": g_aprendizado.ferramentas(memoria, skills, pendencias, diario),
        "manutencao": g_manutencao.ferramentas(manutencao),
        "navegador": g_navegador.ferramentas(),
        "conectores": g_conectores.ferramentas(),
        "atualizacoes": g_atualizacoes.ferramentas(),
        "sobre": g_sobre.ferramentas(sobre),
        "pesquisa": g_pesquisa.ferramentas(pesquisar),
        "profunda": g_profunda.ferramentas(buscador, vigia, pesquisar, pesquisas),
        "modelos": g_modelos.ferramentas(acervo, tela),
        "imagens": g_imagens.ferramentas(acervo),
        "whatsapp": g_whatsapp.ferramentas(leads),
        "instagram": g_instagram.ferramentas(instagram),
        "projetos3d": g_projetos3d.ferramentas(projetos, sessoes, tela, acervo, impressora),
        "tela_tv": g_tela_tv.ferramentas(tela_tv, projetos),
    }
    return {nome: [auditada(f) for f in fs] for nome, fs in grupos.items() if fs}


def auditada(ferramenta: SdkMcpTool[Any]) -> SdkMcpTool[Any]:
    """A mesma ferramenta, registrando na atividade o que fez, como foi autorizada e o resultado."""
    original = ferramenta.handler

    async def registrar(entrada: dict[str, Any]) -> dict[str, Any]:
        inicio = time.monotonic()
        titulo = atividade.titulo_da_ferramenta(ferramenta.name, entrada)
        como = atividade.PADRAO.autorizacao(ferramenta.name)
        andamento.PADRAO.ferramenta(ferramenta.name)  # a barra de carregamento (ADR 0064)
        try:
            resposta = await original(entrada)
        except Exception as erro:
            andamento.PADRAO.pensando()
            atividade.PADRAO.registrar(
                "falha", titulo, ferramenta=ferramenta.name, entrada=entrada, autorizacao=como,
                erro=f"{type(erro).__name__}: {erro}",
            )  # fmt: skip
            raise
        andamento.PADRAO.pensando()
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
