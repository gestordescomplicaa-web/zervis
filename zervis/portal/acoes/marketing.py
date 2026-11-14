"""Ações da página Marketing (ADR 0091): o site, os artigos do blog, os pedidos em andamento e
os PRs abertos. Pedir e abrir PR passam pelo mesmo caminho da voz."""

import json
from datetime import datetime
from typing import Any

from zervis import marketing, marketing_posts
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import JobErro
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.marca import CORES_PADRAO
from zervis.oficina.sessoes import SessaoErro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


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
            "marca": self._marca(),
            "automaticos": [
                {"id": j.id, "agenda": j.agenda, "proxima": j.proxima, "ativo": j.ativo}
                for j in self.n.jobs.listar()
                if j.tipo == "artigo"
            ],
        }

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
