"""O cérebro local (ADR 0063): um modelo no Ollama desta máquina, sem gastar os planos.

As mesmas ferramentas do Zé (o servidor `jarvis` e os conectores, pelo cliente MCP do Codex), a
mesma aprovação falada (`ClaudeBrain._pode_usar`) e o mesmo registro na Atividade; só quem
pensa muda. O laço é o do Ollama (`/api/chat`, em fluxo): o modelo fala, ou pede ferramentas; o
Zé roda cada uma e devolve o resultado, até a resposta final.

Medido nesta máquina (03/11/2026, Ryzen 5 8500G com a Radeon 740M): o Gemma 4 E4B acertou 10 de
10 pedidos com as 55 ferramentas do Zé, em 2,2 s (mediana), porque o Ollama reaproveita a leitura
do começo do prompt (a persona e as ferramentas) entre pedidos. Ler isso do zero leva ~95 s:
por isso o começo do prompt nunca muda numa conversa, o modelo fica carregado (`manter`) e o
cérebro já o lê em segundo plano ao subir (`aquecer`).
"""

import asyncio
import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import PermissionResultDeny, ToolPermissionContext

from zervis import atividade
from zervis.cerebro.base import Aprovar, EventoCerebro, Fim, Texto
from zervis.cerebro.claude import ClaudeBrain, carimbo
from zervis.cerebro.codex_mcp import FerramentasCodex
from zervis.cerebro.rapido import Http, MotorErro

log = logging.getLogger(__name__)

ENDERECO = "http://127.0.0.1:11434"
MODELO = "gemma4:e4b"
CONTEXTO = 32768  # a persona e as ferramentas passam de 19 mil tokens
MANTER = "4h"  # carregado entre pedidos: descarregar custa reler o prompt inteiro
RODADAS = 8  # rodadas de ferramentas num pedido
HISTORICO = 30  # mensagens da conversa guardadas (além da persona)
LEITURA_S = 300.0  # a primeira leitura do prompt, a frio, leva minutos na GPU integrada
REGRAS = """

## Neste modelo (local): regras que valem acima de tudo
- Dado que você não tem (CNPJ, mensagens, pesquisa, agenda, sessões, o que está na internet):
  chame a ferramenta certa ANTES de responder, no mesmo passo. Nunca diga "vou consultar" sem
  chamar a ferramenta, e nunca invente nomes, números, datas ou resultados.
- Use o nome exato da ferramenta e os argumentos do esquema.
- Cada pedido começa com a data e a hora entre colchetes: é só para você saber. Nunca repita.
- Responda curto, em português, como fala, sem Markdown.
- Programar ou mexer num projeto: use as ferramentas de sessão (quem programa são os agentes)."""


class LocalErro(RuntimeError):
    """O Ollama não respondeu ou recusou; a mensagem é falável."""


def _get(endereco: str, caminho: str, espera: float = 5.0) -> Any:
    pedido = urllib.request.Request(endereco.rstrip("/") + caminho)  # noqa: S310 (loopback, validado)
    with urllib.request.urlopen(pedido, timeout=espera) as r:  # noqa: S310
        return json.loads(r.read())


def modelos(endereco: str = ENDERECO) -> list[str]:
    """Os modelos instalados no Ollama; vazio fora do ar."""
    try:
        dados = _get(endereco, "/api/tags")
    except (urllib.error.URLError, OSError, ValueError):
        return []
    return sorted(str(m.get("name", "")) for m in dados.get("models", []) if m.get("name"))


def conferir(endereco: str, modelo: str) -> None:
    """LocalErro (falável) se o Ollama está fora do ar ou sem o modelo."""
    try:
        instalados = {str(m.get("name")) for m in _get(endereco, "/api/tags").get("models", [])}
    except (urllib.error.URLError, OSError, ValueError):
        raise LocalErro("o Ollama está fora do ar") from None
    if modelo not in instalados and f"{modelo}:latest" not in instalados:
        raise LocalErro(f"o modelo {modelo} não está instalado no Ollama")


def nome_curto(chave: str) -> str:
    """`mcp__jarvis__whatsapp_enviar` -> `whatsapp_enviar`; de um conector, com o nome dele."""
    _, servidor, ferramenta = chave.split("__", 2)
    return ferramenta if servidor == "jarvis" else f"{servidor}__{ferramenta}"


def para_ollama(definicoes: list[dict[str, Any]], curtos: dict[str, str]) -> list[dict[str, Any]]:
    """As ferramentas MCP no formato do Ollama, com o nome curto (`curtos`: apelido -> curto)."""
    saida = []
    for d in definicoes:
        nome = curtos.get(d["name"], d["name"])
        saida.append(
            {
                "type": "function",
                "function": {
                    "name": nome,
                    "description": d.get("description") or nome,
                    "parameters": d.get("inputSchema") or {"type": "object", "properties": {}},
                },
            }
        )
    return saida


