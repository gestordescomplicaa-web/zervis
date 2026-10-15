"""Serviço de foco; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import logging
import queue
import random
import threading
import time
from typing import Any, Protocol

from jarvis.cerebro.base import Ponte
from jarvis.foco import tela as foco_tela
from jarvis.foco.frentes import Foco, Frente
from jarvis.habilidades import evidencias
from jarvis.nucleo import estados as e
from jarvis.nucleo.apoio import FALAS_DA_VOLTINHA, FALAS_DE_TONTO
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.sessoes import FOCO_S, SessaoErro, Sessoes
from jarvis.rosto import hud, tela

log = logging.getLogger(__name__)


class ContextoFoco(Protocol):
    _aplicar_depois: bool | None
    _evento_visto: Any
    _foco_acoes: Any
    _foco_lido: Any
    _oferta_ate: Any
    eventos: queue.Queue[e.Evento]
    evidencias: evidencias.Evidencias
    foco: Foco
    hud: hud.Hud
    manutencao: Manutencao
    maquina: e.Maquina
    ponte: Ponte
    sessoes: Sessoes
    tela: tela.Tela
    ultimo_na_tela: list[float | str] | None

    def _detalhe_do_aviso(self) -> str: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...
    def _no_nucleo(self, acoes: list[dict[str, Any]], pronto: str = "Está no Núcleo.") -> str: ...
    def _proximo_aviso(self) -> str: ...
    def ligar_mensagens(self, ativo: bool) -> str: ...
    def mudar_modo_fala(self, modo: str) -> str: ...
    def relatorio_de_baterias(self) -> str: ...
    def trocar_cerebro(self, id_: str) -> str: ...


class ServicoFoco:
    def __init__(self, contexto: ContextoFoco) -> None:
        self.n = contexto

    def _foco_mudou(self, o_que: str, frente: Frente) -> None:
        """Cada mudança de frente na linha do tempo; concluir é festa na tela."""
        self.n._na_linha("foco", f"{o_que}: {frente.titulo}")
        if o_que == "concluida" and self.n.tela.aberto():
            self.n.tela.enviar(
                [{"acao": "expressao", "valor": "alegria", "segundos": 5}, {"acao": "girar"}]
            )

    def _mostrar(self, texto: str) -> None:
        """O que não foi falado (Silencioso) aparece no painel, em qualquer página."""
        self.n.ultimo_na_tela = [time.time(), texto[:200]]

    def _foco_na_tela(self, agora: float) -> None:
        """Publica o quadro do Foco e aplica o que o usuário marcou nele (o "V")."""
        acoes, self.n._foco_lido = foco_tela.ler_acoes(self.n._foco_acoes, self.n._foco_lido)
        for acao in acoes:
            fala = foco_tela.aplicar(self.n.foco, acao)
            log.info("foco na tela: %s %s", acao.get("acao"), acao.get("id"))
            self.n.eventos.put(e.Aviso(fala))
        self.n.hud.gravar("foco", self.n.foco.quadro(), agora)

    def _evento_da_tela(self) -> None:
        """O que aconteceu na página e pede fala (o Zé ficou tonto): uma vez, se estiver livre."""
        evento = tela.evento_novo(self.n.tela.estado_bruto(), self.n._evento_visto, time.time())
        if evento is None:
            return
        self.n._evento_visto = str(evento["id"])
        if evento.get("tipo") == "tonto" and self.n.maquina.estado is e.Estado.ATIVO:
            log.info("tela: o Zé ficou tonto")
            self.n.eventos.put(e.Aviso(random.choice(FALAS_DE_TONTO)))  # noqa: S311 (só variar a fala)

    def _abrir_item(self, argumento: str) -> None:
        """ "abre o burrinho no Acervo": acha pelo nome falado (num orbe ou em todos) e diz."""
        orbe, _, nome = argumento.partition(":")
        acao: dict[str, Any] = {"acao": "abrir", "alvo": nome, **({"orbe": orbe} if orbe else {})}
        try:
            if not self.n.tela.aberto():
                self.n.tela.abrir()
            r = self.n.tela.agir([acao])
            feito = (r.get("resultados") or [{}])[0]
            if feito.get("ok"):
                resposta = f"{feito.get('abriu', nome).capitalize()} na tela."
            else:
                resposta = f"Não achei {nome}" + (f" no {orbe}." if orbe else " no Núcleo.")
                self.n.evidencias.registrar("nao_achei", f"{orbe or 'Núcleo'}: {nome}")
        except (tela.TelaErro, OSError):
            resposta = "Não consegui abrir; a minha tela não respondeu."
        self.n.eventos.put(e.Frase(resposta))
        self.n.eventos.put(e.RespostaFim())

    def _comando_especial(self, nome: str, argumento: str) -> str:
        """Os comandos que fazem mais do que mexer na tela."""
        if nome == "foco_onde":
            return self.n.foco.onde_estava()
        if nome == "foco_pendentes":
            return self.n.foco.falar_pendentes()
        if nome == "avatar_voltinha":
            return self.n._no_nucleo(
                [{"acao": "expressao", "valor": "alegria", "segundos": 4}, {"acao": "girar"}],
                random.choice(FALAS_DA_VOLTINHA),  # noqa: S311 (só variar a fala)
            )
        if nome == "nova_conversa":
            self.n.ponte.reiniciar()
            return "Certo, começando uma conversa nova."
        if nome == "mostrar_mapa":
            self.n.hud.abrir_mapa()
            return self.n._no_nucleo([])
        if nome == "janela_fechar":
            threading.Thread(target=self.n.tela.fechar, daemon=True).start()
            return "Fechei a minha janela; a câmera apagou."
        if nome == "trocar":
            return self.n.trocar_cerebro(argumento)
        if nome in ("modo_silencioso", "modo_avisos", "modo_maos_livres"):
            return self.n.mudar_modo_fala(nome.removeprefix("modo_"))
        if nome == "avisos_proximo":
            return self.n._proximo_aviso()
        if nome == "avisos_depois":
            self.n._oferta_ate = 0.0
            return "Certo. Ficam na Conversa."
        if nome == "aviso_detalhe":
            return self.n._detalhe_do_aviso()
        if nome == "repetir":
            return getattr(self.n, "_ultimo_dito", "") or "Ainda não falei nada."
        if nome == "manutencao_sair":
            self.n._aplicar_depois = None
            return self.n.manutencao.sair()
        if nome == "manutencao_situacao":
            return self.n.manutencao.situacao(time.time())
        if nome in ("whatsapp_liga", "whatsapp_desliga"):
            return self.n.ligar_mensagens(nome == "whatsapp_liga")
        return self.n.relatorio_de_baterias()

    def _se_aberto(self, acoes: list[dict[str, Any]], pronto: str) -> str:
        """Fecha ou recolhe algo na tela; com a janela fechada, não há o que fechar."""
        if not self.n.tela.aberto():
            return "A minha janela já está fechada."
        self.n.tela.enviar(acoes)
        return pronto

    def _no_nucleo(self, acoes: list[dict[str, Any]], pronto: str = "Está no Núcleo.") -> str:
        """Mostra algo no Núcleo sem o cérebro: traz a janela, ou abre a janela se fechada."""
        if self.n.tela.aberto():
            if acoes:
                self.n.tela.enviar(acoes)
            threading.Thread(target=self.n.tela.trazer, daemon=True).start()
            return pronto

        def abrir_e_mostrar() -> None:
            self.n.tela.abrir()
            if acoes:
                self.n.tela.enviar(acoes)

        threading.Thread(target=abrir_e_mostrar, daemon=True).start()
        return "Abrindo a minha janela."

    def _com_foco(self, texto: str) -> str:
        """A sessão de código de que se fala agora vai junto do pedido: "diz pra ela" é ela."""
        id_, quando = self.n.sessoes.em_foco
        if not id_ or time.time() - quando > FOCO_S:
            return texto
        try:
            s = self.n.sessoes.ler(id_)
        except SessaoErro:
            return texto
        return f"(Sessão em foco: {s.nome}, {s.estado}.) {texto}"
