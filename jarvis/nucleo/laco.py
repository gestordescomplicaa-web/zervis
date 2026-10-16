"""Laço do núcleo: liga microfone, detector, escuta, cérebro, voz e anel à máquina de estados.

Uma thread só trata eventos e quadros; o resto (presença, cérebro, voz, transcrição) roda em
threads próprias e fala com ela por uma fila de eventos. Os quadros do microfone chegam por
uma fila curta: se o laço atrasar, os mais velhos caem, mas o laço nunca espera rede.
"""

import collections
import concurrent.futures
import contextlib
import logging
import os
import queue
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from jarvis import atividade
from jarvis.atendimento import agente, cliente, projeto, whatsapp
from jarvis.atendimento import ferramentas as atendente_ferramentas
from jarvis.automacoes.agenda import FUSO
from jarvis.automacoes.calendario import Calendario
from jarvis.automacoes.jobs import Jobs
from jarvis.avisos import mensagens
from jarvis.avisos import modo as modo_fala
from jarvis.avisos.fila import Fila
from jarvis.cerebro import acesso, catalogo, ferramentas, mcp_externo, navegador, omniroute
from jarvis.cerebro.base import Ponte
from jarvis.cerebro.baterias import Bateria, do_omniroute
from jarvis.cerebro.claude import ClaudeBrain
from jarvis.cerebro.consumo import Consumo, UsoDeFerramentas
from jarvis.cerebro.ferramentas import sessoes as ferramentas_sessoes
from jarvis.config import Config
from jarvis.foco import ferramentas as foco_ferramentas
from jarvis.foco.frentes import Foco
from jarvis.habilidades import evidencias, revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import Skills
from jarvis.imersivo import Imersivo
from jarvis.memoria import tempo
from jarvis.memoria.aimemory import AiMemory
from jarvis.memoria.conversas import Conversas
from jarvis.memoria.curta import Memoria
from jarvis.memoria.dias import Dias
from jarvis.memoria.linha import LinhaDoTempo
from jarvis.nucleo import estados as e
from jarvis.nucleo.apoio import AJUSTES_DA_TELA as AJUSTES_DA_TELA
from jarvis.nucleo.apoio import AVISO_RECENTE_S as AVISO_RECENTE_S
from jarvis.nucleo.apoio import BATERIAS_S as BATERIAS_S
from jarvis.nucleo.apoio import CHAMADOS_GUARDADOS as CHAMADOS_GUARDADOS
from jarvis.nucleo.apoio import CURADORIA_S as CURADORIA_S
from jarvis.nucleo.apoio import DADOS as DADOS
from jarvis.nucleo.apoio import EM_SEGUNDO_PLANO as EM_SEGUNDO_PLANO
from jarvis.nucleo.apoio import ESTADO as ESTADO
from jarvis.nucleo.apoio import FALAS_DA_VOLTINHA as FALAS_DA_VOLTINHA
from jarvis.nucleo.apoio import FALAS_DE_TONTO as FALAS_DE_TONTO
from jarvis.nucleo.apoio import FALHA_NO_CEREBRO as FALHA_NO_CEREBRO
from jarvis.nucleo.apoio import JANELA_FALADA as JANELA_FALADA
from jarvis.nucleo.apoio import LIMITE_ESCRITO as LIMITE_ESCRITO
from jarvis.nucleo.apoio import OFERTA_S as OFERTA_S
from jarvis.nucleo.apoio import PASTA_S as PASTA_S
from jarvis.nucleo.apoio import PERSONA as PERSONA
from jarvis.nucleo.apoio import PERSONA_RAPIDA as PERSONA_RAPIDA
from jarvis.nucleo.apoio import PRIMEIRA_FALA_S as PRIMEIRA_FALA_S
from jarvis.nucleo.apoio import VENDO_S as VENDO_S
from jarvis.nucleo.apoio import Status as Status
from jarvis.nucleo.apoio import com_argumento as com_argumento
from jarvis.nucleo.apoio import criar_bip as criar_bip
from jarvis.nucleo.apoio import criar_toque as criar_toque
from jarvis.nucleo.apoio import foto_da_memoria as foto_da_memoria
from jarvis.nucleo.apoio import gravar_json as gravar_json
from jarvis.nucleo.apoio import ler_json as ler_json
from jarvis.nucleo.apoio import nivel_de_pico as nivel_de_pico
from jarvis.nucleo.apoio import primeiro_de as primeiro_de
from jarvis.nucleo.apoio import versoes_das_skills as versoes_das_skills
from jarvis.nucleo.servicos.atendimento import ServicoAtendimento
from jarvis.nucleo.servicos.automacoes import ServicoAutomacoes
from jarvis.nucleo.servicos.avisos import ServicoAvisos
from jarvis.nucleo.servicos.cerebro import ServicoCerebro
from jarvis.nucleo.servicos.foco import ServicoFoco
from jarvis.nucleo.servicos.interface import servico
from jarvis.nucleo.servicos.interface_atendimento import InterfaceAtendimento
from jarvis.nucleo.servicos.interface_automacoes import InterfaceAutomacoes
from jarvis.nucleo.servicos.interface_avisos import InterfaceAvisos
from jarvis.nucleo.servicos.interface_cerebro import InterfaceCerebro
from jarvis.nucleo.servicos.interface_foco import InterfaceFoco
from jarvis.nucleo.servicos.interface_memoria import InterfaceMemoria
from jarvis.nucleo.servicos.interface_oficina import InterfaceOficina
from jarvis.nucleo.servicos.interface_remoto import InterfaceRemoto
from jarvis.nucleo.servicos.interface_voz import InterfaceVoz
from jarvis.nucleo.servicos.memoria import ServicoMemoria
from jarvis.nucleo.servicos.oficina import ServicoOficina
from jarvis.nucleo.servicos.remoto import ServicoRemoto
from jarvis.nucleo.servicos.voz import ServicoVoz
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.progresso import Progresso
from jarvis.oficina.sessoes import SessaoErro, Sessoes
from jarvis.portal import senha, tunel
from jarvis.portal.acoes import Acoes
from jarvis.portal.senha import Acesso
from jarvis.portal.servidor import Portal
from jarvis.presenca import hyprland
from jarvis.presenca import modo as modo_escuta
from jarvis.presenca.hyprland import MonitorPresenca
from jarvis.presenca.rostos import Rostos
from jarvis.rosto import hud, manifesto, pasta, tela
from jarvis.rosto.anel import Anel
from jarvis.rosto.painel import Painel
from jarvis.rosto.quadro import Quadro
from jarvis.rosto.teclado import Teclado
from jarvis.sistema import catalogo as catalogo_sistema
from jarvis.sistema.midia import Midia
from jarvis.sistema.politica import Sistema
from jarvis.sistema.vigia import Eventos, Vigia
from jarvis.transporte import servidor_livekit
from jarvis.transporte.entrada import Entrada
from jarvis.transporte.local import Captura
from jarvis.transporte.remoto import SalaRemota
from jarvis.voz import chamado, espera, piper
from jarvis.voz.ativacao import (
    VAD,
    Detector,
    Features,
    SemFeatures,
    SemVAD,
    carregar_modelo,
    faltando,
)
from jarvis.voz.deepgram import Deepgram, EscutaDeepgram
from jarvis.voz.escuta import Segmentador
from jarvis.voz.fala import falavel, para_fala
from jarvis.voz.fim_de_turno import FimDeTurno
from jarvis.voz.latencia import Latencias
from jarvis.voz.saida import Voz

