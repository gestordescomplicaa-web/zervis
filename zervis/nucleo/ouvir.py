"""Cada evento da voz e cada quadro do microfone: a máquina decide, o núcleo faz; o pedido do
Ao vivo e a fala perdida. Funções do núcleo, tiradas de `laco.py`."""

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from zervis import atividade
from zervis.avisos import modo as modo_fala
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
from zervis.voz.live import live_ativo

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.nucleo.laco")
# Voz ouvida e descartada enquanto o Zé pensa (ao vivo): acima do ruído de fundo, e só conta
# quando passa de meio segundo, para um estalo ou uma tosse não virar aviso.
FALA_PERDIDA_DBFS = -35.0
FALA_PERDIDA_MIN_S = 0.5

if TYPE_CHECKING:
    from zervis.nucleo.laco import Nucleo


def tratar(n: "Nucleo", evento: e.Evento) -> None:
    silencioso = modo_fala.efetivo(n) == "silencioso"
    if isinstance(evento, e.Aviso) and silencioso and not evento.pedido:
        log.info("modo silencioso: aviso só na tela (%d caracteres)", len(evento.texto))
        n._mostrar(evento.texto)
        return
    abertura = getattr(n, "abertura", None)
    if isinstance(evento, e.Aviso) and not evento.pedido and abertura and abertura.rodando():
        n._guardar(evento.texto)  # a entrada do programa não é atropelada: sai depois dela
        return
    # Pedido para ouvir (a abertura, o "Ouvir" do celular): sai mesmo com a voz muda.
    pedidas = getattr(n, "ouvir_mesmo_muda", None)
    if isinstance(evento, e.Aviso) and evento.pedido and pedidas is not None:
        pedidas.add(evento.texto)
    if isinstance(evento, e.Aviso):
        permitido = n._regras_de_fala(evento)
        if permitido is None:
            return
        evento = permitido
    if isinstance(evento, e.Aviso) and n._pessoa_falando():
        n._guardar(evento.texto)  # ao vivo: o aviso espera a pausa, não atropela
        return
    eco = getattr(n, "eco_texto", None)
    if isinstance(evento, e.FimDeFala | e.FalaAoVivo) and eco is not None and eco.eco(evento.texto):
        # A própria fala do Zé voltou pelo microfone, transcrita (ADR 0062): não é pedido.
        log.info("eco: a própria fala voltou transcrita (%d caracteres)", len(evento.texto))
        return
    if isinstance(evento, e.FalaAoVivo):
        n._pedido_ao_vivo(evento)
    antes = n.maquina.estado
    agora = time.monotonic()
    n._digitado_em = (
        agora if isinstance(evento, e.Digitado) and antes is not e.Estado.CONFIRMANDO else None
    )
    if isinstance(evento, e.Ativacao) and n.maquina.detector_ligado:
        n._fechar_latencia("interrompido")
        n._fim_fala_em = None
    if isinstance(evento, e.Presenca) and not evento.ativo:
        n._fechar_latencia("janela_fechada")
    if isinstance(evento, e.RespostaFim) or (
        isinstance(evento, (e.Ativacao, e.FimDeFala)) and antes is not e.Estado.CONFIRMANDO
    ):
        n.teclado.terminou()  # a resposta escrita acabou, ou começou um pedido por voz
    tempo_real = live_ativo(n) is not None and not isinstance(evento, e.AoVivo)
    for efeito in n.maquina.tratar(evento, agora):
        if tempo_real and isinstance(efeito, e.Bip):
            # No Live a conversa é contínua, como numa ligação: o bipe de "sua vez" (depois de
            # um aviso, de uma pergunta, do chamado sozinho) só atrapalha. Fica o de conectar.
            continue
        n._executar(efeito)
    n._digitado_em = None
    if (live := live_ativo(n)) is not None:
        # A resposta acabou (o cérebro terminou, a pergunta de confirmação saiu ou o pedido não
        # deu em nada): a vez fecha e o Live volta a ouvir.
        m = n.maquina
        acabou = m.cerebro_terminou or m.estado not in (e.Estado.PENSANDO, e.Estado.FALANDO)
        live.acompanhar(acabou, n._pedidos_ao_vivo)
    depois = n.maquina.estado
    if depois is not antes and depois in (e.Estado.ATIVO, e.Estado.OUVINDO) and n._turno_atual:
        # Também registra "ok" e transcrição vazia, sem tratá-los como resposta simples.
        n._fechar_latencia(
            "controle"
            if antes is e.Estado.OUVINDO
            else "erro_voz"
            if n.voz.ultimo_erro
            else "concluido"
        )
    if depois is not antes:
        log.info("%s -> %s", antes.value, depois.value)
        if depois is e.Estado.FALANDO and antes is e.Estado.PENSANDO:
            n.status.tempos["ate_primeira_frase_s"] = round(time.monotonic() - n._pedido_em, 2)
        if depois is e.Estado.ATIVO and antes is e.Estado.INATIVO:
            n._bom_dia()
        if antes is e.Estado.PENSANDO:
            n._relatar_fala_perdida()
        if depois is e.Estado.PENSANDO:
            n._fala_perdida_s = 0.0
        if depois is e.Estado.ATIVO:
            n.detector.reiniciar()
            if not n.maquina.em_conversa:
                n._fim_da_conversa()
            n._sair_da_fila()
        if n._pausar_midia():
            n._dar_a_vez(antes, depois)
        if depois is e.Estado.OUVINDO and antes is not e.Estado.OUVINDO:
            n._ouvindo_desde, n._ouviu_voz = time.monotonic(), False
        if depois is e.Estado.OUVINDO and antes is e.Estado.FALANDO:
            n._descartar_escuta()  # conversa contínua: próxima pergunta sem "Ei Zé"


