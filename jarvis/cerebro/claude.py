"""Cérebro Claude pelo Agent SDK, com o login de assinatura do Claude Code (ADR 0002, Prova 1).

Sessão contínua (um `ClaudeSDKClient` conectado), texto em pedaços para falar por frase e
aprovação falada pelo `can_use_tool`. Lições da Fase 0 que valem aqui:
- `permission_mode="default"` sempre explícito: sem ele, via OmniRoute, uma ferramenta que
  exigia aprovação rodou sem perguntar (ADR 0008);
- `strict_mcp_config=True`: sem ele os conectores do claude.ai entram na sessão;
- `setting_sources=[]` e uma pasta vazia: nada de CLAUDE.md ou configurações de projeto.

O OmniRoute é este mesmo cérebro com outro `env` (jarvis/cerebro/omniroute.py). Para os dois
vale o tempo limite: sem nenhuma mensagem do modelo em `tempo_limite_s`, o pedido falha e a
sessão é refeita. Depois da primeira mensagem não há prazo (a aprovação falada pode levar 40 s).
"""

import asyncio
import contextlib
import logging
import warnings
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    ToolPermissionContext,
    ToolUseBlock,
)
from claude_agent_sdk.types import CanUseToolShadowedWarning, HookInput, SyncHookJSONOutput

from jarvis import atividade, fuso
from jarvis.cerebro.base import Aprovar, EventoCerebro, Fim, Texto
from jarvis.sistema.politica import frase_confere

log = logging.getLogger(__name__)
# As ferramentas só de leitura (`livres`) passam sem o `can_use_tool` de propósito.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)
FUSO = fuso.local()
DIAS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]


def carimbo(agora: datetime | None = None) -> str:
    """Data e hora no começo de cada pedido: o cérebro não tem relógio próprio."""
    agora = agora or datetime.now(FUSO)
    return f"[{DIAS[agora.weekday()]}, {agora:%d/%m/%Y, %H:%M}]"


def descrever(nome: str, entrada: dict[str, Any]) -> str:
    """O que vai ser feito, numa frase falável, para o usuário aprovar ou negar."""
    if nome == "WebSearch":
        return f"Vou pesquisar na internet: {entrada.get('query', '')}."
    if nome == "WebFetch":
        endereco = urlsplit(str(entrada.get("url", ""))).hostname or "um endereço"
        return f"Vou abrir a página {endereco.removeprefix('www.')}."
    if nome == "mcp__jarvis__sessao_criar":
        onde = entrada.get("projeto_novo") or entrada.get("pasta", "")
        tarefa = entrada.get("tarefa", "")
        return f"Vou criar a sessão {entrada.get('nome', '')} em {onde}" + (
            f", com a tarefa: {tarefa}" if tarefa else "."
        )
    if nome == "mcp__jarvis__sessao_enviar":
        return f"Vou mandar para a sessão: {entrada.get('texto', '')}"
    if nome == "mcp__jarvis__sessao_trocar":
        conta = f", conta {entrada['conta']}" if entrada.get("conta") else ""
        return f"Vou passar a sessão para o {str(entrada.get('agente', '')).capitalize()}{conta}."
    if nome == "mcp__jarvis__sessao_parar":
        return "Vou parar a sessão."
    if nome == "mcp__jarvis__sessao_continuar":
        return "Vou mandar a sessão continuar de onde parou."
    if nome == "mcp__jarvis__skill_criar":
        return f"Vou criar a skill {entrada.get('nome', '')}. O texto está no Barehands."
    if nome == "mcp__jarvis__skill_corrigir":
        return f"Vou corrigir a skill {entrada.get('nome', '')}. A mudança está no Barehands."
    if nome == "mcp__jarvis__memoria":
        texto, antigo = entrada.get("texto", ""), entrada.get("antigo", "")
        dono = "sobre você" if entrada.get("alvo") == "usuario" else "nas minhas notas"
        if entrada.get("acao") == "trocar":
            return f"Vou trocar na memória {dono} o trecho {antigo} por: {texto}"
        if entrada.get("acao") == "remover":
            return f"Vou tirar da memória {dono}: {antigo}"
        return f"Vou guardar na memória {dono}: {texto}"
    if nome == "mcp__jarvis__automacao_pergunta":
        return f"Vou agendar ({entrada.get('quando', '')}) a pergunta: {entrada.get('texto', '')}"
    if nome == "mcp__jarvis__automacao_mudar":
        acao = {"pausar": "pausar", "retomar": "retomar", "remover": "remover"}.get(
            str(entrada.get("acao")), "mudar"
        )
        return f"Vou {acao} a automação {entrada.get('id', '')}."
    if nome == "mcp__jarvis__janela_abrir":
        return "Vou abrir a minha janela; a câmera acende."
    if nome == "mcp__jarvis__conector_cadastrar":
        if entrada.get("tipo") == "http":
            onde = urlsplit(str(entrada.get("url", ""))).hostname or "um endereço"
            alvo = f"ligado a {onde}"
        else:
            partes = [str(entrada.get("comando", "")), *map(str, entrada.get("argumentos") or [])]
            alvo = f"rodando {' '.join(p for p in partes if p)[:120]}"
        return f"Vou cadastrar o conector {entrada.get('nome', '')}, {alvo}."
    if nome == "mcp__jarvis__sistema_executar":
        argumentos = " ".join(str(a) for a in entrada.get("argumentos") or [])
        return (
            f"Vou executar {str(entrada.get('acao', '')).replace('-', ' ')} {argumentos}".strip()
            + "."
        )
    if nome.startswith("mcp__"):
        _, servidor, ferramenta = [*nome.split("__", 2), "", ""][:3]
        argumentos = ", ".join(f"{k} {v}" for k, v in entrada.items() if isinstance(v, str | int))
        resumo = f": {argumentos[:120]}" if argumentos else ""
        return f"Vou usar {ferramenta.replace('_', ' ')} do {servidor}{resumo}."
    return f"Vou usar a ferramenta {nome}."