log = logging.getLogger(__name__)
# Comandos locais de voz (sem o cérebro), por tipo. "{}" é o argumento do comando
# ("abrir_orbe:Guia" -> Guia). Os que pedem algo à página pelo maos-pedido: nome -> (pedido, fala).
# O jeito do Zé (08/10/2026): o que ele diz quando dá uma voltinha e quando o usuário o roda
# demais com a mão. Frases variadas, sem gastar o cérebro.
# Comandos que falam com a sessão de manutenção ou rodam os testes: respondem quando terminarem.
# Os que mostram algo no Núcleo (abrem a janela se ela estiver fechada): nome -> (ações, fala).
MOSTRAR_NA_TELA: dict[str, tuple[list[dict[str, Any]], str]] = {
    "nucleo_abrir": ([{"acao": "nucleo", "valor": "abrir"}], "Núcleo aberto."),
    "teclado_abrir": ([{"acao": "teclado", "valor": "abrir"}], "Teclado aberto; pode escrever."),
    "foco_mostrar": ([{"acao": "foco"}], "Seu foco na tela."),
    "visual_avatar": ([{"acao": "visual", "valor": "avatar"}], "Pronto, este sou eu."),
    "visual_anel": ([{"acao": "visual", "valor": "anel"}], "Pronto, o anel de volta."),
    "abrir_orbe": ([{"acao": "abrir", "alvo": "{}"}], "{} na tela."),
    # Memória, sessões e automações são áreas do Mapa.
    **{
        f"mostrar_{area}": (
            [{"acao": "abrir_mapa"}, {"acao": "focar", "alvo": area}],
            "Está no Mapa.",
        )
        for area in e.FALAS_DAS_AREAS
    },
}
# Os que fecham algo (com a janela fechada, não há o que fechar): nome -> (ações, fala).
FECHAR_NA_TELA: dict[str, tuple[list[dict[str, Any]], str]] = {
    "nucleo_fechar": ([{"acao": "nucleo", "valor": "fechar"}], "Núcleo recolhido."),
    "teclado_fechar": ([{"acao": "teclado", "valor": "fechar"}], "Teclado fechado."),
    "fechar_alvo": ([{"acao": "fechar", "alvo": "{}"}], "Fechado."),
    "mapa_fechar": ([{"acao": "fechar_mapa"}], "Fechado."),
}


TIPOS_DE_SERVICO = (
    ServicoAtendimento,
    ServicoRemoto,
    ServicoAvisos,
    ServicoOficina,
    ServicoCerebro,
    ServicoVoz,
    ServicoMemoria,
    ServicoFoco,
    ServicoAutomacoes,
)


