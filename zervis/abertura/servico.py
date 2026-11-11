"""O lado do Zé na abertura (ADR 0078), pelo mesmo contrato de arquivos da Imersão (ADR 0045):

- `abertura.json`: o Zé grava o panorama do dia uma vez por minuto (a Imersão o serve em
  `GET /abertura`). O clima e as notícias vêm de um cache renovado em segundo plano;
- `abertura-falar.json`: a página grava `{montado, passo, ts}` (POST /abertura/falar) quando um
  painel aparece, e o Zé fala a fala daquele bloco. A página só escolhe o passo: o texto é
  sempre o do panorama que o próprio Zé montou.
"""

import contextlib
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from zervis import fuso, usuario
from zervis.abertura import ajustes, clima, noticias, panorama
from zervis.automacoes import calendario

log = logging.getLogger(__name__)
RETRATO_S = 60.0
EXTERNAS_S = 20 * 60.0  # o clima e as manchetes mudam devagar
FALA_VALE_S = 15.0  # pedido de fala mais velho que isso (Zé parado, reinício) não vale
CONVERSA_RECENTE_S = 24 * 3600.0
GUARDADOS = 4  # panoramas lembrados: a página pode ter carregado o anterior


class FontesDoDia(Protocol):
    """O que a coleta lê do núcleo (o `Nucleo` serve; os testes passam um falso)."""

    sessoes: Any
    jobs: Any
    calendario: Any
    caixa: Any
    prioridade: Any


def _sessoes(fontes: FontesDoDia) -> list[panorama.SessaoParada]:
    ativas = set(fontes.sessoes.trabalhando())
    lista = []
    for s in fontes.sessoes.listar():
        if s.origem == "manutencao":
            continue
        if s.id in ativas:
            situacao = "trabalhando"
        elif s.interrompida:
            situacao = "interrompida"
        elif s.limite:
            situacao = "limite"
        elif s.estado == "erro":
            situacao = "erro"
        else:
            continue
        lista.append(panorama.SessaoParada(s.nome, situacao))
    ordem = list(panorama.SITUACOES)
    return sorted(lista, key=lambda s: ordem.index(s.situacao))


def _hoje(fontes: FontesDoDia, agora: datetime) -> list[panorama.Item]:
    itens = []
    cache = getattr(fontes.calendario, "cache", calendario.CACHE)
    for evento in calendario.eventos(cache, agora.timestamp()):
        quando = datetime.fromtimestamp(float(evento["inicio"]), agora.tzinfo)  # type: ignore[arg-type]
        if quando.date() == agora.date() and quando >= agora - timedelta(minutes=10):
            itens.append(panorama.Item(quando, str(evento["titulo"]), "compromisso"))
    for job in fontes.jobs.listar():
        if not (job.ativo and job.proxima):
            continue
        quando = datetime.fromisoformat(job.proxima).astimezone(agora.tzinfo)
        if quando.date() == agora.date() and quando >= agora:
            itens.append(panorama.Item(quando, job.nome, "automacao"))
    return itens


def _conversas(fontes: FontesDoDia, agora: float) -> list[panorama.Conversa]:
    return [
        panorama.Conversa(c.nome, c.quando)
        for c in fontes.caixa.conversas(grupos=False)
        if c.sem_resposta
        and agora - c.quando < CONVERSA_RECENTE_S
        and not fontes.prioridade.calado(c.chat, c.telefone)
    ]


def coletar(fontes: FontesDoDia, agora: datetime) -> dict[str, Any]:
    """As partes do Zé; cada uma que falhar fica vazia (a abertura nunca cai por uma delas)."""

    def tentar(fazer: Callable[[], list[Any]]) -> list[Any]:
        try:
            return fazer()
        except Exception:
            log.debug("abertura: uma parte do dia falhou", exc_info=True)
            return []

    return {
        "hoje": tentar(lambda: _hoje(fontes, agora)),
        "sessoes": tentar(lambda: _sessoes(fontes)),
        "conversas": tentar(lambda: _conversas(fontes, agora.timestamp())),
    }


