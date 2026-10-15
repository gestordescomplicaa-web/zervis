"""Serviço de avisos; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import contextlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from jarvis import usuario
from jarvis.automacoes.agenda import FUSO
from jarvis.avisos import central
from jarvis.avisos import modo as modo_fala
from jarvis.avisos.fila import PRIORIDADES, Fila
from jarvis.habilidades import revisao
from jarvis.nucleo import estados as e
from jarvis.nucleo.apoio import AVISO_RECENTE_S, DADOS, ESTADO, OFERTA_S, VENDO_S
from jarvis.oficina.sessoes import SessaoErro

log = logging.getLogger(__name__)


class ContextoAvisos(Protocol):
    _avisos_dados: Any
    _comecados: Any
    _cortados: Any
    _meta: Any
    _na_tela: Any
    _oferta_ate: Any
    _ultimo_de_sessao: Any
    _vendo: Any
    avisos_falados: Any
    cfg: Any
    chamado: Any
    consumo: Any
    eventos: Any
    fila: Any
    foco: Any
    linha: Any
    maquina: Any
    modo_fala: Any
    segmentador: Any
    sessoes: Any
    toque: Any
    transcrevendo: Any
    voz: Any

    def _aviso_da_oficina(
        self, texto: str, tipo: modo_fala.Tipo, id_: str = "", titulo: str = "", detalhe: str = ""
    ) -> None: ...
    def _ligar_ativacao(self) -> None: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...
    def _pessoa_falando(self) -> bool: ...
    def _sair_da_fila(self) -> None: ...
    def _tocar_som(self, som: Path) -> None: ...
    def vendo(self, id_: str) -> bool: ...


class ServicoAvisos:
    def __init__(self, contexto: ContextoAvisos) -> None:
        self.n = contexto

    def _bom_dia(self) -> None:
        """Na primeira abertura do dia (depois das 5h): onde ele parou e o que tem hoje."""
        agora = datetime.now(FUSO)
        marca = ESTADO / "foco-bom-dia.txt"
        hoje = agora.date().isoformat()
        try:
            if agora.hour < 5 or marca.read_text().strip() == hoje:
                return
        except OSError:
            pass
        partes = []
        if self.n.foco.atual() is not None:
            partes.append(self.n.foco.onde_estava())
        hoje_marcos = [ev.texto for ev in self.n.linha.proximos(0, agora)]
        if hoje_marcos:
            partes.append("Hoje: " + "; ".join(hoje_marcos) + ".")
        if not partes:
            return
        with contextlib.suppress(OSError):
            marca.write_text(hoje)
        self.n.eventos.put(e.Aviso(usuario.PERFIL.vocativo("Bom dia") + ". " + " ".join(partes)))

    async def _narrar_fim(
        self, id_: str, nome: str, resposta: str, titulo: str, detalhe: str, pedido: str = ""
    ) -> None:
        resumo = None
        try:
            saida, uso = await asyncio.wait_for(
                revisao.perguntar_ao_modelo(
                    central.pedido_de_resumo(resposta, pedido),
                    self.n.cfg["revisao"]["modelo"],
                    DADOS / "cerebro",
                    0,
                    central.SISTEMA,
                ),
                timeout=25,
            )
            self.n.consumo.somar(uso, "aviso")
            resumo = central.limpar_resumo(saida)
        except Exception as erro:  # sem o resumo, a primeira frase como citação
            log.warning("resumo do aviso: %s", erro)
        texto = central.narrar(nome, resumo, resposta)
        self.n._aviso_da_oficina(texto, "notificacao", id_, titulo, detalhe)

    def _ultima_resposta(self, id_: str) -> str:
        with contextlib.suppress(SessaoErro):
            for m in reversed(self.n.sessoes.mensagens(id_)):
                if m["quem"] == "agente":
                    return str(m["texto"])
        return ""

    def vendo(self, id_: str) -> bool:
        """A pessoa está com esta sessão aberta no painel (o painel avisa a cada batida)."""
        aberta, quando = self.n._vendo
        return bool(id_) and aberta == id_ and time.monotonic() - quando < VENDO_S

    def ver_sessao(self, id_: str) -> None:
        self.n._vendo = (id_, time.monotonic())
        if id_:
            self.n.sessoes.focar(id_)

    def mudar_modo_fala(self, modo: str) -> str:
        """Troca o modo de fala na hora; devolve a confirmação curta para a tela e a voz."""
        self.n.modo_fala = modo_fala.gravar(modo)
        self.n.voz.muda = modo == "silencioso"
        if self.n.voz.muda:
            self.n.voz.parar()
            # Silencioso trava o microfone: nem chamado, nem botão, nem ao vivo (13/10/2026).
            if (captura := getattr(self.n, "captura", None)) is not None:
                captura.fechar()
                self.n.segmentador.limpar()
            if self.n.maquina.estado is e.Estado.OUVINDO:
                self.n.eventos.put(e.Silencio())
        elif (captura := getattr(self.n, "captura", None)) is not None and (
            self.n.maquina.estado is not e.Estado.INATIVO
        ):
            captura.abrir()
        self.n._ligar_ativacao()
        log.info("modo de fala: %s", modo)
        return f"Modo {modo_fala.NOMES[modo].lower()}."

    def _aviso_da_oficina(
        self,
        texto: str,
        tipo: modo_fala.Tipo,
        id_: str = "",
        titulo: str = "",
        detalhe: str = "",
    ) -> None:
        """O resultado é anunciado mesmo com a sessão aberta; Silencioso continua só na tela.
        Na fila, cada sessão preserva nome, prioridade e detalhe (ADR 0029)."""
        self.n._meta[texto] = {
            "prioridade": PRIORIDADES[tipo],
            "titulo": titulo,
            "sessao": id_,
            "detalhe": detalhe,
            "toque": bool(id_),
        }
        self.n._na_linha("aviso", texto)
        if id_:
            self.n.sessoes.focar(id_)
        if modo_fala.falar(self.n.modo_fala, tipo):
            escutar = self.n.modo_fala == "maos_livres" and self.n.chamado == "voz"
            self.n.eventos.put(e.Aviso(texto, escutar=escutar, sequencial=bool(id_)))

    def _guardar(self, texto: str) -> None:
        """O aviso espera na fila com o que se sabe dele (prioridade, sessão, manchete)."""
        m = self.n._meta.get(texto, {})
        self.n.fila.guardar(
            texto,
            prioridade=int(m.get("prioridade", PRIORIDADES["notificacao"])),
            titulo=str(m.get("titulo", "")),
            sessao=str(m.get("sessao", "")),
            detalhe=str(m.get("detalhe", "")),
        )

    def _sair_da_fila(self) -> None:
        """Cada aviso de sessão sai na própria vez, sem pedir para avançar (ADR 0029)."""
        saida = self.n.fila.oferecer()
        if saida is None:
            return
        texto, aviso = saida
        if aviso is not None:  # um só: volta a ser o aviso de antes
            self.n._meta[texto] = {
                "prioridade": aviso.prioridade,
                "titulo": aviso.titulo,
                "sessao": aviso.sessao,
                "detalhe": aviso.detalhe,
                "toque": bool(aviso.sessao),
            }
            self.n.eventos.put(e.Aviso(texto, sequencial=True))
            return
        self.n._meta[texto] = {"toque": True}
        self.n._oferta_ate = time.monotonic() + OFERTA_S
        self.n.eventos.put(e.Aviso(texto, escutar=True))

    def _antes_de_avisar(self, texto: str) -> None:
        """Começou a falar um aviso: o toque, se for de sessão, e a sessão dele em foco."""
        m = self.n._meta.get(texto, {})
        if m.get("toque"):
            self.n._tocar_som(self.n.toque)
        if m.get("sessao"):
            self.n._ultimo_de_sessao = m
            with contextlib.suppress(SessaoErro):
                self.n.sessoes.focar(str(m["sessao"]))

    def _proximo_aviso(self) -> str:
        """ "Começa" ou "próximo": o aviso que vem, e quantos ainda esperam."""
        fila: Fila | None = getattr(self.n, "fila", None)
        aviso = fila.proximo() if fila is not None else None
        if aviso is None:
            self.n._oferta_ate = 0.0
            return "Nenhum aviso esperando."
        if aviso.sessao:
            self.n._ultimo_de_sessao = {"sessao": aviso.sessao, "detalhe": aviso.detalhe}
            with contextlib.suppress(SessaoErro):
                self.n.sessoes.focar(aviso.sessao)
        resto = len(fila.validos()) if fila is not None else 0
        self.n._oferta_ate = time.monotonic() + OFERTA_S if resto else 0.0
        mais = {1: " Mais um.", 2: " Mais dois.", 3: " Mais três."}.get(resto, f" Mais {resto}.")
        return aviso.texto + (mais if resto else "")

    def _detalhe_do_aviso(self) -> str:
        """ "O que ela disse?": o que a sessão do último aviso respondeu, pronto para ouvir."""
        m = getattr(self.n, "_ultimo_de_sessao", None)
        if m and m.get("detalhe"):
            return str(m["detalhe"])
        return "Não tenho mais detalhe desse aviso; a resposta inteira está na sessão."

    def _regras_de_fala(self, aviso: e.Aviso) -> e.Aviso | None:
        """O que vira voz (ADR 0027): o mesmo aviso não se repete em 2 minutos (salvo a volta de
        um aviso cortado, uma vez), e aviso longo vira manchete, com o resto na tela."""
        agora = time.monotonic()
        self.n._avisos_dados = {
            t: q for t, q in self.n._avisos_dados.items() if agora - q < modo_fala.REPETIR_S
        }
        if len(self.n._comecados) > 50:
            self.n._comecados = {
                t: n for t, n in self.n._comecados.items() if t in self.n._cortados
            }
        texto = aviso.texto
        cortado = texto in self.n._cortados
        self.n._cortados.discard(texto)
        curto = modo_fala.manchete(texto)
        # Repetido é o que já foi falado há pouco (marcado quando a fala começa): um aviso que
        # esperou o Zé ficar livre não conta como dado.
        if not cortado and agora - self.n._avisos_dados.get(curto, -1e9) < modo_fala.REPETIR_S:
            log.info("aviso repetido em menos de 2 minutos: só na tela")
            return None
        if curto != texto:
            if texto not in self.n._na_tela:
                self.n._na_linha("aviso", texto)  # o texto inteiro fica na tela
            if texto in self.n._meta:
                self.n._meta[curto] = self.n._meta[texto]
            return e.Aviso(curto, escutar=aviso.escutar, sequencial=aviso.sequencial)
        return aviso

    def _pessoa_falando(self) -> bool:
        """A pessoa no meio de uma frase ou com o pedido ainda sendo transcrito."""
        return self.n.maquina.estado is e.Estado.OUVINDO and (
            self.n.segmentador.em_fala or self.n.transcrevendo is not None
        )

    def _aviso_ao_vivo(self) -> None:
        """Resultados saem na pausa da conversa, um por vez, sem exigir 'próximo'."""
        if (
            self.n.maquina.estado is e.Estado.OUVINDO
            and not self.n.maquina.segurando
            and not self.n._pessoa_falando()
            and (self.n.maquina.ao_vivo or any(aviso.sessao for aviso in self.n.fila.validos()))
        ):
            self.n._sair_da_fila()

    def _com_avisos(self, texto: str) -> str:
        """Os avisos falados nos últimos minutos vão junto do pedido, como contexto."""
        recentes = [a for t, a in self.n.avisos_falados if time.monotonic() - t < AVISO_RECENTE_S]
        self.n.avisos_falados = []
        if not recentes:
            return texto
        lista = " | ".join(recentes[-3:])
        return f"(Você acabou de avisar o usuário, por voz: {lista}) {texto}"
