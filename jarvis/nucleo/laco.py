"""Laço do núcleo: liga microfone, detector, escuta, cérebro, voz e anel à máquina de estados.

Uma thread só trata eventos e quadros; o resto (presença, cérebro, voz, transcrição) roda em
threads próprias e fala com ela por uma fila de eventos. Os quadros do microfone chegam por
uma fila curta: se o laço atrasar, os mais velhos caem, mas o laço nunca espera rede.
"""

import asyncio
import concurrent.futures
import contextlib
import dataclasses
import json
import logging
import math
import os
import queue
import random
import struct
import subprocess
import threading
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from jarvis import lugares, usuario
from jarvis.automacoes import executor
from jarvis.automacoes.agenda import FUSO
from jarvis.automacoes.calendario import Calendario
from jarvis.automacoes.jobs import Job, Jobs
from jarvis.avisos.fila import Fila
from jarvis.cerebro import catalogo, ferramentas, mcp_externo, navegador, rapido
from jarvis.cerebro.base import Brain, Ponte
from jarvis.cerebro.baterias import Bateria, da_assinatura, do_omniroute
from jarvis.cerebro.claude import ClaudeBrain, carimbo
from jarvis.cerebro.consumo import Consumo, UsoDeFerramentas
from jarvis.cerebro.eco import Eco
from jarvis.config import Config
from jarvis.foco import ferramentas as foco_ferramentas
from jarvis.foco import tela as foco_tela
from jarvis.foco.frentes import Foco, FocoErro, Frente
from jarvis.habilidades import evidencias, revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import Skills
from jarvis.memoria import tempo
from jarvis.memoria.conversas import Conversas, publicar_dia
from jarvis.memoria.curta import Memoria
from jarvis.memoria.dias import SISTEMA as SISTEMA_DA_NOTA
from jarvis.memoria.dias import Dias
from jarvis.memoria.linha import LinhaDoTempo
from jarvis.nucleo import estados as e
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.monitor import Monitor
from jarvis.oficina.oficina import Oficina
from jarvis.oficina.orca import OrcaErro
from jarvis.oficina.sessoes import Sessao, Sessoes
from jarvis.portal.acoes import Acoes
from jarvis.portal.servidor import Portal
from jarvis.presenca.hyprland import MonitorPresenca
from jarvis.rosto import hud, manifesto, pasta, tela
from jarvis.rosto.anel import Anel, separar_emocao
from jarvis.rosto.painel import Painel
from jarvis.rosto.quadro import Quadro
from jarvis.rosto.rotina import retrato
from jarvis.rosto.teclado import Teclado
from jarvis.sistema import catalogo as catalogo_sistema
from jarvis.sistema.politica import Sistema
from jarvis.sistema.vigia import Eventos, Vigia
from jarvis.transporte.local import SERVIDOR, Captura
from jarvis.voz import piper
from jarvis.voz.ativacao import VAD, Detector, Features, SemAtivacao, carregar_modelo
from jarvis.voz.deepgram import Deepgram, EscutaDeepgram, EscutaErro
from jarvis.voz.escuta import DURACAO_QUADRO_S, Segmentador
from jarvis.voz.fala import falavel, para_fala, separar_fontes
from jarvis.voz.fim_de_turno import FimDeTurno
from jarvis.voz.latencia import Latencias
from jarvis.voz.saida import Voz