def _pedido_ao_vivo(n: "Nucleo", evento: e.FalaAoVivo) -> None:
    """Uma fala pelo Live: as latências do pedido (fim da fala, fim da vez, transcrito) e o
    registro do que foi ouvido, como no recorte de sempre (`_pedido_fechado`, `_transcrito`)."""
    n._pedidos_ao_vivo += 1
    if n.maquina.estado is e.Estado.OUVINDO:  # um pedido, não a resposta a uma pergunta
        n._fechar_latencia("interrompido")
        turno = n.latencias.iniciar("voz", evento.fim_fala_em)
        n._turno_atual = turno
        n.latencias.marcar(turno, "fim_fala", evento.fim_fala_em)
        n.latencias.marcar(turno, "pedido_fechado", evento.fechado_em)
        n.latencias.marcar(turno, "transcrito", evento.fechado_em)
        n.latencias.contexto(turno, fim_por="live", transcricao_por="deepgram")
    n.status.meio_transcricao = "live"
    if n.cfg["escuta"]["registrar_texto"]:
        log.info("transcrição (diagnóstico, live): %r", evento.texto)
    n._ouvido = evento.texto


def _relatar_fala_perdida(n: "Nucleo") -> None:
    """Ao vivo, o que a pessoa diz enquanto o Zé pensa não é ouvido (só o "Ei Zé" interrompe).
    Com o Codex o pensamento leva segundos, e isso parecia "surdez" (VPS, 16/10/2026): agora
    o registro e a Atividade dizem quanto foi perdido."""
    perdida, n._fala_perdida_s = n._fala_perdida_s, 0.0
    if perdida < FALA_PERDIDA_MIN_S:
        return
    log.info("fala perdida: %.1f s de voz enquanto o Zé pensava", perdida)
    atividade.PADRAO.registrar(
        "falha",
        "Fala não ouvida enquanto o Zé pensava",
        origem="voz",
        erro=f'{perdida:.0f} s de voz; espere a resposta ou diga "Ei Zé" para interromper',
    )


def _quadro(n: "Nucleo", dados: bytes) -> None:
    if n.maquina.transcrevendo:
        if n.transcrevendo is not None:
            return  # um pedido por vez; o que vier durante a transcrição é descartado
        if n.escuta is None and n.deepgram is not None and n.deepgram.disponivel:
            n.escuta = n.deepgram.nova()  # só agora o áudio começa a sair da máquina
        if n.escuta is not None:
            n.escuta.enviar(dados)
        amostras = np.frombuffer(dados, dtype="<i2")
        voz = n.vad.prever(amostras) >= n.cfg["escuta"]["limiar_vad"]
        if voz:
            n._fim_fala_em = time.monotonic()
            n._ouviu_voz = True
        n.segmentador.segurando = n.maquina.segurando
        trecho = n.segmentador.quadro(dados, voz)
        if trecho is not None:
            n._pedido_fechado(trecho)
        elif (
            n.maquina.estado is e.Estado.OUVINDO
            and not n.segmentador.em_fala
            and (time.monotonic() > n.maquina.prazo or n._ninguem_falou())
        ):
            n.tratar(e.Silencio())
    else:
        n._fechar_escuta()
        if n.maquina.ao_vivo and n.maquina.estado is e.Estado.PENSANDO:
            amostras = np.frombuffer(dados, dtype="<i2").astype(np.float64)
            rms = float(np.sqrt((amostras**2).mean())) if len(amostras) else 0.0
            if 20 * np.log10(rms / 32768 + 1e-12) > FALA_PERDIDA_DBFS:
                n._fala_perdida_s += len(dados) / 32000  # 80 ms por quadro
        n._antes_do_chamado.append(dados)
        if n.maquina.detector_ligado and n.detector.processar(np.frombuffer(dados, dtype="<i2")):
            nivel = nivel_de_pico(b"".join(n._antes_do_chamado))
            minimo = float(n.cfg["ativacao"].get("nivel_minimo_dbfs", -45.0))
            n._guardar_chamado(nivel < minimo)
            if nivel < minimo:
                log.info(
                    "chamado ignorado: baixo demais (nota %.3f, %.0f dBFS)",
                    n.detector.nota_disparo,
                    nivel,
                )
                return
            log.info("ativação (nota %.3f, %.0f dBFS)", n.detector.nota_disparo, nivel)
            n.tratar(e.Ativacao())
