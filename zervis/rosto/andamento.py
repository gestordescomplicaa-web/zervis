"""O andamento de um pedido (ADR 0064): a barra de carregamento da Imersão e do painel.

Enquanto o Zé pensa, não dá para saber quanto falta, mas dá para mostrar o que ele está fazendo e
quanto isso costuma levar. Cada ferramenta que começa grava aqui o rótulo ("Pesquisando na
internet") e o tempo esperado, que é a média real dela na Atividade; quando termina, a etapa
volta a ser "Pensando na resposta", com o tempo que o cérebro costuma levar. A página junta isso
ao estado do Zé (pensando, falando) e anda a barra como num jogo: rápida no começo, mais devagar
perto do fim, e só completa quando a resposta começa.

O arquivo é `andamento.json`, na pasta de estado da Imersão (o mesmo lugar do anel).
"""

import contextlib
import json
import logging
import statistics
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

NOME = "andamento.json"
PENSAR_S = 3.0  # sem histórico: o tempo até a primeira frase do cérebro
FERRAMENTA_S = 4.0  # sem histórico: uma ferramenta
ROTULOS = {
    "pesquisa_profunda": "Pesquisando a fundo na internet",
    "internet_pesquisar": "Pesquisando na internet",
    "pagina_ler": "Lendo a página",
    "empresa_cnpj": "Consultando o CNPJ",
    "pesquisas_guardadas": "Procurando nas pesquisas guardadas",
    "pesquisa_guardada": "Abrindo a pesquisa guardada",
    "fontes_saude": "Testando as fontes",
    "imagem_buscar": "Procurando imagens",
    "imagem_baixar": "Baixando a imagem",
    "pagina_capturar": "Tirando o print da página",
    "modelo3d_buscar": "Procurando um modelo 3D",
    "modelo3d_baixar": "Baixando o modelo 3D",
    "tela_explicar": "Montando a cena",
    "tela_agir": "Mexendo na tela",
    "tela_ver": "Olhando a tela",
    "whatsapp_conversas": "Olhando o WhatsApp",
    "whatsapp_ler": "Lendo a conversa",
    "whatsapp_buscar": "Procurando no WhatsApp",
    "whatsapp_contatos": "Procurando na agenda",
    "whatsapp_ligacoes": "Lendo as ligações",
    "whatsapp_ligacao": "Passando a ligação",
    "whatsapp_ligar": "Ligando",
    "whatsapp_responder": "Enviando no WhatsApp",
    "whatsapp_enviar": "Enviando no WhatsApp",
    "instagram_perfil": "Lendo o Instagram",
    "instagram_posts": "Analisando as publicações",
    "sessoes_listar": "Olhando as sessões",
    "sessao_ler": "Lendo a sessão",
    "sessao_enviar": "Falando com a sessão",
    "sessao_criar": "Abrindo a sessão",
    "sessao_renomear": "Renomeando a sessão",
    "historico_buscar": "Procurando no histórico",
    "sistema_executar": "Mexendo no computador",
    "automacao_lembrete": "Agendando o lembrete",
    "ze_sobre": "Olhando a minha configuração",
    "memoria": "Guardando na memória",
    "marketing_situacao": "Olhando o site e o blog",
    "marketing_pedir": "Abrindo o pedido de marketing",
    "marketing_abrir_pr": "Abrindo o PR no site",
    "marketing_publicar": "Publicando no site",
    "marketing_agendar": "Agendando os artigos",
    "marketing_posts": "Olhando os posts",
    "marketing_post_criar": "Criando o post",
    "marketing_post_refazer": "Refazendo o post",
    "marketing_post_publicar": "Publicando no Instagram",
}


def rotulo(nome: str) -> str:
    """O nome da ferramenta (mcp__jarvis__x) como frase curta para a tela."""
    curto = nome.rsplit("__", 1)[-1]
    return ROTULOS.get(curto) or curto.replace("_", " ").capitalize()


def esperas_da_atividade(registros: list[dict[str, Any]]) -> dict[str, float]:
    """A mediana da duração de cada ferramenta (em segundos), das execuções registradas."""
    por_nome: dict[str, list[float]] = {}
    for r in registros:
        nome, ms = str(r.get("ferramenta") or ""), r.get("duracao_ms")
        if nome and isinstance(ms, (int, float)) and r.get("tipo") == "execucao":
            por_nome.setdefault(nome.rsplit("__", 1)[-1], []).append(float(ms) / 1000)
    return {n: round(statistics.median(v[:50]), 1) for n, v in por_nome.items() if v}


def pensar_das_latencias(pasta: Path, maximo: int = 200) -> float:
    """A mediana do tempo até a primeira frase do cérebro, nos registros de latência."""
    tempos: list[float] = []
    for arquivo in sorted(pasta.glob("????-??-??.jsonl"), reverse=True)[:5]:
        try:
            linhas = arquivo.read_text().splitlines()
        except OSError:
            continue
        for linha in reversed(linhas):
            try:
                etapas = json.loads(linha).get("etapas_ms") or {}
            except ValueError:
                continue
            if "cerebro" in etapas:
                tempos.append((etapas["cerebro"] + etapas.get("formacao_frase", 0)) / 1000)
            if len(tempos) >= maximo:
                break
    return round(statistics.median(tempos), 1) if tempos else PENSAR_S


class Andamento:
    def __init__(self, pasta: Path | None = None, agora: Callable[[], float] = time.time) -> None:
        self.pasta = pasta
        self.agora = agora
        self.esperas: dict[str, float] = {}
        self.pensar_s = PENSAR_S
        self.atual: dict[str, Any] = {}
        self._trava = threading.Lock()

    def configurar(
        self, pasta: Path, esperas: dict[str, float] | None = None, pensar_s: float | None = None
    ) -> None:
        self.pasta = pasta
        if esperas is not None:
            self.esperas = esperas
        if pensar_s is not None:
            self.pensar_s = pensar_s

    def ferramenta(self, nome: str) -> None:
        """Uma ferramenta começou."""
        curto = nome.rsplit("__", 1)[-1]
        self._gravar(rotulo(nome), self.esperas.get(curto, FERRAMENTA_S))

    def pensando(self) -> None:
        """A ferramenta terminou: o cérebro volta a pensar na resposta."""
        self._gravar("Pensando na resposta", self.pensar_s)

    def para_tela(self) -> dict[str, Any]:
        return dict(self.atual)

    def _gravar(self, texto: str, esperado_s: float) -> None:
        agora = self.agora()
        with self._trava:
            self.atual = {"rotulo": texto, "esperado_s": max(0.5, esperado_s), "ts": agora}
            if self.pasta is None:
                return
            with contextlib.suppress(OSError):
                temporario = self.pasta / (NOME + ".next")
                temporario.write_text(json.dumps(self.atual, ensure_ascii=False))
                temporario.replace(self.pasta / NOME)


PADRAO = Andamento()