log = logging.getLogger(__name__)
ESTADO = lugares.ESTADO
DADOS = lugares.DADOS
PERSONA = Path(__file__).resolve().parents[2] / "persona" / "JARVIS.md"
PERSONA_RAPIDA = PERSONA.with_name("RAPIDO.md")
AVISO_RECENTE_S = 600.0  # aviso falado há mais que isso não é contexto do pedido
BATERIAS_S = 30.0  # releitura das cotas do OmniRoute
# Comandos locais de voz (sem o cérebro), por tipo. "{}" é o argumento do comando
# ("abrir_orbe:Guia" -> Guia). Os que pedem algo à página pelo maos-pedido: nome -> (pedido, fala).
AJUSTES_DA_TELA = {
    "calibrar_maos": ("calibrar", "Vamos calibrar. Siga as instruções na tela."),
    "maos_padrao": ("padrao", "Pronto, voltei à calibração e à câmera originais."),
    "brilho_mais": ("brilho:+", "Brilho da câmera aumentado."),
    "brilho_menos": ("brilho:-", "Brilho da câmera diminuído."),
    "brilho_liga": ("brilho:liga", "Filtro de brilho ligado."),
    "brilho_desliga": ("brilho:desliga", "Filtro de brilho desligado."),
    "tema_roxo": ("tema:roxo", "Pronto, tema roxo."),
    "tema_marinho": ("tema:marinho", "Pronto, tema marinho."),
    "tema_esmeralda": ("tema:esmeralda", "Pronto, tema esmeralda."),
    "tema_grafite": ("tema:grafite", "Pronto, tema grafite."),
    "tema_original": ("tema:original", "Pronto, cores originais de volta."),
    "configuracoes": ("config", "Configurações na tela."),
}
ORCA_AREAS = ("projetos", "agentes", "tarefas")
# O jeito do Zé (08/10/2026): o que ele diz quando dá uma voltinha e quando o usuário o roda
# demais com a mão. Frases variadas, sem gastar o cérebro.
FALAS_DA_VOLTINHA = (
    "Uma voltinha, como pedido!",
    "Trezentos e sessenta graus de puro charme.",
    "Pronto. Gostou do meu perfil?",
    "Ufa! Quase fiquei tonto.",
    "Olha eu aqui de novo.",
)
FALAS_DE_TONTO = (
    "Ei, estou ficando tonto!",
    "Ei, calma! Está tudo girando aqui.",
    "Opa, opa! Assim eu enjoo.",
    "Para, para! Já vi o mundo dar três voltas.",
    "Socorro, eu sou um holograma, não um pião!",
)
# Comandos que falam com o Orca ou rodam os testes: respondem quando terminarem.
EM_SEGUNDO_PLANO = ("manutencao_entrar", "manutencao_pedido", "rodada_melhoria", "reiniciar")
# Os que mostram algo no Núcleo (abrem a janela se ela estiver fechada): nome -> (ações, fala).
MOSTRAR_NA_TELA: dict[str, tuple[list[dict[str, Any]], str]] = {
    "nucleo_abrir": ([{"acao": "nucleo", "valor": "abrir"}], "Núcleo aberto."),
    "teclado_abrir": ([{"acao": "teclado", "valor": "abrir"}], "Teclado aberto; pode escrever."),
    "foco_mostrar": ([{"acao": "foco"}], "Seu foco na tela."),
    "visual_avatar": ([{"acao": "visual", "valor": "avatar"}], "Pronto, este sou eu."),
    "visual_anel": ([{"acao": "visual", "valor": "anel"}], "Pronto, o anel de volta."),
    "abrir_orbe": ([{"acao": "abrir", "alvo": "{}"}], "{} na tela."),
    # Projetos, agentes e tarefas moram no orbe Orca; conexões e memória, no Mapa.
    **{
        f"mostrar_{area}": (
            [{"acao": "abrir", "alvo": area.capitalize(), "orbe": "Orca"}]
            if area in ORCA_AREAS
            else [{"acao": "abrir_mapa"}, {"acao": "focar", "alvo": area}],
            "Está no Núcleo.",
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


def com_argumento(acoes: list[dict[str, Any]], argumento: str) -> list[dict[str, Any]]:
    return [{k: argumento if v == "{}" else v for k, v in a.items()} for a in acoes]


PASTA_S = 15.0  # a pasta do JARVIS no Barehands (só regrava a nota que mudou)
CURADORIA_S = 6 * 3600.0  # skills paradas vão para o arquivo
JANELA_FALADA = {"5 h": "na janela de cinco horas", "semana": "na semana", "mês": "no mês"}
FALHA_NO_CEREBRO = "Tive um problema para responder. Tente de novo em instantes."


def primeiro_de(*ganchos: Any) -> Any:
    """Junta ganchos (nome, entrada) -> valor: vale o primeiro que não devolver None."""

    def gancho(nome: str, entrada: dict[str, Any]) -> Any:
        for g in ganchos:
            if (valor := g(nome, entrada)) is not None:
                return valor
        return None

    return gancho


def ler_json(caminho: Path) -> dict[str, Any]:
    try:
        dados = json.loads(caminho.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def gravar_json(caminho: Path, dados: dict[str, object]) -> None:
    temporario = caminho.with_suffix(".next")
    temporario.write_text(json.dumps(dados, ensure_ascii=False))
    temporario.chmod(0o600)
    temporario.replace(caminho)


def criar_bip(caminho: Path) -> None:
    with wave.open(str(caminho), "wb") as w:
        w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        w.writeframes(
            b"".join(
                struct.pack("<h", int(2200 * math.sin(2 * math.pi * 660 * i / 16000)))
                for i in range(2400)
            )
        )


@dataclass
class Status:
    ultimo_erro: str | None = None
    erro_em: float = 0.0
    ativacoes: int = 0
    pedidos: int = 0
    meio_transcricao: str = ""
    tempos: dict[str, float | bool | None] = field(default_factory=dict)


class Nucleo:
    def __init__(self, cfg: Config, parar: threading.Event) -> None:
        self.cfg = cfg
        self.parar = parar
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
        self._fim_fala_em: float | None = None

        modelos = cfg.caminho("ativacao", "modelos_onnx")
        self.vad = VAD(modelos / "silero_vad.onnx")
        modelo_ativacao = carregar_modelo(cfg.caminho("ativacao", "modelo"))
        if not modelo_ativacao.treinada:
            log.warning(
                "sem a palavra de ativação treinada: o Zé atende pelo teclado e pelo painel"
            )
        self.detector = Detector(
            modelo_ativacao,
            Features(modelos / "melspectrogram.onnx", modelos / "embedding_model.onnx"),
            paciencia=cfg["ativacao"]["paciencia"],
        )
        limiar = cfg["escuta"]["limiar_fim_de_turno"]
        self.segmentador = Segmentador(
            fim_silencio_s=cfg["escuta"]["fim_silencio_s"],
            fim_de_turno=FimDeTurno(modelos / "smart-turn-v3.2-cpu.onnx") if limiar > 0 else None,
            limiar_fim_de_turno=limiar,
            pausa_consulta=max(1, round(cfg["escuta"]["pausa_fim_de_turno_s"] / DURACAO_QUADRO_S)),
        )
        self.transcricoes = concurrent.futures.ThreadPoolExecutor(1, "transcricao")
        # Só Deepgram (decisão de 09/10/2026): sem a chave o Zé não escuta; painel e teclado
        # continuam. Nada de modelo local de transcrição ocupando a máquina.
        self.deepgram = Deepgram(cfg.caminho("escuta", "chave_deepgram"))
        self.meio_transcricao = "deepgram"
        if not self.deepgram.disponivel:
            log.warning("sem a chave do Deepgram: voz desligada (painel e teclado funcionam)")
            self.detector.modelo = SemAtivacao()
            self.detector.limiar = SemAtivacao.limiar
        self.escuta: EscutaDeepgram | None = None  # o pedido atual em streaming
        self.transcrevendo: concurrent.futures.Future[str] | None = None

        self.captura = Captura(cfg["audio"]["microfone"])
        self.anel = Anel(cfg.caminho("barehands", "pasta_estado"))
        self.voz = Voz(onda=self.anel, abrir_fluxo=piper.PADRAO.abrir_fluxo)
        # A voz carrega em segundo plano: a primeira fala já a encontra pronta.
        threading.Thread(target=self._carregar_voz, name="carregar-voz", daemon=True).start()
        self._ultima_fala = 0
        self.voz.ao_ficar_ociosa = self._voz_ociosa
        self.fila = Fila(ESTADO / "avisos.json")  # durável: reinício não perde aviso
        self.jobs = Jobs(DADOS / "automacoes" / "jobs.json")
        self.calendario = Calendario(ESTADO / "agenda-avisada.json")
        self._rodando: set[str] = set()  # automações do tipo pergunta em execução
        self._agenda_em = 0.0
        self.avisos_falados: list[tuple[float, str]] = []
        self.eventos_sistema = Eventos(ESTADO / "eventos-sistema.jsonl")
        self.vigia = Vigia()
        self._vigia_em = 0.0
        self.consumo = Consumo(ESTADO / "consumo.json")
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
        self.oficina = Oficina(
            ESTADO / "oficina.json", raiz=cfg.caminho("oficina", "raiz_projetos")
        )
        self.monitor = Monitor(self.oficina, self._aviso_da_oficina, parar)
        # O Foco (08/10/2026): as frentes do usuário; a oficina avisa o que ele aprovou.
        self.foco = Foco(DADOS / "foco/frentes.json", self._foco_mudou)
        self.oficina.ao_mudar = self._oficina_mudou
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
        self.quadro = Quadro(lambda: self.maquina.estado is not e.Estado.INATIVO)
        self._fontes: tuple[int, list[str]] = (-1, [])
        self._evento_visto = (
            ""  # o último evento da página já tratado (id)  # marca da resposta, fontes guardadas
        )
        s = cfg["sistema"]
        forcados = {n: 4 for n in s["proibidos"]} | {n: 2 for n in s["confirmar"]}
        forcados |= {n: 1 for n in s["livres"]}
        self.sistema = Sistema(catalogo_sistema.carregar(forcados=forcados))
        self.tela = tela.Tela(cfg.caminho("barehands", "pasta_estado"))
        self.maquina.nucleo_em_foco = self.tela.em_foco
        self.manutencao = Manutencao(self.oficina, ESTADO / "manutencao")
        self.evidencias = evidencias.Evidencias(ESTADO / "evidencias.jsonl")
        self.maquina.manutencao = lambda: self.manutencao.ligado
        self.orbes = manifesto.ler(
            cfg.caminho("barehands", "pasta_estado").parent / "barehands.json"
        )
        self.maquina.orbes = manifesto.falados(self.orbes)
        self.proprias = ferramentas.montar(
            self.oficina,
            self.monitor,
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
                **externos.servidores,
            },
            (*ferramentas.LIVRES, *tempo.LIVRES, *foco_ferramentas.LIVRES, *externos.livres),
            bloqueadas=tuple(externos.bloqueadas),
            foto=lambda: self.memoria.foto() + "\n\n" + self.skills.catalogo(),
            prechecar=primeiro_de(
                ferramentas.prechecagem(self.memoria, self.skills),
                self.sistema.prechecar,
                navegador.prechecar,
            ),
            mostrar=ferramentas.mostrador(self.skills, self.quadro.apresentar, self.pendencias),
            descrever_extra=primeiro_de(
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
            PERSONA.read_text()
            + "\n\n"
            + usuario.PERFIL.para_persona()
            + "\n\n"
            + manifesto.para_persona(self.orbes),
            self._frase_do_cerebro,
            self._fim_do_cerebro,
            self._pedido_de_aprovacao,
            self._primeiro_texto_do_cerebro,
        )
        self.sessoes = Sessoes(
            DADOS / "sessoes",
            (Path.home(),),
            self._sessao_terminou,
            projetos_novos=cfg.caminho("oficina", "raiz_projetos"),
            skills=self.skills,
        )
        self.portal: Portal | None = None
        try:
            acoes = Acoes(self, ESTADO / "latencias", DADOS / "cerebro-teste")
            self.portal = Portal(acoes.leituras(), acoes.escritas(), envios=acoes.envios())
            self.portal.iniciar()
        except OSError as erro:
            log.warning("painel não subiu: %s", erro)
        self.bip = ESTADO / "bip.wav"
        criar_bip(self.bip)
        self.presenca = MonitorPresenca(
            lambda aberta: self.eventos.put(e.Presenca(aberta)),
            parar,
            classe=cfg["presenca"]["classe_janela"],
        )

    # --- callbacks de outras threads (só põem eventos na fila) --------------------------

    def _latencia_do_cerebro(self, marca: int) -> str | None:
        atual, turno = self._turno_cerebro
        return turno if marca == atual and marca == self.marca else None

    def _primeiro_texto_do_cerebro(self, marca: int, em: float) -> None:
        self.latencias.marcar(self._latencia_do_cerebro(marca), "primeiro_token", em)

    def _frase_do_cerebro(self, marca: int, frase: str) -> None:
        if marca == self.marca:
            # Depois de "Fontes:" o resto da resposta é a lista de links: tela, não voz.
            if self._fontes[0] != marca:
                self._fontes = (marca, [])
            if self._fontes[1]:
                self._fontes[1].append(frase)
                return
            frase, fontes = separar_fontes(frase)
            if fontes:
                self._fontes[1].append(fontes)
            emocao, frase = separar_emocao(frase)
            if emocao:
                self.anel.expressao(emocao, time.time())
            if not frase.strip():
                return
            self.latencias.marcar(self._latencia_do_cerebro(marca), "primeira_frase")
            if self.turnos:
                self.turnos[-1]["jarvis"] = (self.turnos[-1]["jarvis"] + " " + frase).strip()
            self.eventos.put(e.Frase(frase))

    def _voz_ociosa(self, numero: int) -> None:
        # Só a última fala pedida conta: o aviso atrasado de uma frase anterior não pode abrir
        # o microfone no meio da pergunta de confirmação (eco aprovando o próprio "sim").
        if numero >= self._ultima_fala:
            self.eventos.put(e.FalaOcioso())

    def _pedido_de_aprovacao(self, marca: int, descricao: str) -> None:
        if marca == self.marca:
            self.latencias.contexto(self._latencia_do_cerebro(marca), aprovacao=True)
            self.pergunta = descricao
            self.eventos.put(e.PedidoAprovacao(descricao))
        else:
            self.ponte.responder_aprovacao(False)  # pedido de uma resposta abandonada

    def _fim_do_cerebro(self, marca: int, erro: str | None) -> None:
        self.consumo.somar(getattr(self.cerebro, "uso", None), self.provedor)
        self.uso_ferramentas.somar(
            list(getattr(self.cerebro, "ferramentas_usadas", [])), time.time()
        )
        usadas = {n.rsplit("__", 1)[-1] for n in getattr(self.cerebro, "ferramentas_usadas", [])}
        if usadas and usadas <= {"tela_agir", "tela_ver"} and self.turnos:
            self.evidencias.registrar("so_tela", self.turnos[-1]["gabriel"])
        if erro:
            self.evidencias.registrar("falha_cerebro", erro)
        if marca != self.marca:
            return
        turno = self._latencia_do_cerebro(marca)
        if getattr(self.cerebro, "via", "") == "rapida":
            motor = self.cerebro.motor  # type: ignore[attr-defined]
            self.latencias.contexto(turno, provedor=f"rapida:{motor.nome}", modelo=motor.modelo)
        self.latencias.marcar(turno, "fim_cerebro")
        self.latencias.contexto(turno, erro_cerebro=bool(erro))
        if not erro and self.turnos and self.turnos[-1]["jarvis"]:
            self._registrar_turno(self.turnos[-1])
        if self._fontes[0] == marca and self._fontes[1]:
            corpo = "\n".join(self._fontes[1])
            threading.Thread(
                target=self.quadro.apresentar, args=("Fontes", corpo, 120), daemon=True
            ).start()
        if erro:
            self._erro(f"cérebro: {erro}")
            self.eventos.put(e.Frase(FALHA_NO_CEREBRO))
        self.eventos.put(e.RespostaFim())

    def _transcrito(self, futuro: concurrent.futures.Future[str], turno: str | None = None) -> None:
        try:
            texto = futuro.result()
        except Exception as erro:
            self._erro(f"transcrição: {type(erro).__name__}: {erro}")
            texto = ""
        self.latencias.marcar(turno, "transcrito")
        self.latencias.contexto(turno, transcricao_por=self.meio_transcricao)
        log.info(
            "transcrito em %.2f s (%s)",
            time.monotonic() - self._transcricao_inicio,
            self.meio_transcricao,
        )
        if self.cfg["escuta"]["registrar_texto"]:
            log.info("transcrição (diagnóstico): %r", texto)
        self.status.tempos["transcricao_s"] = round(time.monotonic() - self._transcricao_inicio, 2)
        self.status.meio_transcricao = self.meio_transcricao
        if not texto.strip():
            self.evidencias.registrar("transcricao_vazia")
        self.eventos.put(e.FimDeFala(texto))

    def _erro(self, mensagem: str) -> None:
        log.warning(mensagem)
        self.status.ultimo_erro = mensagem[:180]
        self.status.erro_em = time.time()

    # --- efeitos ------------------------------------------------------------------------

    def _abrir_latencia(self, rota: str) -> None:
        if self._digitado_em is not None:
            self._fechar_latencia("interrompido")
            self._turno_atual = self.latencias.iniciar("teclado", self._digitado_em)
            self.latencias.marcar(self._turno_atual, "pedido_fechado", self._digitado_em)
        self.latencias.contexto(self._turno_atual, rota=rota)

    def _fechar_latencia(self, resultado: str = "concluido") -> None:
        turno, self._turno_atual = self._turno_atual, None
        self.latencias.finalizar(turno, resultado)

    def _executar(self, efeito: e.Efeito) -> None:
        match efeito:
            case e.AbrirMicrofone():
                self.detector.reiniciar()
                self.vad.reiniciar()
                self.segmentador.limpar()
                self._fim_fala_em = None
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
            case e.EnviarAoCerebro(texto):
                self._abrir_latencia("cerebro")
                self.marca += 1
                self.status.pedidos += 1
                self._pedido_em = time.monotonic()
                self._conversa_suja = True
                self.turnos.append({"gabriel": texto, "jarvis": ""})
                self._pedido_quando = datetime.now(FUSO)
                pedido = self._com_avisos(self._com_nucleo(texto))
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
                if texto == self.maquina.aviso_falando:
                    # O cérebro não ouve a própria voz: sem isto, "pode aprovar" depois de um
                    # aviso chegava sem contexto (teste de 06/10/2026).
                    self.avisos_falados.append((time.monotonic(), texto))
                self.teclado.falou(texto)
                if texto == e.NAO_ENTENDI:
                    self.evidencias.registrar("nao_entendi")
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
                if aprovado and self.pergunta:
                    self._na_linha("aprovado", self.pergunta)
                self.ponte.responder_aprovacao(aprovado, fala)
            case e.Comando(nome):
                self._abrir_latencia(
                    "manutencao" if nome.startswith("manutencao_pedido:") else "comando"
                )
                self._comando(nome)
            case e.ReterAviso(texto):
                # Fila durável (Fase 7): o aviso sai quando o JARVIS voltar a ATIVO.
                log.info("aviso retido até ficar ativo: %d caracteres", len(texto))
                self.fila.guardar(texto)

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
            if (
                base.removeprefix("mostrar_") in ORCA_AREAS
                and "Orca" not in self.maquina.orbes.values()
            ):
                acoes = [{"acao": "abrir_mapa"}, {"acao": "focar", "alvo": base[8:]}]
            resposta = self._no_nucleo(com_argumento(acoes, argumento), pronto.format(argumento))
        elif base in FECHAR_NA_TELA:
            acoes, pronto = FECHAR_NA_TELA[base]
            resposta = self._se_aberto(com_argumento(acoes, argumento), pronto)
        elif base in EM_SEGUNDO_PLANO:
            # Falam com o Orca ou rodam os testes: a resposta sai quando terminar.
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
                resposta = m.encaminhar(argumento, self._contexto_da_manutencao(), time.time())
                self._na_linha("manutencao", f"Pedido à sessão de código: {argumento}")
            elif nome == "rodada_melhoria":
                resposta = self._rodada_de_melhoria()
            else:  # reiniciar
                _, resposta = m.reiniciar(revisado=argumento == "revisado")
        except (OrcaErro, OSError, subprocess.SubprocessError) as erro:
            log.warning("manutenção: %s", erro)
            resposta = "Não consegui falar com o Orca agora."
        self.eventos.put(e.Frase(resposta))
        self.eventos.put(e.RespostaFim())

    def _contexto_da_manutencao(self) -> str:
        partes = [self.tela.resumo()]
        if self.status.ultimo_erro and time.time() - self.status.erro_em < 3600:
            partes.append(f"Último erro do JARVIS: {self.status.ultimo_erro}.")
        return " ".join(partes)

    @staticmethod
    def _descrever_manutencao(nome: str, entrada: dict[str, Any]) -> str | None:
        """A frase da aprovação do modo manutenção (pelo cérebro, quando a frase escapou)."""
        if nome != f"mcp__{ferramentas.SERVIDOR}__modo_manutencao":
            return None
        if entrada.get("acao") == "entrar":
            agente = "Codex" if entrada.get("agente") == "codex" else "Claude"
            return (
                f"Vou ligar o modo manutenção com o {agente}; "
                "seus pedidos vão para a sessão de código."
            )
        return "Vou desligar o modo manutenção." if entrada.get("acao") == "sair" else None

    def _rodada_de_melhoria(self) -> str:
        """Junta as evidências do uso real e pede à sessão de código uma lista curta, sem fazer."""
        m = self.manutencao
        if not m.ligado:
            entrou = m.entrar("")
            if not m.ligado:
                return entrou
        agora = time.time()
        provas = self.evidencias.resumo(agora)
        if maos := evidencias.maos(self.tela.pasta / "maos-diagnostico.json"):
            provas += " " + maos
        corpo = (
            "Rodada de melhoria pedida pelo usuário. Evidências do uso real do JARVIS: "
            f"{provas} Proponha até cinco melhorias numeradas, da mais útil para a menos, cada "
            "uma com o problema que resolve e o risco. Não implemente nada ainda: o usuário "
            "aprova por voz quais fazer, e então faça uma por vez."
        )
        return m.encaminhar("rodada de melhoria", self._contexto_da_manutencao(), agora, corpo)

    def _manutencao_chegou(self, agora: float) -> None:
        """O que a sessão de código respondeu vira um aviso falado (na hora, se estiver livre)."""
        try:
            chegadas = self.manutencao.verificar(agora)
        except OSError as erro:
            log.warning("manutenção: %s", erro)
            return
        # O script do reinício seguro escreve o resultado depois que este processo já subiu.
        if (voltou := self.manutencao.resultado_do_reinicio()) is not None:
            self.eventos.put(e.Aviso(voltou))
        agente = self.manutencao.nome_do_agente
        for c in chegadas:
            if c.tipo == "pergunta":
                texto = f"O {agente} pergunta: {c.texto}"
                if not self.manutencao.ligado:
                    texto += " Entre no modo manutenção para responder."
            elif c.tipo == "demora":
                texto = "O pedido de manutenção passou de quarenta e cinco minutos; veja no Orca."
            else:
                texto = f"O {agente} terminou. {c.texto}"
                if c.protegidos:
                    texto += (
                        " Atenção: a mudança mexeu na zona protegida, nas regras do que eu faço "
                        "sem perguntar. Revise no Orca antes de valer."
                    )
                if c.mudou_codigo:
                    texto += " Para valer, diga: reinicia o JARVIS."
            log.info("manutenção: %s do pedido %s", c.tipo, c.pedido)
            self.eventos.put(e.Aviso(texto))

    def _na_linha(self, tipo: str, texto: str) -> None:
        """Um evento na linha do tempo; falha de disco não derruba nada."""
        try:
            self.linha.registrar(tipo, texto)
        except (OSError, ValueError) as erro:
            log.warning("linha do tempo: %s", erro)

    def _foco_mudou(self, o_que: str, frente: Frente) -> None:
        """Cada mudança de frente na linha do tempo; concluir é festa na tela."""
        self._na_linha("foco", f"{o_que}: {frente.titulo}")
        if o_que == "concluida" and self.tela.aberto():
            self.tela.enviar(
                [{"acao": "expressao", "valor": "alegria", "segundos": 5}, {"acao": "girar"}]
            )

    def _oficina_mudou(self, o_que: str, d: dict[str, str]) -> None:
        """O que ele aprova na oficina vira frente sozinho; o fim de um agente avança a frente."""
        try:
            projeto = d.get("projeto", "")
            if o_que == "projeto":
                self.foco.criar(projeto, "definir a primeira tarefa", projeto, origem="orca")
            elif o_que == "delegado":
                self.foco.criar(
                    projeto,
                    f"acompanhar o {d.get('agente', 'agente')}: {d.get('tarefa', '')[:100]}",
                    projeto,
                    origem="orca",
                )
            elif o_que == "concluido":
                self.foco.anotar_projeto(
                    projeto,
                    f"o {d.get('agente', 'agente')} terminou: {d.get('tarefa', '')[:80]}",
                    "revisar o que o agente entregou",
                )
        except (FocoErro, OSError) as erro:
            log.warning("foco: %s", erro)

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
        if self.foco.atual() is not None:
            partes.append(self.foco.onde_estava())
        hoje_marcos = [ev.texto for ev in self.linha.proximos(0, agora)]
        if hoje_marcos:
            partes.append("Hoje: " + "; ".join(hoje_marcos) + ".")
        if not partes:
            return
        with contextlib.suppress(OSError):
            marca.write_text(hoje)
        self.eventos.put(e.Aviso(usuario.PERFIL.vocativo("Bom dia") + ". " + " ".join(partes)))

    def _sessao_terminou(self, sessao: Sessao, resumo: str) -> None:
        """Uma sessão da oficina própria acabou de trabalhar: o Zé conta em uma frase."""
        if sessao.estado == "erro":
            self._aviso_da_oficina(f"A sessão {sessao.nome} falhou; veja no painel.")
        else:
            self._aviso_da_oficina(f"A sessão {sessao.nome} terminou: {resumo}")

    def _aviso_da_oficina(self, texto: str) -> None:
        """O que os agentes do Orca avisam também entra na linha do tempo."""
        self._na_linha("aviso", texto)
        self.eventos.put(e.Aviso(texto))

    def _registrar_turno(self, turno: dict[str, str]) -> None:
        """O pedido e a resposta, com a hora do pedido; a página do dia sai em segundo plano."""
        try:
            feito = self.conversas.registrar(turno["gabriel"], turno["jarvis"], self._pedido_quando)
        except OSError as erro:
            log.warning("conversas: %s", erro)
            return
        threading.Thread(
            target=publicar_dia, args=(self.conversas, feito.em.date()), daemon=True
        ).start()

    def _nota_do_dia(self, agora: float) -> None:
        """Depois das 5h, os dias sem nota ganham a nota (um modelo menor, uma vez por dia)."""
        if self._notas_em_curso or agora < self._proxima_nota:
            return
        self._proxima_nota = agora + 600
        faltando = self.dias.faltando(datetime.fromtimestamp(agora, FUSO))
        if faltando:
            self._notas_em_curso = True
            asyncio.run_coroutine_threadsafe(self._escrever_notas(faltando), self.ponte.laco)

    async def _escrever_notas(self, dias: list[Any]) -> None:
        try:
            r = self.cfg["revisao"]
            for dia in dias:
                resumo, uso = await revisao.perguntar_ao_modelo(
                    self.dias.prompt(dia), r["modelo"], DADOS / "cerebro", 0, SISTEMA_DA_NOTA
                )
                self.consumo.somar(uso, "nota do dia")
                if resumo.strip():
                    await asyncio.to_thread(self.dias.guardar, dia, resumo)
                    log.info("nota do dia %s escrita", dia)
        except Exception:
            log.exception("nota do dia falhou")
        finally:
            self._notas_em_curso = False

    def _foco_na_tela(self, agora: float) -> None:
        """Publica o quadro do Foco e aplica o que o usuário marcou nele (o "V")."""
        acoes, self._foco_lido = foco_tela.ler_acoes(self._foco_acoes, self._foco_lido)
        for acao in acoes:
            fala = foco_tela.aplicar(self.foco, acao)
            log.info("foco na tela: %s %s", acao.get("acao"), acao.get("id"))
            self.eventos.put(e.Aviso(fala))
        self.hud.gravar("foco", self.foco.quadro(), agora)

    def _evento_da_tela(self) -> None:
        """O que aconteceu na página e pede fala (o Zé ficou tonto): uma vez, se estiver livre."""
        evento = tela.evento_novo(self.tela.estado_bruto(), self._evento_visto, time.time())
        if evento is None:
            return
        self._evento_visto = str(evento["id"])
        if evento.get("tipo") == "tonto" and self.maquina.estado is e.Estado.ATIVO:
            log.info("tela: o Zé ficou tonto")
            self.eventos.put(e.Aviso(random.choice(FALAS_DE_TONTO)))  # noqa: S311 (só variar a fala)

    def _abrir_item(self, argumento: str) -> None:
        """ "abre o burrinho no Acervo": acha pelo nome falado (num orbe ou em todos) e diz."""
        orbe, _, nome = argumento.partition(":")
        acao: dict[str, Any] = {"acao": "abrir", "alvo": nome, **({"orbe": orbe} if orbe else {})}
        try:
            if not self.tela.aberto():
                self.tela.abrir()
            r = self.tela.agir([acao])
            feito = (r.get("resultados") or [{}])[0]
            if feito.get("ok"):
                resposta = f"{feito.get('abriu', nome).capitalize()} na tela."
            else:
                resposta = f"Não achei {nome}" + (f" no {orbe}." if orbe else " no Núcleo.")
                self.evidencias.registrar("nao_achei", f"{orbe or 'Núcleo'}: {nome}")
        except (tela.TelaErro, OSError):
            resposta = "Não consegui abrir; a minha tela não respondeu."
        self.eventos.put(e.Frase(resposta))
        self.eventos.put(e.RespostaFim())

    def _comando_especial(self, nome: str, argumento: str) -> str:
        """Os comandos que fazem mais do que mexer na tela."""
        if nome == "foco_onde":
            return self.foco.onde_estava()
        if nome == "foco_pendentes":
            return self.foco.falar_pendentes()
        if nome == "avatar_voltinha":
            return self._no_nucleo(
                [{"acao": "expressao", "valor": "alegria", "segundos": 4}, {"acao": "girar"}],
                random.choice(FALAS_DA_VOLTINHA),  # noqa: S311 (só variar a fala)
            )
        if nome == "nova_conversa":
            self.ponte.reiniciar()
            return "Certo, começando uma conversa nova."
        if nome == "mostrar_mapa":
            self.hud.abrir_mapa()
            return self._no_nucleo([])
        if nome == "janela_fechar":
            threading.Thread(target=self.tela.fechar, daemon=True).start()
            return "Fechei a minha janela; a câmera apagou."
        if nome == "trocar":
            return self.trocar_cerebro(argumento)
        if nome == "manutencao_sair":
            return self.manutencao.sair()
        if nome == "manutencao_situacao":
            return self.manutencao.situacao(time.time())
        return self.relatorio_de_baterias()

    def _se_aberto(self, acoes: list[dict[str, Any]], pronto: str) -> str:
        """Fecha ou recolhe algo na tela; com a janela fechada, não há o que fechar."""
        if not self.tela.aberto():
            return "A minha janela já está fechada."
        self.tela.enviar(acoes)
        return pronto

    def _no_nucleo(self, acoes: list[dict[str, Any]], pronto: str = "Está no Núcleo.") -> str:
        """Mostra algo no Núcleo sem o cérebro: traz a janela, ou abre a janela se fechada."""
        if self.tela.aberto():
            if acoes:
                self.tela.enviar(acoes)
            threading.Thread(target=self.tela.trazer, daemon=True).start()
            return pronto

        def abrir_e_mostrar() -> None:
            self.tela.abrir()
            if acoes:
                self.tela.enviar(acoes)

        threading.Thread(target=abrir_e_mostrar, daemon=True).start()
        return "Abrindo a minha janela."

    def _carregar_voz(self) -> None:
        try:
            piper.PADRAO.carregar()
        except Exception as erro:
            log.warning("voz indisponível: %s", erro)

    def _tocar_bip(self) -> None:
        try:
            subprocess.run(  # noqa: S603 (comando fixo, arquivo nosso)
                [
                    "/usr/bin/paplay",
                    "--server",
                    SERVIDOR,
                    "--device",
                    "@DEFAULT_SINK@",
                    str(self.bip),
                ],
                timeout=3,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError) as erro:
            self._erro(f"bip: {erro}")
        self._descartar_escuta()

    def _descartar_escuta(self) -> None:
        """O bip e a cauda da própria voz não podem virar começo do próximo pedido."""
        with contextlib.suppress(queue.Empty):
            while True:
                self.captura.quadros.get_nowait()
        self.segmentador.limpar()
        self.vad.reiniciar()

    # --- laço ---------------------------------------------------------------------------

    def tratar(self, evento: e.Evento) -> None:
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
                if (pendente := self.fila.tirar_tudo()) is not None:
                    self.eventos.put(e.Aviso(pendente))
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
            trecho = self.segmentador.quadro(dados, voz)
            if trecho is not None:
                self.status.tempos["fim_pelo_modelo"] = self.segmentador.fechou_pelo_modelo
                notas = " ".join(f"{n:.2f}" for n in self.segmentador.notas_do_ultimo)
                log.info(
                    "pedido fechado %s (fim de turno: %s)",
                    "pelo modelo" if self.segmentador.fechou_pelo_modelo else "pelo silêncio",
                    notas or "sem consulta",
                )
                self._transcricao_inicio = time.monotonic()
                turno = None
                if self.maquina.estado is e.Estado.OUVINDO:
                    fim = self._fim_fala_em or self._transcricao_inicio
                    self._turno_atual = turno = self.latencias.iniciar("voz", fim)
                    self.latencias.marcar(turno, "fim_fala", fim)
                    self.latencias.marcar(turno, "pedido_fechado", self._transcricao_inicio)
                    self.latencias.contexto(
                        turno,
                        fim_por="modelo" if self.segmentador.fechou_pelo_modelo else "silencio",
                    )
                self._fim_fala_em = None
                escuta, self.escuta = self.escuta, None
                self.transcrevendo = self.transcricoes.submit(self._transcrever, trecho, escuta)
                self.transcrevendo.add_done_callback(partial(self._transcrito, turno=turno))
            elif (
                self.maquina.estado is e.Estado.OUVINDO
                and not self.segmentador.em_fala
                and time.monotonic() > self.maquina.prazo
            ):
                self.tratar(e.Silencio())
        else:
            self._fechar_escuta()
            if self.maquina.detector_ligado and self.detector.processar(
                np.frombuffer(dados, dtype="<i2")
            ):
                log.info("ativação (nota %.3f)", self.detector.nota_disparo)
                self.tratar(e.Ativacao())

    def _fechar_escuta(self) -> None:
        """Parou de ouvir sem pedido (silêncio, janela fechada): a conexão fecha na hora."""
        if self.escuta is not None:
            self.escuta.cancelar()
            self.escuta = None

    def _transcrever(self, trecho: bytes, escuta: EscutaDeepgram | None) -> str:
        """O texto do pedido pelo Deepgram; sem ele (ou se falhar), vazio: o Zé diz que não
        entendeu e o usuário repete, ou usa o teclado."""
        if escuta is None:
            return ""
        try:
            texto = escuta.terminar()
            self.deepgram.contar(escuta)
            return texto
        except EscutaErro as erro:
            log.warning("Deepgram falhou (%s)", erro)
            return ""

    # --- cérebros e baterias (ADR 0010) -----------------------------------------------------

    def _com_via_rapida(self, cerebro: Brain) -> Brain:
        """A via rápida na frente do cérebro escolhido (docs/plano-voz-rapida.md)."""
        if isinstance(cerebro, Eco):
            return cerebro
        return rapido.envolver(
            cerebro,
            rapido.efetiva(self.cfg["via_rapida"]),
            DADOS / "cerebro-rapido",
            self.persona_rapida(),
            self.extras.foto,
        )

    def recarregar_conectores(self) -> str:
        """O painel mudou os conectores MCP: remonta o cérebro com eles (a conversa recomeça)."""
        try:
            novos = mcp_externo.carregar(painel=mcp_externo.PAINEL)
        except mcp_externo.McpInvalido as erro:
            return f"Conectores com erro: {erro}."
        antigos = self.externos
        mcp = {k: v for k, v in self.extras.mcp.items() if k not in antigos.servidores}
        livres = tuple(n for n in self.extras.livres if n not in antigos.livres)
        self.extras = dataclasses.replace(
            self.extras,
            mcp={**mcp, **novos.servidores},
            livres=(*livres, *novos.livres),
            bloqueadas=tuple(novos.bloqueadas),
        )
        self.externos = novos
        if self.provedor not in catalogo.OPCOES:
            return "Com o cérebro de teste os conectores não valem."
        try:
            novo = catalogo.criar(self.provedor, self.cfg, DADOS / "cerebro", self.extras)
        except catalogo.Indisponivel as motivo:
            return f"Não remontei o cérebro: {motivo}."
        cerebro = self._com_via_rapida(novo)
        self.ponte.trocar(cerebro)
        self.cerebro = cerebro
        ligados = ", ".join(novos.servidores) or "nenhum"
        log.info("conectores MCP recarregados: %s", ligados)
        return f"Pronto: o Zé agora usa os conectores {ligados}."

    def persona_rapida(self) -> str:
        return PERSONA_RAPIDA.read_text() + "\n\n" + usuario.PERFIL.para_persona()

    def aplicar_via_rapida(self) -> str:
        """O painel mudou a via rápida: troca só o motor, na hora; devolve um aviso ou ""."""
        if isinstance(getattr(self.cerebro, "completo", self.cerebro), Eco):
            return "Com o cérebro de teste não há via rápida."
        via = rapido.efetiva(self.cfg["via_rapida"])
        aviso = ""
        motor: rapido.Motor | None = None
        if via["ligada"]:
            try:
                motor = rapido.criar_motor(via, DADOS / "cerebro-rapido", self.extras.foto)
            except rapido.MotorErro as erro:
                aviso = f"Não montei a via rápida: {erro}."
            if motor is None and not aviso:
                aviso = "Falta a chave deste motor; sigo só com o cérebro completo."

        async def _trocar() -> Brain:
            async with self.ponte._troca():
                novo = await rapido.religar(
                    self.ponte.cerebro,
                    motor,
                    self.persona_rapida(),
                    self.extras.foto,
                    float(via["espera_s"]),
                    int(via["historico"]),
                )
                self.ponte.cerebro = novo
                return novo

        try:
            self.cerebro = asyncio.run_coroutine_threadsafe(_trocar(), self.ponte.laco).result(60)
        except Exception as erro:
            log.warning("via rápida: troca falhou (%s)", type(erro).__name__)
            return f"A troca falhou ({type(erro).__name__}); veja o log."
        log.info("via rápida: %s", f"{motor.nome} ({motor.modelo})" if motor else "desligada")
        return aviso

    def trocar_cerebro(self, id_: str) -> str:
        """Troca pedida por voz ou no Barehands; devolve a frase a falar."""
        atual = catalogo.OPCOES.get(self.provedor)
        if atual is None:
            return "Com o cérebro de teste não há troca."
        if id_ == self.provedor:
            return f"Já estou com o {atual.nome}."
        try:
            novo = catalogo.criar(id_, self.cfg, DADOS / "cerebro", self.extras)
        except catalogo.Indisponivel as motivo:
            log.warning("troca para %s recusada: %s", id_, motivo)
            return f"Não consegui trocar: {motivo}. Continuo com o {atual.nome}."
        log.info("cérebro: %s -> %s", self.provedor, id_)
        cerebro = self._com_via_rapida(novo)
        self.ponte.trocar(cerebro)
        self.cerebro, self.provedor = cerebro, id_
        with contextlib.suppress(OSError):
            catalogo.gravar_escolha(self.escolhido, id_)
        if id_ == "auto":
            return "Pronto, agora é o automático: o OmniRoute escolhe o modelo a cada pedido."
        nome = catalogo.OPCOES[id_].nome
        return f"Pronto, agora quem responde é o {nome}, com o {self.modelos()[id_]}."

    def modelos(self) -> dict[str, str]:
        """O modelo de cada opção; o do cérebro ativo é o que respondeu de fato, se já houver."""
        c = self.cfg["cerebro"]
        modelos = {
            "claude": catalogo.rotulo(c["modelo"]),
            "gpt": catalogo.rotulo(catalogo.OPCOES["gpt"].rota or ""),
            "gemini": catalogo.rotulo(catalogo.OPCOES["gemini"].rota or ""),
            "auto": self.modelo_auto or "OmniRoute escolhe",
        }
        usado = getattr(self.cerebro, "modelo_usado", None)
        if usado and self.provedor in modelos:
            modelos[self.provedor] = catalogo.rotulo(usado)
            if self.provedor == "auto":
                self.modelo_auto = modelos["auto"]
        return modelos

    def baterias(self) -> dict[str, Bateria]:
        baterias = dict(self.baterias_omniroute)
        if (claude := da_assinatura(self.limite_claude, time.time())) is not None:
            baterias["claude"] = claude
        return baterias

    def relatorio_de_baterias(self) -> str:
        baterias = self.baterias()
        partes = []
        for familia, nome in (("claude", "Claude"), ("gpt", "GPT"), ("gemini", "Gemini")):
            b = baterias.get(familia)
            if b is None:
                partes.append(f"{nome} sem dado")
            else:
                partes.append(f"{nome} com {b.restante}% {JANELA_FALADA.get(b.janela, '')}".strip())
        atual = catalogo.OPCOES.get(self.provedor)
        fim = f" Agora estou com o {atual.nome}, {self.modelos()[atual.id]}." if atual else ""
        return "Baterias: " + ", ".join(partes) + "." + fim + " " + self.consumo.resumo_falado()

    def _atualizar_painel(self, agora: float) -> None:
        completo = getattr(self.cerebro, "completo", self.cerebro)
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

    def _fim_da_conversa(self) -> None:
        """A conversa acabou: se valer a pena e houver cota no dia, o JARVIS revisa e aprende."""
        turnos, self.turnos = self.turnos, []
        r = self.cfg["revisao"]
        if not r["ligada"] or not revisao.vale_revisar(turnos):
            return
        hoje = time.strftime("%Y-%m-%d")
        if self._revisoes[0] != hoje:
            self._revisoes = (hoje, 0)
        if self._revisoes[1] >= r["max_por_dia"]:
            log.info("revisão pulada: limite de %d por dia", r["max_por_dia"])
            return
        self._revisoes = (hoje, self._revisoes[1] + 1)
        log.info("revisão da conversa (%d turnos) em segundo plano", len(turnos))
        asyncio.run_coroutine_threadsafe(self._revisar(turnos), self.ponte.laco)

    async def _revisar(self, turnos: list[dict[str, str]]) -> None:
        try:
            prompt = revisao.montar_prompt(turnos, self.memoria, self.skills)
            r = self.cfg["revisao"]
            saida, uso = await revisao.perguntar_ao_modelo(
                prompt, r["modelo"], DADOS / "cerebro", r["pensamento_tokens"]
            )
            self.consumo.somar(uso, "revisão")
            propostas = revisao.interpretar(saida, self.memoria, self.skills)
            for proposta in propostas:
                proposta.origem = revisao.origem(turnos)
        except Exception:
            log.exception("revisão falhou")
            return
        log.info("revisão: %d sugestões", len(propostas))
        if propostas:
            self.pendencias.adicionar(propostas)
            n = len(propostas)
            plural = "sugestão" if n == 1 else "sugestões"
            self.eventos.put(
                e.Aviso(
                    f"Aprendi algo na última conversa: {n} {plural} para você aprovar. "
                    "Quando quiser, peça para ver as sugestões."
                )
            )

    def _com_nucleo(self, texto: str) -> str:
        """Onde está o Núcleo e o que ele mostra, numa linha: o cérebro age sem perguntar."""
        try:
            return f"({self.tela.resumo()}) {texto}"
        except OSError:
            return texto

    def _com_avisos(self, texto: str) -> str:
        """Os avisos falados nos últimos minutos vão junto do pedido, como contexto."""
        recentes = [a for t, a in self.avisos_falados if time.monotonic() - t < AVISO_RECENTE_S]
        self.avisos_falados = []
        if not recentes:
            return texto
        lista = " | ".join(recentes[-3:])
        return f"(Você acabou de avisar o usuário, por voz: {lista}) {texto}"

    # --- automações e agenda (Fase 7) -------------------------------------------------------

    def _agendador(self, agora: float) -> None:
        momento = datetime.fromtimestamp(agora, FUSO)
        for job in self.jobs.vencidos(momento):
            if job.id in self._rodando:
                continue
            if job.tipo == "lembrete":
                log.info("automação %s: lembrete", job.id)
                self._na_linha("lembrete", job.texto)
                self.jobs.registrar(job.id, "ok", momento)
                self.eventos.put(e.Aviso(f"Lembrete: {job.texto}"))
            else:
                self._rodando.add(job.id)
                asyncio.run_coroutine_threadsafe(self._rodar_pergunta(job), self.ponte.laco)
        for texto in self.eventos_sistema.novos():
            log.info("evento do sistema: %s", texto)
            self.eventos.put(e.Aviso(texto))
        if agora - self._vigia_em >= 60:
            self._vigia_em = agora
            for texto in self.vigia.amostrar(agora):
                log.info("vigia: %s", texto)
                self.eventos.put(e.Aviso(texto))
        if agora - self._agenda_em >= 30:
            self._agenda_em = agora
            for texto, expira in self.calendario.vencidos(agora):
                log.info("agenda: %s", texto)
                if self.maquina.estado is e.Estado.ATIVO:
                    self.eventos.put(e.Aviso(texto))
                else:
                    self.fila.guardar(texto, "agenda", expira)  # some quando a reunião começa

    async def _rodar_pergunta(self, job: Job) -> None:
        momento = datetime.now(FUSO)
        try:
            texto, uso = await executor.executar(
                job.texto, self.cfg["cerebro"]["modelo"], DADOS / "cerebro", carimbo(momento)
            )
            self.consumo.somar(uso, "automação")
            self.jobs.registrar(job.id, "ok" if texto else "erro", momento)
            if texto:
                self.eventos.put(e.Aviso(texto))
        except Exception as erro:
            log.exception("automação %s falhou", job.id)
            self.jobs.registrar(job.id, "erro", momento, type(erro).__name__)
            self.eventos.put(e.Aviso(f"A automação {job.nome} falhou."))
        finally:
            self._rodando.discard(job.id)

    def _conversa_parada(self) -> None:
        """Muito tempo sem falar: a próxima pergunta começa uma sessão nova, com a memória."""
        limite_min = self.cfg["cerebro"]["nova_conversa_apos_min"]
        parado = time.monotonic() - self._pedido_em
        if (
            limite_min > 0
            and self._conversa_suja
            and parado > limite_min * 60
            and self.maquina.estado is e.Estado.ATIVO
        ):
            log.info("conversa parada há %.0f min: a próxima começa do zero", parado / 60)
            self._fim_da_conversa()
            self.ponte.reiniciar()
            self._conversa_suja = False

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

    def _atualizar_pasta(self, agora: float) -> None:
        """Fora da thread do laço: lê memória, skills, jobs e diário do disco."""
        if self._pasta_rodando is not None and not self._pasta_rodando.done():
            return
        if agora - self._pasta_em < PASTA_S:
            return
        self._pasta_em = agora
        curar = agora - self._curadoria_em >= CURADORIA_S
        if curar:
            self._curadoria_em = agora
        self._pasta_rodando = self._pasta_exec.submit(self._escrever_pasta, self._conexoes(), curar)

    def _escrever_pasta(self, conexoes: pasta.Conexoes, curar: bool) -> None:
        dias = self.cfg["skills"]["arquivar_apos_dias"]
        try:
            if curar and dias > 0:
                for nome in self.skills.arquivar_paradas(dias, time.time()):
                    log.info("curadoria: skill %s arquivada (sem uso há %.0f dias)", nome, dias)
                    self.diario.registrar(
                        "arquivada", f"a skill {nome}, sem uso há {dias:.0f} dias"
                    )
            notas = pasta.notas(
                conexoes,
                self.memoria,
                self.skills,
                dias,
                self.jobs,
                self.pendencias,
                self.diario,
                self.consumo,
            )
            if mudadas := self.pasta.gravar(notas):
                log.info("pasta do JARVIS: %s", ", ".join(mudadas))
            agora = time.time()
            self.hud.gravar("eficiencia", hud.eficiencia(self.consumo), agora)
            self.hud.gravar(
                "mapa",
                hud.mapa(
                    conexoes,
                    self.memoria,
                    self.skills,
                    self.jobs,
                    self.diario,
                    self.uso_ferramentas.ler(),
                    agora,
                ),
                agora,
            )
        except Exception:
            log.exception("pasta do JARVIS falhou")
        # Consulta somente leitura, limitada e fora do áudio. Falha do Orca não
        # esconde a memória nem transforma um estado antigo em agente online.
        try:
            rotina = retrato(self.oficina.tarefas.copy())
        except Exception:
            rotina = {"disponivel": False, "projetos": [], "agentes": [], "tarefas": []}
        self.hud.gravar("rotina", rotina, time.time())

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
        self.presenca.start()
        self.monitor.start()
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
                    self._agendador(agora)
                    self._atualizar_pasta(agora)
                    self._manutencao_chegou(agora)
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
        self.transcricoes.shutdown(wait=False, cancel_futures=True)
        self._pasta_exec.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            self.ponte.fechar()
        self.anel.mostrado = None
        self.anel.mostrar("idle", "green", time.time())
        gravar_json(ESTADO / "status.json", {"pid": os.getpid(), "estado": "parado"})
