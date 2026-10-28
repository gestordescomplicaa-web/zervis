"""Laço do núcleo: liga microfone, detector, escuta, cérebro, voz e anel à máquina de estados.

Uma thread só trata eventos e quadros; o resto (presença, cérebro, voz, transcrição) roda em
threads próprias e fala com ela por uma fila de eventos. Os quadros do microfone chegam por
uma fila curta: se o laço atrasar, os mais velhos caem, mas o laço nunca espera rede.
"""

import collections
import concurrent.futures
import contextlib
import dataclasses
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

from zervis import __version__, atividade, versoes
from zervis.atendimento import agente, cliente, projeto, whatsapp
from zervis.atendimento import ferramentas as atendente_ferramentas
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.calendario import Calendario
from zervis.automacoes.jobs import Jobs
from zervis.avisos import mensagens
from zervis.avisos import modo as modo_fala
from zervis.avisos.fila import Fila
from zervis.cerebro import (
    acesso,
    catalogo,
    contas,
    ferramentas,
    mcp_externo,
    mcp_oauth,
    navegador,
    omniroute,
    pesquisa,
    rapido,
)
from zervis.cerebro.base import Ponte
from zervis.cerebro.baterias import Bateria, do_omniroute
from zervis.cerebro.claude import ClaudeBrain, carimbo
from zervis.cerebro.consumo import Consumo, UsoDeFerramentas, gasto
from zervis.cerebro.ferramentas import sessoes as ferramentas_sessoes
from zervis.config import Config
from zervis.foco import ferramentas as foco_ferramentas
from zervis.foco.frentes import Foco
from zervis.habilidades import evidencias, revisao
from zervis.habilidades.diario import Diario
from zervis.habilidades.skills import Skills
from zervis.imersivo import Imersivo
from zervis.memoria import tempo
from zervis.memoria.aimemory import AiMemory
from zervis.memoria.conversas import Conversas
from zervis.memoria.curta import Memoria
from zervis.memoria.dias import Dias
from zervis.memoria.linha import LinhaDoTempo
from zervis.nucleo import autoconhecimento
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
from zervis.nucleo.servicos.atendimento import ServicoAtendimento
from zervis.nucleo.servicos.automacoes import ServicoAutomacoes
from zervis.nucleo.servicos.avisos import ServicoAvisos
from zervis.nucleo.servicos.cerebro import ServicoCerebro
from zervis.nucleo.servicos.foco import ServicoFoco
from zervis.nucleo.servicos.interface import servico
from zervis.nucleo.servicos.interface_atendimento import InterfaceAtendimento
from zervis.nucleo.servicos.interface_automacoes import InterfaceAutomacoes
from zervis.nucleo.servicos.interface_avisos import InterfaceAvisos
from zervis.nucleo.servicos.interface_cerebro import InterfaceCerebro
from zervis.nucleo.servicos.interface_foco import InterfaceFoco
from zervis.nucleo.servicos.interface_memoria import InterfaceMemoria
from zervis.nucleo.servicos.interface_oficina import InterfaceOficina
from zervis.nucleo.servicos.interface_remoto import InterfaceRemoto
from zervis.nucleo.servicos.interface_voz import InterfaceVoz
from zervis.nucleo.servicos.memoria import ServicoMemoria
from zervis.nucleo.servicos.oficina import ServicoOficina
from zervis.nucleo.servicos.remoto import ServicoRemoto
from zervis.nucleo.servicos.voz import ServicoVoz
from zervis.oficina.manutencao import Manutencao
from zervis.oficina.progresso import Progresso
from zervis.oficina.sessoes import SessaoErro, Sessoes
from zervis.portal import senha, tunel
from zervis.portal.acoes import Acoes
from zervis.portal.senha import Acesso
from zervis.portal.servidor import Portal
from zervis.portal.voz_app import AparelhosDeVoz
from zervis.presenca import hyprland
from zervis.presenca import modo as modo_escuta
from zervis.presenca.hyprland import MonitorPresenca
from zervis.presenca.rostos import Rostos
from zervis.rosto import hud, manifesto, pasta, tela
from zervis.rosto.anel import Anel
from zervis.rosto.painel import Painel
from zervis.rosto.quadro import Quadro
from zervis.rosto.teclado import Teclado
from zervis.sistema import catalogo as catalogo_sistema
from zervis.sistema import maquina as maquina_atual
from zervis.sistema.midia import Midia
from zervis.sistema.politica import Sistema
from zervis.sistema.vigia import Eventos, Vigia
from zervis.sistema.vigia_n8n import VigiaN8n
from zervis.transporte import servidor_livekit
from zervis.transporte.entrada import Entrada
from zervis.transporte.local import Captura
from zervis.transporte.remoto import SalaRemota
from zervis.versoes import Versoes
from zervis.voz import chamado, espera, nuvem, piper
from zervis.voz.ativacao import (
    VAD,
    Detector,
    Features,
    SemFeatures,
    SemVAD,
    carregar_modelo,
    faltando,
)
from zervis.voz.deepgram import Deepgram, EscutaDeepgram
from zervis.voz.escuta import Segmentador
from zervis.voz.fala import falavel, para_fala
from zervis.voz.fim_de_turno import FimDeTurno
from zervis.voz.latencia import Latencias
from zervis.voz.live import Live, live_ativo
from zervis.voz.saida import Voz

