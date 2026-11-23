"""Os vídeos de Marketing (ADR 0106, 0107 e 0109): do pedido ao Reels publicado.

1. **Roteiro:** o modelo escreve as cenas e as falas (`roteiro`), a partir de um tema ou de um
   artigo do blog, na linha editorial do site e no tom do estilo.
2. **Voz:** cada fala pela voz do painel (`narracao`); a linha do tempo sai dela.
3. **Trilha:** a música composta em código, abaixando sob a voz (`trilha`).
4. **Quadros e MP4:** a página do motor no Chromium, em paralelo, e o FFmpeg (`captura`,
   `montagem`). Os quadros são apagados no fim; ficam o MP4, a capa e o roteiro.

Um vídeo por vez (é o que mais pesa no Zé); o seguinte espera na fila. Pronto, o vídeo fica como
rascunho, com a prévia e o download em Marketing.

5. **Publicar** (ADR 0109): só com a aprovação de quem usa (quem chama já a recebeu). O MP4 sai
   por um link público temporário no endereço fixo do Zé (a Meta busca o vídeo), fechado logo
   depois; o Reels leva a legenda que o diretor escreveu e vai também ao feed. Se o Zé parar no
   meio, o vídeo não fica preso em "publicando": ele confere no perfil se o Reels saiu antes de
   deixar publicar de novo (nada de Reels em dobro).
"""

import asyncio
import base64
import contextlib
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
from zervis.marca import CORES_PADRAO, Marca
from zervis.portal import publico
from zervis.redes import instagram_publicar
from zervis.redes.instagram import Instagram, InstagramErro
from zervis.video import (
    biblioteca,
    captura,
    estilos,
    formatos,
    montagem,
    narracao,
    paleta,
    roteiro,
    trilha,
)
from zervis.video import fotos as fotos_mod