class ClaudeBrain:
    def __init__(
        self,
        modelo: str,
        ferramentas: list[str],
        pasta: Path,
        env: dict[str, str] | None = None,
        tempo_limite_s: float = 30.0,
        assinatura: bool = True,
        mcp: dict[str, Any] | None = None,
        livres: list[str] | None = None,
        bloqueadas: list[str] | None = None,
        foto: Callable[[], str] | None = None,
        prechecar: Callable[[str, dict[str, Any]], str | None] | None = None,
        mostrar: Callable[[str, dict[str, Any]], None] | None = None,
        descrever_extra: Callable[[str, dict[str, Any]], str | None] | None = None,
        autoaprovar: Callable[[str, dict[str, Any]], bool] | None = None,
        frase_exata: Callable[[str, dict[str, Any]], str | None] | None = None,
        depois: Callable[[str, Any], Any | None] | None = None,
    ) -> None:
        self.modelo = modelo
        self.ferramentas = ferramentas
        self.pasta = pasta
        self.env = env or {}
        self.tempo_limite_s = tempo_limite_s
        self.mcp = mcp or {}  # servidores MCP do JARVIS (o pacote ferramentas)
        self.livres = livres or []  # ferramentas só de leitura: sem pergunta falada
        # Ferramentas MCP fora da lista: o cérebro nem as vê (cada descrição custa tokens em
        # todo turno; o navegador tem 25 e o Zé usa umas 15).
        self.bloqueadas = bloqueadas or []
        self.foto = foto  # memória curta, lida a cada sessão nova (foto congelada)
        self.prechecar = prechecar  # recusa antes da pergunta falada o que já vai falhar
        self.mostrar = mostrar  # põe na tela o que a fala resume (o diff de uma skill)
        self.descrever_extra = descrever_extra  # frase que depende de estado (uma sugestão)
        self.autoaprovar = (
            autoaprovar  # risco baixo pela política (volume, abrir app): sem pergunta
        )
        self.frase_exata = frase_exata  # risco 3: "sim" não basta, só a frase exata
        # O que uma ferramenta devolveu, como o modelo deve ver (o navegador corta e mascara);
        # None = sem mudança. Roda também nas livres, que não passam pelo can_use_tool.
        self.depois = depois
        self.assinatura = assinatura  # False pelo OmniRoute: o RateLimitEvent não é da assinatura
        self.cliente: ClaudeSDKClient | None = None
        self.persona = ""
        self.aprovar: Aprovar | None = None
        self.limite: dict[str, Any] = {}  # último RateLimitEvent (janela de 5 horas etc.)
        self.ferramentas_usadas: list[str] = []  # as desta resposta (o mapa do cérebro conta)
        self.uso: dict[str, Any] | None = None
        self._erro_resposta: str | None = None
        self.modelo_usado: str | None = None  # o que respondeu de fato (o OmniRoute escolhe)

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        self.persona, self.aprovar = persona, aprovar
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            await self._conectar()  # aquece: a primeira pergunta não paga a conexão
        except Exception as erro:
            log.warning("cérebro não conectou ao subir: %s", type(erro).__name__)
            self.cliente = None

    def opcoes(self) -> ClaudeAgentOptions:
        prompt = self.persona
        if self.foto is not None:
            prompt += "\n\n" + self.foto()
        return ClaudeAgentOptions(
            system_prompt=prompt,
            tools=self.ferramentas,
            allowed_tools=list(self.livres),
            disallowed_tools=list(self.bloqueadas),
            mcp_servers=self.mcp,
            can_use_tool=self._pode_usar,
            hooks={"PostToolUse": [HookMatcher(hooks=[self._depois_da_ferramenta])]}
            if self.depois is not None
            else None,
            permission_mode="default",
            setting_sources=[],
            strict_mcp_config=True,
            include_partial_messages=True,
            model=self.modelo,
            cwd=str(self.pasta),
            env=self.env,
        )

    async def _conectar(self) -> ClaudeSDKClient:
        if self.cliente is None:
            cliente = ClaudeSDKClient(options=self.opcoes())
            await cliente.connect()
            self.cliente = cliente
        return self.cliente

    async def _depois_da_ferramenta(
        self, entrada: HookInput, _id: str | None, _contexto: HookContext
    ) -> SyncHookJSONOutput:
        if self.depois is None or entrada["hook_event_name"] != "PostToolUse":
            return {}
        try:
            novo = self.depois(entrada["tool_name"], entrada["tool_response"])
        except Exception:
            log.exception("ajuste da resposta de %s falhou; vai a original", entrada["tool_name"])
            return {}
        if novo is None:
            return {}
        return {
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedMCPToolOutput": novo}
        }

    async def _pode_usar(
        self, nome: str, entrada: dict[str, Any], _ctx: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        # Falhar fechado: sem quem aprove, ou na dúvida, nega.
        curto = nome.removeprefix("mcp__jarvis__")
        titulo = atividade.titulo_da_ferramenta(nome, entrada)
        if self.prechecar is not None and (erro := self.prechecar(nome, entrada)):
            log.info("ferramenta %s: recusada antes de perguntar (%s)", nome, erro[:80])
            atividade.PADRAO.registrar(
                "negada", titulo, ferramenta=curto, entrada=entrada, motivo=erro
            )
            return PermissionResultDeny(message=erro)
        if self.autoaprovar is not None and self.autoaprovar(nome, entrada):
            log.info("ferramenta %s: liberada pela política de risco", nome)
            atividade.PADRAO.autorizada(curto, "livre (risco baixo)")
            return PermissionResultAllow()
        exigida = self.frase_exata(nome, entrada) if self.frase_exata else None
        if self.mostrar is not None:
            try:
                self.mostrar(nome, entrada)
            except Exception:
                log.exception("falha ao mostrar o pedido na tela")
        aprovado, fala = False, ""
        if self.aprovar is not None:
            try:
                frase = self.descrever_extra(nome, entrada) if self.descrever_extra else None
                resposta = await self.aprovar(frase or descrever(nome, entrada))
                aprovado, fala = bool(resposta), getattr(resposta, "fala", "")
            except Exception:
                log.exception("falha ao pedir aprovação")
        if exigida and aprovado and not frase_confere(fala, exigida):
            log.info("ferramenta %s: faltou a frase exata", nome)
            atividade.PADRAO.registrar(
                "negada", titulo, ferramenta=curto, entrada=entrada, motivo="sem a frase exata"
            )
            return PermissionResultDeny(
                message=f'Não executado: o usuário não disse a frase exata "{exigida}".'
            )
        log.info("ferramenta %s: %s", nome, "aprovada" if aprovado else "negada")
        if aprovado:
            atividade.PADRAO.autorizada(curto, "frase exata" if exigida else "aprovada")
            return PermissionResultAllow()
        atividade.PADRAO.registrar(
            "negada", titulo, ferramenta=curto, entrada=entrada, motivo="não aprovada", fala=fala
        )
        motivo = "O usuário não aprovou por voz."
        if fala:
            # Uma correção ("sim, mas no projeto Y") chega aqui: o cérebro ajusta e pergunta.
            motivo += f' Ele respondeu: "{fala}". Siga o que ele disse; se corrigiu, ajuste.'
        return PermissionResultDeny(message=motivo + " Não use a ferramenta agora.")

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.uso = None  # o desta resposta; o núcleo soma no consumo do dia
        self._erro_resposta = None
        self.ferramentas_usadas = []
        try:
            async with asyncio.timeout(self.tempo_limite_s) as prazo:
                cliente = await self._conectar()
                await cliente.query(f"{carimbo()} {texto}")
                mensagens = aiter(cliente.receive_response())
                primeira = await anext(mensagens, None)
                prazo.reschedule(None)
        except TimeoutError:
            log.warning("cérebro sem resposta em %.0f s; refazendo a sessão", self.tempo_limite_s)
            await self.reset()
            yield Fim(erro="tempo_esgotado")
            return
        if primeira is None:
            yield Fim(erro="sem_resposta")
            return
        if (evento := self._traduzir(primeira)) is not None:
            yield evento
        async for msg in mensagens:
            if (evento := self._traduzir(msg)) is not None:
                yield evento

    def _traduzir(self, msg: object) -> EventoCerebro | None:
        if isinstance(msg, StreamEvent):
            evento = msg.event
            delta = evento.get("delta", {})
            if evento.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                return Texto(delta["text"])
            if evento.get("type") == "content_block_stop":
                # Fim de um bloco de texto (antes de uma ferramenta): fecha a frase pendente.
                return Texto(" ")
        elif isinstance(msg, AssistantMessage):
            if msg.error:
                self._erro_resposta = (
                    "limite_de_uso"
                    if msg.error == "rate_limit"
                    else "acesso_invalido"
                    if msg.error == "authentication_failed"
                    else "falha_claude"
                )
            self.modelo_usado = msg.model or self.modelo_usado
            self.ferramentas_usadas += [b.name for b in msg.content if isinstance(b, ToolUseBlock)]
        elif isinstance(msg, RateLimitEvent):
            self.limite = msg.rate_limit_info.raw or {}
        elif isinstance(msg, ResultMessage):
            self.uso = msg.usage
            if msg.is_error:
                resultado = (msg.result or "").lower()
                erro = self._erro_resposta
                if any(
                    x in resultado
                    for x in ("usage limit", "session limit", "rate limit", "credit balance")
                ):
                    erro = "limite_de_uso"
                return Fim(erro or (msg.subtype if msg.subtype != "success" else "falha_claude"))
            return Fim()
        return None

    async def interrupt(self) -> None:
        if self.cliente is None:
            return
        try:
            await self.cliente.interrupt()
            # Esvazia o que sobrou do turno interrompido, para não vazar na próxima resposta.
            async with asyncio.timeout(5):
                async for msg in self.cliente.receive_response():
                    if isinstance(msg, ResultMessage):
                        break
        except Exception as erro:
            log.warning("interrupção falhou (%s); reconectando", type(erro).__name__)
            await self.reset()

    async def reset(self) -> None:
        cliente, self.cliente = self.cliente, None
        if cliente is not None:
            with contextlib.suppress(Exception):
                await cliente.disconnect()

    async def close(self) -> None:
        await self.reset()
