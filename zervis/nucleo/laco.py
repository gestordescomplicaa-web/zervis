"""Laço do núcleo: liga microfone, detector, escuta, cérebro, voz e anel à máquina de estados.

Uma thread só trata eventos e quadros; o resto (presença, cérebro, voz, transcrição) roda em
threads próprias e fala com ela por uma fila de eventos. Os quadros do microfone chegam por
uma fila curta: se o laço atrasar, os mais velhos caem, mas o laço nunca espera rede.
"""

import collections
import concurrent.futures
import contextlib
import functools
import logging
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import atividade, versoes
from zervis.abertura.servico import Abertura, Externas
from zervis.atendimento import agente, cliente, projeto
from zervis.atendimento import ferramentas as atendente_ferramentas
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.calendario import Calendario
from zervis.automacoes.jobs import Jobs
from zervis.avisos import caixa, ligacoes, mensagens, pendentes, prioridade
from zervis.avisos import modo as modo_fala
from zervis.avisos.fila import Fila
from zervis.cerebro import (
    acesso,
    catalogo,
    ferramentas,
    mcp_externo,
    mcp_oauth,
    navegador,
    omniroute,
    pesquisa,
)
from zervis.cerebro.base import Ponte
from zervis.cerebro.baterias import Bateria
from zervis.cerebro.claude import carimbo
from zervis.cerebro.consumo import Consumo, UsoDeFerramentas, gasto
from zervis.cerebro.ferramentas import sessoes as ferramentas_sessoes
from zervis.cerebro.ferramentas import whatsapp as ferramentas_whatsapp
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
from zervis.nucleo import autoconhecimento, ciclo, efeitos, oficina3d, ouvir, retrato
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
from zervis.oficina import ponte as ponte_conectores
from zervis.oficina.manutencao import Manutencao
from zervis.oficina.progresso import Progresso
from zervis.oficina.sessoes import Sessoes
from zervis.oficina.supervisor import Oficina, caminho_padrao
from zervis.pesquisa import saude
from zervis.pesquisa.buscador import Buscador
from zervis.pesquisa.guardadas import Guardadas, guardando
from zervis.portal import senha, tunel
from zervis.portal.acoes import Acoes
from zervis.portal.senha import Acesso
from zervis.portal.servidor import Portal
from zervis.portal.voz_app import AparelhosDeVoz
from zervis.presenca import hyprland
from zervis.presenca import modo as modo_escuta
from zervis.presenca.hyprland import MonitorPresenca
from zervis.presenca.rostos import Rostos
from zervis.redes import instagram
from zervis.rosto import andamento, hud, manifesto, pasta, tela
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
from zervis.voz.eco_texto import EcoDeTexto
from zervis.voz.escuta import Segmentador
from zervis.voz.fim_de_turno import FimDeTurno
from zervis.voz.latencia import Latencias
from zervis.voz.live import Live
from zervis.voz.saida import Voz