class Externas:
    """O clima e as manchetes, buscados fora do laço do Zé e guardados por 20 minutos."""

    def __init__(
        self,
        localizar: Callable[[str], clima.Lugar | None] = clima.localizar,
        buscar_clima: Callable[[clima.Lugar], clima.Clima | None] = clima.buscar,
        buscar_noticias: Callable[[], list[noticias.Noticia]] = noticias.buscar,
    ) -> None:
        self._localizar, self._clima, self._noticias = localizar, buscar_clima, buscar_noticias
        self.clima: clima.Clima | None = None
        self.noticias: list[noticias.Noticia] = []
        self._lugares: dict[str, clima.Lugar | None] = {}
        self._cidade = ""
        self._buscado = float("-inf")
        self._buscando: threading.Thread | None = None
        self.versao = 0  # sobe a cada busca terminada: o panorama é regravado na hora

    def renovar(self, cidade: str, agora: float) -> None:
        mudou = cidade != self._cidade
        if self._buscando is not None and self._buscando.is_alive():
            return
        if not mudou and agora - self._buscado < EXTERNAS_S:
            return
        self._cidade, self._buscado = cidade, agora
        self._buscando = threading.Thread(
            target=self._buscar, args=(cidade,), name="abertura-externas", daemon=True
        )
        self._buscando.start()

    def _buscar(self, cidade: str) -> None:
        if cidade and cidade not in self._lugares:
            self._lugares[cidade] = self._localizar(cidade)
        lugar = self._lugares.get(cidade) if cidade else None
        self.clima = self._clima(lugar) if lugar is not None else None
        if novas := self._noticias():
            self.noticias = novas
        self.versao += 1

    def esperar(self, prazo: float = 10.0) -> None:
        """Só para os testes e para a primeira abertura: a busca em andamento termina."""
        if self._buscando is not None:
            self._buscando.join(prazo)


class Abertura:
    def __init__(
        self,
        pasta: Path,
        fontes: FontesDoDia,
        externas: Externas | None = None,
        ler_ajustes: Callable[[], ajustes.Ajustes] = ajustes.ler,
    ) -> None:
        self.pasta = pasta
        self.fontes = fontes
        self.externas = externas or Externas()
        self.ler_ajustes = ler_ajustes
        self.retratado = float("-inf")
        self._versao = -1
        self.guardados: dict[str, list[str]] = {}  # montado -> as falas, na ordem dos blocos
        self._pedido = self.pasta / "abertura-falar.json"
        self._mtime = self._modificado()

    def cidade(self) -> str:
        return self.ler_ajustes().cidade or ajustes.cidade_do_fuso(str(fuso.local()))

    def montar(self, agora: datetime) -> dict[str, Any]:
        partes = coletar(self.fontes, agora)
        dia = panorama.montar(
            agora,
            usuario.ler().nome,
            self.externas.clima,
            partes["hoje"],
            partes["sessoes"],
            partes["conversas"],
            self.externas.noticias,
        )
        dia["ligada"] = self.ler_ajustes().ligada
        dia["musica"] = ajustes.musica() is not None
        return dia

    def retratar(self, agora: float, ja: bool = False) -> None:
        """Uma vez por minuto (ou `ja`): o panorama para a Imersão. Falhar não derruba o laço."""
        self.externas.renovar(self.cidade(), agora)
        novas = self.externas.versao != self._versao
        if not (ja or novas) and agora - self.retratado < RETRATO_S:
            return
        self.retratado, self._versao = agora, self.externas.versao
        try:
            dia = self.montar(datetime.fromtimestamp(agora, fuso.local()))
        except Exception:
            log.warning("abertura: o panorama do dia falhou", exc_info=True)
            return
        self.guardados[dia["montado"]] = [str(b["fala"]) for b in dia["blocos"]]
        while len(self.guardados) > GUARDADOS:
            self.guardados.pop(next(iter(self.guardados)))
        with contextlib.suppress(OSError):
            arquivo = self.pasta / "abertura.json"
            temporario = arquivo.with_suffix(".next")
            temporario.write_text(json.dumps({**dia, "ts": agora}, ensure_ascii=False))
            temporario.replace(arquivo)

    def _modificado(self) -> float:
        try:
            return self._pedido.stat().st_mtime
        except OSError:
            return 0.0

    def fala(self, agora: float | None = None) -> str | None:
        """A fala pedida pela página, uma vez só (barato: só lê se o arquivo mudou)."""
        if (mtime := self._modificado()) == self._mtime:
            return None
        self._mtime = mtime
        try:
            pedido = json.loads(self._pedido.read_text())
            agora = time.time() if agora is None else agora
            if agora - float(pedido["ts"]) > FALA_VALE_S:
                return None
            falas = self.guardados.get(str(pedido["montado"]))
            passo = int(pedido["passo"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if falas is None or not 0 <= passo < len(falas):
            return None
        return falas[passo] or None
