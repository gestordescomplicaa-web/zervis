"""Laço do núcleo: liga microfone, detector, escuta, cérebro, voz e anel à máquina de estados.

Uma thread só trata eventos e quadros; o resto (presença, cérebro, voz, transcrição) roda em
threads próprias e fala com ela por uma fila de eventos. Os quadros do microfone chegam por
uma fila curta: se o laço atrasar, os mais velhos caem, mas o laço nunca espera rede.
"""

import contextlib
import json
import logging
import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from jarvis import lugares
from jarvis.nucleo import estados as e

log = logging.getLogger(__name__)
ESTADO = lugares.ESTADO
DADOS = lugares.DADOS
PERSONA = Path(__file__).resolve().parents[1] / "persona" / "JARVIS.md"
PERSONA_RAPIDA = PERSONA.with_name("RAPIDO.md")
AVISO_RECENTE_S = 600.0  # aviso falado há mais que isso não é contexto do pedido
BATERIAS_S = 30.0  # releitura das cotas do OmniRoute
# Comandos locais de voz (sem o cérebro), por tipo. "{}" é o argumento do comando
# ("abrir_orbe:Guia" -> Guia). Os que pedem algo à página pelo maos-pedido: nome -> (pedido, fala).
VENDO_S = 6.0  # o painel avisa a sessão aberta a cada batida (~2 s)
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
# Comandos que falam com a sessão de manutenção ou rodam os testes: respondem quando terminarem.
CHAMADOS_GUARDADOS = 10  # os últimos sons que dispararam o chamado (ESTADO/chamados)
PRIMEIRA_FALA_S = 6.0  # depois do chamado, sem nenhuma fala nesse tempo, a escuta fecha
OFERTA_S = 45.0  # quanto tempo "sim", "próximo" e "depois" respondem a uma oferta de avisos
LIMITE_ESCRITO = 4000  # caracteres de um pedido escrito no painel
EM_SEGUNDO_PLANO = ("manutencao_entrar", "manutencao_pedido", "rodada_melhoria", "reiniciar")
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


def foto_da_memoria(memoria: Any, skills: Any = None) -> str:
    """O que o cérebro recebe no começo da conversa: a memória curta e a lista de skills."""
    texto = str(memoria.foto())
    return texto + ("\n\n" + str(skills.catalogo()) if skills is not None else "")


def versoes_das_skills(skills: Any) -> dict[str, float]:
    """Quando cada skill ligada mudou pela última vez (o SKILL.md): para saber se o cérebro tem
    uma versão velha na conversa."""
    if skills is None or not hasattr(skills, "listar"):
        return {}
    versoes = {}
    for nome, _ in skills.listar():
        with contextlib.suppress(OSError):
            versoes[nome] = (Path(skills.pasta) / nome / "SKILL.md").stat().st_mtime
    return versoes


def nivel_de_pico(audio: bytes, janela: int = 1600, segundos: float = 1.2) -> float:
    """O volume mais alto (dBFS) em janelas de 100 ms no fim do trecho: o chamado de verdade é
    alguém falando ao microfone; silêncio e som de fundo ficam bem abaixo."""
    x = np.frombuffer(audio, dtype="<i2").astype(np.float64)[-int(16000 * segundos) :]
    if len(x) < janela:
        return -120.0
    blocos = x[: len(x) // janela * janela].reshape(-1, janela)
    rms = np.sqrt((blocos**2).mean(axis=1)).max()
    return float(20 * np.log10(rms / 32768 + 1e-12))


def criar_toque(caminho: Path) -> None:
    """O toque antes de um aviso de sessão (ADR 0029): duas notas subindo, diferente do bip."""
    quadros = []
    for nota in (880, 1175):
        for i in range(1440):  # 90 ms cada
            envelope = min(1.0, i / 160, (1440 - i) / 400)
            quadros.append(
                struct.pack("<h", int(1800 * envelope * math.sin(2 * math.pi * nota * i / 16000)))
            )
    with wave.open(str(caminho), "wb") as w:
        w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        w.writeframes(b"".join(quadros))


@dataclass
class Status:
    ultimo_erro: str | None = None
    erro_em: float = 0.0
    ativacoes: int = 0
    pedidos: int = 0
    meio_transcricao: str = ""
    tempos: dict[str, float | bool | None] = field(default_factory=dict)
