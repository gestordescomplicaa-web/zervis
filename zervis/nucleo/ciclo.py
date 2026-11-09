"""O laço principal do núcleo: subir as peças, cada volta (eventos, microfone, anel) e, uma
vez por segundo, o status, o painel, a decisão na tela e a vigia das fontes. Funções do
núcleo, tiradas de `laco.py`."""

import contextlib
import logging
import os
import queue
import threading
import time
from typing import TYPE_CHECKING

from zervis.atendimento import whatsapp
from zervis.avisos import mensagens
from zervis.cerebro.baterias import do_omniroute
from zervis.cerebro.claude import ClaudeBrain
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import AJUSTES_DA_TELA as AJUSTES_DA_TELA
from zervis.nucleo.apoio import AVISO_RECENTE_S as AVISO_RECENTE_S
from zervis.nucleo.apoio import BATERIAS_S as BATERIAS_S
from zervis.nucleo.apoio import CHAMADOS_GUARDADOS as CHAMADOS_GUARDADOS
from zervis.nucleo.apoio import CURADORIA_S as CURADORIA_S
from zervis.nucleo.apoio import DADOS as DADOS
from zervis.nucleo.apoio import EM_SEGUNDO_PLANO as EM_SEGUNDO_PLANO
from zervis.nucleo.apoio import ESTADO as ESTADO
from zervis.nucleo.apoio import FALAS_DA_VOLTINHA as FALAS_DA_VOLTINHA
from zervis.nucleo.apoio import FALAS_DE_TONTO as FALAS_DE_TONTO
from zervis.nucleo.apoio import FALHA_NO_CEREBRO as FALHA_NO_CEREBRO
from zervis.nucleo.apoio import JANELA_FALADA as JANELA_FALADA
from zervis.nucleo.apoio import LIMITE_ESCRITO as LIMITE_ESCRITO
from zervis.nucleo.apoio import OFERTA_S as OFERTA_S
from zervis.nucleo.apoio import PASTA_S as PASTA_S
from zervis.nucleo.apoio import PERSONA as PERSONA
from zervis.nucleo.apoio import PERSONA_RAPIDA as PERSONA_RAPIDA
from zervis.nucleo.apoio import PRIMEIRA_FALA_S as PRIMEIRA_FALA_S
from zervis.nucleo.apoio import VENDO_S as VENDO_S
from zervis.nucleo.apoio import Status as Status
from zervis.nucleo.apoio import com_argumento as com_argumento
from zervis.nucleo.apoio import criar_bip as criar_bip
from zervis.nucleo.apoio import criar_toque as criar_toque
from zervis.nucleo.apoio import foto_da_memoria as foto_da_memoria
from zervis.nucleo.apoio import gravar_json as gravar_json
from zervis.nucleo.apoio import ler_json as ler_json
from zervis.nucleo.apoio import nivel_de_pico as nivel_de_pico
from zervis.nucleo.apoio import primeiro_de as primeiro_de
from zervis.nucleo.apoio import versoes_das_skills as versoes_das_skills
from zervis.nucleo.efeitos import JANELA_PERMISSAO_S as JANELA_PERMISSAO_S
from zervis.portal import tunel
from zervis.rosto import hud
from zervis.sistema import maquina as maquina_atual

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.nucleo.laco")
VIGIA_ESPERA_S = 600.0  # a primeira checagem das fontes, depois de o Zé assentar

if TYPE_CHECKING:
    from zervis.nucleo.laco import Nucleo


def _atualizar_painel(n: "Nucleo", agora: float) -> None:
    completo = getattr(n.cerebro, "completo", n.cerebro)
    completo = getattr(completo, "cerebro_ativo", completo)
    if (
        isinstance(completo, ClaudeBrain)
        and completo.assinatura
        and completo.limite
        and completo.limite != n.limite_claude
    ):
        n.limite_claude = dict(completo.limite)
        with contextlib.suppress(OSError):
            gravar_json(ESTADO / "limite_claude.json", n.limite_claude)
    if agora - n._baterias_em >= BATERIAS_S:
        n._baterias_em = agora
        n.baterias_omniroute = do_omniroute(n.cfg.caminho("cerebro", "omniroute_banco"), agora)
    if (escolha := n.painel.escolha(agora)) is not None:
        log.info("troca pedida no Barehands: %s", escolha)
        n.trocar_cerebro(escolha)
    n.painel.mostrar(n.provedor, n.baterias(), n.modelos(), agora)
    n.painel.autoconhecimento(n.autoconhecimento, agora)
    n._mostrar_decisao(agora)


def _mostrar_decisao(n: "Nucleo", agora: float) -> None:
    """O card do Barehands: a pergunta que espera o "sim" e o prazo (só depois de falada)."""
    pergunta, expira = None, None
    if n.maquina.estado is e.Estado.CONFIRMANDO:
        pergunta = n.pergunta
        if not n.maquina.pergunta_falando:
            expira = round(agora + n.maquina.prazo - time.monotonic())
    n.hud.gravar("decisao", hud.decisao(pergunta, expira, n.pendencias), agora)