log = logging.getLogger(__name__)
# Depois da pergunta de permissão de uma sessão, quanto tempo o "sim" e o "não" valem para ela:
# a fala da pergunta e a escuta que vem depois (mãos livres), ou um "Ei Zé, sim" logo em seguida.
JANELA_PERMISSAO_S = 45.0
# Voz ouvida e descartada enquanto o Zé pensa (ao vivo): acima do ruído de fundo, e só conta
# quando passa de meio segundo, para um estalo ou uma tosse não virar aviso.
FALA_PERDIDA_DBFS = -35.0
FALA_PERDIDA_MIN_S = 0.5
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


# Como o retrato diz cada motor das respostas rápidas (ADR 0043).
NOMES_DOS_MOTORES = {
    "plano": "o Claude pela assinatura",
    "codex": "o Codex pela assinatura",
    "contas": "as contas dos agentes",
    "anthropic": "a API da Anthropic",
    "openai": "a API da OpenAI",
    "openrouter": "o OpenRouter",
    "ponte": "uma ponte compatível com a OpenAI",
    "omniroute": "o OmniRoute",
}


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
        self._fala_perdida_s = 0.0  # voz ouvida enquanto o Zé pensava: ninguém a transcreveu
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
        # Quem fala: o Cadu, ou a voz da nuvem escolhida no painel (com o Cadu de reserva).
        self.motor_voz = nuvem.Motor(piper.PADRAO)
        self.voz = Voz(onda=self.anel, abrir_fluxo=self.motor_voz.abrir_fluxo)
        # A voz carrega em segundo plano: a primeira fala já a encontra pronta.
        threading.Thread(target=self._carregar_voz, name="carregar-voz", daemon=True).start()
        self._ultima_fala = 0
        self.voz.ao_ficar_ociosa = self._voz_ociosa
        self.voz.muda = self.modo_fala == "silencioso"
        # O Live (ADR 0042): com a voz conectada ao vivo, os ouvidos, a boca e o revezamento vão
        # para a sessão do LiveKit Agents; o pedido e a resposta continuam por aqui.
        self.live = Live(
            chave=lambda: self.deepgram.chave,
            motor_voz=self.motor_voz,
            ao_pedido=lambda texto, fim, fechado: self.eventos.put(
                e.FalaAoVivo(texto, fim, fechado)
            ),
            ao_interromper=lambda: self.eventos.put(e.Interrompido()),
            ao_ociosa=self._voz_ociosa,
            espera=lambda: self.espera,
        )
        self._pedidos_ao_vivo = 0  # os pedidos do Live que o laço já tratou
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
        # As perguntas de permissão das sessões (ADR 0039): a fala de cada uma → (sessão,
        # pedido); a última que o Zé fez e até quando o "sim" e o "não" a respondem.
        self._perguntas_permissao: dict[str, tuple[str, str]] = {}
        self._permissao_falada: tuple[str, str] | None = None
        self._permissao_ate = 0.0
        self.eventos_sistema = Eventos(ESTADO / "eventos-sistema.jsonl")
        self.vigia = Vigia()
        self._vigia_em = 0.0
        self.vigia_n8n = VigiaN8n()  # os n8n dos conectores estão de pé? (ADR 0038)
        self._n8n_em = 0.0
        self._n8n_conferindo = threading.Event()
        self.versoes = Versoes()  # atualizações pelo painel: a procura diária só avisa
        self._versoes_em = time.time() - versoes.DIA_S + versoes.PRIMEIRA_S
        self._versoes_procurando = threading.Event()
        self.consumo = Consumo(DADOS / "consumo.db", legado=ESTADO / "consumo.json")
        self.uso_ferramentas = UsoDeFerramentas(ESTADO / "uso-ferramentas.json")
        self.pergunta = ""  # a última pergunta de aprovação (o card de decisão do Barehands)
        self.turnos: list[dict[str, str]] = []  # a conversa atual, para a revisão
        self._gasto_do_turno: dict[str, Any] | None = None  # vai com a troca para a Conversa
        self._gastos_extras: list[dict[str, Any]] = []
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
        self.maquina.permissao = lambda: time.monotonic() < self._permissao_ate
        self.maquina.ze_perguntou = lambda: (
            str(getattr(self, "_ultimo_dito", "")).rstrip().endswith("?")
        )
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
            sobre=lambda: autoconhecimento.texto(self.retrato()),
            pesquisar=lambda pedido: pesquisa.pesquisar(
                pedido, carimbo(), DADOS / "cerebro", cfg["cerebro"]["modelo"], self._gastou
            ),
        )
        servidor = ferramentas.servidor(self.proprias)
        try:
            externos = mcp_externo.para_conversa(painel=mcp_externo.PAINEL)
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
        self.aparelhos_voz = AparelhosDeVoz()  # o app de voz do celular, pareado no painel
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
            escritas = acoes.escritas()
            self.portal = Portal(
                acoes.leituras(),
                escritas,
                envios=acoes.envios(),
                acesso=self.acesso,
                voz=self.voz_pelo_navegador,
                voz_app=self.voz_pelo_app,
                aparelhos_voz=self.aparelhos_voz,
                entrada_terminal=escritas["terminal/escrever"],
                saida_terminal=escritas["terminal/ler"],
                so_no_pc=senha.SO_NO_PC,
                servidor=maquina_atual.detectar().servidor,
                retorno_oauth=mcp_oauth.concluir_pela_volta,
                permissoes=self.sessoes.permissoes,
            )
            self.portal.iniciar()
            # Os pedidos de permissão das sessões do Claude chegam por esta rota (ADR 0039).
            self.sessoes.permissoes.endereco = f"{self.portal.endereco}sessoes/permissao"
            self.sessoes.permissoes.ao_decidir = self._permissao_decidida
            self.sessoes.permissoes.ao_pedir = self._permissao_pedida
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
                if (live := live_ativo(self)) is not None:
                    live.parar()
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
                self.turnos.append({"pessoa": texto, "jarvis": ""})
                self._gastos_extras = []  # o que as ferramentas desta mensagem gastarem
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
                self.motor_voz.aquecer()  # a conexão da voz abre enquanto o cérebro pensa
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
                perguntas = getattr(self, "_perguntas_permissao", {})
                if (alvo := perguntas.get(texto)) and texto.endswith("Aprovo?"):
                    # A pergunta de uma sessão (ou ela repetida, "não entendi"): o "sim" e o
                    # "não" logo depois a respondem, sem passar pelo cérebro (ADR 0039).
                    self._permissao_falada = alvo
                    self._permissao_ate = time.monotonic() + JANELA_PERMISSAO_S
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
                    self.latencias.contexto(turno, voz_por=self.motor_voz.ultimo)

                falado = falavel(para_fala(texto))
                if (live := live_ativo(self)) is not None and not self.voz.muda:
                    self.voz.numero += 1  # a mesma contagem: o aviso de ociosa vale para os dois
                    self._ultima_fala = self.voz.numero
                    live.falar(falado, self.voz.numero, ao_iniciar if turno else None)
                else:
                    self._ultima_fala = self.voz.falar(
                        falado, ao_iniciar=ao_iniciar if turno else None
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
                # Fila durável (Fase 7): o aviso sai quando o Zé voltar a ATIVO.
                log.info("aviso retido até ficar ativo: %d caracteres", len(texto))
                self._guardar(texto)

    def _gastou(self, uso: dict[str, Any], por: str) -> None:
        """Uma ferramenta que chama um modelo por fora (a pesquisa na internet): o gasto entra no
        consumo do dia e na mensagem em que ela rodou."""
        self.consumo.somar(uso, "pesquisa")
        if parte := gasto(uso, "pesquisa", por):
            self._gastos_extras.append(parte)

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
        if isinstance(evento, e.FalaAoVivo):
            self._pedido_ao_vivo(evento)
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
        tempo_real = live_ativo(self) is not None and not isinstance(evento, e.AoVivo)
        for efeito in self.maquina.tratar(evento, agora):
            if tempo_real and isinstance(efeito, e.Bip):
                # No Live a conversa é contínua, como numa ligação: o bipe de "sua vez" (depois de
                # um aviso, de uma pergunta, do chamado sozinho) só atrapalha. Fica o de conectar.
                continue
            self._executar(efeito)
        self._digitado_em = None
        if (live := live_ativo(self)) is not None:
            # A resposta acabou (o cérebro terminou, a pergunta de confirmação saiu ou o pedido não
            # deu em nada): a vez fecha e o Live volta a ouvir.
            m = self.maquina
            acabou = m.cerebro_terminou or m.estado not in (e.Estado.PENSANDO, e.Estado.FALANDO)
            live.acompanhar(acabou, self._pedidos_ao_vivo)
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
            if antes is e.Estado.PENSANDO:
                self._relatar_fala_perdida()
            if depois is e.Estado.PENSANDO:
                self._fala_perdida_s = 0.0
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
                self._descartar_escuta()  # conversa contínua: próxima pergunta sem "Ei Zé"

    def _pedido_ao_vivo(self, evento: e.FalaAoVivo) -> None:
        """Uma fala pelo Live: as latências do pedido (fim da fala, fim da vez, transcrito) e o
        registro do que foi ouvido, como no recorte de sempre (`_pedido_fechado`, `_transcrito`)."""
        self._pedidos_ao_vivo += 1
        if self.maquina.estado is e.Estado.OUVINDO:  # um pedido, não a resposta a uma pergunta
            self._fechar_latencia("interrompido")
            turno = self.latencias.iniciar("voz", evento.fim_fala_em)
            self._turno_atual = turno
            self.latencias.marcar(turno, "fim_fala", evento.fim_fala_em)
            self.latencias.marcar(turno, "pedido_fechado", evento.fechado_em)
            self.latencias.marcar(turno, "transcrito", evento.fechado_em)
            self.latencias.contexto(turno, fim_por="live", transcricao_por="deepgram")
        self.status.meio_transcricao = "live"
        if self.cfg["escuta"]["registrar_texto"]:
            log.info("transcrição (diagnóstico, live): %r", evento.texto)
        self._ouvido = evento.texto

    def _relatar_fala_perdida(self) -> None:
        """Ao vivo, o que a pessoa diz enquanto o Zé pensa não é ouvido (só o "Ei Zé" interrompe).
        Com o Codex o pensamento leva segundos, e isso parecia "surdez" (VPS, 16/10/2026): agora
        o registro e a Atividade dizem quanto foi perdido."""
        perdida, self._fala_perdida_s = self._fala_perdida_s, 0.0
        if perdida < FALA_PERDIDA_MIN_S:
            return
        log.info("fala perdida: %.1f s de voz enquanto o Zé pensava", perdida)
        atividade.PADRAO.registrar(
            "falha",
            "Fala não ouvida enquanto o Zé pensava",
            origem="voz",
            erro=f'{perdida:.0f} s de voz; espere a resposta ou diga "Ei Zé" para interromper',
        )

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
            if self.maquina.ao_vivo and self.maquina.estado is e.Estado.PENSANDO:
                amostras = np.frombuffer(dados, dtype="<i2").astype(np.float64)
                rms = float(np.sqrt((amostras**2).mean())) if len(amostras) else 0.0
                if 20 * np.log10(rms / 32768 + 1e-12) > FALA_PERDIDA_DBFS:
                    self._fala_perdida_s += len(dados) / 32000  # 80 ms por quadro
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

    # --- a pasta do Zé no Barehands e a curadoria das skills ----------------------------

    def _conexoes(self) -> pasta.Conexoes:
        c, r = self.cfg["cerebro"], self.cfg["revisao"]
        opcao = catalogo.OPCOES.get(self.provedor)
        nome = opcao.nome if opcao else self.provedor
        modelo = self.modelos().get(self.provedor, "")
        reserva = catalogo.OPCOES.get(c["reserva"])
        escuta = "Deepgram" if self.deepgram.disponivel else "desligada (sem chave do Deepgram)"
        livres = set(ferramentas.LIVRES)
        revisao = (
            f"{catalogo.rotulo(r['modelo'])}, até {r['max_por_dia']} por dia" if r["ligada"] else ""
        )
        return pasta.Conexoes(
            cerebro=f"{nome}, com o {modelo}" if modelo else nome,
            reserva=reserva.nome if reserva else c["reserva"],
            revisao=revisao,
            voz=f"fala pelo {self._fala_por()}, escuta pelo {escuta}",
            agora=self._agora_para_a_pasta(revisao),
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

    def retrato(self) -> autoconhecimento.Retrato:
        """O Zé agora, para ele mesmo responder e ajudar (ADR 0043). Sem segredos."""
        c = self.cfg["cerebro"]
        opcao = catalogo.OPCOES.get(self.provedor)
        nome = opcao.nome if opcao else self.provedor
        modelo = self.modelos().get(self.provedor, "")
        reserva = catalogo.OPCOES.get(c["reserva"])
        via = rapido.efetiva(self.cfg["via_rapida"])
        cerebro = self.cerebro
        roteado = isinstance(cerebro, rapido.Roteado) and cerebro.motor_ok
        modelo_rapido = str(cerebro.motor.modelo) if isinstance(cerebro, rapido.Roteado) else ""
        if via["ligada"]:
            quando = "só no Live" if via.get("quando", "live") == "live" else "sempre"
            motor = NOMES_DOS_MOTORES.get(str(via["motor"]), str(via["motor"]))
            rapidas = f"{motor}, com o {catalogo.rotulo(str(via['modelo']))}, {quando}"
            rapidas += "; respondendo agora" if roteado else ""
        else:
            rapidas = "desligadas (tudo vai ao cérebro completo)"
        live = live_ativo(self)
        if live is not None:
            onde = "o app do celular" if getattr(live.fonte, "do_app", False) else "o navegador"
            estado_live = (
                f"conectado agora, por {onde}: percebe o fim da fala pelo detector do LiveKit e "
                "dá para cortar o Zé falando por cima"
            )
        elif self.live.disponivel:
            estado_live = 'pronto; liga ao conectar a voz do aparelho (o botão "Conectar voz")'
        else:
            estado_live = f"indisponível ({self.live.erro or 'sem a chave do Deepgram'})"
        m = maquina_atual.detectar()
        endereco = getattr(getattr(self, "tunel", None), "endereco", "")
        cs = contas.Contas()
        return autoconhecimento.Retrato(
            cerebro=f"{nome}, com o {catalogo.rotulo(modelo)}" if modelo else nome,
            reserva=reserva.nome if reserva else str(c["reserva"]),
            rapidas=rapidas,
            rapidas_agora=roteado,
            rapidas_modelo=catalogo.rotulo(modelo_rapido) if roteado else "",
            voz=self._fala_por(),
            escuta=(
                "Deepgram nova-3, em português"
                if self.deepgram.disponivel
                else "desligada (sem a chave do Deepgram)"
            ),
            live=estado_live,
            modo=modo_fala.NOMES.get(self.modo_fala, self.modo_fala),
            ativacao=chamado.NOMES.get(self.chamado, self.chamado),
            espera=espera.NOMES.get(self.espera, self.espera),
            acesso=(
                f"pelo celular no endereço {endereco}, com senha e código"
                if endereco
                else "neste computador (o acesso de qualquer lugar está desligado)"
            ),
            contas=f"Claude: {cs.em_uso('claude').nome}; Codex: {cs.em_uso('codex').nome}",
            maquina=("um servidor sem tela" if m.servidor else "este computador")
            + f" ({m.sistema}{', com Omarchy' if m.omarchy else ''})",
            versao=__version__,
        )

    def _agora_para_a_pasta(self, revisao: str) -> str:
        try:
            r = self.retrato()
        except Exception:  # a nota não pode derrubar a pasta: sem retrato, o resumo de antes
            log.debug("retrato do Zé falhou", exc_info=True)
            return ""
        extras = [f"**Revisão em segundo plano:** {revisao or 'desligada'}"]
        return autoconhecimento.texto(dataclasses.replace(r, extras=extras))

    def _fala_por(self) -> str:
        ativo = self.motor_voz.ativo
        if ativo is None:
            return "Piper (Cadu)"
        nome = self.motor_voz.escolha.voz(ativo).get("nome", "")
        titulo = self.motor_voz.titulo(ativo)
        return f"{titulo} ({nome}), com o Cadu de reserva" if nome else titulo

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
        if not self.live.preparar():
            log.info(
                "Live indisponível (%s): a voz ao vivo usa o recorte de sempre", self.live.erro
            )
        self.memoria_longa.iniciar()
        self._avisar_interrompidas()
        self._ligar_voz_remota()
        if tunel.escolhido():  # o acesso de qualquer lugar continua depois de um reinício
            # O convite do primeiro acesso (servidor) abre o túnel antes da senha existir: é por
            # ele que a pessoa chega para criá-la (`python -m zervis.portal.primeiro_acesso`).
            # Num servidor, a senha basta para manter o endereço: sem ele, quem ainda não ligou o
            # código do autenticador ficaria trancado fora depois de um reinício.
            servidor = maquina_atual.detectar().servidor
            pronto = self.acesso.tem_senha and (self.acesso.tem_codigo or servidor)
            if pronto or self.acesso.convite_valido:
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

    def conversa_em_andamento(self) -> dict[str, str] | None:
        """O pedido em curso e o que o Zé já respondeu dele, antes de a troca ir para o histórico
        (ela só é gravada no fim): a Conversa mostra os dois na hora, como um chat."""
        estado = self.maquina.estado
        if not self.turnos or estado not in (
            e.Estado.PENSANDO,
            e.Estado.FALANDO,
            e.Estado.CONFIRMANDO,
        ):
            return None
        turno = self.turnos[-1]
        if turno is getattr(self, "_turno_gravado", None):
            return None
        quando = getattr(self, "_pedido_quando", None)
        return {
            "quando": quando.isoformat(timespec="seconds") if quando else "",
            "pessoa": turno["pessoa"],
            "ze": turno["jarvis"],
        }

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
        self.live.desligar()
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
