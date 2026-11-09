"""Via rápida da conversa (docs/plano-voz-rapida.md, etapa 1; 09/10/2026).

O agente de voz do Ligatia responde em menos de meio segundo porque fala direto com o modelo,
com um prompt curto e poucas ferramentas. O Zé completo passa pelo Claude Code (Agent SDK),
com a persona inteira e dezenas de ferramentas: de 1,4 a 2,2 s até a primeira palavra. Aqui a
conversa simples vai primeiro a um **motor rápido**, com a persona enxuta
(`zervis/persona/RAPIDO.md`); quando o pedido precisa de ferramenta, o motor responde só
`[completo]` e o pedido segue para
o cérebro completo, que recebe a mesma conversa. Antes dele, o Zé diz "Deixa eu ver.", para
não ficar calado (etapa 2).

Motores, agnósticos de provedor:
- `openai`, `openrouter` e `ponte`: HTTP no formato OpenAI (chat/completions em fluxo); a
  ponte é qualquer proxy compatível (OmniRoute, LiteLLM...), com endereço próprio;
- `anthropic`: HTTP no formato da Anthropic (Messages em fluxo);
- `plano`: o Claude pela assinatura, pelo SDK, com a persona enxuta e sem ferramentas (o login
  do Claude só funciona por ele).

As chaves vêm de um arquivo próprio (`chmod 600`) ou da variável de ambiente; nunca da config.
O HTTP mantém a conexão aberta entre pedidos: o aperto de mão TLS acontece uma vez só.
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import time
import unicodedata
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from zervis import lugares, usuario
from zervis.cerebro import contas
from zervis.cerebro.base import Aprovar, Brain, EventoCerebro, Fim, Texto
from zervis.cerebro.consumo import gasto, somar_usos
from zervis.cerebro.motores import ENDERECOS as ENDERECOS
from zervis.cerebro.motores import Http as Http
from zervis.cerebro.motores import Motor as Motor
from zervis.cerebro.motores import MotorAnthropic as MotorAnthropic
from zervis.cerebro.motores import MotorCodex as MotorCodex
from zervis.cerebro.motores import MotorContas as MotorContas
from zervis.cerebro.motores import MotorErro as MotorErro
from zervis.cerebro.motores import MotorOpenAI as MotorOpenAI
from zervis.cerebro.motores import MotorPlano as MotorPlano
from zervis.cerebro.motores import _dados_sse as _dados_sse
from zervis.cerebro.motores import _raciocina as _raciocina
from zervis.cerebro.motores import pela_assinatura as pela_assinatura

log = logging.getLogger(__name__)
PASSAR = "[completo]"
# A frase de espera, só quando a resposta demora (03/11/2026: "vou ver aqui" a cada pedido, até
# nos que saíam na hora, cansava). Duas, alternadas.
AVISOS = ("Só um momento.", "Um instante.")
AVISO_APOS_S = 3.0  # sem nenhuma palavra da resposta até aqui (desde o pedido), o Zé avisa
# O que claramente pede ferramenta vai direto ao completo, sem esperar a via rápida decidir:
# o aviso sai na hora. Na dúvida fica na via rápida, que ainda pode passar a vez.
VERBOS_DE_ACAO = {
    *("abre", "abra", "abrir", "fecha", "feche", "mostra", "mostre", "mostrar"),
    *("pesquisa", "pesquise", "procura", "procure", "busca", "busque"),
    *("lembra", "lembre", "anota", "anote", "guarda", "guarde", "marca", "marque"),
    *("agenda", "agende", "manda", "mande", "envia", "envie", "escreve", "escreva"),
    *("cria", "crie", "delega", "delegue", "coloca", "coloque", "bota", "toca", "toque"),
    *("muda", "mude", "troca", "troque", "aumenta", "aumente", "diminui", "diminua"),
    *("executa", "execute", "roda", "rode", "instala", "instale", "apaga", "apague"),
    *("acessa", "acesse", "entra", "entre", "verifica", "verifique", "confere", "confira"),
    *("comecei", "terminei", "travei", "conclui", "pausa", "pause", "foca", "foque"),
}
ASSUNTOS_DE_FERRAMENTA = {
    *("foco", "frente", "frentes", "projeto", "projetos", "lembrete", "lembretes", "agenda"),
    *(
        "sessao",
        "sessoes",
        "codex",
        "claude",
        "agente",
        "agentes",
        "tarefa",
        "tarefas",
        "automacao",
    ),
    *("ontem", "anteontem", "semana", "conversamos", "falamos", "memoria", "tela", "mapa"),
    *("site", "navegador", "internet", "noticia", "noticias", "preco", "dolar", "clima"),
    *("tempo", "previsao", "volume", "computador", "janela", "arquivo", "pasta"),
}
# Com a janela do Zé aberta, explicar vira uma cena na tela (tela_explicar, ADR 0047): só o
# completo tem a ferramenta. Fechada, a explicação fica na via rápida, falada.
EXPLICAR = {"explica", "explique", "explicar", "ensina", "ensine", "apresenta", "apresente"}
# "Quem é fulano?" com a janela aberta pede a foto dele na tela (ADR 0058): vai ao cérebro completo.
QUEM_E = {("quem", "e"), ("quem", "foi"), ("quem", "era")}
JANELA_ABERTA = "janela do ze aberta"
FALADO = re.compile(r"^\s*(?:\[[^\]]*\]\s*|\([^)]*\)\s*)*")
MARCA = re.compile(r"\s*\[[a-zà-ú_]{2,12}\]\s*", re.IGNORECASE)
VARIAVEIS = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "ponte": "ZERVIS_PONTE_API_KEY",
}
LEGADO = {"ponte": "JARVIS_PONTE_API_KEY"}  # o nome até 20/10/2026, ainda aceito


def _do_ambiente(motor: str) -> str:
    for variavel in (VARIAVEIS.get(motor, ""), LEGADO.get(motor, "")):
        if variavel and (valor := os.environ.get(variavel, "").strip()):
            return valor
    return ""


MOTORES = {"plano", "codex", "contas", "openai", "openrouter", "anthropic", "ponte", "omniroute"}


def palavras(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", limpo)


def precisa_do_completo(pedido: str) -> bool:
    """O pedido (sem o colchete da hora e os parênteses de contexto) claramente pede ação?"""
    p = palavras(pedido[FALADO.match(pedido).end() :])  # type: ignore[union-attr]
    while p and p[0] in ("ze", "jarvis", "ei", "hey", "oi", "por", "favor", "agora", "entao"):
        p = p[1:]
    if not p:
        return False
    explica = any(w in EXPLICAR for w in p[:3])
    quem = tuple(p[:2]) in QUEM_E and (p[2:3] or [""])[0] not in ("voce", "vc", "tu")
    if (explica or quem) and JANELA_ABERTA in " ".join(palavras(pedido)):
        return True
    return p[0] in VERBOS_DE_ACAO or any(w in ASSUNTOS_DE_FERRAMENTA for w in p)


CHAVES = lugares.CONFIG / "chaves"  # uma por motor, 0600 (o painel grava aqui)
ESCOLHA = lugares.ESTADO / "via-rapida.json"  # o painel, por cima da config
AJUSTAVEIS = ("ligada", "quando", "motor", "modelo", "endereco", "raciocinio")
# Quando a via rápida responde (ADR 0042, etapa 2): só no Live, a conversa em tempo real (o
# padrão), ou sempre, também no Normal e no teclado.
QUANDOS = ("live", "sempre")
RACIOCINIOS = ("", "minimal", "low", "medium", "high")


def arquivo_da_chave(motor: str, pasta: Path | None = None) -> Path:
    pasta = pasta or CHAVES
    if motor not in VARIAVEIS:
        raise MotorErro(f"o motor {motor} não usa chave")
    return pasta / f"{motor}.key"


def ler_chave(motor: str, arquivo: str, pasta: Path | None = None) -> str | None:
    """A variável de ambiente, o arquivo da config ou o arquivo que o painel gravou."""
    if valor := _do_ambiente(motor):
        return valor
    caminho = Path(arquivo).expanduser() if arquivo else None
    if caminho is None and motor in VARIAVEIS:
        caminho = arquivo_da_chave(motor, pasta)
    if caminho is None:
        return None
    try:
        return caminho.read_text().strip() or None
    except OSError:
        return None


def gravar_chave(motor: str, chave: str, pasta: Path | None = None) -> None:
    pasta = pasta or CHAVES
    """Grava a chave colada no painel: arquivo 0600 numa pasta 0700, escrita atômica."""
    chave = chave.strip()
    if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
        raise MotorErro("chave vazia ou com espaços")
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    pasta.chmod(0o700)
    destino = arquivo_da_chave(motor, pasta)
    temporario = destino.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(chave + "\n")
    temporario.replace(destino)


def apagar_chave(motor: str, pasta: Path | None = None) -> None:
    arquivo_da_chave(motor, pasta).unlink(missing_ok=True)


def situacao_da_chave(motor: str, arquivo: str = "", pasta: Path | None = None) -> dict[str, Any]:
    """O que a tela pode saber de uma chave: se existe, de onde e os quatro últimos caracteres."""
    if motor not in VARIAVEIS:
        return {"usa": False}
    chave = ler_chave(motor, arquivo, pasta)
    if _do_ambiente(motor):
        origem = "ambiente"
    elif arquivo:
        origem = "config"
    else:
        origem = "painel"
    return {"usa": True, "tem": bool(chave), "origem": origem, "fim": chave[-4:] if chave else ""}


def ler_escolha(arquivo: Path | None = None) -> dict[str, Any]:
    try:
        dados = json.loads((arquivo or ESCOLHA).read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in dados.items() if k in AJUSTAVEIS} if isinstance(dados, dict) else {}


def validar_escolha(dados: dict[str, Any]) -> dict[str, Any]:
    """Só os campos ajustáveis, com o tipo certo; o que vier errado é recusado inteiro."""
    escolha: dict[str, Any] = {}
    for chave, valor in dados.items():
        if chave not in AJUSTAVEIS:
            raise MotorErro(f"campo não ajustável: {chave}")
        if chave == "ligada":
            if not isinstance(valor, bool):
                raise MotorErro("ligada precisa ser verdadeiro ou falso")
        elif chave == "quando":
            if valor not in QUANDOS:
                raise MotorErro("quando deve ser live ou sempre")
        elif not isinstance(valor, str) or len(valor) > 200:
            raise MotorErro(f"{chave} precisa ser texto curto")
        escolha[chave] = valor.strip() if isinstance(valor, str) else valor
    if "motor" in escolha and escolha["motor"] not in MOTORES:
        raise MotorErro(f"motor desconhecido: {escolha['motor']}")
    if "raciocinio" in escolha and escolha["raciocinio"] not in RACIOCINIOS:
        raise MotorErro("raciocínio deve ser minimal, low, medium ou high")
    if escolha.get("endereco"):
        partes = urlsplit(escolha["endereco"])
        local = partes.hostname in ("127.0.0.1", "localhost", "::1")
        if partes.scheme != "https" and not (partes.scheme == "http" and local):
            raise MotorErro("o endereço precisa ser https (ou http na própria máquina)")
    if (
        "modelo" in escolha
        and not escolha["modelo"]
        and escolha.get("motor") not in ("codex", "contas")
    ):
        raise MotorErro("o modelo não pode ficar vazio")
    return escolha


def gravar_escolha(dados: dict[str, Any], arquivo: Path | None = None) -> dict[str, Any]:
    arquivo = arquivo or ESCOLHA
    escolha = {**ler_escolha(arquivo), **validar_escolha(dados)}
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps(escolha, ensure_ascii=False))
    temporario.replace(arquivo)
    return escolha


def vale_agora(via: dict[str, Any], live: bool) -> bool:
    """A via rápida responde agora? Ligada e, se for só no Live, com o Live conversando."""
    return bool(via["ligada"]) and (via.get("quando", "live") == "sempre" or live)


def efetiva(via_da_config: dict[str, Any], arquivo: Path | None = None) -> dict[str, Any]:
    """A config com a escolha do painel por cima; a ponte sem endereço não vale."""
    via = {**via_da_config, **ler_escolha(arquivo)}
    if via["motor"] == "ponte" and not via["endereco"]:
        return dict(via_da_config)
    return via


def criar_motor(
    via: dict[str, Any], pasta: Path, foto: Callable[[], str] | None = None
) -> Motor | None:
    """O motor da config, ou None (sem chave: avisa e o Zé segue só com o cérebro completo)."""
    nome = str(via["motor"])
    if nome not in MOTORES:
        raise MotorErro(f"motor desconhecido: {nome}")
    modelo = str(via["modelo"])
    if nome == "plano":
        return MotorPlano(modelo, pasta, foto)
    if nome == "codex":
        return MotorCodex(modelo, pasta / "codex", foto)
    if nome == "contas":
        cs = contas.Contas()
        motores: list[Motor] = []
        for agente in ("codex", "claude"):
            if agente == "codex" and shutil.which("codex") is None:
                continue
            atual = cs.em_uso(agente)
            for conta in sorted(cs.listar(agente), key=lambda c: c.id != atual.id):
                if not conta.login.is_file():
                    continue
                if agente == "codex":
                    motores.append(MotorCodex("", pasta / conta.id.replace(":", "-"), foto, conta))
                else:
                    motores.append(
                        MotorPlano("sonnet", pasta / conta.id.replace(":", "-"), foto, conta)
                    )
        if not motores:
            raise MotorErro("Nenhuma conta de agente configurada.")
        return MotorContas(motores)
    if nome == "omniroute":  # a mesma conexão do cérebro (Modelos → Cérebro → OmniRoute)
        from zervis.cerebro import omniroute

        chave_omni = omniroute.ler_chave(lugares.CONFIG / "omniroute.key")
        if chave_omni is None:
            log.warning("via rápida: sem a chave do OmniRoute; seguindo só com o cérebro completo")
            return None
        base = omniroute.ler_endereco() or "http://127.0.0.1:20128"
        return MotorOpenAI(
            "omniroute",
            f"{base}/v1",
            chave_omni,
            modelo,
            str(via["raciocinio"]),
            int(via["max_tokens"]),
        )
    chave = ler_chave(nome, str(via["arquivo_chave"]))
    if chave is None and nome != "ponte":
        log.warning("via rápida: sem a chave do %s; seguindo só com o cérebro completo", nome)
        return None
    endereco = str(via["endereco"]) or ENDERECOS.get(nome, "")
    if not endereco:
        raise MotorErro("a ponte precisa de endereço")
    if nome == "anthropic":
        return MotorAnthropic(chave or "", modelo, endereco, int(via["max_tokens"]))
    return MotorOpenAI(
        nome, endereco, chave, modelo, str(via["raciocinio"]), int(via["max_tokens"])
    )


class Roteado:
    """O cérebro do Zé com a via rápida na frente: conversa nela, ferramenta no completo."""

    def __init__(
        self,
        completo: Brain,
        motor: Motor,
        persona_rapida: str,
        foto: Callable[[], str] | None = None,
        espera_s: float = 3.0,
        historico: int = 12,
    ) -> None:
        self.completo = completo
        self.motor = motor
        self.persona_rapida = persona_rapida
        self.foto = foto
        self.espera_s = espera_s
        self.limite_historico = historico
        self.motor_ok = False
        self._avisos = -1
        self.turnos: list[dict[str, str]] = []  # {"pessoa", "ze", "via"}
        self.visto_completo = 0  # quantos turnos o completo já tem na sessão dele
        self.visto_motor = 0
        self.via = ""  # quem respondeu o último pedido: "rapida" ou "completo"
        self.uso: dict[str, Any] | None = None
        self.ferramentas_usadas: list[str] = []
        self.modelo_usado: str | None = None
        self.gastos: list[dict[str, Any]] = []
        self._uso_rapida: dict[str, Any] | None = None
        self._parando: asyncio.Future[None] | None = None

    # --- o que o núcleo lê do cérebro, como antes ------------------------------------------

    @property
    def modelo(self) -> str:
        return str(getattr(self.completo, "modelo", "") or "")

    @property
    def assinatura(self) -> bool:
        return bool(getattr(self.completo, "assinatura", False))

    @property
    def limite(self) -> dict[str, Any]:
        return dict(getattr(self.completo, "limite", {}) or {})

    @property
    def provedor_rapido(self) -> str:
        return f"rapida:{self.motor.nome}"

    # --- ciclo ---------------------------------------------------------------------------

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        await self.completo.start(persona, aprovar)
        try:
            await self.motor.iniciar(self._sistema())
            self.motor_ok = True
        except Exception as erro:
            log.warning("via rápida fora (%s); só o cérebro completo", type(erro).__name__)

    def _sistema(self) -> str:
        return self.sistema_para(self.motor)

    def sistema_para(self, motor: Motor) -> str:
        if motor.com_estado:
            return self.persona_rapida  # o SDK já acrescenta a memória (foto) sozinho
        foto = self.foto() if self.foto else ""
        return self.persona_rapida + ("\n\n" + foto if foto else "")

    def _perdidos(self, desde: int) -> str:
        """O que foi conversado sem este lado, para ele continuar a mesma conversa."""
        trechos = [
            f"{usuario.PERFIL.rotulo}: «{t['pessoa']}» Zé: «{t['ze']}»" for t in self.turnos[desde:]
        ]
        if not trechos:
            return ""
        return "(Antes disto, na mesma conversa: " + " ".join(trechos[-6:]) + ")\n"

    def _mensagens(self, texto: str) -> list[dict[str, str]]:
        if self.motor.com_estado:
            return [{"role": "user", "content": self._perdidos(self.visto_motor) + texto}]
        mensagens: list[dict[str, str]] = []
        for t in self.turnos[-self.limite_historico :]:
            mensagens += [
                {"role": "user", "content": t["pessoa"]},
                {"role": "assistant", "content": t["ze"]},
            ]
        return [*mensagens, {"role": "user", "content": texto}]

    def _guardar(self, texto: str, resposta: str, via: str) -> None:
        self.turnos.append({"pessoa": texto, "ze": resposta.strip(), "via": via})
        if len(self.turnos) > 4 * self.limite_historico:
            corte = len(self.turnos) - 2 * self.limite_historico
            self.turnos = self.turnos[corte:]
            self.visto_completo = max(0, self.visto_completo - corte)
            self.visto_motor = max(0, self.visto_motor - corte)

    def _gasto_rapida(self) -> list[dict[str, Any]]:
        parte = gasto(self.motor.uso, "rapida", self.motor.modelo)
        return [parte] if parte else []

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.uso, self.ferramentas_usadas, self.via = None, [], ""
        inicio = time.monotonic()
        # Cada chamada desta mensagem, para a Conversa mostrar como o Zé gastou os tokens.
        self.gastos, self._uso_rapida = [], None
        falou = False
        if self.motor_ok and not precisa_do_completo(texto):
            resposta = ""
            passar = False
            try:
                async for pedaco in self._rapida(texto):
                    if pedaco is None:
                        passar = True
                        break
                    falou = True
                    resposta += pedaco
                    yield Texto(pedaco)
            except (MotorErro, TimeoutError) as erro:
                log.warning("via rápida falhou (%s: %s)", type(erro).__name__, str(erro)[:160])
                passar = True
                # Em segundo plano: parar o motor travado levava 5 s (TimeoutError do SDK) e o
                # cérebro completo só começava depois (teste de 27/10/2026).
                self._parando = asyncio.ensure_future(self._parar_motor())
                if falou:
                    self.uso, self.via = self.motor.uso, "rapida"
                    self.gastos = self._gasto_rapida()
                    self._guardar(texto, resposta, "rapida")
                    yield Fim(
                        "tempo_esgotado" if isinstance(erro, TimeoutError) else "falha_resposta"
                    )
                    return
            if not passar:
                self.uso, self.via = self.motor.uso, "rapida"
                self.gastos = self._gasto_rapida()
                self.modelo_usado = self.motor.modelo
                self._guardar(texto, resposta, "rapida")
                if self.motor.com_estado:
                    self.visto_motor = len(self.turnos)
                yield Fim()
                return
            if self.motor.com_estado:
                self.visto_motor = len(self.turnos)  # ele viu o pedido, não a resposta
            # A via rápida leu o pedido para decidir passar a vez: isso também gastou.
            self.gastos, self._uso_rapida = self._gasto_rapida(), self.motor.uso
        async for evento in self._completo(texto, aviso=not falou, inicio=inicio):
            yield evento

    async def _parar_motor(self) -> None:
        with contextlib.suppress(Exception):
            await self.motor.interromper()

    async def _rapida(self, texto: str) -> AsyncIterator[str | None]:
        """Os pedaços da via rápida; None = passar a vez ao completo (nada foi falado)."""
        fluxo = self.motor.gerar(self._sistema(), self._mensagens(texto)).__aiter__()
        buffer = ""
        decidido = False
        primeiro = True
        while True:
            try:
                if primeiro:
                    # A autenticação e a troca de conta do CLI podem levar mais que o HTTP.
                    espera = (
                        max(self.espera_s, 30)
                        if self.motor.nome in ("contas", "codex")
                        else self.espera_s
                    )
                    pedaco = await asyncio.wait_for(fluxo.__anext__(), espera)
                    primeiro = False
                else:
                    pedaco = await fluxo.__anext__()
            except StopAsyncIteration:
                break
            if decidido:
                yield pedaco
                continue
            buffer += pedaco
            decisao = self._decidir(buffer)
            if decisao == "passar":
                # Lê o resto (é só a marca) para a sessão do motor terminar o turno inteira.
                with contextlib.suppress(StopAsyncIteration, MotorErro):
                    async with asyncio.timeout(self.espera_s):
                        while True:
                            await fluxo.__anext__()
                yield None
                return
            if decisao == "falar":
                decidido = True
                yield buffer
        if not decidido:
            decisao = self._decidir(buffer, fim=True)
            if decisao in ("passar", "falar_nada") or not buffer.strip():
                yield None
                return
            yield buffer

    @staticmethod
    def _decidir(buffer: str, fim: bool = False) -> str:
        """`passar`, `falar` ou `esperar`: as marcas do começo ([alegria] [completo]) decidem."""
        resto = buffer
        while m := MARCA.match(resto):
            if m.group(0).strip().lower() == PASSAR:
                return "passar"
            resto = resto[m.end() :]
        inicio = resto.lstrip()
        if not inicio:
            return "falar" if fim and buffer.strip() else "esperar"
        if inicio.startswith("[") and "]" not in inicio and len(inicio) < 14:
            if not fim:
                return "esperar"  # uma marca chegando pela metade
            # A resposta acabou no meio da marca ("[complet", 06/11/2026: o motor estourou o
            # tempo e "complet" foi falado). O começo de [completo] passa a vez; outra marca
            # pela metade não é fala.
            return "passar" if PASSAR.startswith(inicio.lower()) else "falar_nada"
        return "falar"

    async def _completo(
        self, texto: str, aviso: bool, inicio: float | None = None
    ) -> AsyncIterator[EventoCerebro]:
        pedido = self._perdidos(self.visto_completo) + texto
        resposta = ""
        erro: str | None = None
        prazo = (inicio if inicio is not None else time.monotonic()) + AVISO_APOS_S
        # Sem aviso de espera se a resposta começar antes do prazo: o primeiro evento é esperado
        # sem cancelar (asyncio.wait), para o aviso entrar no meio quando o prazo vence.
        eventos = self.completo.ask(pedido).__aiter__()
        proximo: asyncio.Future[EventoCerebro] = asyncio.ensure_future(eventos.__anext__())
        try:
            while True:
                if aviso and not resposta.strip():
                    pronto, _ = await asyncio.wait({proximo}, timeout=prazo - time.monotonic())
                    if not pronto:
                        aviso = False
                        self._avisos += 1
                        yield Texto(AVISOS[self._avisos % len(AVISOS)] + " ")
                try:
                    evento = await proximo
                except StopAsyncIteration:
                    break
                if isinstance(evento, Texto):
                    resposta += evento.texto
                    if evento.texto.strip():
                        aviso = False
                elif isinstance(evento, Fim):
                    erro = evento.erro
                yield evento
                proximo = asyncio.ensure_future(eventos.__anext__())
        finally:
            if not proximo.done():
                proximo.cancel()
        uso_completo = getattr(self.completo, "uso", None)
        self.ferramentas_usadas = list(getattr(self.completo, "ferramentas_usadas", []))
        self.modelo_usado = getattr(self.completo, "modelo_usado", None)
        modelo = str(self.modelo_usado or getattr(self.completo, "modelo", "") or "")
        self.uso = somar_usos(self._uso_rapida, uso_completo)
        if parte := gasto(uso_completo, "completo", modelo):
            self.gastos = [*self.gastos, parte]
        self.via = "completo"
        if not erro:
            self._guardar(texto, resposta, "completo")
        self.visto_completo = len(self.turnos)

    async def interrupt(self) -> None:
        # Juntos: no Live, falar por cima interrompe; um motor lento para parar não pode segurar
        # o completo (cada um tem o seu prazo).
        await asyncio.gather(
            self.motor.interromper(), self.completo.interrupt(), return_exceptions=True
        )

    async def reset(self) -> None:
        self.turnos, self.visto_completo, self.visto_motor = [], 0, 0
        await self.motor.reiniciar()
        await self.completo.reset()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.motor.fechar()
        await self.completo.close()


def envolver(
    cerebro: Brain,
    via: dict[str, Any],
    pasta: Path,
    persona_rapida: str,
    foto: Callable[[], str] | None = None,
    live: bool = False,
) -> Brain:
    """O cérebro com a via rápida na frente, se ela valer agora (`vale_agora`) e for montável."""
    if not vale_agora(via, live):
        return cerebro
    try:
        motor = criar_motor(via, pasta, foto)
    except MotorErro as erro:
        log.warning("via rápida não montada: %s", erro)
        return cerebro
    if motor is None:
        return cerebro
    log.info("via rápida: %s (%s)", motor.nome, motor.modelo)
    return Roteado(
        cerebro, motor, persona_rapida, foto, float(via["espera_s"]), int(via["historico"])
    )


async def religar(
    atual: Brain,
    motor: Motor | None,
    persona_rapida: str,
    foto: Callable[[], str] | None = None,
    espera_s: float = 3.0,
    historico: int = 12,
) -> Brain:
    """Troca só o motor da via rápida (ou a liga/desliga), sem reiniciar o cérebro completo.

    Roda no laço do cérebro (dentro da trava de troca da Ponte); devolve o cérebro novo.
    """
    completo = atual.completo if isinstance(atual, Roteado) else atual
    antigo = atual.motor if isinstance(atual, Roteado) else None
    if motor is None:
        novo: Brain = completo
    elif isinstance(atual, Roteado):
        await motor.iniciar(atual.sistema_para(motor))
        atual.motor, atual.motor_ok, atual.visto_motor = motor, True, len(atual.turnos)
        novo = atual
    else:
        roteado = Roteado(completo, motor, persona_rapida, foto, espera_s, historico)
        await motor.iniciar(roteado.sistema_para(motor))
        roteado.motor_ok = True
        novo = roteado
    if antigo is not None and antigo is not motor:
        with contextlib.suppress(Exception):
            await antigo.fechar()
    return novo


async def medir(motor: Motor, persona_rapida: str, limite_s: float = 20.0) -> dict[str, Any]:
    """O botão Testar: sobe o motor, pergunta "oi" e mede o tempo até a primeira palavra."""
    import time

    sistema = persona_rapida
    try:
        async with asyncio.timeout(limite_s):
            inicio = time.monotonic()
            await motor.iniciar(sistema)
            conectar_ms = round((time.monotonic() - inicio) * 1000)
            inicio = time.monotonic()
            primeira: float | None = None
            texto = ""
            mensagens = [{"role": "user", "content": "Oi Zé, tudo bem? Responda em uma frase."}]
            async for pedaco in motor.gerar(sistema, mensagens):
                if primeira is None:
                    primeira = time.monotonic() - inicio
                texto += pedaco
            if primeira is None:
                return {"ok": False, "erro": "o modelo não respondeu nada"}
            return {
                "ok": True,
                "conectar_ms": conectar_ms,
                "primeira_palavra_ms": round(primeira * 1000),
                "total_ms": round((time.monotonic() - inicio) * 1000),
                "texto": texto.strip()[:200],
            }
    except TimeoutError:
        return {"ok": False, "erro": f"sem resposta em {limite_s:.0f} s"}
    except MotorErro as erro:
        return {"ok": False, "erro": str(erro)[:200]}
    except Exception as erro:
        return {"ok": False, "erro": type(erro).__name__}
    finally:
        with contextlib.suppress(Exception):
            await motor.fechar()
