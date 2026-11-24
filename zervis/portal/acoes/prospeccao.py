"""A página Prospecção (ADR 0127): a configuração do funil, a chave da Apify, as mensagens que
esperam aprovação e as empresas contatadas."""

from typing import Any

from zervis import atividade
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.prospeccao import apify, funil


class AcoesProspeccao(Pagina):
    def prospeccao(self) -> dict[str, Any]:
        return funil.padrao().para_tela()

    def salvar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        ramos = dados.get("ramos")
        linhas = ramos.splitlines() if isinstance(ramos, str) else []
        try:
            por_dia = int(dados.get("por_dia") or funil.POR_DIA)
        except (TypeError, ValueError):
            raise PedidoInvalido("Envios por dia: um número.") from None
        cfg = funil.Config(
            ligada=dados.get("ligada") is True,
            sozinho=dados.get("sozinho") is True,
            cidade=" ".join(str(dados.get("cidade") or "").split())[:80],
            ramos=[r for r in (" ".join(x.split())[:60] for x in linhas[:20]) if r],
            oferta=str(dados.get("oferta") or "").strip()[:1500],
            por_dia=por_dia,
        )
        try:
            funil.salvar_config(cfg)
        except funil.ProspeccaoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        estado = "ligada" if cfg.ligada else "desligada"
        modo = ", envio sozinho" if cfg.sozinho else ""
        atividade.PADRAO.registrar("execucao", f"Prospecção {estado}{modo}", origem="painel")
        return {**self.prospeccao(), "aviso": "Salvo."}

    def chave_apify(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A chave da Apify: conferida na conta antes de guardar; vazio remove."""
        chave = str(dados.get("chave") or "").strip()
        try:
            if chave:
                apify.conferir(chave)
            apify.guardar(chave)
        except apify.ApifyErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.prospeccao(), "aviso": "Chave válida." if chave else "Chave removida."}

    def _fazer(self, acao: Any) -> dict[str, Any]:
        try:
            acao()
        except funil.ProspeccaoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.prospeccao()

    def buscar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        resposta = self._fazer(funil.padrao().buscar_agora)
        return {**resposta, "ocupado": True, "aviso": "Busca iniciada."}

    def adicionar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        cnpj = str(dados.get("cnpj") or "")[:30]
        return {**self._fazer(lambda: funil.padrao().adicionar_cnpj(cnpj)), "aviso": "Adicionada."}

    def aprovar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        ident, texto = str(dados.get("id") or ""), str(dados.get("texto") or "")
        return {**self._fazer(lambda: funil.padrao().aprovar(ident, texto)), "aviso": "Aprovada."}

    def descartar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        ident = str(dados.get("id") or "")
        return self._fazer(lambda: funil.padrao().descartar(ident))

    def marcar_prospeccao(self, dados: dict[str, Any]) -> dict[str, Any]:
        ident, status = str(dados.get("id") or ""), str(dados.get("status") or "")
        return self._fazer(lambda: funil.padrao().marcar(ident, status))