def _gravar_status(n: "Nucleo", agora: float) -> None:
    n.hud.gravar(
        "presenca",
        {
            "batimento": agora,
            "estado": n.maquina.estado.value,
            "microfone_aberto": n.captura.aberta,
        },
        agora,
    )
    gravar_json(
        ESTADO / "status.json",
        {
            "pid": os.getpid(),
            "batimento": agora,
            "estado": n.maquina.estado.value,
            "microfone_aberto": n.captura.aberta,
            "provedor": n.provedor,
            "ativacoes": n.status.ativacoes,
            "pedidos": n.status.pedidos,
            "transcricao_por": n.status.meio_transcricao,
            "modelo": getattr(n.cerebro, "modelo", None),
            "limite_assinatura": n.limite_claude,
            "consumo_hoje": n.consumo.hoje,
            "ultimo_erro": n.status.ultimo_erro,
            "tempos": {**n.status.tempos, "primeira_fala_s": n.voz.primeira_fala_s},
            "engasgos_de_voz": n.voz.engasgos,
            "erro_de_voz": n.voz.ultimo_erro,
            "latencia": {
                "ultimo_turno": n.latencias.ultimo,
                "descartados": n.latencias.descartados,
                "erro_gravacao": n.latencias.erro,
            },
        },
    )


def rodar(n: "Nucleo") -> None:
    if not n.live.preparar():
        log.info("Live indisponível (%s): a voz ao vivo usa o recorte de sempre", n.live.erro)
    n.memoria_longa.iniciar()
    n._avisar_interrompidas()
    n._retomar_execucoes()
    n._ligar_voz_remota()
    if tunel.escolhido():  # o acesso de qualquer lugar continua depois de um reinício
        # O convite do primeiro acesso (servidor) abre o túnel antes da senha existir: é por
        # ele que a pessoa chega para criá-la (`python -m zervis.portal.primeiro_acesso`).
        # Num servidor, a senha basta para manter o endereço: sem ele, quem ainda não ligou o
        # código do autenticador ficaria trancado fora depois de um reinício.
        servidor = maquina_atual.detectar().servidor
        pronto = n.acesso.tem_senha and (n.acesso.tem_codigo or servidor)
        if pronto or n.acesso.convite_valido:
            threading.Thread(target=n._subir_tunel, name="tunel", daemon=True).start()
        else:
            log.warning("túnel não sobe: falta a senha ou o código do autenticador")
    if whatsapp.escolhido():
        threading.Thread(target=n._subir_central, name="central", daemon=True).start()
    if mensagens.escolhido() and (mensagens.disponivel() or whatsapp.escolhido()):
        n.mensagens.iniciar()
    n.imersivo.iniciar()
    n.buscador.preparar_em_segundo_plano()  # só baixa na primeira vez (ou numa versão nova)
    if n.presenca is not None:
        n.presenca.start()
    n.rostos.marcar("sempre", n.modo_escuta == "sempre")
    proximo_status = 0.0
    try:
        while not n.parar.is_set():
            agora = time.time()
            if n.transcrevendo is not None and n.transcrevendo.done():
                n.transcrevendo = None
                n.segmentador.limpar()
            n._ler_teclado()
            while True:
                try:
                    n.tratar(n.eventos.get_nowait())
                except queue.Empty:
                    break
            n.tratar(e.Tempo())
            humor = "red" if agora - n.status.erro_em < 30 else "green"
            if humor == "green" and n.manutencao.ligado:
                humor = "amber"  # o anel diz que os pedidos vão para a sessão de código
            n.anel.mostrar(n.maquina.anel, humor, agora)
            if agora >= proximo_status:
                n._gravar_status(agora)
                n._atualizar_painel(agora)
                n._conversa_parada()
                n._aviso_ao_vivo()
                n._agendador(agora)
                n._lembrar_leads()
                n._vigiar_fontes()
                n._atualizar_pasta(agora)
                n._manutencao_chegou(agora)
                n._aplicar_quando_livre()
                n._evento_da_tela()
                n._foco_na_tela(agora)
                n._nota_do_dia(agora)
                proximo_status = agora + 1
            if not n.captura.aberta:
                # Inativo: sem microfone, o laço só espera eventos (CPU parada).
                with contextlib.suppress(queue.Empty):
                    n.tratar(n.eventos.get(timeout=0.5))
                continue
            try:
                n._quadro(n.captura.quadros.get(timeout=0.1))
            except queue.Empty:
                continue
    finally:
        n.desligar()


def _vigiar_fontes(n: "Nucleo") -> None:
    """Uma vez por semana, as fontes de fora testadas de verdade; o Zé fala só o que mudou
    (ADR 0059). Espera o Zé assentar (e o buscador se preparar) antes da primeira rodada."""
    if (
        n.fontes_de_fora.rodando
        or n.buscador.preparando
        or time.monotonic() - n._vigia_desde < VIGIA_ESPERA_S
        or not n.fontes_de_fora.vencido()
    ):
        return
    n.fontes_de_fora.rodando = True

    def vigiar() -> None:
        try:
            fala = n.fontes_de_fora.checar_e_contar()
        except Exception:
            log.exception("vigia das fontes falhou")
            n.fontes_de_fora.rodando = False
            return
        if fala:
            log.warning("fontes: %s", fala)
            n.eventos.put(e.Aviso(f"Sobre as fontes de fora que eu uso: {fala}"))

    threading.Thread(target=vigiar, name="vigia-fontes", daemon=True).start()
