"""Os efeitos da máquina de voz (abrir o microfone, falar, mandar ao cérebro, aprovar) e os
comandos locais, executados pelo núcleo. Funções do núcleo, tiradas de `laco.py`."""

import logging
import subprocess
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

from zervis import atividade
from zervis.automacoes.agenda import FUSO
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
from zervis.nucleo.apoio import FECHAR_NA_TELA, MOSTRAR_NA_TELA
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
from zervis.oficina.sessoes import SessaoErro
from zervis.voz.fala import falavel, para_fala
from zervis.voz.live import live_ativo

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.nucleo.laco")
# Depois da pergunta de permissão de uma sessão, quanto tempo o "sim" e o "não" valem para ela:
# a fala da pergunta e a escuta que vem depois (mãos livres), ou um "Ei Zé, sim" logo em seguida.
JANELA_PERMISSAO_S = 45.0

if TYPE_CHECKING:
    from zervis.nucleo.laco import Nucleo


def _executar(n: "Nucleo", efeito: e.Efeito) -> None:
    match efeito:
        case e.AbrirMicrofone():
            n.detector.reiniciar()
            n.vad.reiniciar()
            n.segmentador.limpar()
            n._fim_fala_em = None
            if not n.microfone_travado:  # Silencioso: o microfone fica fechado
                n.captura.abrir()
        case e.FecharMicrofone():
            n.captura.fechar()
            n.segmentador.limpar()
        case e.CortarFala():
            n.voz.parar()
            n.anel.parar()
            if (live := live_ativo(n)) is not None:
                live.parar()
        case e.Bip():
            n.status.ativacoes += 1
            n._tocar_bip()
        case e.FecharPedido():
            n._fechar_pelo_botao()
        case e.EnviarAoCerebro(texto):
            atividade.PADRAO.origem = n._origem()
            n._abrir_latencia("cerebro")
            n.marca += 1
            n.status.pedidos += 1
            n._pedido_em = time.monotonic()
            n._conversa_suja = True
            n.turnos.append({"pessoa": texto, "jarvis": ""})
            n._gastos_extras = []  # o que as ferramentas desta mensagem gastarem
            n._pedido_quando = datetime.now(FUSO)
            pedido = n._com_memoria(n._com_foco(n._com_avisos(n._com_nucleo(texto))))
            n._turno_cerebro = (n.marca, n._turno_atual)
            n.latencias.contexto(
                n._turno_atual,
                provedor=n.provedor,
                modelo=str(getattr(n.cerebro, "modelo", "") or ""),
            )
            n.latencias.marcar(n._turno_atual, "cerebro_enviado")
            n.ponte.perguntar(pedido, n.marca)
            n.motor_voz.aquecer()  # a conexão da voz abre enquanto o cérebro pensa
        case e.InterromperCerebro():
            n.marca += 1
            n.ponte.interromper()
        case e.Falar(texto):
            if (eco := getattr(n, "eco_texto", None)) is not None:
                eco.falou(texto)
            # O que foi dito por último, inteiro, para "repete": um aviso, ou as frases de
            # uma mesma resposta (a marca muda a cada pedido).
            if texto == n.maquina.aviso_falando:
                n._ultimo_dito, n._dito_marca = texto, None
            elif getattr(n, "_dito_marca", None) == n.marca:
                n._ultimo_dito = f"{n._ultimo_dito} {texto}"
            else:
                n._ultimo_dito, n._dito_marca = texto, n.marca
            if texto == n.maquina.aviso_falando:
                # O cérebro não ouve a própria voz: sem isto, "pode aprovar" depois de um
                # aviso chegava sem contexto (teste de 06/10/2026).
                contexto = n.avisos_lidos.get(texto, texto)
                n.avisos_falados.append((time.monotonic(), contexto))
                n._comecados[texto] = n._comecados.get(texto, 0) + 1
                n._avisos_dados[texto] = time.monotonic()  # falado: conta como dado
                n._antes_de_avisar(texto)
            perguntas = getattr(n, "_perguntas_permissao", {})
            if (alvo := perguntas.get(texto)) and texto.endswith("Aprovo?"):
                # A pergunta de uma sessão (ou ela repetida, "não entendi"): o "sim" e o
                # "não" logo depois a respondem, sem passar pelo cérebro (ADR 0039).
                n._permissao_falada = alvo
                n._permissao_ate = time.monotonic() + JANELA_PERMISSAO_S
            n.teclado.falou(texto)
            if texto == e.NAO_ENTENDI:
                n.evidencias.registrar("nao_entendi", n._ouvido)
                ouvido = f'Ouviu "{n._ouvido}"' if n._ouvido.strip() else "Não ouviu nada"
                atividade.PADRAO.registrar("nao_entendi", ouvido)
            turno = n._turno_atual
            if turno is not None:
                n.latencias.marcar(turno, "primeira_frase")
                n.latencias.marcar(turno, "sintese_pedida")
            tipo = "confirmacao" if n.maquina.estado is e.Estado.CONFIRMANDO else "resposta"

            def ao_iniciar(em: float) -> None:
                n.latencias.primeiro_som(turno, em, tipo)
                n.latencias.contexto(turno, voz_por=n.motor_voz.ultimo)

            falado = falavel(para_fala(texto))
            if (live := live_ativo(n)) is not None and not n.voz.muda:
                n.voz.numero += 1  # a mesma contagem: o aviso de ociosa vale para os dois
                n._ultima_fala = n.voz.numero
                live.falar(falado, n.voz.numero, ao_iniciar if turno else None)
            else:
                n._ultima_fala = n.voz.falar(falado, ao_iniciar=ao_iniciar if turno else None)
        case e.ResponderAprovacao(aprovado, fala):
            log.info("aprovação respondida: %s", "sim" if aprovado else "não")
            if not getattr(n.ponte, "aprovacao_pendente", True):
                # A pergunta já tinha expirado: o cérebro seguiu sem ela. Sem isto, o "sim"
                # atrasado deixava o Zé pensando para sempre, sem ouvir (14/10/2026).
                log.info("resposta depois de a pergunta expirar")
                n.eventos.put(e.Frase("Essa pergunta já tinha expirado. Peça de novo, por favor."))
                n.eventos.put(e.RespostaFim())
                return
            if aprovado and n.pergunta:
                n._na_linha("aprovado", n.pergunta)
            n.ponte.responder_aprovacao(aprovado, fala)
        case e.Comando(nome):
            atividade.PADRAO.origem = n._origem()
            atividade.PADRAO.registrar(
                "execucao", f"Comando local: {nome}", autorizacao="comando local"
            )
            n._abrir_latencia("comando")
            n._comando(nome)
        case e.ReterAviso(texto):
            if n._comecados.get(texto, 0) >= 2:
                # Já foi cortado uma vez e voltou: não lê pela terceira vez (ADR 0027).
                log.info("aviso cortado de novo: fica só na tela")
                return
            if n._comecados.get(texto):
                n._cortados.add(texto)  # a volta de um aviso cortado não é repetição
            # Fila durável (Fase 7): o aviso sai quando o Zé voltar a ATIVO.
            log.info("aviso retido até ficar ativo: %d caracteres", len(texto))
            n._guardar(texto)


