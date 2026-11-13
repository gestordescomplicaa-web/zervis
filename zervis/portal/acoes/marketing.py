"""Ações da página Marketing (ADR 0091): o site, os artigos do blog, os pedidos em andamento e
os PRs abertos. Pedir e abrir PR passam pelo mesmo caminho da voz."""

import json
from datetime import datetime
from typing import Any

from zervis import marketing
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import JobErro
from zervis.cerebro.ferramentas.sessoes import motor_conectado
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