def aparar(mensagens: list[dict[str, Any]], maximo: int = HISTORICO) -> list[dict[str, Any]]:
    """A persona e as últimas mensagens, cortando sempre num pedido do usuário (nunca entre um
    pedido de ferramenta e o resultado dela)."""
    sistema, resto = mensagens[:1], mensagens[1:]
    while len(resto) > maximo:
        proximo = next((i for i, m in enumerate(resto) if i > 0 and m.get("role") == "user"), None)
        if proximo is None:
            break
        resto = resto[proximo:]
    return sistema + resto


CARIMBO = re.compile(r"^\s*\[[^\]]{0,80}\]\s*")


def sem_carimbo(inicio: str) -> str | None:
    """O começo da resposta sem a data entre colchetes que abre cada pedido (o modelo às vezes
    copia); None enquanto não dá para saber (um "[" ainda sem o "]")."""
    aberto = inicio.lstrip()
    if aberto.startswith("[") and "]" not in aberto and len(aberto) < 80:
        return None
    return CARIMBO.sub("", inicio, count=1)


class LocalBrain(ClaudeBrain):
    """O cérebro no Ollama; a política de aprovação é a do `ClaudeBrain`."""

    def __init__(
        self,
        modelo: str,
        pasta: Path,
        endereco: str = ENDERECO,
        contexto: int = CONTEXTO,
        manter: str = MANTER,
        **kwargs: Any,
    ) -> None:
        super().__init__(modelo, [], pasta, assinatura=False, **kwargs)
        self.endereco = endereco.rstrip("/")
        self.contexto = contexto
        self.manter = manter
        self.http = Http(self.endereco, tempo_limite_s=LEITURA_S)
        self.ponte_mcp: FerramentasCodex | None = None
        self.nomes: dict[str, str] = {}  # o nome curto que o modelo vê -> mcp__servidor__nome
        self.ferramentas_ollama: list[dict[str, Any]] = []
        self.mensagens: list[dict[str, Any]] = []
        self.aquecimento: asyncio.Task[None] | None = None
        self._parar = False

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        self.persona, self.aprovar = persona, aprovar
        self.modelo_usado = self.modelo
        try:
            await self._preparar()
        except Exception as erro:
            log.warning("cérebro local não preparou ao subir: %s", type(erro).__name__)

    async def _preparar(self) -> None:
        if self.ponte_mcp is None and self.mcp:
            self.ponte_mcp = FerramentasCodex(self.mcp, self.bloqueadas)
            await self.ponte_mcp.iniciar()
            curtos = {a: nome_curto(c) for a, c in self.ponte_mcp.apelidos.items()}
            self.nomes = {nome_curto(c): c for c in self.ponte_mcp.apelidos.values()}
            self.ferramentas_ollama = para_ollama(self.ponte_mcp.definicoes, curtos)
        if not self.mensagens:
            foto = ("\n\n" + self.foto()) if self.foto else ""
            self.mensagens = [{"role": "system", "content": self.persona + foto + REGRAS}]
            if self.aquecimento is None or self.aquecimento.done():
                self.aquecimento = asyncio.create_task(self._aquecer())

    def _corpo(self, mensagens: list[dict[str, Any]], prever: int | None = None) -> dict[str, Any]:
        opcoes: dict[str, Any] = {"num_ctx": self.contexto, "temperature": 0.2}
        if prever is not None:
            opcoes["num_predict"] = prever
        return {
            "model": self.modelo,
            "messages": mensagens,
            "tools": self.ferramentas_ollama,
            "stream": True,
            "think": False,
            "keep_alive": self.manter,
            "options": opcoes,
        }

    async def _aquecer(self) -> None:
        """Lê a persona e as ferramentas em segundo plano: o primeiro pedido já vem rápido."""
        try:
            corpo = self._corpo([*self.mensagens[:1], {"role": "user", "content": "ok"}], 1)
            async for _ in self.http.linhas("/api/chat", corpo, {}):
                pass
            log.info("cérebro local: %s aquecido", self.modelo)
        except Exception as erro:
            log.warning("cérebro local: aquecimento falhou (%s)", erro)

    async def _rodada(self) -> AsyncIterator[dict[str, Any]]:
        async for linha in self.http.linhas("/api/chat", self._corpo(self.mensagens), {}):
            if self._parar:
                return
            try:
                dados = json.loads(linha)
            except ValueError:
                continue
            if isinstance(dados, dict):
                if dados.get("error"):
                    raise MotorErro(str(dados["error"])[:200])
                yield dados

    async def _executar(self, chamada: dict[str, Any]) -> dict[str, Any]:
        """Uma ferramenta pedida pelo modelo, pela mesma aprovação do Zé; volta a mensagem
        `tool` para o modelo."""
        funcao = chamada.get("function") or {}
        curto = str(funcao.get("name", ""))
        argumentos = funcao.get("arguments") or {}
        if isinstance(argumentos, str):
            try:
                argumentos = json.loads(argumentos)
            except ValueError:
                argumentos = {}
        nome = self.nomes.get(curto, "")
        resposta: dict[str, Any] = {"role": "tool", "tool_name": curto}
        if not nome or self.ponte_mcp is None or not isinstance(argumentos, dict):
            return {**resposta, "content": f"Ferramenta {curto!r} não existe. Use as da lista."}
        # Marca antes de aprovar/executar: uma falha posterior não repete a ação na reserva.
        self.ferramentas_usadas.append(nome)
        if nome not in self.livres:
            decisao = await self._pode_usar(nome, argumentos, ToolPermissionContext())
            if isinstance(decisao, PermissionResultDeny):
                return {**resposta, "content": decisao.message}
        try:
            resultado = await self.ponte_mcp.chamar(nome, argumentos)
        except Exception as erro:
            return {**resposta, "content": f"Falhou: {type(erro).__name__}"}
        bruto = resultado.model_dump(mode="json", by_alias=True)
        try:
            atividade.registrar_externa(nome, argumentos, bruto)
        except Exception:
            log.exception("registro de %s na atividade falhou", nome)
        if self.depois is not None and (novo := self.depois(nome, bruto)) is not None:
            bruto = (
                novo
                if isinstance(novo, dict)
                else {"content": [{"type": "text", "text": str(novo)}]}
            )
        textos, imagens = [], []
        for bloco in bruto.get("content", []):
            if bloco.get("type") == "text":
                textos.append(str(bloco.get("text", "")))
            elif bloco.get("type") == "image" and bloco.get("data"):
                imagens.append(str(bloco["data"]))  # o Gemma 4 vê imagens
        conteudo = "\n".join(textos) or ("Feito." if not bruto.get("isError") else "Falhou.")
        if bruto.get("isError"):
            conteudo = f"[erro] {conteudo}"
        return {**resposta, "content": conteudo, **({"images": imagens} if imagens else {})}

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.uso, self.ferramentas_usadas, self._parar = None, [], False
        entrada = saida = 0
        try:
            await self._preparar()
            if self.aquecimento is not None and not self.aquecimento.done():
                await asyncio.shield(self.aquecimento)  # o mesmo prefixo: espera e reaproveita
            self.mensagens = aparar(
                [*self.mensagens, {"role": "user", "content": f"{carimbo()} {texto}"}]
            )
            for _ in range(RODADAS):
                falado = inicio = ""
                falou = False
                chamadas: list[dict[str, Any]] = []
                async for dados in self._rodada():
                    mensagem = dados.get("message") or {}
                    if pedaco := str(mensagem.get("content") or ""):
                        falado += pedaco
                        if not falou:  # o começo: a data entre colchetes, se o modelo repetir
                            inicio += pedaco
                            limpo = sem_carimbo(inicio)
                            if limpo is None:
                                continue
                            pedaco, falou = limpo, True
                        yield Texto(pedaco)
                    chamadas.extend(mensagem.get("tool_calls") or [])
                    if dados.get("done"):
                        entrada += int(dados.get("prompt_eval_count") or 0)
                        saida += int(dados.get("eval_count") or 0)
                if self._parar:
                    return
                self.mensagens.append(
                    {
                        "role": "assistant",
                        "content": falado,
                        **({"tool_calls": chamadas} if chamadas else {}),
                    }
                )
                self.uso = {"input_tokens": entrada, "output_tokens": saida}
                if not chamadas:
                    yield Fim(None)
                    return
                for chamada in chamadas:
                    self.mensagens.append(await self._executar(chamada))
            yield Fim("ferramentas_demais")
        except asyncio.CancelledError:
            self._parar = True
            raise
        except (MotorErro, OSError) as erro:
            log.warning("cérebro local falhou: %s", erro)
            yield Fim("falha_local")

    async def interrupt(self) -> None:
        self._parar = True
        self.http.abortar()  # o Ollama para de gerar (ou de ler o prompt) na hora

    async def reset(self) -> None:
        self.mensagens = []
        self._parar = False

    async def close(self) -> None:
        await self.reset()
        self.http.abortar()  # a leitura em curso não fica ocupando a GPU para um cérebro morto
        if self.aquecimento is not None:
            self.aquecimento.cancel()
        if self.ponte_mcp is not None:
            await self.ponte_mcp.fechar()
            self.ponte_mcp = None
        self.http.fechar()


async def testar(endereco: str, modelo: str) -> tuple[bool, str]:
    """O Ollama no ar e o modelo carregado, sem fazer pergunta: uma pergunta entraria na fila
    atrás da leitura do prompt do cérebro (minutos) e apagaria o que ele já leu."""
    try:
        await asyncio.to_thread(conferir, endereco, modelo)
    except LocalErro as erro:
        return False, f"{str(erro)[:1].upper()}{str(erro)[1:]}."

    def carregar() -> Any:
        corpo = json.dumps({"model": modelo, "keep_alive": MANTER}).encode()
        pedido = urllib.request.Request(  # noqa: S310 (loopback, validado)
            endereco.rstrip("/") + "/api/generate", corpo, {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(pedido, timeout=120) as r:  # noqa: S310
            return json.loads(r.read())

    try:
        dados = await asyncio.to_thread(carregar)
    except (urllib.error.URLError, OSError, ValueError):
        return False, "O Ollama não carregou o modelo."
    if not dados.get("done"):
        return False, "O Ollama não carregou o modelo."
    return True, f"Conectado: {modelo} carregado."