log = logging.getLogger(__name__)


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
        self.ouvir_mesmo_muda: set[str] = set()  # avisos pedidos: saem no Silencioso
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
        self._rodando: set[str] = set()  # execuções de automação em andamento
        self._agenda_em = 0.0
        self.avisos_falados: list[tuple[float, str]] = []
        # Avisos que leem um texto de terceiros (a mensagem de um lead, ADR 0053): falados
        # inteiros, sem virar manchete, e o cérebro recebe só o resumo, nunca o texto.
        self.avisos_lidos: dict[str, str] = {}
        self.leads = pendentes.Pendentes()  # os leads do WhatsApp esperando a sua resposta
        self.caixa = caixa.Caixa()  # as conversas privadas recentes do WhatsApp (ADR 0054)
        self.prioridade = prioridade.Prioridade()  # quem o Zé vigia em tempo real (ADR 0055)
        self.ligacoes = ligacoes.Ligacoes(DADOS / "ligacoes.json")  # o que foi dito nas ligações
        self.ligacao_pendente: dict[str, str] | None = None  # quem espera você na linha
        self.ponte_ligacao: Any = None  # a ligação passada para o app de voz (ADR 0066)
        self.instagram = instagram.Instagram()  # métricas do Instagram, só leitura (ADR 0057)
        # A pesquisa profunda (ADR 0059): o SearXNG próprio e o vigia semanal das fontes de fora.
        self.buscador = Buscador()
        self.pesquisas = Guardadas()  # cada pesquisa feita, para o painel e a voz (ADR 0060)
        self.fontes_de_fora = saude.Vigia(
            lambda: saude.verificacoes(
                self.buscador, lambda: getattr(self, "central", None), lambda: self.instagram
            )
        )
        self._vigia_desde = time.monotonic()
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
        self._permissao_escolha = False  # a pergunta aberta é de um formulário (as opções)
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
        # A barra de carregamento (ADR 0064): o rótulo de cada ferramenta e quanto ela costuma
        # levar, das médias reais da Atividade e das latências (lidas em segundo plano).
        andamento.PADRAO.configurar(cfg.caminho("barehands", "pasta_estado"))
        threading.Thread(target=self._medir_andamento, name="andamento", daemon=True).start()
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
            # Os terminais num serviço à parte: reiniciar o Zé não derruba as sessões (ADR 0068).
            oficina=Oficina(caminho_padrao()),
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
        self.manutencao.contexto = lambda: self._contexto_da_manutencao()
        self.evidencias = evidencias.Evidencias(ESTADO / "evidencias.jsonl")
        self.maquina.oferta = lambda: time.monotonic() < self._oferta_ate
        self.maquina.permissao = lambda: time.monotonic() < self._permissao_ate
        self.maquina.escolha = lambda: self._permissao_escolha and self.maquina.permissao()
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
        # A oficina 3D: os projetos, a impressora com o vigia e o Modo TV (ADR 0082 a 0085).
        (
            self.projetos3d,
            self.impressora3d,
            self.vigia_impressora,
            self.camera,
            self.vigia_camera,
            self.tela_tv,
        ) = oficina3d.montar(
            cfg.caminho("oficina", "raiz_projetos"),
            self.imersivo.acervo,
            DADOS,
            lambda texto: self.eventos.put(e.Aviso(texto, pedido=True)),
            lambda: self.maquina.estado is e.Estado.FALANDO,
            lambda caminho, titulo: self.imagem_ao_aparelho(caminho, titulo),
        )
        self.ferramentas_por_grupo = ferramentas.por_grupo(
            self.sessoes,
            self.memoria,
            self.skills,
            self.pendencias,
            self.jobs,
            self.sistema,
            self.diario,
            self.tela,
            self.manutencao,
            sobre=lambda: autoconhecimento.texto(
                self.retrato(), self.capacidades(), self.historico()
            ),
            pesquisar=guardando(
                lambda pedido: pesquisa.pesquisar(
                    pedido, carimbo(), DADOS / "cerebro", cfg["cerebro"]["modelo"], self._gastou
                ),
                self.pesquisas,
            ),
            acervo=self.imersivo.acervo,
            leads=self,
            instagram=self.instagram,
            buscador=self.buscador,
            vigia=self.fontes_de_fora,
            pesquisas=self.pesquisas,
            projetos=self.projetos3d,
            impressora=self.impressora3d,
            tela_tv=self.tela_tv,
            camera_dispositivo=self.camera,
            vigia_camera=self.vigia_camera,
            mostrar_camera=lambda caminho, titulo: self.imagem_ao_aparelho(caminho, titulo),
            conversa_camera=(self.atender_camera, self.encerrar_camera),
        )
        self.proprias = [f for fs in self.ferramentas_por_grupo.values() for f in fs]
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
                ferramentas_whatsapp.prechecar(self),
                self.sistema.prechecar,
                navegador.prechecar,
            ),
            mostrar=ferramentas.mostrador(self.skills, self.quadro.apresentar, self.pendencias),
            descrever_extra=primeiro_de(
                ferramentas_sessoes.descritor(self.sessoes),
                self._descrever_manutencao,
                navegador.descrever,
                ferramentas.descritor(self.pendencias),
                ferramentas_whatsapp.descritor(self),
                self.sistema.descrever,
            ),
            autoaprovar=lambda nome, entrada: (
                self.sistema.autoaprovar(nome, entrada) or navegador.autoaprovar(nome, entrada)
            ),
            frase_exata=self.sistema.frase_exata,
            depois=navegador.ajustar,
            de_fora=ferramentas.de_fora,
            com_efeito=ferramentas.COM_EFEITO,
            autoaprovar_de_fora=navegador.autoaprovar,  # rolar a página não muda nada nela
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
        self.abertura = Abertura(  # ADR 0078
            cfg.caminho("barehands", "pasta_estado"),
            self,
            Externas(instagram=lambda: self.instagram, melhorias=self._melhorias_prontas),
        )
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
            ao_lead=self._lead_qualificado,
            continuar=self._continuar_lead,
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
                conectores=self.sessoes.ponte.atender,
            )
            self.portal.iniciar()
            # Os pedidos de permissão das sessões do Claude chegam por esta rota (ADR 0039).
            self.sessoes.permissoes.endereco = f"{self.portal.endereco}sessoes/permissao"
            self.sessoes.ponte.endereco = f"{self.portal.endereco}{ponte_conectores.CAMINHO}"
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
        efeitos._executar(self, efeito)

    def _gastou(self, uso: dict[str, Any], por: str) -> None:
        """Uma ferramenta que chama um modelo por fora (a pesquisa na internet): o gasto entra no
        consumo do dia e na mensagem em que ela rodou."""
        self.consumo.somar(uso, "pesquisa")
        if parte := gasto(uso, "pesquisa", por):
            self._gastos_extras.append(parte)

    def _comando(self, nome: str) -> None:
        efeitos._comando(self, nome)

    def _responder_depois(self, nome: str, argumento: str) -> None:
        efeitos._responder_depois(self, nome, argumento)

    # --- laço ---------------------------------------------------------------------------

    def tratar(self, evento: e.Evento) -> None:
        ouvir.tratar(self, evento)

    def _pedido_ao_vivo(self, evento: e.FalaAoVivo) -> None:
        ouvir._pedido_ao_vivo(self, evento)

    def _relatar_fala_perdida(self) -> None:
        ouvir._relatar_fala_perdida(self)

    def _quadro(self, dados: bytes) -> None:
        ouvir._quadro(self, dados)

    # --- cérebros e baterias (ADR 0010) -----------------------------------------------------

    def _atualizar_painel(self, agora: float) -> None:
        ciclo._atualizar_painel(self, agora)

    def _mostrar_decisao(self, agora: float) -> None:
        ciclo._mostrar_decisao(self, agora)

    # --- automações e agenda (Fase 7) -------------------------------------------------------

    # --- a pasta do Zé no Barehands e a curadoria das skills ----------------------------

    def _conexoes(self) -> pasta.Conexoes:
        return retrato._conexoes(self)

    def retrato(self) -> autoconhecimento.Retrato:
        return retrato.retrato(self)

    def capacidades(self) -> autoconhecimento.Capacidades:
        return retrato.capacidades(self)

    def historico(self, dias: int = 7) -> autoconhecimento.Historico:
        return retrato.historico(self, dias)

    def _melhorias_prontas(self) -> int:
        """Quantas mudanças o autodesenvolvimento tem para aprovar (a abertura, ADR 0078)."""
        m = self.manutencao.mudancas()
        return len(m.get("commits") or ()) or int(bool(m.get("arquivos")))

    def autoconhecimento(self) -> dict[str, Any]:
        """O retrato inteiro em dados, para a tela (ADR 0045)."""
        return autoconhecimento.dados(self.retrato(), self.capacidades(), self.historico())

    def _agora_para_a_pasta(self, revisao: str) -> str:
        return retrato._agora_para_a_pasta(self, revisao)

    def _fala_por(self) -> str:
        return retrato._fala_por(self)

    def _gravar_status(self, agora: float) -> None:
        ciclo._gravar_status(self, agora)

    def rodar(self) -> None:
        ciclo.rodar(self)

    @functools.cached_property
    def eco_texto(self) -> EcoDeTexto:
        """O que o Zé disse há pouco, se voltar pelo microfone transcrito (ADR 0062)."""
        return EcoDeTexto()

    @staticmethod
    def _medir_andamento() -> None:
        try:
            esperas = andamento.esperas_da_atividade(
                atividade.PADRAO.listar(limite=5000, tipos=("execucao",))
            )
            pensar = andamento.pensar_das_latencias(ESTADO / "latencias")
            andamento.PADRAO.configurar(andamento.PADRAO.pasta or ESTADO, esperas, pensar)
        except Exception:
            log.exception("andamento: médias não lidas; ficam os padrões")

    def _vigiar_fontes(self) -> None:
        ciclo._vigiar_fontes(self)

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
        self.vigia_camera.parar()
        self.captura.fechar()
        self.imersivo.parar()
        if self.remota is not None:
            self.remota.parar()
        self.livekit.parar()
        self.tunel.soltar()  # o túnel continua de pé: o endereço não muda
        self.mensagens.parar()
        self.buscador.parar()
        self.central.parar()  # só para de ouvir: a Central continua atendendo
        self.testes_do_atendente.parar()
        self.memoria_longa.parar()
        self.sessoes.ponte.parar()
        self.transcricoes.shutdown(wait=False, cancel_futures=True)
        self._pasta_exec.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            self.ponte.fechar()
        self.anel.mostrado = None
        self.anel.mostrar("idle", "green", time.time())
        gravar_json(ESTADO / "status.json", {"pid": os.getpid(), "estado": "parado"})
