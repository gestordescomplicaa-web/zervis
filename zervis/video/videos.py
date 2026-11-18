"""Os vídeos de Marketing (ADR 0106): do pedido ao MP4, em segundo plano.

1. **Roteiro:** o modelo escreve as cenas e as falas (`roteiro`), a partir de um tema ou de um
   artigo do blog, na linha editorial do site e no tom do estilo.
2. **Voz:** cada fala pela voz do painel (`narracao`); a linha do tempo sai dela.
3. **Trilha:** a música composta em código, abaixando sob a voz (`trilha`).
4. **Quadros e MP4:** a página do motor no Chromium, em paralelo, e o FFmpeg (`captura`,
   `montagem`). Os quadros são apagados no fim; ficam o MP4, a capa e o roteiro.

Um vídeo por vez (é o que mais pesa no Zé); o seguinte espera na fila. Publicar no Instagram é a
etapa 2 do plano; aqui o vídeo fica como rascunho, com a prévia e o download em Marketing.
"""

import asyncio
import base64
import json
import logging
import re
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares, marketing
from zervis.video import captura, estilos, montagem, narracao, roteiro, trilha

log = logging.getLogger(__name__)
PASTA = lugares.DADOS / "marketing" / "videos"
# O diretor: o plano de direção é uma chamada só, e a qualidade dele é o vídeo (ADR 0107).
MODELOS = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5"}
MODELO = "claude-opus-5-5"
PENSAMENTO = 3000  # tokens de raciocínio: contar as palavras e variar as cenas cabe aqui
SISTEMA = "Você é diretor de criação de vídeos curtos para empresas. Responda só com o JSON pedido."
LIMITE_ARTIGO = 9000
FORMATO = ("vertical", 1080, 1920)
ESTADOS = ("criando", "rascunho", "erro")
# O tempo mínimo de cada cena na tela, mesmo com a fala curta (uma lista precisa ser lida).
MINIMOS: dict[str, Callable[[dict[str, Any]], float]] = {
    "gancho": lambda c: 2.2,
    "frase": lambda c: 2.4,
    "passos": lambda c: 1.4 + 0.7 * len(c.get("passos", [])),
    "antes_depois": lambda c: 3.4,
    "conversa": lambda c: 1.4 + 1.0 * len(c.get("mensagens", [])),
    "lista": lambda c: 1.3 + 0.6 * len(c.get("itens", [])),
    "numero": lambda c: 3.0,
    "fecho": lambda c: 3.2,
}


class VideoErro(ValueError):
    """Um pedido que não pode seguir; a mensagem vai para a tela."""


@dataclass
class Video:
    id: str
    tema: str = ""
    artigo: str = ""
    instrucao: str = ""
    estilo: str = estilos.PADRAO
    voz: bool = True
    modelo: str = MODELO
    duracao_alvo: int = roteiro.DURACAO_PADRAO
    estado: str = "criando"
    etapa: str = "Na fila"
    erro: str = ""
    titulo: str = ""
    legenda: str = ""
    roteiro: dict[str, Any] = field(default_factory=dict)
    duracao: float = 0.0
    criado: float = field(default_factory=time.time)
    feito_em: float = 0.0


def _perguntar_ao_modelo(prompt: str, modelo: str) -> str:
    from zervis.habilidades import revisao

    saida, _uso = asyncio.run(
        revisao.perguntar_ao_modelo(prompt, modelo, lugares.DADOS / "cerebro", PENSAMENTO, SISTEMA)
    )
    return saida


def _ouvinte_do_ze() -> narracao.Ouvir | None:
    """O tempo real das palavras pelo Deepgram (a chave da escuta); sem a chave, None."""
    from zervis.voz import deepgram

    chave = deepgram.ler_chave(lugares.CONFIG / "deepgram.key")
    if not chave:
        return None
    return lambda wav: deepgram.palavras(chave, wav, "audio/wav")


def _sintetizador_do_ze() -> narracao.Sintetizar:
    from zervis.voz import nuvem

    return narracao.sintetizador(nuvem.Motor())


