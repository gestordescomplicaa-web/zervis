"""Ações da página Marketing (ADR 0091): o site, os artigos do blog, os pedidos em andamento e
os PRs abertos. Pedir e abrir PR passam pelo mesmo caminho da voz."""

import base64
import io
import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from zervis import atividade, marketing, marketing_posts, metricas_site
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import JobErro
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.marca import CORES_PADRAO
from zervis.oficina.sessoes import SessaoErro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.redes import instagram_comentarios, instagram_direct
from zervis.redes.instagram import InstagramErro
from zervis.video import estilos as estilos_video
from zervis.video import roteiro as roteiro_video
from zervis.video import videos


class AcoesMarketing(Pagina):
    dependencias = ("sessoes", "jobs")

    def marketing(self) -> dict[str, Any]:
        m = marketing.PADRAO
        artigos = m.artigos()
        return {
            "site": m.situacao(),
            "artigos": artigos,
            "categorias": m.por_categoria(artigos),
            "pedidos": m.pedidos(self.n.sessoes),
            "prs": m.prs(),
            "posts": [marketing_posts.PADRAO.para_tela(p) for p in marketing_posts.PADRAO.listar()],
            "videos": self.videos(),
            "comentarios": self._comentarios(),
            "marca": self._marca(),
            "automaticos": self._automaticos("artigo"),
            "videos_automaticos": self._automaticos("video"),
        }

    def _automaticos(self, tipo: str) -> list[dict[str, Any]]:
        saida = []
        for j in self.n.jobs.listar():
            if j.tipo != tipo:
                continue
            item = {"id": j.id, "agenda": j.agenda, "proxima": j.proxima, "ativo": j.ativo}
            if tipo == "video":
                try:
                    pedido = json.loads(j.texto)
                except ValueError:
                    pedido = {}
                item["temas"] = len(pedido.get("temas") or [])
                item["duracao"] = pedido.get("duracao")
            saida.append(item)
        return saida

    # --- os comentários do Instagram viram conversa no direct (ADR 0118) --------------------

    def _comentarios(self) -> dict[str, Any]:
        c = instagram_comentarios.PADRAO
        e = c.estado()
        d = instagram_direct.PADRAO.estado()
        campos = ("etapa", "resumo", "motivo", "pausado", "respostas")
        contatos = [
            {"usuario": u, **{k: x.get(k) for k in campos}}
            for u, x in sorted(d["contatos"].items())
        ]
        return {
            "direct": {
                "ligado": d["ligado"],
                "link": d["link"],
                "como": d["como"],
                "contatos": contatos,
            },
            "ligado": e["ligado"],
            "conectado": marketing_posts.PADRAO.instagram.conectado,
            "contatos": len(e["contatos"]),
            "recentes": [
                {k: x.get(k) for k in ("autor", "texto", "quando", "publico", "direct", "erro")}
                for x in c.recentes(8)
            ],
        }

    def ligar_comentarios(self, dados: dict[str, Any]) -> dict[str, Any]:
        ligado = dados.get("ligado") is True
        if ligado and not marketing_posts.PADRAO.instagram.conectado:
            raise PedidoInvalido("Conecte o Instagram em Redes sociais.")
        instagram_comentarios.PADRAO.ligar(ligado)
        atividade.PADRAO.registrar(
            "execucao",
            "Respostas aos comentários do Instagram " + ("ligadas" if ligado else "desligadas"),
            origem="painel",
        )
        return {**self.marketing(), "aviso": "Ligado." if ligado else "Desligado."}

    def ajustar_direct(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A conversa no direct (ADR 0119): ligada, o link de agendamento e o como conversar."""
        try:
            instagram_direct.PADRAO.ajustar(
                dados.get("ligado") is True, str(dados.get("link", "")), str(dados.get("como", ""))
            )
        except InstagramErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        atividade.PADRAO.registrar(
            "execucao", "Conversa no direct do Instagram ajustada", origem="painel"
        )
        return {**self.marketing(), "aviso": "Salvo."}

    def devolver_direct(self, dados: dict[str, Any]) -> dict[str, Any]:
        instagram_direct.PADRAO.devolver(str(dados.get("usuario", "")))
        return {**self.marketing(), "aviso": "O Zé volta a conversar com esse contato."}

    def guardar_site(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            marketing.PADRAO.guardar(str(dados.get("pasta", "")), str(dados.get("base", "")))
        except marketing.MarketingErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.marketing(), "aviso": "Salvo."}

    def pedir_marketing(self, dados: dict[str, Any]) -> dict[str, Any]:
        tipo, texto = str(dados.get("tipo", "")), str(dados.get("texto", ""))
        try:
            s = marketing.PADRAO.pedir(self.n.sessoes, tipo, texto, motor_conectado())
        except (marketing.MarketingErro, SessaoErro) as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.marketing(), "sessao": s.id, "aviso": "Pedido enviado à sessão."}

    def pr_marketing(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            r = marketing.PADRAO.abrir_pr(self.n.sessoes, str(dados.get("sessao", "")))
        except (marketing.MarketingErro, SessaoErro) as erro:
            raise PedidoInvalido(str(erro)) from erro
        if not r.ok:
            raise PedidoInvalido(r.texto)
        return {**self.marketing(), "aviso": r.texto, "endereco": r.endereco}

    def publicar_marketing(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            r = marketing.PADRAO.publicar(self.n.sessoes, str(dados.get("sessao", "")))
        except (marketing.MarketingErro, SessaoErro) as erro:
            raise PedidoInvalido(str(erro)) from erro
        if not r.ok:
            raise PedidoInvalido(r.texto)
        return {**self.marketing(), "aviso": r.texto}

    def agendar_marketing(self, dados: dict[str, Any]) -> dict[str, Any]:
        texto = json.dumps({"tema": ""})
        try:
            self.n.jobs.criar(
                "Artigo do blog", str(dados.get("quando", "")), "artigo", texto, datetime.now(FUSO)
            )
        except JobErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.marketing(), "aviso": "Agendado."}

    # --- o Instagram: a marca e os posts (ADR 0093) ---------------------------------------

    def _marca(self) -> dict[str, Any]:
        m = marketing.PADRAO
        do_site = m.marca_do_site()
        return {
            **m.paleta(),
            "atual": dict(m.marca().cores),
            "site": dict(do_site.cores) if do_site else dict(CORES_PADRAO),
            "declarada": do_site is not None,
            "instagram": marketing_posts.PADRAO.instagram.conectado,
            "publicavel": bool(marketing_posts.PADRAO.endereco()),
        }

    def _posts(self, fazer: Any) -> Any:
        try:
            return fazer()
        except (marketing_posts.PostErro, marketing.MarketingErro) as erro:
            raise PedidoInvalido(str(erro)) from erro

    def guardar_paleta(self, dados: dict[str, Any]) -> dict[str, Any]:
        cruas = dados.get("cores")
        cores: dict[str, Any] = cruas if isinstance(cruas, dict) else {}
        self._posts(lambda: marketing.PADRAO.guardar_paleta(str(dados.get("paleta", "")), cores))
        return {**self.marketing(), "aviso": "Salvo."}

    def criar_post(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._posts(
            lambda: marketing_posts.PADRAO.criar(
                str(dados.get("tema", "")), str(dados.get("artigo", ""))
            )
        )
        return {
            **self.marketing(),
            "aviso": "Criando o post. Aviso quando a prévia estiver pronta.",
        }

    def ver_post(self, dados: dict[str, Any]) -> dict[str, Any]:
        posts = marketing_posts.PADRAO
        post = self._posts(lambda: posts.ler(str(dados.get("id", ""))))
        return posts.para_tela(post, com_imagens=True)

    def refazer_post(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_, instrucao = str(dados.get("id", "")), str(dados.get("instrucao", ""))
        self._posts(lambda: marketing_posts.PADRAO.refazer(id_, instrucao))
        return {**self.marketing(), "aviso": "Refazendo o post."}

    def publicar_post(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._posts(lambda: marketing_posts.PADRAO.publicar(str(dados.get("id", ""))))
        return {**self.marketing(), "aviso": "Publicando no Instagram."}

    def descartar_post(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._posts(lambda: marketing_posts.PADRAO.descartar(str(dados.get("id", ""))))
        return {**self.marketing(), "aviso": "Descartado."}

    # --- as fotos da marca (a capa dos posts) ---------------------------------------------

    def enviar_foto(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        nome = self._posts(
            lambda: marketing_posts.PADRAO.adicionar_foto(consulta.get("nome", ""), corpo)
        )
        return {"nome": nome, "aviso": "Foto salva."}

    def fotos_da_marca(self, _dados: dict[str, Any]) -> list[dict[str, str]]:
        """As fotos, com uma miniatura cada (o painel não lê a pasta)."""
        from PIL import Image

        posts, lista = marketing_posts.PADRAO, []
        for nome in posts.fotos():
            with Image.open(io.BytesIO(posts.foto(nome))) as imagem:
                imagem.thumbnail((240, 240))
                saida = io.BytesIO()
                imagem.convert("RGB").save(saida, "JPEG", quality=80)
            miniatura = "data:image/jpeg;base64," + base64.b64encode(saida.getvalue()).decode()
            lista.append({"nome": nome, "miniatura": miniatura})
        return lista

    def remover_foto(self, dados: dict[str, Any]) -> list[dict[str, str]]:
        self._posts(lambda: marketing_posts.PADRAO.remover_foto(str(dados.get("nome", ""))))
        return self.fotos_da_marca({})

    # --- as métricas do site (ADR 0094): só leitura do Google ------------------------------

    def metricas(self) -> dict[str, Any]:
        """Lida à parte do resto da página: o Google pode demorar, e o cache segura 30 minutos."""
        return metricas_site.PADRAO.resumo()

    def guardar_metricas(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            conta = metricas_site.PADRAO.guardar(str(dados.get("chave", ""))[:20000])
        except metricas_site.MetricasErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        atividade.PADRAO.registrar(
            "execucao", f"Métricas do site ligadas ({conta})", origem="painel"
        )
        return {**self.metricas(), "aviso": "Chave válida."}

    def remover_metricas(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("confirmação necessária")
        metricas_site.PADRAO.remover()
        atividade.PADRAO.registrar("execucao", "Métricas do site desligadas", origem="painel")
        return {**self.metricas(), "aviso": "Chave removida."}

    # --- os vídeos (Reels) da marca (ADR 0106) --------------------------------------------

    def videos(self) -> dict[str, Any]:
        v = videos.PADRAO
        return {
            "lista": [v.para_tela(x) for x in v.listar()],
            "estilos": [e.para_tela() for e in estilos_video.listar()],
            "modelos": [{"id": k, "nome": n} for k, n in videos.MODELOS.items()],
            "duracoes": sorted(roteiro_video.DURACOES),
            "vozes": v.vozes(),
            "paleta": v.paleta(),
            "locutor": v.locutor_padrao(),
            "preferencias": v.preferencias(),
            "indisponivel": v.disponivel(),
            "instagram": marketing_posts.PADRAO.instagram.conectado,
            "publicavel": bool(marketing_posts.PADRAO.endereco()),
        }

    def _videos(self, fazer: Any) -> Any:
        try:
            return fazer()
        except (videos.VideoErro, marketing.MarketingErro, FileNotFoundError) as erro:
            raise PedidoInvalido(str(erro)) from erro

    def criar_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._videos(
            lambda: videos.PADRAO.criar(
                str(dados.get("tema", "")),
                str(dados.get("artigo", "")),
                str(dados.get("estilo", "")) or estilos_video.PADRAO,
                dados.get("voz") is not False,
                duracao=int(dados.get("duracao") or roteiro_video.DURACAO_PADRAO),
                modelo=str(dados.get("modelo") or videos.MODELO),
                locutor=str(dados.get("locutor", "")) if "locutor" in dados else None,
                linha=str(dados.get("linha", "")),
                entrega=str(dados.get("entrega", "")),
                palavra=str(dados.get("palavra", "")),
            )
        )
        atividade.PADRAO.registrar("execucao", "Vídeo pedido em Marketing", origem="painel")
        return {**self.videos(), "aviso": "Criando o vídeo. Aviso quando estiver pronto."}

    def preferencias_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        """As escolhas do cartão Vídeos, guardadas assim que mudam."""
        try:
            prefs = videos.PADRAO.guardar_preferencias(dados)
        except (TypeError, ValueError) as erro:
            raise PedidoInvalido("Escolha inválida.") from erro
        return {"preferencias": prefs}

    def paleta_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A paleta dos vídeos: a da marca ou a de um site (o Zé tira as cores do site)."""
        if dados.get("origem") == "marca":
            self._videos(videos.PADRAO.paleta_da_marca)
            return {**self.videos(), "aviso": "Usando as cores da marca."}
        url = str(dados.get("url", ""))
        self._videos(lambda: videos.PADRAO.paleta_do_site(url))
        atividade.PADRAO.registrar(
            "execucao", "Paleta dos vídeos tirada de um site", origem="painel"
        )
        return {**self.videos(), "aviso": "Cores do site salvas."}

    def agendar_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        cruas = dados.get("temas")
        temas: list[str] | str = cruas if isinstance(cruas, (list, str)) else ""
        texto = self._videos(
            lambda: videos.Videos.pedido_agendado(
                temas, int(dados.get("duracao") or roteiro_video.DURACAO_PADRAO)
            )
        )
        try:
            self.n.jobs.criar(
                "Vídeo da marca", str(dados.get("quando", "")), "video", texto, datetime.now(FUSO)
            )
        except JobErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        atividade.PADRAO.registrar("execucao", "Vídeos automáticos agendados", origem="painel")
        return {**self.marketing(), "aviso": "Agendado."}

    def refazer_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_, instrucao = str(dados.get("id", "")), str(dados.get("instrucao", ""))
        self._videos(lambda: videos.PADRAO.refazer(id_, instrucao))
        return {**self.videos(), "aviso": "Refazendo o vídeo."}

    def publicar_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Publica como Reels: o clique em "Confirmar publicação" é a aprovação (ADR 0109)."""
        video = self._videos(lambda: videos.PADRAO.publicar(str(dados.get("id", ""))))
        atividade.PADRAO.registrar(
            "execucao", f"Vídeo enviado ao Instagram: {video.titulo or video.tema}", origem="painel"
        )
        return {**self.videos(), "aviso": "Publicando no Instagram. Aviso quando estiver no ar."}

    def descartar_video(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._videos(lambda: videos.PADRAO.descartar(str(dados.get("id", ""))))
        return {**self.videos(), "aviso": "Descartado."}

    def arquivo_video(self, consulta: dict[str, str]) -> tuple[str, Iterator[bytes]]:
        """O MP4 (ou a capa) para a prévia e o download, em pedaços."""
        qual = "capa" if consulta.get("qual") == "capa" else "video"
        arquivo = self._videos(lambda: videos.PADRAO.arquivo(consulta.get("id", ""), qual))

        def pedacos() -> Iterator[bytes]:
            with arquivo.open("rb") as f:
                while pedaco := f.read(256 * 1024):
                    yield pedaco

        return ("image/jpeg" if qual == "capa" else "video/mp4"), pedacos()