class Nucleo(
    InterfaceAtendimento,
    InterfaceRemoto,
    InterfaceAvisos,
    InterfaceOficina,
    InterfaceCerebro,
    InterfaceVoz,
    InterfaceMemoria,
    InterfaceFoco,
    InterfaceAutomacoes,
):
    def __init__(self, cfg: Config, parar: threading.Event) -> None:
        self.cfg = cfg
        self.parar = parar
        self.servicos = tuple(servico(self, tipo) for tipo in TIPOS_DE_SERVICO)
        acesso.aplicar()  # assinatura ou chave do Claude, antes de qualquer cérebro subir
        self.maquina = e.Maquina(prazo_conversa_s=cfg["escuta"]["conversa_s"])
        self.eventos: queue.Queue[e.Evento] = queue.Queue()
        self.status = Status()
        self.marca = 0  # pedido atual do cérebro; frases de marcas antigas são descartadas
        self._pedido_em = self._transcricao_inicio = time.monotonic()
        ESTADO.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.latencias = Latencias(ESTADO / "latencias")
        self._turno_atual: str | None = None
        self._turno_cerebro: tuple[int, str | None] = (0, None)
        self._digitado_em: float | None = None
        self.midia = Midia()  # vídeo e música pausam enquanto o Zé ouve ou fala
        self._antes_do_chamado: collections.deque[bytes] = collections.deque(maxlen=38)  # ~3 s
        self._ouvindo_desde = 0.0  # quando começou a ouvir, e se já ouviu voz desde então
        self._ouviu_voz = False
        self._fim_fala_em: float | None = None

        modelos = cfg.caminho("ativacao", "modelos_onnx")
        # Falha por função (ADR 0034): modelo que não baixou desliga só a peça dele.
        silero = modelos / "silero_vad.onnx"
        mel, embedding = modelos / "melspectrogram.onnx", modelos / "embedding_model.onnx"
        smart_turn = modelos / "smart-turn-v3.2-cpu.onnx"
        self.modelos_faltando = faltando(silero, mel, embedding, smart_turn, piper.PADRAO.modelo)
        if self.modelos_faltando:
            log.warning("modelos de som faltando: %s", ", ".join(self.modelos_faltando))
        self.vad: VAD | SemVAD = VAD(silero) if silero.is_file() else SemVAD()
        modelo_ativacao = carregar_modelo(cfg.caminho("ativacao", "modelo"))
        self.modelo_ativacao = modelo_ativacao  # volta ao detector quando a escuta liga
        if not modelo_ativacao.treinada:
            log.warning(
                "sem a palavra de ativação treinada: o Zé atende pelo teclado e pelo painel"
            )
        self.detector = Detector(
            modelo_ativacao,
            Features(mel, embedding) if mel.is_file() and embedding.is_file() else SemFeatures(),
            paciencia=cfg["ativacao"]["paciencia"],
        )
        limiar = cfg["escuta"]["limiar_fim_de_turno"]
        self.segmentador = Segmentador(
            fim_de_turno=FimDeTurno(smart_turn) if limiar > 0 and smart_turn.is_file() else None,
            limiar_fim_de_turno=limiar,
            fala_ate_agora=lambda: self.escuta.ate_agora() if self.escuta is not None else "",
        )
        self.espera = espera.ler()  # quanto esperar antes de achar que a pessoa terminou
        self._aplicar_espera()
        self.transcricoes = concurrent.futures.ThreadPoolExecutor(1, "transcricao")
        # Só Deepgram (decisão de 09/10/2026): sem a chave o Zé não escuta; painel e teclado
        # continuam. Nada de modelo local de transcrição ocupando a máquina.
        self.modo_fala = modo_fala.ler()  # quando o Zé fala sozinho (ADR 0018)
        self.chamado = chamado.ler()  # "Ei Zé" ou só o botão (ADR 0022)
        self.deepgram = Deepgram(cfg.caminho("escuta", "chave_deepgram"))
        self.meio_transcricao = "deepgram"
        if not self.deepgram.disponivel:
            log.warning("sem a chave do Deepgram: voz desligada (painel e teclado funcionam)")
        self._ligar_ativacao()
        self.escuta: EscutaDeepgram | None = None  # o pedido atual em streaming
        self.transcrevendo: concurrent.futures.Future[str] | None = None

        self.captura = Entrada(Captura(cfg["audio"]["microfone"]))
        self.anel = Anel(cfg.caminho("barehands", "pasta_estado"))
        self.voz = Voz(onda=self.anel, abrir_fluxo=piper.PADRAO.abrir_fluxo)
        # A voz carrega em segundo plano: a primeira fala já a encontra pronta.
        threading.Thread(target=self._carregar_voz, name="carregar-voz", daemon=True).start()
        self._ultima_fala = 0
        self.voz.ao_ficar_ociosa = self._voz_ociosa
        self.voz.muda = self.modo_fala == "silencioso"
        self._vendo: tuple[str, float] = ("", 0.0)  # a sessão aberta no painel, e quando
        self.fila = Fila(ESTADO / "avisos.json")  # durável: reinício não perde aviso
        self.jobs = Jobs(DADOS / "automacoes" / "jobs.json")
        self.calendario = Calendario(ESTADO / "agenda-avisada.json")
        self._rodando: set[str] = set()  # automações do tipo pergunta em execução
        self._agenda_em = 0.0
        self.avisos_falados: list[tuple[float, str]] = []
        # Regras de fala (ADR 0027): quantas vezes cada aviso começou a ser falado, os cortados
        # que podem voltar uma vez e quando cada aviso foi dado.
        self._comecados: dict[str, int] = {}
        self._cortados: set[str] = set()
        self._avisos_dados: dict[str, float] = {}
        self._na_tela: dict[str, None] = {}  # os últimos avisos já postos na linha do tempo
        self.ultimo_na_tela: list[float | str] | None = None  # o painel mostra (Silencioso)
        # Central de avisos (ADR 0029): o que se sabe de cada aviso (prioridade, sessão,
        # manchete, detalhe), até quando vale responder a uma oferta e o último aviso de sessão.
        self._meta: dict[str, dict[str, Any]] = {}
        self._ultimo_dito = ""  # a última fala inteira, para "repete"
        self._memoria_vista: str | None = None  # a memória que o cérebro já tem nesta conversa
        self._skills_vistas: dict[str, float] = {}  # e a versão de cada skill
        self._dito_marca: int | None = None
        self._oferta_ate = 0.0
        self._ultimo_de_sessao: dict[str, Any] | None = None
        self.eventos_sistema = Eventos(ESTADO / "eventos-sistema.jsonl")
        self.vigia = Vigia()
        self._vigia_em = 0.0
        self.consumo = Consumo(DADOS / "consumo.db", legado=ESTADO / "consumo.json")
        self.uso_ferramentas = UsoDeFerramentas(ESTADO / "uso-ferramentas.json")
        self.pergunta = ""  # a última pergunta de aprovação (o card de decisão do Barehands)
        self.turnos: list[dict[str, str]] = []  # a conversa atual, para a revisão
        self._revisoes = ("", 0)  # (dia, quantas) — teto diário do ADR 0011
        self.pendencias = revisao.Pendencias(cfg.caminho("revisao", "pendencias"))
        # Memória contínua (08/10/2026): cada fala com a hora, a linha do tempo e a nota do dia.
        self.conversas = Conversas(DADOS / "conversas")
        self.linha = LinhaDoTempo(DADOS / "linha-do-tempo.jsonl")
        self.dias = Dias(DADOS / "dias", self.conversas, self.linha)
        self._pedido_quando = datetime.now(FUSO)
        self._proxima_nota = 0.0
        self._notas_em_curso = False
        self._conversa_suja = False  # houve pedido ao cérebro desde a última conversa nova
        # O Foco (08/10/2026): as frentes do usuário.
        self.foco = Foco(DADOS / "foco/frentes.json", self._foco_mudou)
        # As marcações do "V" na tela: só as novas (o que já estava no arquivo não se repete).
        self._foco_acoes = cfg.caminho("barehands", "pasta_estado") / "foco-acoes.jsonl"
        try:
            self._foco_lido = self._foco_acoes.stat().st_size
        except OSError:
            self._foco_lido = 0
        m = cfg["memoria"]
        self.memoria = Memoria(
            cfg.caminho("memoria", "pasta"),
            {"usuario": m["limite_usuario"], "jarvis": m["limite_jarvis"]},
        )
        self.skills = Skills(cfg.caminho("skills", "pasta"))
        self.diario = Diario(DADOS / "diario.jsonl")
        self.pasta = pasta.Pasta(cfg.caminho("barehands", "pasta_jarvis"))
        self._pasta_em = 0.0
        self._curadoria_em = 0.0
        self._pasta_rodando: concurrent.futures.Future[None] | None = None
        self._pasta_exec = concurrent.futures.ThreadPoolExecutor(1, "pasta")
        self._fontes: tuple[int, list[str]] = (-1, [])
        self._evento_visto = (
            ""  # o último evento da página já tratado (id)  # marca da resposta, fontes guardadas
        )
        s = cfg["sistema"]
        forcados = {n: 4 for n in s["proibidos"]} | {n: 2 for n in s["confirmar"]}
        forcados |= {n: 1 for n in s["livres"]}
        self.sistema = Sistema(catalogo_sistema.carregar(forcados=forcados))
        self.tela = tela.Tela(cfg.caminho("barehands", "pasta_estado"))
        self.memoria_longa = AiMemory()  # o ai-memory: o da máquina ou um filho do Zé
        self.livekit = servidor_livekit.ServidorLiveKit()  # a sala da voz remota
        self.remota: SalaRemota | None = None
        self._fonte: Any = None  # a voz remota em uso: o navegador ou a sala LiveKit
        self._ouvido = ""  # a última transcrição
        self.imersivo = Imersivo(
            cfg.caminho("barehands", "pasta_estado"),
            acervo=cfg.caminho("barehands", "pasta_acervo"),
        )
        self.quadro = Quadro(
            lambda: self.maquina.estado is not e.Estado.INATIVO,
            url=f"http://127.0.0.1:{self.imersivo.porta}/cmd",
            token=self.imersivo.token,
        )
        self.maquina.nucleo_em_foco = self.tela.em_foco
        self.sessoes = Sessoes(
            DADOS / "sessoes",
            (Path.home(),),
            self._sessao_terminou,
            projetos_novos=cfg.caminho("oficina", "raiz_projetos"),
            skills=self.skills,
        )
        self.sessoes.ao_avisar = self._sessao_pede
        # A pasta do agente de atendimento: um projeto do usuário, ao lado dos outros (ADR 0031).
        self.projeto_agente = cfg.caminho("oficina", "raiz_projetos") / projeto.NOME
        with contextlib.suppress(OSError, agente.AgenteErro):
            projeto.migrar(self.projeto_agente)
        self.manutencao = Manutencao(self.sessoes, ESTADO / "manutencao")
        self.atualizacao = Progresso(ESTADO / "manutencao")  # aplicar, em tempo real no painel
        self.manutencao.ao_etapa = self.atualizacao.etapa
        self.manutencao.atualizando = lambda: self.atualizacao.reserva() is not None
        self.evidencias = evidencias.Evidencias(ESTADO / "evidencias.jsonl")
        self.maquina.manutencao = lambda: self.manutencao.ligado
        self.maquina.oferta = lambda: time.monotonic() < self._oferta_ate
        # Atualização esperando as outras sessões (ADR 0028): None, ou se a revisão foi feita.
        self._aplicar_depois: bool | None = None
        self.sessoes.reservada = self.atualizacao.reserva
        self.orbes = manifesto.ler(
            cfg.caminho("barehands", "pasta_estado").parent / "barehands.json"
        )
        self.maquina.orbes = manifesto.falados(self.orbes)
        self.proprias = ferramentas.montar(
            self.sessoes,
            self.memoria,
            self.skills,
            self.pendencias,
            self.jobs,
            self.sistema,
            self.diario,
            self.tela,
            self.manutencao,
        )
        servidor = ferramentas.servidor(self.proprias)
        try:
            externos = mcp_externo.carregar(painel=mcp_externo.PAINEL)
        except mcp_externo.McpInvalido as erro:
            log.error("MCPs externos ignorados: %s", erro)
            self._erro(f"mcp.toml: {erro}")
            externos = mcp_externo.Externos()
        self.externos = externos
        self.extras = catalogo.Extras(
            {
                ferramentas.SERVIDOR: servidor,
                tempo.SERVIDOR: tempo.servidor(self.conversas, self.linha, self.dias),
                foco_ferramentas.SERVIDOR: foco_ferramentas.servidor(self.foco),
                atendente_ferramentas.SERVIDOR: atendente_ferramentas.servidor(self.projeto_agente),
                **externos.servidores,
            },
            (
                *ferramentas.LIVRES,
                *tempo.LIVRES,
                *foco_ferramentas.LIVRES,
                *atendente_ferramentas.LIVRES,
                *externos.livres,
            ),
            bloqueadas=tuple(externos.bloqueadas),
            foto=self._foto_do_cerebro,
            prechecar=primeiro_de(
                ferramentas_sessoes.preparador(self.sessoes),
                ferramentas.prechecagem(self.memoria, self.skills),
                self.sistema.prechecar,
                navegador.prechecar,
            ),
            mostrar=ferramentas.mostrador(self.skills, self.quadro.apresentar, self.pendencias),
            descrever_extra=primeiro_de(
                ferramentas_sessoes.descritor(self.sessoes),
                self._descrever_manutencao,
                navegador.descrever,
                ferramentas.descritor(self.pendencias),
                self.sistema.descrever,
            ),
            autoaprovar=lambda nome, entrada: (
                self.sistema.autoaprovar(nome, entrada) or navegador.autoaprovar(nome, entrada)
            ),
            frase_exata=self.sistema.frase_exata,
            depois=navegador.ajustar,
        )
        self.escolhido = ESTADO / "cerebro"
        self.modelos_escolhidos = ESTADO / "cerebro-modelos.json"
        catalogo.aplicar_modelos(cfg, catalogo.ler_modelos(self.modelos_escolhidos))
        if endereco_omni := omniroute.ler_endereco():  # o OmniRoute configurado no painel
            cfg["cerebro"]["omniroute_endereco"] = endereco_omni
        cerebro, self.provedor = catalogo.montar(
            cfg, DADOS / "cerebro", catalogo.ler_escolha(self.escolhido), self.extras
        )
        self.cerebro = self._com_via_rapida(cerebro)
        log.info("cérebro: %s", self.provedor)
        self.painel = Painel(cfg.caminho("barehands", "pasta_estado"))
        self.hud = hud.Hud(cfg.caminho("barehands", "pasta_estado"))
        self.teclado = Teclado(cfg.caminho("barehands", "pasta_estado"), self.hud)
        self.limite_claude = ler_json(ESTADO / "limite_claude.json")
        self.baterias_omniroute: dict[str, Bateria] = {}
        self.modelo_auto: str | None = None  # o último que o OmniRoute escolheu no automático
        self._baterias_em = 0.0
        self.ponte = Ponte(
            self.cerebro,
            self.persona(),
            self._frase_do_cerebro,
            self._fim_do_cerebro,
            self._pedido_de_aprovacao,
            self._primeiro_texto_do_cerebro,
        )
        self.ponte.ao_expirar_aprovacao = lambda: self.eventos.put(e.AprovacaoExpirou())
        self.portal: Portal | None = None
        self.acesso = Acesso(ao_entrar=self._aparelho_entrou)  # quem entra de outro aparelho
        self.tunel = tunel.Tunel(self._tunel_pronto, self._tunel_caiu)  # acesso de qualquer lugar
        self.mensagens = mensagens.Mensagens(
            self._mensagem_importante,
            self._motor_das_mensagens,
            usar_notificacoes=lambda: not self.central.whatsapp_ativo,
        )
        # O atendimento (ADR 0031) roda na Central, um serviço próprio: o WhatsApp e o agente
        # seguem de pé quando o Zé reinicia. Aqui ficam só a tela, o Testar e o Publicar.
        self.central = cliente.Cliente(self._evento_da_central)
        self.testes_do_atendente = agente.Executor()
        try:
            acoes = Acoes(self, ESTADO / "latencias", DADOS / "cerebro-teste")
            self.portal = Portal(
                acoes.leituras(),
                acoes.escritas(),
                envios=acoes.envios(),
                acesso=self.acesso,
                voz=self.voz_pelo_navegador,
                so_no_pc=senha.SO_NO_PC,
            )
            self.portal.iniciar()
        except OSError as erro:
            log.warning("painel não subiu: %s", erro)
        self.bip = ESTADO / "bip.wav"
        criar_bip(self.bip)
        self.toque = ESTADO / "toque.wav"
        criar_toque(self.toque)
        # Rostos (ADR 0021): a janela no Hyprland, a escuta sempre ligada e, depois, a voz remota.
        self.rostos = Rostos(lambda ativo: self.eventos.put(e.Presenca(ativo)))
        self.tem_janela = hyprland.disponivel()
        self.presenca: MonitorPresenca | None = None
        if self.tem_janela:
            self.presenca = MonitorPresenca(
                lambda aberta: self.rostos.marcar("janela", aberta),
                parar,
                classe=cfg["presenca"]["classe_janela"],
            )
        self.modo_escuta = modo_escuta.ler(self.tem_janela)

    # --- callbacks de outras threads (só põem eventos na fila) --------------------------

    def _erro(self, mensagem: str) -> None:
        log.warning(mensagem)
        self.status.ultimo_erro = mensagem[:180]
        self.status.erro_em = time.time()

    # --- efeitos ------------------------------------------------------------------------

    def _executar(self, efeito: e.Efeito) -> None:
        match efeito:
            case e.AbrirMicrofone():
                self.detector.reiniciar()
                self.vad.reiniciar()
                self.segmentador.limpar()
                self._fim_fala_em = None
                if not self.microfone_travado:  # Silencioso: o microfone fica fechado
                    self.captura.abrir()
            case e.FecharMicrofone():
                self.captura.fechar()
                self.segmentador.limpar()
            case e.CortarFala():
                self.voz.parar()
                self.anel.parar()
            case e.Bip():
                self.status.ativacoes += 1
                self._tocar_bip()
            case e.FecharPedido():
                self._fechar_pelo_botao()
            case e.EnviarAoCerebro(texto):
                atividade.PADRAO.origem = self._origem()
                self._abrir_latencia("cerebro")
                self.marca += 1
                self.status.pedidos += 1
                self._pedido_em = time.monotonic()
                self._conversa_suja = True
                self.turnos.append({"gabriel": texto, "jarvis": ""})
                self._pedido_quando = datetime.now(FUSO)
                pedido = self._com_memoria(
                    self._com_foco(self._com_avisos(self._com_nucleo(texto)))
                )
                self._turno_cerebro = (self.marca, self._turno_atual)
                self.latencias.contexto(
                    self._turno_atual,
                    provedor=self.provedor,
                    modelo=str(getattr(self.cerebro, "modelo", "") or ""),
                )
                self.latencias.marcar(self._turno_atual, "cerebro_enviado")
                self.ponte.perguntar(pedido, self.marca)
            case e.InterromperCerebro():
                self.marca += 1
                self.ponte.interromper()
            case e.Falar(texto):
                # O que foi dito por último, inteiro, para "repete": um aviso, ou as frases de
                # uma mesma resposta (a marca muda a cada pedido).
                if texto == self.maquina.aviso_falando:
                    self._ultimo_dito, self._dito_marca = texto, None
                elif getattr(self, "_dito_marca", None) == self.marca:
                    self._ultimo_dito = f"{self._ultimo_dito} {texto}"
                else:
                    self._ultimo_dito, self._dito_marca = texto, self.marca
                if texto == self.maquina.aviso_falando:
                    # O cérebro não ouve a própria voz: sem isto, "pode aprovar" depois de um
                    # aviso chegava sem contexto (teste de 06/10/2026).
                    self.avisos_falados.append((time.monotonic(), texto))
                    self._comecados[texto] = self._comecados.get(texto, 0) + 1
                    self._avisos_dados[texto] = time.monotonic()  # falado: conta como dado
                    self._antes_de_avisar(texto)
                self.teclado.falou(texto)
                if texto == e.NAO_ENTENDI:
                    self.evidencias.registrar("nao_entendi", self._ouvido)
                    ouvido = f'Ouviu "{self._ouvido}"' if self._ouvido.strip() else "Não ouviu nada"
                    atividade.PADRAO.registrar("nao_entendi", ouvido)
                turno = self._turno_atual
                if turno is not None:
                    self.latencias.marcar(turno, "primeira_frase")
                    self.latencias.marcar(turno, "sintese_pedida")
                tipo = "confirmacao" if self.maquina.estado is e.Estado.CONFIRMANDO else "resposta"

                def ao_iniciar(em: float) -> None:
                    self.latencias.primeiro_som(turno, em, tipo)

                self._ultima_fala = self.voz.falar(
                    falavel(para_fala(texto)), ao_iniciar=ao_iniciar if turno else None
                )
            case e.ResponderAprovacao(aprovado, fala):
                log.info("aprovação respondida: %s", "sim" if aprovado else "não")
                if not getattr(self.ponte, "aprovacao_pendente", True):
                    # A pergunta já tinha expirado: o cérebro seguiu sem ela. Sem isto, o "sim"
                    # atrasado deixava o Zé pensando para sempre, sem ouvir (14/10/2026).
                    log.info("resposta depois de a pergunta expirar")
                    self.eventos.put(
                        e.Frase("Essa pergunta já tinha expirado. Peça de novo, por favor.")
                    )
                    self.eventos.put(e.RespostaFim())
                    return
                if aprovado and self.pergunta:
                    self._na_linha("aprovado", self.pergunta)
                self.ponte.responder_aprovacao(aprovado, fala)
            case e.Comando(nome):
                atividade.PADRAO.origem = self._origem()
                atividade.PADRAO.registrar(
                    "execucao", f"Comando local: {nome}", autorizacao="comando local"
                )
                self._abrir_latencia(
                    "manutencao" if nome.startswith("manutencao_pedido:") else "comando"
                )
                self._comando(nome)
            case e.ReterAviso(texto):
                if self._comecados.get(texto, 0) >= 2:
                    # Já foi cortado uma vez e voltou: não lê pela terceira vez (ADR 0027).
                    log.info("aviso cortado de novo: fica só na tela")
                    return
                if self._comecados.get(texto):
                    self._cortados.add(texto)  # a volta de um aviso cortado não é repetição
                # Fila durável (Fase 7): o aviso sai quando o JARVIS voltar a ATIVO.
                log.info("aviso retido até ficar ativo: %d caracteres", len(texto))
                self._guardar(texto)

    def _comando(self, nome: str) -> None:
        log.info("comando: %s", nome)
        self.consumo.somar_local()
        self.marca += 1  # o que ainda vier do cérebro é de um pedido anterior
        base, _, argumento = nome.partition(":")
        if base in AJUSTES_DA_TELA:
            pedido, resposta = AJUSTES_DA_TELA[base]
            self.hud.pedir_maos(pedido)
        elif base in MOSTRAR_NA_TELA:
            acoes, pronto = MOSTRAR_NA_TELA[base]
            if base == "foco_mostrar":
                pronto = self.foco.fala_do_quadro()
            resposta = self._no_nucleo(com_argumento(acoes, argumento), pronto.format(argumento))
        elif base in FECHAR_NA_TELA:
            acoes, pronto = FECHAR_NA_TELA[base]
            resposta = self._se_aberto(com_argumento(acoes, argumento), pronto)
        elif base in EM_SEGUNDO_PLANO:
            # Falam com a sessão de manutenção ou rodam os testes: a resposta sai quando terminar.
            threading.Thread(
                target=self._responder_depois, args=(base, argumento), daemon=True
            ).start()
            return
        elif base == "abrir_item":
            # A busca no Núcleo responde se achou: a fala espera a página (uma fração de segundo).
            threading.Thread(target=self._abrir_item, args=(argumento,), daemon=True).start()
            return
        else:
            resposta = self._comando_especial(base, argumento)
        self.eventos.put(e.Frase(resposta))
        self.eventos.put(e.RespostaFim())

    def _responder_depois(self, nome: str, argumento: str) -> None:
        m = self.manutencao
        try:
            if nome == "manutencao_entrar":
                resposta = m.entrar(argumento)
            elif nome == "manutencao_pedido":
                if not m.ligado:
                    resposta = "Manutenção desligada. Faça o pedido na conversa."
                else:
                    resposta = m.encaminhar(argumento, self._contexto_da_manutencao(), time.time())
                    self._na_linha("manutencao", f"Pedido à sessão de código: {argumento}")
            elif nome == "rodada_melhoria":
                resposta = self._rodada_de_melhoria()
            elif not self._no_proprio_pc():
                # Reiniciar e aplicar mudam o Zé em uso: nunca de outro aparelho (ADR 0028).
                resposta = "Aplique no computador."
            # Pela voz, nunca com "eu revisei": a zona protegida só se aplica no painel, no PC,
            # com a revisão marcada (docs/essencia.md, item 7).
            elif m.mudancas().get("commits"):  # reiniciar: há melhorias na cópia, aplica
                resposta = self.aplicar_melhorias(revisado=False)
            else:  # reiniciar
                _, resposta = m.reiniciar(revisado=False)
        except (SessaoErro, OSError, subprocess.SubprocessError) as erro:
            log.warning("manutenção: %s", erro)
            resposta = "Não consegui falar com a sessão de manutenção agora."
        self.eventos.put(e.Frase(resposta))
        self.eventos.put(e.RespostaFim())

    # --- laço ---------------------------------------------------------------------------

    def tratar(self, evento: e.Evento) -> None:
        if isinstance(evento, e.Aviso) and self.modo_fala == "silencioso":
            log.info("modo silencioso: aviso só na tela (%d caracteres)", len(evento.texto))
            self._mostrar(evento.texto)
            return
        if isinstance(evento, e.Aviso):
            permitido = self._regras_de_fala(evento)
            if permitido is None:
                return
            evento = permitido
        if isinstance(evento, e.Aviso) and self._pessoa_falando():
            self._guardar(evento.texto)  # ao vivo: o aviso espera a pausa, não atropela
            return
        antes = self.maquina.estado
        agora = time.monotonic()
        self._digitado_em = (
            agora if isinstance(evento, e.Digitado) and antes is not e.Estado.CONFIRMANDO else None
        )
        if isinstance(evento, e.Ativacao) and self.maquina.detector_ligado:
            self._fechar_latencia("interrompido")
            self._fim_fala_em = None
        if isinstance(evento, e.Presenca) and not evento.ativo:
            self._fechar_latencia("janela_fechada")
        if isinstance(evento, e.RespostaFim) or (
            isinstance(evento, (e.Ativacao, e.FimDeFala)) and antes is not e.Estado.CONFIRMANDO
        ):
            self.teclado.terminou()  # a resposta escrita acabou, ou começou um pedido por voz
        for efeito in self.maquina.tratar(evento, agora):
            self._executar(efeito)
        self._digitado_em = None
        depois = self.maquina.estado
        if (
            depois is not antes
            and depois in (e.Estado.ATIVO, e.Estado.OUVINDO)
            and self._turno_atual
        ):
            # Também registra "ok" e transcrição vazia, sem tratá-los como resposta simples.
            self._fechar_latencia(
                "controle"
                if antes is e.Estado.OUVINDO
                else "erro_voz"
                if self.voz.ultimo_erro
                else "concluido"
            )
        if depois is not antes:
            log.info("%s -> %s", antes.value, depois.value)
            if depois is e.Estado.FALANDO and antes is e.Estado.PENSANDO:
                self.status.tempos["ate_primeira_frase_s"] = round(
                    time.monotonic() - self._pedido_em, 2
                )
            if depois is e.Estado.ATIVO and antes is e.Estado.INATIVO:
                self._bom_dia()
            if depois is e.Estado.ATIVO:
                self.detector.reiniciar()
                if not self.maquina.em_conversa:
                    self._fim_da_conversa()
                self._sair_da_fila()
            if self._pausar_midia():
                self._dar_a_vez(antes, depois)
            if depois is e.Estado.OUVINDO and antes is not e.Estado.OUVINDO:
                self._ouvindo_desde, self._ouviu_voz = time.monotonic(), False
            if depois is e.Estado.OUVINDO and antes is e.Estado.FALANDO:
                self._descartar_escuta()  # conversa contínua: próxima pergunta sem "Hey Orca"

    def _quadro(self, dados: bytes) -> None:
        if self.maquina.transcrevendo:
            if self.transcrevendo is not None:
                return  # um pedido por vez; o que vier durante a transcrição é descartado
            if self.escuta is None and self.deepgram is not None and self.deepgram.disponivel:
                self.escuta = self.deepgram.nova()  # só agora o áudio começa a sair da máquina
            if self.escuta is not None:
                self.escuta.enviar(dados)
            amostras = np.frombuffer(dados, dtype="<i2")
            voz = self.vad.prever(amostras) >= self.cfg["escuta"]["limiar_vad"]
            if voz:
                self._fim_fala_em = time.monotonic()
                self._ouviu_voz = True
            self.segmentador.segurando = self.maquina.segurando
            trecho = self.segmentador.quadro(dados, voz)
            if trecho is not None:
                self._pedido_fechado(trecho)
            elif (
                self.maquina.estado is e.Estado.OUVINDO
                and not self.segmentador.em_fala
                and (time.monotonic() > self.maquina.prazo or self._ninguem_falou())
            ):
                self.tratar(e.Silencio())
        else:
            self._fechar_escuta()
            self._antes_do_chamado.append(dados)
            if self.maquina.detector_ligado and self.detector.processar(
                np.frombuffer(dados, dtype="<i2")
            ):
                nivel = nivel_de_pico(b"".join(self._antes_do_chamado))
                minimo = float(self.cfg["ativacao"].get("nivel_minimo_dbfs", -45.0))
                self._guardar_chamado(nivel < minimo)
                if nivel < minimo:
                    log.info(
                        "chamado ignorado: baixo demais (nota %.3f, %.0f dBFS)",
                        self.detector.nota_disparo,
                        nivel,
                    )
                    return
                log.info("ativação (nota %.3f, %.0f dBFS)", self.detector.nota_disparo, nivel)
                self.tratar(e.Ativacao())

    # --- cérebros e baterias (ADR 0010) -----------------------------------------------------

    def _atualizar_painel(self, agora: float) -> None:
        completo = getattr(self.cerebro, "completo", self.cerebro)
        completo = getattr(completo, "cerebro_ativo", completo)
        if (
            isinstance(completo, ClaudeBrain)
            and completo.assinatura
            and completo.limite
            and completo.limite != self.limite_claude
        ):
            self.limite_claude = dict(completo.limite)
            with contextlib.suppress(OSError):
                gravar_json(ESTADO / "limite_claude.json", self.limite_claude)
        if agora - self._baterias_em >= BATERIAS_S:
            self._baterias_em = agora
            self.baterias_omniroute = do_omniroute(
                self.cfg.caminho("cerebro", "omniroute_banco"), agora
            )
        if (escolha := self.painel.escolha(agora)) is not None:
            log.info("troca pedida no Barehands: %s", escolha)
            self.trocar_cerebro(escolha)
        self.painel.mostrar(self.provedor, self.baterias(), self.modelos(), agora)
        self._mostrar_decisao(agora)

    def _mostrar_decisao(self, agora: float) -> None:
        """O card do Barehands: a pergunta que espera o "sim" e o prazo (só depois de falada)."""
        pergunta, expira = None, None
        if self.maquina.estado is e.Estado.CONFIRMANDO:
            pergunta = self.pergunta
            if not self.maquina.pergunta_falando:
                expira = round(agora + self.maquina.prazo - time.monotonic())
        self.hud.gravar("decisao", hud.decisao(pergunta, expira, self.pendencias), agora)

    # --- automações e agenda (Fase 7) -------------------------------------------------------

    # --- a pasta do JARVIS no Barehands e a curadoria das skills ----------------------------

    def _conexoes(self) -> pasta.Conexoes:
        c, r = self.cfg["cerebro"], self.cfg["revisao"]
        opcao = catalogo.OPCOES.get(self.provedor)
        nome = opcao.nome if opcao else self.provedor
        modelo = self.modelos().get(self.provedor, "")
        reserva = catalogo.OPCOES.get(c["reserva"])
        escuta = "Deepgram" if self.deepgram.disponivel else "desligada (sem chave do Deepgram)"
        livres = set(ferramentas.LIVRES)
        return pasta.Conexoes(
            cerebro=f"{nome}, com o {modelo}" if modelo else nome,
            reserva=reserva.nome if reserva else c["reserva"],
            revisao=f"{catalogo.rotulo(r['modelo'])}, até {r['max_por_dia']} por dia"
            if r["ligada"]
            else "",
            voz=f"fala pelo {self.cfg['voz']['motor'].capitalize()} (Cadu), escuta pelo {escuta}",
            proprias=[
                (t.name, f"mcp__{ferramentas.SERVIDOR}__{t.name}" in livres) for t in self.proprias
            ],
            embutidas=list(c["ferramentas"]),
            externos={
                nome: [
                    livre.rsplit("__", 1)[-1]
                    for livre in self.externos.livres
                    if livre.startswith(f"mcp__{nome}__")
                ]
                for nome in self.externos.servidores
            },
        )

    def _gravar_status(self, agora: float) -> None:
        self.hud.gravar(
            "presenca",
            {
                "batimento": agora,
                "estado": self.maquina.estado.value,
                "microfone_aberto": self.captura.aberta,
            },
            agora,
        )
        gravar_json(
            ESTADO / "status.json",
            {
                "pid": os.getpid(),
                "batimento": agora,
                "estado": self.maquina.estado.value,
                "microfone_aberto": self.captura.aberta,
                "provedor": self.provedor,
                "ativacoes": self.status.ativacoes,
                "pedidos": self.status.pedidos,
                "transcricao_por": self.status.meio_transcricao,
                "modelo": getattr(self.cerebro, "modelo", None),
                "limite_assinatura": self.limite_claude,
                "consumo_hoje": self.consumo.hoje,
                "ultimo_erro": self.status.ultimo_erro,
                "tempos": {**self.status.tempos, "primeira_fala_s": self.voz.primeira_fala_s},
                "engasgos_de_voz": self.voz.engasgos,
                "erro_de_voz": self.voz.ultimo_erro,
                "latencia": {
                    "ultimo_turno": self.latencias.ultimo,
                    "descartados": self.latencias.descartados,
                    "erro_gravacao": self.latencias.erro,
                },
            },
        )

    def rodar(self) -> None:
        self.memoria_longa.iniciar()
        self._avisar_interrompidas()
        self._ligar_voz_remota()
        if tunel.escolhido():  # o acesso de qualquer lugar continua depois de um reinício
            if self.acesso.tem_senha and self.acesso.tem_codigo:
                threading.Thread(target=self._subir_tunel, name="tunel", daemon=True).start()
            else:
                log.warning("túnel não sobe: falta a senha ou o código do autenticador")
        if whatsapp.escolhido():
            threading.Thread(target=self._subir_central, name="central", daemon=True).start()
        if mensagens.escolhido() and (mensagens.disponivel() or whatsapp.escolhido()):
            self.mensagens.iniciar()
        self.imersivo.iniciar()
        if self.presenca is not None:
            self.presenca.start()
        self.rostos.marcar("sempre", self.modo_escuta == "sempre")
        proximo_status = 0.0
        try:
            while not self.parar.is_set():
                agora = time.time()
                if self.transcrevendo is not None and self.transcrevendo.done():
                    self.transcrevendo = None
                    self.segmentador.limpar()
                self._ler_teclado()
                while True:
                    try:
                        self.tratar(self.eventos.get_nowait())
                    except queue.Empty:
                        break
                self.tratar(e.Tempo())
                humor = "red" if agora - self.status.erro_em < 30 else "green"
                if humor == "green" and self.manutencao.ligado:
                    humor = "amber"  # o anel diz que os pedidos vão para a sessão de código
                self.anel.mostrar(self.maquina.anel, humor, agora)
                if agora >= proximo_status:
                    self._gravar_status(agora)
                    self._atualizar_painel(agora)
                    self._conversa_parada()
                    self._aviso_ao_vivo()
                    self._agendador(agora)
                    self._atualizar_pasta(agora)
                    self._manutencao_chegou(agora)
                    self._aplicar_quando_livre()
                    self._evento_da_tela()
                    self._foco_na_tela(agora)
                    self._nota_do_dia(agora)
                    proximo_status = agora + 1
                if not self.captura.aberta:
                    # Inativo: sem microfone, o laço só espera eventos (CPU parada).
                    with contextlib.suppress(queue.Empty):
                        self.tratar(self.eventos.get(timeout=0.5))
                    continue
                try:
                    self._quadro(self.captura.quadros.get(timeout=0.1))
                except queue.Empty:
                    continue
        finally:
            self.desligar()

    def escrever(self, texto: str) -> str:
        """Um pedido escrito no painel (Conversa) vira um Digitado, como no Teclado do Núcleo."""
        texto = " ".join(texto.split())[:LIMITE_ESCRITO]
        if not texto:
            return "Mensagem vazia."
        estado = self.maquina.estado
        if estado is e.Estado.INATIVO:
            return "O Zé está inativo."
        if estado is not e.Estado.CONFIRMANDO and not e.pedido_valido(texto):
            return "Não entendi o que foi escrito."
        log.info("painel: pedido escrito (%d caracteres)", len(texto))
        self.eventos.put(e.Digitado(texto))
        return "Enviado."

    def _ler_teclado(self) -> None:
        """Um pedido escrito no Teclado do Núcleo vira um Digitado, como uma fala autorizada."""
        if (texto := self.teclado.novo()) is None:
            return
        log.info("teclado: pedido escrito (%d caracteres)", len(texto))
        confirmando = self.maquina.estado is e.Estado.CONFIRMANDO
        if self.maquina.estado is e.Estado.INATIVO:
            self.teclado.avisar("Estou inativo agora: a tela está bloqueada ou você saiu.")
        elif not confirmando and not e.pedido_valido(texto):
            self.teclado.avisar("Não entendi o que foi escrito.")
        else:
            self.tratar(e.Digitado(texto))

    def desligar(self) -> None:
        self.parar.set()
        self._fechar_latencia("servico_parado")
        self.latencias.fechar()
        self._fechar_escuta()
        self.voz.parar()
        self.captura.fechar()
        self.imersivo.parar()
        if self.remota is not None:
            self.remota.parar()
        self.livekit.parar()
        self.tunel.soltar()  # o túnel continua de pé: o endereço não muda
        self.mensagens.parar()
        self.central.parar()  # só para de ouvir: a Central continua atendendo
        self.testes_do_atendente.parar()
        self.memoria_longa.parar()
        self.transcricoes.shutdown(wait=False, cancel_futures=True)
        self._pasta_exec.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            self.ponte.fechar()
        self.anel.mostrado = None
        self.anel.mostrar("idle", "green", time.time())
        gravar_json(ESTADO / "status.json", {"pid": os.getpid(), "estado": "parado"})