def _logo_como_dado(logo: bytes) -> str:
    """O logo da marca como data URI (SVG, PNG, JPEG ou WebP); vazio se não reconhecido."""
    if not logo:
        return ""
    cabeca = logo[:512].lstrip()
    if cabeca.startswith(b"<svg") or cabeca.startswith(b"<?xml"):
        tipo = "image/svg+xml"
    elif logo.startswith(b"\x89PNG"):
        tipo = "image/png"
    elif logo.startswith(b"\xff\xd8"):
        tipo = "image/jpeg"
    elif logo[8:12] == b"WEBP":
        tipo = "image/webp"
    else:
        return ""
    return f"data:{tipo};base64,{base64.b64encode(logo).decode('ascii')}"


class Videos:
    def __init__(
        self,
        pasta: Path = PASTA,
        site: marketing.Marketing | None = None,
        perguntar: Callable[[str, str], str] = _perguntar_ao_modelo,
        sintetizador: Callable[[], narracao.Sintetizar] = _sintetizador_do_ze,
        ouvinte: Callable[[], narracao.Ouvir | None] = _ouvinte_do_ze,
        capturar: Callable[..., list[Path]] = captura.capturar,
        montar: Callable[..., Path] = montagem.montar,
    ) -> None:
        self.pasta = pasta
        self.site = site or marketing.PADRAO
        self.perguntar = perguntar
        self.sintetizador = sintetizador
        self.ouvinte = ouvinte
        self.capturar = capturar
        self.montar = montar
        self._trava = threading.RLock()
        self._fila = threading.Lock()  # um vídeo por vez
        self._andando: set[str] = set()

    # --- guardar --------------------------------------------------------------------------

    def _dir(self, id_: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{8}", id_):
            raise VideoErro("Vídeo desconhecido.")
        return self.pasta / id_

    def _gravar(self, video: Video) -> Video:
        with self._trava:
            pasta = self._dir(video.id)
            pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporario = pasta / "video.json.next"
            temporario.write_text(json.dumps(asdict(video), ensure_ascii=False))
            temporario.replace(pasta / "video.json")
        return video

    def ler(self, id_: str) -> Video:
        try:
            dados = json.loads((self._dir(id_) / "video.json").read_text())
        except (OSError, ValueError) as erro:
            raise VideoErro("Vídeo não encontrado.") from erro
        video = Video(**{k: dados[k] for k in Video.__dataclass_fields__ if k in dados})
        if video.estado == "criando" and video.id not in self._andando:
            # o Zé reiniciou no meio: não fica preso em "criando"
            video.estado, video.etapa, video.erro = "erro", "", "Interrompido. Refaça o vídeo."
            self._gravar(video)
        return video

    def listar(self) -> list[Video]:
        if not self.pasta.is_dir():
            return []
        videos = []
        for p in self.pasta.iterdir():
            if (p / "video.json").is_file():
                try:
                    videos.append(self.ler(p.name))
                except VideoErro:
                    continue
        return sorted(videos, key=lambda v: v.criado, reverse=True)

    def arquivo(self, id_: str, qual: str = "video") -> Path:
        alvo = self._dir(id_) / ("capa.jpg" if qual == "capa" else "video.mp4")
        if not alvo.is_file():
            raise VideoErro("O vídeo ainda não está pronto.")
        return alvo

    def descartar(self, id_: str) -> None:
        video = self.ler(id_)
        if video.estado == "criando":
            raise VideoErro("Espere o vídeo terminar para descartar.")
        shutil.rmtree(self._dir(id_), ignore_errors=True)

    # --- criar ----------------------------------------------------------------------------

    @staticmethod
    def disponivel() -> str:
        """Vazio se dá para criar vídeos aqui; senão, o que falta."""
        if captura.navegador() is None:
            return "Falta o Chromium."
        if montagem.ffmpeg() is None:
            return "Falta o FFmpeg."
        return ""

    def criar(
        self,
        tema: str = "",
        artigo: str = "",
        estilo: str = estilos.PADRAO,
        voz: bool = True,
        esperar: bool = False,
        duracao: int = roteiro.DURACAO_PADRAO,
        modelo: str = MODELO,
    ) -> Video:
        tema, artigo = " ".join(tema.split())[:200], artigo.strip()
        if not tema and not artigo:
            raise VideoErro("Diga o tema do vídeo ou o artigo de origem.")
        if artigo and not self.site.artigo(artigo):
            raise VideoErro("Artigo não encontrado no blog.")
        if falta := self.disponivel():
            raise VideoErro(f"Vídeos indisponíveis: {falta.lower()}")
        if duracao not in roteiro.DURACOES:
            raise VideoErro("Duração inválida.")
        if modelo not in MODELOS:
            raise VideoErro("Modelo inválido.")
        video = Video(
            uuid.uuid4().hex[:8], tema, artigo, "", estilos.achar(estilo).id, voz, modelo=modelo,
            duracao_alvo=duracao,
        )  # fmt: skip
        return self._comecar(self._gravar(video), esperar)

    def refazer(self, id_: str, instrucao: str, esperar: bool = False) -> Video:
        video = self.ler(id_)
        if video.estado == "criando":
            raise VideoErro("Este vídeo ainda está sendo criado.")
        video.instrucao = " ".join(instrucao.split())[:400]
        video.estado, video.etapa, video.erro = "criando", "Na fila", ""
        return self._comecar(self._gravar(video), esperar)

    def _comecar(self, video: Video, esperar: bool) -> Video:
        self._andando.add(video.id)
        if esperar:
            self._fazer(video)
            return self.ler(video.id)
        threading.Thread(target=self._fazer, args=(video,), name="video", daemon=True).start()
        return video

    def _etapa(self, video: Video, texto: str) -> None:
        video.etapa = texto
        self._gravar(video)

    def _pedido(self, video: Video) -> str:
        if video.artigo:
            partes = [
                "Transforme este artigo do blog num Reels que explique a ideia principal e leve "
                "ao artigo e à oferta.",
                "## Artigo",
                self.site.artigo(video.artigo)[:LIMITE_ARTIGO],
            ]
        else:
            partes = [f"Tema: {video.tema}"]
        if video.instrucao and video.roteiro:
            anterior = json.dumps(video.roteiro, ensure_ascii=False)
            partes += [f"Versão anterior: {anterior}", f"Ajuste pedido: {video.instrucao}"]
        return "\n\n".join(partes)

    def _fazer(self, video: Video) -> None:
        try:
            with self._fila:
                self._produzir(video)
            video.estado, video.etapa, video.erro, video.feito_em = "rascunho", "", "", time.time()
            texto = f"O vídeo {video.titulo or video.tema} está pronto para assistir em Marketing."
        except (
            VideoErro, roteiro.RoteiroErro, captura.CapturaErro, montagem.MontagemErro, OSError,
        ) as erro:  # fmt: skip
            log.warning("vídeo %s: %s", video.id, erro)
            # um erro de disco ou de rede não vai cru para a tela
            motivo = (
                "Falha ao gravar ou ler os arquivos." if isinstance(erro, OSError) else str(erro)
            )
            video.estado, video.etapa, video.erro = "erro", "", motivo or "Falhou."
            texto = f"Não consegui criar o vídeo: {video.erro}"
        except Exception:  # um defeito não deixa o vídeo preso em "criando"
            log.exception("vídeo %s: falha inesperada", video.id)
            video.estado, video.etapa, video.erro = "erro", "", "Falhou."
            texto = "Não consegui criar o vídeo."
        finally:
            self._andando.discard(video.id)
            shutil.rmtree(self._dir(video.id) / "quadros", ignore_errors=True)
        self._gravar(video)
        if self.site.avisar is not None:
            self.site.avisar(texto)

    def _produzir(self, video: Video) -> None:
        pasta = self._dir(video.id)
        estilo = estilos.achar(video.estilo)
        marca = self.site.marca()
        nome = f"{marca.nome} (@{marca.instagram})" if marca.instagram else marca.nome

        self._etapa(video, "Escrevendo o roteiro")
        alvo = video.duracao_alvo
        prompt = roteiro.montar_prompt(nome, self._pedido(video), self.site.manual(), estilo, alvo)
        resposta = self.perguntar(prompt, video.modelo)
        try:
            r = roteiro.interpretar(resposta, estilo, alvo)
        except roteiro.RoteiroErro as erro:
            # uma volta: o modelo recebe o que escreveu e o que está errado (acontece com a fala
            # longa demais); se errar de novo, o vídeo fica com o erro
            log.info("vídeo %s: roteiro recusado (%s), pedindo de novo", video.id, erro)
            corrigir = (
                f"{prompt}\n\n## Sua resposta anterior foi recusada\n{erro}\n"
                f"Resposta anterior: {resposta[:6000]}\nEscreva de novo, corrigindo isso."
            )
            r = roteiro.interpretar(self.perguntar(corrigir, video.modelo), estilo, alvo)
        video.titulo, video.legenda, video.roteiro = r.titulo, r.legenda, r.para_json()

        self._etapa(video, "Gravando a voz" if video.voz else "Montando o tempo")
        minimos = [MINIMOS[c["tipo"]](c) if c["tipo"] in MINIMOS else 3.0 for c in r.cenas]
        n = narracao.narrar(
            r.falas,
            self.sintetizador() if video.voz else None,
            minimos,
            estilo.bpm,
            self.ouvinte() if video.voz else None,
        )
        video.duracao = n.duracao

        _, largura, altura = FORMATO
        cenas = []
        for c, (a, b), fala in zip(r.cenas, n.cenas, n.falas, strict=True):
            cena = {**c, "inicio": a, "fim": b, "palavras": fala["palavras"]}
            cena.update(roteiro.tempos_dos_gatilhos(cena, fala["palavras"]))
            cena["legenda"] = "cinetica" if c["tipo"] in roteiro.DE_TEXTO else "rodape"
            cenas.append(cena)
        dados = {
            "largura": largura, "altura": altura, "formato": FORMATO[0], "fps": captura.FPS,
            "duracao": n.duracao, "cenas": cenas, "falas": n.falas, "volume": n.volume,
            "marca": {
                "nome": marca.nome, "instagram": marca.instagram,
                "logo": _logo_como_dado(self.site.logo()), "cores": dict(marca.cores),
            },
            "estilo": {
                "id": estilo.id,
                "css": estilo.css.resolve().as_uri() if estilo.css else "",
                "js": estilo.js.resolve().as_uri() if estilo.js else "",
                "onda": estilo.onda and video.voz,
                "fontes": {
                    "titulo": marca.titulo or estilo.fonte_titulo,
                    "texto": marca.texto or estilo.fonte_texto,
                },
                "fontes_url": estilo.fontes_url(marca.titulo, marca.texto),
            },
        }  # fmt: skip
        arquivo_dados = pasta / "dados.js"
        arquivo_dados.write_text(f"window.VIDEO = {json.dumps(dados, ensure_ascii=False)};\n")

        self._etapa(video, "Compondo a trilha")
        mix = trilha.compor(
            n.duracao, [a for a, _ in n.cenas[1:]], n.voz if video.voz else None,
            estilo.bpm, estilo.energia,
        )  # fmt: skip
        trilha.gravar(mix, pasta / "trilha.wav")

        total = round(n.duracao * captura.FPS)
        self._etapa(video, f"Desenhando os quadros (0 de {total})")

        def progresso(feitos: int, de: int) -> None:
            self._etapa(video, f"Desenhando os quadros ({feitos} de {de})")

        quadros = self.capturar(
            captura.url_da_pagina(arquivo_dados), pasta / "quadros", largura, altura,
            duracao=n.duracao, progresso=progresso,
        )  # fmt: skip

        self._etapa(video, "Montando o vídeo")
        fim_gancho = n.cenas[0][1]
        capa = round(min(2.4, max(1.2, fim_gancho - 0.5)) * captura.FPS)
        self.montar(quadros, pasta / "trilha.wav", pasta / "video.mp4", capa)
        (pasta / "trilha.wav").unlink(missing_ok=True)

    # --- a tela ---------------------------------------------------------------------------

    def para_tela(self, video: Video) -> dict[str, Any]:
        dados = {
            k: getattr(video, k)
            for k in (
                "id", "tema", "artigo", "estilo", "voz", "estado", "etapa", "erro", "titulo",
                "legenda", "duracao", "criado", "modelo", "duracao_alvo",
            )
        }  # fmt: skip
        dados["cenas"] = len(video.roteiro.get("cenas", []))
        dados["pronto"] = (self.pasta / video.id / "video.mp4").is_file()
        return dados


PADRAO = Videos()