log = logging.getLogger(__name__)
PASTA = lugares.DADOS / "marketing" / "videos"
# O diretor: o plano de direção é uma chamada só, e a qualidade dele é o vídeo (ADR 0107).
MODELOS = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5"}
MODELO = "claude-opus-5-5"
PENSAMENTO = 3000  # tokens de raciocínio: contar as palavras e variar as cenas cabe aqui
# os modelos do Fish que um vídeo pode pedir (o seletor "Qualidade da voz")
MODELOS_VOZ = ("s2.1-pro", "drama-3", "s2-pro", "s2.1-pro-free")
# a memória do diretor: quantos vídeos recentes ele vê para não repetir a receita
RECENTES = 5
# o vídeo agendado sem tema da lista nem artigo novo: o diretor escolhe
TEMA_LIVRE = "Um assunto da linha editorial do site que os últimos vídeos ainda não trataram"
SISTEMA = "Você é diretor de criação de vídeos curtos para empresas. Responda só com o JSON pedido."
LIMITE_ARTIGO = 9000
FORMATO = ("vertical", 1080, 1920)
ESTADOS = ("criando", "rascunho", "erro", "publicando", "publicado")
REELS_S = (3.0, 90.0)  # a duração que a Meta aceita num Reels
LINK_DO_VIDEO_S = 25 * 60.0  # o link público fica aberto enquanto a Meta processa
# Um vídeo "publicando" sem dono só é conferido no Instagram depois disto (a Meta pode levar uns
# minutos para listar um Reels publicado logo antes de o Zé parar).
CONFERIR_APOS_S = 15 * 60.0
# O tempo mínimo de cada cena na tela, mesmo com a fala curta (uma lista precisa ser lida).
MINIMOS: dict[str, Callable[[dict[str, Any]], float]] = {
    "gancho": lambda c: 2.2,
    "frase": lambda c: 2.4,
    "passos": lambda c: 1.4 + 0.7 * len(c.get("passos", [])),
    "antes_depois": lambda c: 3.4,
    "conversa": lambda c: 1.4 + 1.0 * len(c.get("mensagens", [])),
    "lista": lambda c: 1.3 + 0.6 * len(c.get("itens", [])),
    "numero": lambda c: 3.0,
    "fecho": lambda c: 3.4,
    "icone": lambda c: 2.6,
    "conexao": lambda c: 1.2 + 0.8 * len(c.get("nos", [])),
    "hub": lambda c: 1.6 + 0.55 * len(c.get("ao_redor", [])),
    "caos": lambda c: 3.4,
    "foto": lambda c: 2.8,
    "item": lambda c: 2.6,
    "visual": lambda c: 0.9 + 0.75 * len(c.get("batidas", [])),
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
    permalink: str = ""  # o link do Reels publicado
    publicado: float = 0.0
    publicando_desde: float = 0.0  # epoch: quando o pedido de publicar saiu
    locutor: str = ""  # "" a voz da página Voz; "cadu"; ou o id de uma voz do Fish (ADR 0113)
    modelo_voz: str = ""  # o modelo do Fish deste vídeo; "" o da página Voz
    linha: str = ""  # "empresarios" ou "ferramenta"; vazio: o diretor escolhe (ADR 0116)
    entrega: str = ""  # o que quem comentar recebe, se quem pediu disse; vazio: o diretor sugere
    palavra: str = ""  # a palavra para comentar, se quem pediu disse


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


def _sintetizador_do_ze(locutor: str = "", modelo: str = "") -> narracao.Sintetizar:
    from zervis.voz import nuvem

    return narracao.sintetizador(nuvem.Motor(), locutor, modelo)


def _vozes_do_fish() -> list[dict[str, str]]:
    """As vozes do Fish Audio da página Voz (as suas e as mais usadas em português)."""
    from zervis.voz import fish
    from zervis.voz.deepgram import ler_chave

    chave = ler_chave(lugares.CONFIG / f"{fish.NOME}.key")
    return fish.vozes(chave) if chave else []


def efeitos_sonoros(cenas: list[dict[str, Any]]) -> list[tuple[float, str]]:
    """O som de cada ação na tela (ADR 0113): o corte seco bate, a carta estala com o whoosh,
    as outras transições passam com o whoosh; as palavras do gancho em cortes estalam e o
    carimbo bate."""
    efeitos: list[tuple[float, str]] = []
    for i, c in enumerate(cenas):
        a = float(c["inicio"])
        if i:
            transicao = c.get("transicao")
            if transicao == "corte":
                efeitos.append((a, "impacto"))
            else:
                efeitos.append((a, "whoosh"))
                if transicao in ("carta", "baralho"):
                    efeitos.append((a + 0.25, "estalo"))
        palavras = c.get("palavras") or []
        if c.get("composicao") == "cortes":
            efeitos += [(float(w["i"]), "estalo") for w in palavras[1:] if len(w["p"]) > 2]
        elif c.get("composicao") == "carimbo" and palavras:
            marcadas = {roteiro.base(p) for p in str(c.get("destaque", "")).split()}
            alvo = next((w for w in palavras if roteiro.base(w["p"]) in marcadas), palavras[-1])
            efeitos.append((float(alvo["i"]), "impacto"))
    return efeitos


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
        sintetizador: Callable[..., narracao.Sintetizar] = _sintetizador_do_ze,
        ouvinte: Callable[[], narracao.Ouvir | None] = _ouvinte_do_ze,
        capturar: Callable[..., list[Path]] = captura.capturar,
        montar: Callable[..., Path] = montagem.montar,
        instagram: Instagram | None = None,
        links: publico.Publicos = publico.PADRAO,
        endereco: Callable[[], str] | None = None,
        publicar_reels: Callable[..., str] = instagram_publicar.publicar_reels,
        procurar: Callable[[Instagram, str, float], str] = instagram_publicar.procurar,
        fotos: fotos_mod.Fotos | None = None,
        vozes_do_fish: Callable[[], list[dict[str, str]]] = _vozes_do_fish,
        capturar_site: Callable[[str, Path], dict[str, Any]] | None = None,
    ) -> None:
        self.pasta = pasta
        self.site = site or marketing.PADRAO
        self.perguntar = perguntar
        self.sintetizador = sintetizador
        self.ouvinte = ouvinte
        self.capturar = capturar
        self.montar = montar
        self._instagram = instagram
        self.links = links
        self._endereco = endereco
        self._publicar_reels = publicar_reels
        self._procurar = procurar
        self.fotos = fotos or fotos_mod.PADRAO
        self._vozes_do_fish = vozes_do_fish
        self._capturar_site = capturar_site
        self._vozes_cache: tuple[float, list[dict[str, str]]] = (0.0, [])
        self._trava = threading.RLock()
        self._fila = threading.Lock()  # um vídeo por vez
        self._andando: set[str] = set()
        self._publicando: set[str] = set()

    @property
    def instagram(self) -> Instagram:
        if self._instagram is None:
            from zervis import marketing_posts

            self._instagram = marketing_posts.PADRAO.instagram  # a mesma conta dos posts
        return self._instagram

    def endereco(self) -> str:
        if self._endereco is not None:
            return self._endereco()
        from zervis import marketing_posts

        return marketing_posts.endereco_publico()

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
        elif video.estado == "publicando" and video.id not in self._publicando:
            video = self._conferir_publicacao(video)
        return video

    def _conferir_publicacao(self, video: Video) -> Video:
        """Um "publicando" sem dono (o Zé parou no meio): depois de um tempo, confere no perfil
        se o Reels saiu. Saiu: publicado. Não saiu (ou sem resposta): volta a rascunho, com o
        aviso para conferir antes de publicar de novo."""
        if time.time() - video.publicando_desde < CONFERIR_APOS_S:
            return video
        link = ""
        try:
            link = self._procurar(self.instagram, video.legenda, video.publicando_desde)
        except (InstagramErro, OSError) as erro:
            log.warning("vídeo %s: não consegui conferir a publicação (%s)", video.id, erro)
        if link:
            video.estado, video.permalink, video.publicado, video.erro = (
                "publicado", "" if link == "publicado" else link, time.time(), "",
            )  # fmt: skip
        else:
            video.estado = "rascunho"
            video.erro = "A publicação foi interrompida. Confira no Instagram antes de publicar."
        return self._gravar(video)

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

    # --- o locutor dos vídeos (ADR 0113) ---------------------------------------------------

    def vozes(self) -> list[dict[str, str]]:
        """As vozes que um vídeo pode ter: a do Zé, o Cadu e as suas do Fish (lista guardada 10
        min; o Fish fora do ar não tira as outras). Só as suas: a biblioteca popular do Fish tem
        vozes que imitam pessoas reais, e um vídeo de marca não fala com a voz de ninguém."""
        quando, fish = self._vozes_cache
        if time.time() - quando > 600:
            try:
                fish = self._vozes_do_fish()
            except (OSError, ValueError, RuntimeError):  # rede ou chave: a lista fica sem o Fish
                log.info("vozes do Fish indisponíveis", exc_info=True)
                fish = []
            self._vozes_cache = (time.time(), fish)
        suas = [v for v in fish if str(v.get("detalhe", "")).startswith("sua")]
        return [
            {"id": "", "nome": "Voz do Zé", "detalhe": "a da página Voz"},
            {"id": narracao.CADU, "nome": "Cadu", "detalhe": "local"},
            *suas,
        ]

    # --- a paleta dos vídeos (ADR 0117): a da marca ou a de um site ------------------------

    def paleta(self) -> dict[str, Any]:
        return paleta.ler(self.pasta / "paleta.json")

    def paleta_do_site(self, url: str) -> dict[str, Any]:
        """Abre o site, tira as cores e passa a usá-las nos vídeos."""
        if not url.strip():
            raise VideoErro("Diga o endereço do site.")
        pasta = self.pasta / "paleta"
        try:
            if self._capturar_site is not None:
                cores = paleta.do_site(url, pasta, self._capturar_site)
            else:
                cores = paleta.do_site(url, pasta)
        except paleta.PaletaErro as erro:
            raise VideoErro(str(erro)) from erro
        finally:
            shutil.rmtree(pasta, ignore_errors=True)  # o print não fica
        escolha = {"origem": "site", "url": url.strip()[:200], "cores": cores}
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "paleta.json").write_text(json.dumps(escolha))
        return self.paleta()

    def paleta_da_marca(self) -> dict[str, Any]:
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "paleta.json").write_text(json.dumps({"origem": "marca"}))
        return self.paleta()

    def _cores(self, marca: Marca) -> dict[str, str]:
        """As cores do vídeo: as da marca ou as do site escolhido, com a tinta e o papel."""
        escolha = self.paleta()
        cores = {**CORES_PADRAO, **dict(marca.cores)}
        if escolha["origem"] == "site":
            cores.update(escolha["cores"])
        return {**cores, **paleta.tinta_e_papel(cores)}

    def _sintetizador(self, video: Video) -> narracao.Sintetizar:
        if video.modelo_voz:
            return self.sintetizador(video.locutor, video.modelo_voz)
        return self.sintetizador(video.locutor) if video.locutor else self.sintetizador()

    # --- as escolhas do cartão Vídeos (lembradas entre uma visita e outra) ------------------

    def preferencias(self) -> dict[str, Any]:
        """O que quem usa escolheu por último no cartão Vídeos; vale também para os vídeos
        agendados e os pedidos pela voz (quando eles não dizem o contrário)."""
        try:
            dados = json.loads((self.pasta / "preferencias.json").read_text())
        except (OSError, ValueError):
            dados = {}
        dados = dados if isinstance(dados, dict) else {}
        duracao = dados.get("duracao")
        return {
            "linha": dados["linha"] if dados.get("linha") in formatos.LINHAS else "",
            "duracao": duracao if duracao in roteiro.DURACOES else roteiro.DURACAO_PADRAO,
            "modelo": dados["modelo"] if dados.get("modelo") in MODELOS else MODELO,
            "estilo": estilos.achar(str(dados.get("estilo") or estilos.PADRAO)).id,
            "voz": dados.get("voz") is not False,
            "locutor": self.locutor_padrao(),
            "modelo_voz": dados["modelo_voz"] if dados.get("modelo_voz") in MODELOS_VOZ else "",
        }

    def guardar_preferencias(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Guarda as escolhas que vieram (as outras ficam como estavam), conferidas."""
        atual = self.preferencias()
        if "locutor" in dados:
            self._guardar_locutor(re.sub(r"[^a-z0-9]", "", str(dados["locutor"]).lower())[:40])
        novas = {
            "linha": str(dados.get("linha", atual["linha"])),
            "duracao": int(dados.get("duracao") or atual["duracao"]),
            "modelo": str(dados.get("modelo", atual["modelo"])),
            "estilo": str(dados.get("estilo", atual["estilo"])),
            "voz": dados.get("voz", atual["voz"]) is not False,
            "modelo_voz": str(dados.get("modelo_voz", atual["modelo_voz"])),
        }
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "preferencias.json").write_text(json.dumps(novas))
        return self.preferencias()

    def locutor_padrao(self) -> str:
        try:
            return str(json.loads((self.pasta / "locutor.json").read_text()).get("id", ""))
        except (OSError, ValueError, AttributeError):
            return ""

    def _guardar_locutor(self, locutor: str) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "locutor.json").write_text(json.dumps({"id": locutor}))

    def recentes(self, menos: str = "") -> list[dict[str, Any]]:
        """Os roteiros dos últimos vídeos feitos (a memória do diretor, para não repetir)."""
        feitos = [
            v.roteiro
            for v in self.listar()
            if v.id != menos and v.estado != "erro" and v.roteiro.get("cenas")
        ]
        return feitos[:RECENTES]

    def proximo_tema(self, temas: list[str]) -> tuple[str, str]:
        """O tema do vídeo agendado: o primeiro da lista que ainda não virou vídeo; sem ele, o
        artigo publicado mais novo que ainda não virou vídeo; sem ele, o diretor escolhe pela
        linha editorial do site, longe dos últimos vídeos. Devolve (tema, artigo)."""
        feitos = self.listar()
        usados = {roteiro.base(v.tema) for v in feitos if v.tema}
        for tema in temas:
            if (limpo := " ".join(str(tema).split())[:200]) and roteiro.base(limpo) not in usados:
                return limpo, ""
        de_artigo = {v.artigo for v in feitos if v.artigo}
        # um site fora do ar não impede o vídeo
        with contextlib.suppress(marketing.MarketingErro, OSError, ValueError):
            for a in self.site.artigos():
                if a.get("estado") == "Publicado" and a.get("slug") not in de_artigo:
                    return "", str(a["slug"])
        return TEMA_LIVRE, ""

    @staticmethod
    def pedido_agendado(temas: list[str] | str, duracao: int) -> str:
        """O texto da automação de vídeos: até 10 temas curtos e a duração, em JSON."""
        if isinstance(temas, str):
            temas = temas.splitlines()
        limpos = [" ".join(str(t).split())[:80] for t in temas if str(t).strip()][:10]
        if duracao not in roteiro.DURACOES:
            raise VideoErro("Duração inválida.")
        texto = json.dumps({"temas": limpos, "duracao": duracao}, ensure_ascii=False)
        if len(texto) > 600:
            raise VideoErro("Temas longos demais. Use frases curtas.")
        return texto

    def arquivo(self, id_: str, qual: str = "video") -> Path:
        alvo = self._dir(id_) / ("capa.jpg" if qual == "capa" else "video.mp4")
        if not alvo.is_file():
            raise VideoErro("O vídeo ainda não está pronto.")
        return alvo

    def descartar(self, id_: str) -> None:
        video = self.ler(id_)
        if video.estado in ("criando", "publicando"):
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
        estilo: str | None = None,
        voz: bool | None = None,
        esperar: bool = False,
        duracao: int | None = None,
        modelo: str | None = None,
        locutor: str | None = None,
        linha: str | None = None,
        modelo_voz: str | None = None,
        entrega: str = "",
        palavra: str = "",
    ) -> Video:
        # o que não veio (o agendado, a voz) sai das escolhas do cartão Vídeos
        prefs = self.preferencias()
        estilo = prefs["estilo"] if estilo is None else estilo
        voz = prefs["voz"] if voz is None else voz
        duracao = prefs["duracao"] if duracao is None else duracao
        modelo = prefs["modelo"] if modelo is None else modelo
        linha = prefs["linha"] if linha is None else linha
        modelo_voz = prefs["modelo_voz"] if modelo_voz is None else modelo_voz
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
        # sem escolha (o agendado, a voz), o último locutor; com escolha, ela vira o padrão
        if locutor is None:
            locutor = self.locutor_padrao()
        else:
            locutor = re.sub(r"[^a-z0-9]", "", locutor.lower())[:40]
            self._guardar_locutor(locutor)
        video = Video(
            uuid.uuid4().hex[:8], tema, artigo, "", estilos.achar(estilo).id, voz, modelo=modelo,
            duracao_alvo=duracao, locutor=locutor,
            modelo_voz=modelo_voz if modelo_voz in MODELOS_VOZ else "",
            linha=linha if linha in formatos.LINHAS else "",
            entrega=" ".join(entrega.split())[:140],
            palavra=" ".join(re.sub(r"[^\wÀ-ÿ ]", "", palavra).split())[:16].upper(),
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
        # um ajuste pedido segue a versão anterior; um vídeo novo foge da receita dos últimos
        recentes = [] if video.instrucao else self.recentes(video.id)
        prompt = roteiro.montar_prompt(
            nome, self._pedido(video), self.site.manual(), estilo, alvo, recentes,
            self.fotos.nomes(), video.linha, video.entrega, video.palavra,
        )  # fmt: skip
        resposta = self.perguntar(prompt, video.modelo)
        try:
            r = roteiro.interpretar(resposta, estilo, alvo)
            if roteiro.miolo(r.cenas) in {roteiro.miolo(x["cenas"]) for x in recentes}:
                raise roteiro.RoteiroErro(
                    "A sequência de cenas ficou igual à de um vídeo recente. Mude a receita."
                )
            if r.formato and recentes and r.formato == recentes[0].get("formato"):
                raise roteiro.RoteiroErro(
                    f'O formato "{r.formato}" é o mesmo do último vídeo. Escolha outro formato.'
                )
        except roteiro.RoteiroErro as erro:
            # uma volta: o modelo recebe o que escreveu e o que está errado (acontece com a fala
            # longa demais); se errar de novo, o vídeo fica com o erro
            log.info("vídeo %s: roteiro recusado (%s), pedindo de novo", video.id, erro)
            corrigir = (
                f"{prompt}\n\n## Sua resposta anterior foi recusada\n{erro}\n"
                f"Resposta anterior: {resposta[:6000]}\nEscreva de novo, corrigindo isso."
            )
            r = roteiro.interpretar(self.perguntar(corrigir, video.modelo), estilo, alvo)
        # as fotos viram arquivos na pasta do vídeo (a que não vier vira ícone); crédito na legenda
        if creditos := self.fotos.resolver(r.cenas, pasta):
            r.legenda = f"{r.legenda}\n\nFotos: {'; '.join(dict.fromkeys(creditos))}"
        video.titulo, video.legenda, video.roteiro = r.titulo, r.legenda, r.para_json()

        self._etapa(video, "Gravando a voz" if video.voz else "Montando o tempo")
        minimos = [MINIMOS[c["tipo"]](c) if c["tipo"] in MINIMOS else 3.0 for c in r.cenas]
        n = narracao.narrar(
            r.falas,
            self._sintetizador(video) if video.voz else None,
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
            "semente": int(video.id, 16) if re.fullmatch(r"[0-9a-f]{1,12}", video.id) else 7,
            "icones": {
                n: biblioteca.todos()[n]
                for n in roteiro.icones_usados(cenas) | {"sparkles", "arrow-down"}
            },
            "marca": {
                "nome": marca.nome, "instagram": marca.instagram,
                "logo": _logo_como_dado(self.site.logo()), "cores": self._cores(marca),
            },
            "estilo": {
                "id": estilo.id,
                "css": estilo.css.resolve().as_uri() if estilo.css else "",
                "js": estilo.js.resolve().as_uri() if estilo.js else "",
                "onda": estilo.onda and video.voz,
                "fontes": {
                    "titulo": marca.titulo or estilo.fonte_titulo,
                    "texto": marca.texto or estilo.fonte_texto,
                    "legenda": estilo.fonte_legenda,
                },
                "fontes_url": estilo.fontes_url(marca.titulo, marca.texto),
            },
        }  # fmt: skip
        arquivo_dados = pasta / "dados.js"
        arquivo_dados.write_text(f"window.VIDEO = {json.dumps(dados, ensure_ascii=False)};\n")

        self._etapa(video, "Compondo a trilha")
        mix = trilha.compor(
            n.duracao, [a for a, _ in n.cenas[1:]], n.voz if video.voz else None,
            estilo.bpm, estilo.energia, int(str(dados["semente"])), efeitos_sonoros(cenas),
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

    # --- publicar (ADR 0109) ---------------------------------------------------------------

    def publicar(self, id_: str, esperar: bool = False) -> Video:
        """Publica como Reels. Só com a aprovação de quem usa: quem chama já a recebeu."""
        with self._trava:
            video = self.ler(id_)
            if video.estado != "rascunho":
                raise VideoErro("Só um vídeo pronto pode ser publicado.")
            if not self.instagram.conectado:
                raise VideoErro("Conecte o Instagram em Redes sociais.")
            if not self.endereco():
                raise VideoErro("Publicar exige o acesso de qualquer lugar com endereço fixo.")
            self.arquivo(id_)
            if not REELS_S[0] <= video.duracao <= REELS_S[1]:
                raise VideoErro("Um Reels tem de 3 a 90 segundos.")
            video.estado, video.erro, video.publicando_desde = "publicando", "", time.time()
            self._publicando.add(video.id)
            self._gravar(video)
        if esperar:
            self._enviar(video)
            return self.ler(id_)
        threading.Thread(
            target=self._enviar, args=(video,), name="video-publicar", daemon=True
        ).start()
        return video

    def _enviar(self, video: Video) -> None:
        mp4 = self.arquivo(video.id)
        segredo = self.links.abrir([mp4], LINK_DO_VIDEO_S)
        try:
            url = f"{self.endereco()}{publico.PREFIXO}{segredo}/{mp4.name}"
            video.permalink = self._publicar_reels(self.instagram, url, video.legenda)
            video.estado, video.publicado, video.erro = "publicado", time.time(), ""
            texto = f"O vídeo {video.titulo or video.tema} foi publicado no Instagram."
        except InstagramErro as erro:
            video.estado, video.erro = "rascunho", str(erro)
            texto = f"Não publiquei o vídeo: {erro}"
        except Exception:  # um defeito não deixa o vídeo preso em "publicando"
            log.exception("vídeo %s: falha inesperada ao publicar", video.id)
            video.estado = "rascunho"
            video.erro = "A publicação falhou. Confira no Instagram antes de publicar."
            texto = f"Não publiquei o vídeo: {video.erro}"
        finally:
            self.links.fechar(segredo)
            self._publicando.discard(video.id)
        self._gravar(video)
        if self.site.avisar is not None:
            self.site.avisar(texto)

    # --- a tela ---------------------------------------------------------------------------

    def para_tela(self, video: Video) -> dict[str, Any]:
        dados = {
            k: getattr(video, k)
            for k in (
                "id", "tema", "artigo", "estilo", "voz", "estado", "etapa", "erro", "titulo",
                "legenda", "duracao", "criado", "modelo", "duracao_alvo", "permalink", "publicado",
                "locutor", "linha", "modelo_voz",
            )
        }  # fmt: skip
        dados["palavra"] = video.roteiro.get("palavra", "")
        dados["entrega"] = video.roteiro.get("entrega", "")
        dados["cenas"] = len(video.roteiro.get("cenas", []))
        dados["pronto"] = (self.pasta / video.id / "video.mp4").is_file()
        return dados


PADRAO = Videos()