def _comando(n: "Nucleo", nome: str) -> None:
    log.info("comando: %s", nome)
    n.consumo.somar_local()
    n.marca += 1  # o que ainda vier do cérebro é de um pedido anterior
    base, _, argumento = nome.partition(":")
    if base in AJUSTES_DA_TELA:
        pedido, resposta = AJUSTES_DA_TELA[base]
        n.hud.pedir_maos(pedido)
    elif base in MOSTRAR_NA_TELA:
        acoes, pronto = MOSTRAR_NA_TELA[base]
        if base == "foco_mostrar":
            pronto = n.foco.fala_do_quadro()
        resposta = n._no_nucleo(com_argumento(acoes, argumento), pronto.format(argumento))
    elif base in FECHAR_NA_TELA:
        acoes, pronto = FECHAR_NA_TELA[base]
        resposta = n._se_aberto(com_argumento(acoes, argumento), pronto)
    elif base in EM_SEGUNDO_PLANO:
        # Falam com a sessão de manutenção ou rodam os testes: a resposta sai quando terminar.
        threading.Thread(target=n._responder_depois, args=(base, argumento), daemon=True).start()
        return
    elif base == "abrir_item":
        # A busca no Núcleo responde se achou: a fala espera a página (uma fração de segundo).
        threading.Thread(target=n._abrir_item, args=(argumento,), daemon=True).start()
        return
    else:
        resposta = n._comando_especial(base, argumento)
    n.eventos.put(e.Frase(resposta))
    n.eventos.put(e.RespostaFim())


def _responder_depois(n: "Nucleo", nome: str, argumento: str) -> None:
    m = n.manutencao
    try:
        if nome == "manutencao_entrar":
            resposta = m.entrar(argumento)
        elif nome == "rodada_melhoria":
            resposta = n._rodada_de_melhoria()
        elif not n._no_proprio_pc():
            # Reiniciar e aplicar mudam o Zé em uso: nunca de outro aparelho (ADR 0028).
            resposta = "Aplique no computador."
        # Pela voz, nunca com "eu revisei": a zona protegida só se aplica no painel, no PC,
        # com a revisão marcada (docs/essencia.md, item 7).
        elif m.mudancas().get("commits"):  # reiniciar: há melhorias na cópia, aplica
            resposta = n.aplicar_melhorias(revisado=False)
        else:  # reiniciar
            _, resposta = m.reiniciar(revisado=False)
    except (SessaoErro, OSError, subprocess.SubprocessError) as erro:
        log.warning("manutenção: %s", erro)
        resposta = "Não consegui falar com a sessão de manutenção agora."
    n.eventos.put(e.Frase(resposta))
    n.eventos.put(e.RespostaFim())
