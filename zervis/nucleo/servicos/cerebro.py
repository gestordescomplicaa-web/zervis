"""Serviço de cerebro; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import contextlib
import dataclasses
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from zervis import atividade, usuario
from zervis.cerebro import acesso, catalogo, mcp_externo, omniroute, rapido
from zervis.cerebro import modelos as modelos_dos_agentes
from zervis.cerebro.base import Brain, Ponte
from zervis.cerebro.baterias import Bateria, da_assinatura
from zervis.cerebro.consumo import Consumo, UsoDeFerramentas, gasto
from zervis.cerebro.eco import Eco
from zervis.config import Config
from zervis.habilidades import evidencias, revisao
from zervis.habilidades.skills import Skills
from zervis.memoria.curta import Memoria
from zervis.nucleo import autoconhecimento
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import DADOS, FALHA_NO_CEREBRO, JANELA_FALADA, PERSONA, PERSONA_RAPIDA
from zervis.rosto import manifesto, tela
from zervis.rosto.anel import Anel, separar_emocao
from zervis.rosto.quadro import Quadro
from zervis.sistema import maquina
from zervis.voz.fala import separar_fontes
from zervis.voz.latencia import Latencias
from zervis.voz.live import live_ativo

log = logging.getLogger(__name__)


class ContextoCerebro(Protocol):
    _fontes: tuple[int, list[str]]
    _gasto_do_turno: Any
    _gastos_extras: list[dict[str, Any]]
    _revisoes: Any
    _turno_cerebro: tuple[int, str | None]
    anel: Anel
    baterias_omniroute: dict[str, Bateria]
    cerebro: Brain
    cfg: Config
    consumo: Consumo
    escolhido: Path
    eventos: queue.Queue[e.Evento]
    evidencias: evidencias.Evidencias
    externos: Any
    extras: catalogo.Extras
    latencias: Latencias
    limite_claude: Any
    marca: Any
    memoria: Memoria
    modelo_auto: str | None
    modelos_escolhidos: Path
    orbes: Any
    pendencias: revisao.Pendencias
    pergunta: Any
    ponte: Ponte
    provedor: str
    quadro: Quadro
    skills: Skills
    tela: tela.Tela
    turnos: list[dict[str, str]]
    uso_ferramentas: UsoDeFerramentas

    def _chave_do_omniroute(self) -> str | None: ...
    def _com_via_rapida(self, cerebro: Brain) -> Brain: ...
    def _erro(self, mensagem: str) -> None: ...
    def _foto_simples(self) -> str: ...
    def _latencia_do_cerebro(self, marca: int) -> str | None: ...
    def _registrar_turno(self, turno: dict[str, str]) -> None: ...
    def _remontar(self) -> str: ...
    async def _revisar(self, turnos: list[dict[str, str]]) -> None: ...
    def _testar_modelo(self, modelo: str) -> str | None: ...
    def baterias(self) -> dict[str, Bateria]: ...
    def modelos(self) -> dict[str, str]: ...
    def modelos_do_omniroute(self) -> list[str]: ...
    def persona(self) -> str: ...
    def persona_rapida(self) -> str: ...


class ServicoCerebro:
    def __init__(self, contexto: ContextoCerebro) -> None:
        self.n = contexto

    def _latencia_do_cerebro(self, marca: int) -> str | None:
        atual, turno = self.n._turno_cerebro
        return turno if marca == atual and marca == self.n.marca else None

    def _primeiro_texto_do_cerebro(self, marca: int, em: float) -> None:
        self.n.latencias.marcar(self.n._latencia_do_cerebro(marca), "primeiro_token", em)

    def _frase_do_cerebro(self, marca: int, frase: str) -> None:
        if marca == self.n.marca:
            # Depois de "Fontes:" o resto da resposta é a lista de links: tela, não voz.
            if self.n._fontes[0] != marca:
                self.n._fontes = (marca, [])
            if self.n._fontes[1]:
                self.n._fontes[1].append(frase)
                return
            frase, fontes = separar_fontes(frase)
            if fontes:
                self.n._fontes[1].append(fontes)
            emocao, frase = separar_emocao(frase)
            if emocao:
                self.n.anel.expressao(emocao, time.time())
            if not frase.strip():
                return
            self.n.latencias.marcar(self.n._latencia_do_cerebro(marca), "primeira_frase")
            if self.n.turnos:
                self.n.turnos[-1]["jarvis"] = (self.n.turnos[-1]["jarvis"] + " " + frase).strip()
            self.n.eventos.put(e.Frase(frase))

    def _gasto_do_turno(self) -> dict[str, Any] | None:
        """O que esta mensagem gastou, por parte: a via rápida, o cérebro e o que as ferramentas
        gastaram por fora (a pesquisa), para a Conversa (pedido de 27/10/2026)."""
        cerebro = self.n.cerebro
        partes = list(getattr(cerebro, "gastos", None) or [])
        if not partes:
            modelo = str(getattr(cerebro, "modelo_usado", None) or getattr(cerebro, "modelo", ""))
            if parte := gasto(getattr(cerebro, "uso", None), "completo", modelo):
                partes = [parte]
        partes += getattr(self.n, "_gastos_extras", [])
        if not partes:
            return None
        ferramentas = [n.rsplit("__", 1)[-1] for n in getattr(cerebro, "ferramentas_usadas", [])]
        return {"provedor": self.n.provedor, "partes": partes, "ferramentas": ferramentas}

    def _pedido_de_aprovacao(self, marca: int, descricao: str) -> None:
        if marca == self.n.marca:
            self.n.latencias.contexto(self.n._latencia_do_cerebro(marca), aprovacao=True)
            self.n.pergunta = descricao
            self.n.eventos.put(e.PedidoAprovacao(descricao))
        else:
            self.n.ponte.responder_aprovacao(False)  # pedido de uma resposta abandonada

    def _fim_do_cerebro(self, marca: int, erro: str | None) -> None:
        self.n.consumo.somar(getattr(self.n.cerebro, "uso", None), self.n.provedor)
        self.n.uso_ferramentas.somar(
            list(getattr(self.n.cerebro, "ferramentas_usadas", [])), time.time()
        )
        usadas = {n.rsplit("__", 1)[-1] for n in getattr(self.n.cerebro, "ferramentas_usadas", [])}
        if usadas and usadas <= {"tela_agir", "tela_ver", "tela_explicar"} and self.n.turnos:
            self.n.evidencias.registrar("so_tela", self.n.turnos[-1]["pessoa"])
        if erro:
            self.n.evidencias.registrar("falha_cerebro", erro)
            pedido = self.n.turnos[-1]["pessoa"] if self.n.turnos else ""
            atividade.PADRAO.registrar("falha", "O cérebro falhou", erro=erro, pedido=pedido)
        if marca != self.n.marca:
            return
        turno = self.n._latencia_do_cerebro(marca)
        if getattr(self.n.cerebro, "via", "") == "rapida":
            motor = self.n.cerebro.motor  # type: ignore[attr-defined]
            self.n.latencias.contexto(turno, provedor=f"rapida:{motor.nome}", modelo=motor.modelo)
        self.n.latencias.marcar(turno, "fim_cerebro")
        self.n.latencias.contexto(turno, erro_cerebro=bool(erro))
        if not erro and self.n.turnos and self.n.turnos[-1]["jarvis"]:
            self.n._gasto_do_turno = self._gasto_do_turno()
            self.n._registrar_turno(self.n.turnos[-1])
        if self.n._fontes[0] == marca and self.n._fontes[1]:
            corpo = "\n".join(self.n._fontes[1])
            threading.Thread(
                target=self.n.quadro.apresentar, args=("Fontes", corpo, 120), daemon=True
            ).start()
        if erro:
            self.n._erro(f"cérebro: {erro}")
            mensagem = {
                "limite_de_uso": "Limite de uso atingido. Troque a conta em Modelos.",
                "acesso_invalido": "Acesso ao modelo inválido. Confira a conta em Modelos.",
            }.get(erro, FALHA_NO_CEREBRO)
            self.n.eventos.put(e.Frase(mensagem))
        self.n.eventos.put(e.RespostaFim())

    def _com_via_rapida(self, cerebro: Brain) -> Brain:
        """A via rápida na frente do cérebro escolhido (docs/plano-voz-rapida.md)."""
        if isinstance(cerebro, Eco):
            return cerebro
        return rapido.envolver(
            cerebro,
            rapido.efetiva(self.n.cfg["via_rapida"]),
            DADOS / "cerebro-rapido",
            self.n.persona_rapida(),
            self.n._foto_simples,
            live=live_ativo(self.n) is not None,
        )

    def recarregar_conectores(self) -> str:
        """O painel mudou os conectores MCP: remonta o cérebro com eles (a conversa recomeça)."""
        try:
            novos = mcp_externo.para_conversa(painel=mcp_externo.PAINEL)
        except mcp_externo.McpInvalido as erro:
            return f"Conectores com erro: {erro}."
        antigos = self.n.externos
        mcp = {k: v for k, v in self.n.extras.mcp.items() if k not in antigos.servidores}
        livres = tuple(n for n in self.n.extras.livres if n not in antigos.livres)
        self.n.extras = dataclasses.replace(
            self.n.extras,
            mcp={**mcp, **novos.servidores},
            livres=(*livres, *novos.livres),
            bloqueadas=tuple(novos.bloqueadas),
        )
        self.n.externos = novos
        if self.n.provedor not in catalogo.OPCOES:
            return "Com o cérebro de teste os conectores não valem."
        try:
            novo = catalogo.com_reserva(
                self.n.provedor, self.n.cfg, DADOS / "cerebro", self.n.extras
            )
        except catalogo.Indisponivel as motivo:
            return f"Não remontei o cérebro: {motivo}."
        cerebro = self.n._com_via_rapida(novo)
        self.n.ponte.trocar(cerebro)
        self.n.cerebro = cerebro
        ligados = ", ".join(novos.servidores) or "nenhum"
        log.info("conectores MCP recarregados: %s", ligados)
        return f"Pronto: o Zé agora usa os conectores {ligados}."

    def persona(self) -> str:
        return (
            PERSONA.read_text()
            + "\n\n"
            + usuario.PERFIL.para_persona()
            + "\n\n"
            + maquina.detectar().para_persona()
            + "\n\n"
            + manifesto.para_persona(self.n.orbes)
        )

    def aplicar_perfil(self, perfil: usuario.Perfil) -> str:
        """O painel salvou o perfil: a persona muda e o cérebro recomeça com ela."""
        usuario.PERFIL = perfil
        self.n.ponte.persona = self.n.persona()
        return self.n._remontar()

    def aplicar_acesso(self) -> str:
        """O painel mudou o acesso: aplica a conta e remonta as duas camadas de conversa."""
        acesso.aplicar()
        return self.n._remontar()

    def _remontar(self) -> str:
        """Cérebro novo do mesmo provedor (a conversa recomeça); devolve um aviso ou ""."""
        if self.n.provedor not in catalogo.OPCOES:
            return ""
        try:
            novo = catalogo.com_reserva(
                self.n.provedor, self.n.cfg, DADOS / "cerebro", self.n.extras
            )
        except catalogo.Indisponivel as motivo:
            return f"Cérebro indisponível: {motivo}."
        cerebro = self.n._com_via_rapida(novo)
        self.n.ponte.trocar(cerebro)
        self.n.cerebro = cerebro
        return ""

    def persona_rapida(self) -> str:
        return (
            PERSONA_RAPIDA.read_text()
            + "\n\n"
            + usuario.PERFIL.para_persona()
            + "\n\n"
            + maquina.detectar().para_persona()
            + self._voce_agora()
        )

    def _voce_agora(self) -> str:
        """O retrato do Zé para a via rápida (ADR 0043): ela sobe só quando vai responder, então
        é ela quem responde, com o modelo escolhido."""
        retrato = getattr(self.n, "retrato", None)
        if retrato is None:
            return ""
        try:
            r = retrato()
        except Exception:
            log.debug("retrato do Zé falhou", exc_info=True)
            return ""
        modelo = catalogo.rotulo(str(rapido.efetiva(self.n.cfg["via_rapida"])["modelo"]))
        agora = dataclasses.replace(r, rapidas_agora=True, rapidas_modelo=modelo)
        return "\n\n" + autoconhecimento.resumo(agora)

    def aplicar_via_rapida(self) -> str:
        """O painel mudou a via rápida, ou o Live conectou ou saiu: troca só o motor, na hora;
        devolve um aviso ou ""."""
        if isinstance(getattr(self.n.cerebro, "completo", self.n.cerebro), Eco):
            return "Com o cérebro de teste não há via rápida."
        via = rapido.efetiva(self.n.cfg["via_rapida"])
        aviso = ""
        motor: rapido.Motor | None = None
        if rapido.vale_agora(via, live_ativo(self.n) is not None):
            try:
                motor = rapido.criar_motor(via, DADOS / "cerebro-rapido", self.n._foto_simples)
            except rapido.MotorErro as erro:
                aviso = f"Não montei a via rápida: {erro}."
            if motor is None and not aviso:
                aviso = "Falta a chave deste motor; sigo só com o cérebro completo."

        async def _trocar() -> Brain:
            async with self.n.ponte._troca():
                novo = await rapido.religar(
                    self.n.ponte.cerebro,
                    motor,
                    self.n.persona_rapida(),
                    self.n._foto_simples,
                    float(via["espera_s"]),
                    int(via["historico"]),
                )
                self.n.ponte.cerebro = novo
                return novo

        try:
            self.n.cerebro = asyncio.run_coroutine_threadsafe(_trocar(), self.n.ponte.laco).result(
                60
            )
        except Exception as erro:
            log.warning("via rápida: troca falhou (%s)", type(erro).__name__)
            return f"A troca falhou ({type(erro).__name__}); veja o log."
        log.info("via rápida: %s", f"{motor.nome} ({motor.modelo})" if motor else "desligada")
        return aviso

    def trocar_cerebro(self, id_: str) -> str:
        """Troca pedida por voz ou no Barehands; devolve a frase a falar."""
        atual = catalogo.OPCOES.get(self.n.provedor)
        if atual is None:
            return "Com o cérebro de teste não há troca."
        if id_ == self.n.provedor:
            return f"Já estou com o {atual.nome}."
        try:
            novo = catalogo.com_reserva(id_, self.n.cfg, DADOS / "cerebro", self.n.extras)
        except catalogo.Indisponivel as motivo:
            log.warning("troca para %s recusada: %s", id_, motivo)
            return f"Não consegui trocar: {motivo}. Continuo com o {atual.nome}."
        log.info("cérebro: %s -> %s", self.n.provedor, id_)
        cerebro = self.n._com_via_rapida(novo)
        self.n.ponte.trocar(cerebro)
        self.n.cerebro, self.n.provedor = cerebro, id_
        with contextlib.suppress(OSError):
            catalogo.gravar_escolha(self.n.escolhido, id_)
        if id_ == "auto":
            return "Pronto, agora é o automático: o OmniRoute escolhe o modelo a cada pedido."
        nome = catalogo.OPCOES[id_].nome
        return f"Pronto, agora quem responde é o {nome}, com o {self.n.modelos()[id_]}."

    def _testar_modelo(self, modelo: str) -> str | None:
        """Uma pergunta mínima ao modelo antes de trocar: a conta pode não ter acesso a ele (o
        Fable 5.1 pede créditos de uso fora da assinatura, 13/10/2026). None se respondeu."""
        try:
            futuro = asyncio.run_coroutine_threadsafe(
                revisao.perguntar_ao_modelo(
                    "Responda só: ok", modelo, DADOS / "cerebro", 0, "Responda em uma palavra."
                ),
                self.n.ponte.laco,
            )
            futuro.result(timeout=40)
        except Exception as erro:
            log.warning("cérebro: %s recusado no teste: %s", modelo, erro)
            if "credit" in str(erro).lower():
                return "Este modelo exige créditos de uso nesta conta."
            return "Este modelo não respondeu nesta conta."
        return None

    def mudar_modelo_do_cerebro(self, agente: str, modelo: str) -> str:
        """O modelo do cérebro escolhido no painel: vale na hora, se o agente for o atual, e
        depois de reiniciar."""
        if agente not in catalogo.CHAVE_DO_MODELO:
            raise ValueError("Agente desconhecido.")
        padrao = agente == "codex" and not modelo  # o Codex pode usar o padrão da conta
        if agente == "omniroute":
            if modelo not in {
                *self.n.modelos_do_omniroute(),
                self.n.cfg["cerebro"]["omniroute_rota"],
            }:
                raise ValueError("Modelo indisponível neste OmniRoute.")
        elif not padrao and modelo not in {m["id"] for m in modelos_dos_agentes.do_cerebro(agente)}:
            raise ValueError("Modelo indisponível para esta conta.")
        if agente == "claude" and (recusa := self.n._testar_modelo(modelo)):
            raise ValueError(recusa)
        escolhas = catalogo.ler_modelos(self.n.modelos_escolhidos) | {agente: modelo}
        catalogo.aplicar_modelos(self.n.cfg, escolhas)
        catalogo.gravar_modelos(self.n.modelos_escolhidos, escolhas)
        provedor = catalogo.PROVEDOR_DO_AGENTE.get(agente, agente)
        if provedor == self.n.provedor:
            try:
                novo = catalogo.com_reserva(provedor, self.n.cfg, DADOS / "cerebro", self.n.extras)
            except catalogo.Indisponivel as motivo:
                return f"Modelo guardado, mas o cérebro não trocou: {motivo}."
            cerebro = self.n._com_via_rapida(novo)
            self.n.ponte.trocar(cerebro)
            self.n.cerebro = cerebro
        log.info("cérebro: modelo do %s agora é %s", agente, modelo)
        nomes = {m["id"]: m["nome"] for m in modelos_dos_agentes.do_cerebro(agente)}
        return f"Modelo do cérebro: {nomes.get(modelo, modelo or 'padrão da conta')}."

    def _chave_do_omniroute(self) -> str | None:
        return omniroute.ler_chave(self.n.cfg.caminho("cerebro", "omniroute_arquivo_chave"))

    def modelos_do_omniroute(self) -> list[str]:
        """Os modelos do OmniRoute configurado; vazio sem chave ou sem conexão."""
        chave = self.n._chave_do_omniroute()
        if not chave:
            return []
        try:
            return omniroute.modelos(self.n.cfg["cerebro"]["omniroute_endereco"], chave)
        except omniroute.OmniErro:
            return []

    def configurar_omniroute(self, endereco: str, chave: str | None) -> str:
        """O endereço e a chave do OmniRoute de quem usa, salvos no painel (só no próprio PC)."""
        omniroute.gravar_conexao(
            endereco, chave, self.n.cfg.caminho("cerebro", "omniroute_arquivo_chave")
        )
        self.n.cfg["cerebro"]["omniroute_endereco"] = omniroute.validar_endereco(endereco)
        if self.n.provedor == "auto":
            with contextlib.suppress(catalogo.Indisponivel):
                novo = catalogo.com_reserva("auto", self.n.cfg, DADOS / "cerebro", self.n.extras)
                self.n.cerebro = self.n._com_via_rapida(novo)
                self.n.ponte.trocar(self.n.cerebro)
        return "OmniRoute salvo."

    def testar_omniroute(self) -> tuple[bool, str]:
        chave = self.n._chave_do_omniroute()
        if not chave:
            return False, "Chave não configurada."
        try:
            n = len(omniroute.modelos(self.n.cfg["cerebro"]["omniroute_endereco"], chave))
        except omniroute.OmniErro as erro:
            return False, str(erro)
        return True, f"Conectado: {n} modelos."

    def modelos(self) -> dict[str, str]:
        """O modelo de cada opção; o do cérebro ativo é o que respondeu de fato, se já houver."""
        c = self.n.cfg["cerebro"]
        modelos = {
            "claude": catalogo.rotulo(c["modelo"]),
            "codex": catalogo.rotulo(c["modelo_codex"]) or "Padrão da conta",
            "gpt": catalogo.rotulo(catalogo.OPCOES["gpt"].rota or ""),
            "gemini": catalogo.rotulo(catalogo.OPCOES["gemini"].rota or ""),
            "auto": self.n.modelo_auto or "OmniRoute escolhe",
        }
        usado = getattr(self.n.cerebro, "modelo_usado", None)
        if usado and self.n.provedor in modelos:
            modelos[self.n.provedor] = catalogo.rotulo(usado)
            if self.n.provedor == "auto":
                self.n.modelo_auto = modelos["auto"]
        return modelos

    def baterias(self) -> dict[str, Bateria]:
        baterias = dict(self.n.baterias_omniroute)
        if (claude := da_assinatura(self.n.limite_claude, time.time())) is not None:
            baterias["claude"] = claude
        return baterias

    def relatorio_de_baterias(self) -> str:
        baterias = self.n.baterias()
        partes = []
        for familia, nome in (("claude", "Claude"), ("gpt", "GPT"), ("gemini", "Gemini")):
            b = baterias.get(familia)
            if b is None:
                partes.append(f"{nome} sem dado")
            else:
                partes.append(f"{nome} com {b.restante}% {JANELA_FALADA.get(b.janela, '')}".strip())
        atual = catalogo.OPCOES.get(self.n.provedor)
        fim = f" Agora estou com o {atual.nome}, {self.n.modelos()[atual.id]}." if atual else ""
        return "Baterias: " + ", ".join(partes) + "." + fim + " " + self.n.consumo.resumo_falado()

    def _fim_da_conversa(self) -> None:
        """A conversa acabou: se valer a pena e houver cota no dia, o Zé revisa e aprende."""
        turnos, self.n.turnos = self.n.turnos, []
        r = self.n.cfg["revisao"]
        if not r["ligada"] or not revisao.vale_revisar(turnos):
            return
        hoje = time.strftime("%Y-%m-%d")
        if self.n._revisoes[0] != hoje:
            self.n._revisoes = (hoje, 0)
        if self.n._revisoes[1] >= r["max_por_dia"]:
            log.info("revisão pulada: limite de %d por dia", r["max_por_dia"])
            return
        self.n._revisoes = (hoje, self.n._revisoes[1] + 1)
        log.info("revisão da conversa (%d turnos) em segundo plano", len(turnos))
        asyncio.run_coroutine_threadsafe(self.n._revisar(turnos), self.n.ponte.laco)

    async def _revisar(self, turnos: list[dict[str, str]]) -> None:
        try:
            prompt = revisao.montar_prompt(turnos, self.n.memoria, self.n.skills)
            r = self.n.cfg["revisao"]
            saida, uso = await revisao.perguntar_ao_modelo(
                prompt, r["modelo"], DADOS / "cerebro", r["pensamento_tokens"]
            )
            self.n.consumo.somar(uso, "revisão")
            propostas = revisao.interpretar(saida, self.n.memoria, self.n.skills)
            for proposta in propostas:
                proposta.origem = revisao.origem(turnos)
        except Exception:
            log.exception("revisão falhou")
            return
        log.info("revisão: %d sugestões", len(propostas))
        if propostas:
            self.n.pendencias.adicionar(propostas)
            n = len(propostas)
            plural = "sugestão" if n == 1 else "sugestões"
            self.n.eventos.put(
                e.Aviso(
                    f"Aprendi algo na última conversa: {n} {plural} para você aprovar. "
                    "Quando quiser, peça para ver as sugestões."
                )
            )

    def _com_nucleo(self, texto: str) -> str:
        """Onde está o Núcleo e o que ele mostra, numa linha: o cérebro age sem perguntar."""
        try:
            return f"({self.n.tela.resumo()}) {texto}"
        except OSError:
            return texto
