"""Ações da página sessoes."""

import base64
import logging
from pathlib import Path
from typing import Any

from zervis import atividade
from zervis.cerebro import conectores, contas
from zervis.oficina import arquivos
from zervis.oficina.manutencao import ORIGEM
from zervis.oficina.sessoes import Sessao
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesSessoes(Pagina):
    dependencias = ("cfg", "sessoes", "manutencao")

    @staticmethod
    def _nome_da_conta(id_: str) -> str:
        try:
            return contas.Contas().achar(id_).nome if id_ else ""
        except contas.ContaErro:
            return ""

    def _sessao(self, s: Sessao) -> dict[str, Any]:
        return {
            "id": s.id,
            "nome": s.nome,
            "pasta": s.pasta.replace(str(Path.home()), "~", 1),
            "motor": s.motor,
            "agente": contas.NOMES.get(s.motor, s.motor),
            "conta": self.painel._nome_da_conta(s.conta),
            "modelo": s.modelo,
            "modelos": [
                {"id": m["id"], "nome": m["nome"]} for m in self.n.sessoes.modelos_da_sessao(s)
            ],
            "esforco": s.esforco,
            "isolada": s.isolada,
            "branch": s.branch,
            "melhorias": s.origem == "manutencao" and bool(s.worktree),  # a sessão do Zé
            "estado": "trabalhando" if s.id in self.n.sessoes.trabalhando() else s.estado,
            "conta_id": s.conta,
            "limite": s.limite,
            "interrompida": s.interrompida[:300],
            "resumo": s.resumo,
            "atualizada": s.atualizada,
        }

    def sessoes(self) -> list[dict[str, Any]]:
        # A sessão do Zé (melhorias) mora na página Melhorias, não junto dos projetos.
        return [self.painel._sessao(s) for s in self.n.sessoes.listar() if s.origem != "manutencao"]

    def pastas(self) -> list[str]:
        """Sugestões para uma sessão nova: as pastas de projetos que existem nesta máquina."""
        raizes = [self.n.cfg.caminho("oficina", "raiz_projetos"), Path.home() / "Work"]
        raizes += [Path.home() / n for n in ("DESENVOLVIMENTO", "Projetos", "projetos", "code")]
        achadas: list[str] = []
        for raiz in dict.fromkeys(r.expanduser() for r in raizes):  # a raiz padrão é ~/projetos
            if raiz.is_dir():
                achadas += sorted(
                    str(p).replace(str(Path.home()), "~", 1)
                    for p in raiz.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                )
        return achadas[:200]

    def _onde(self, dados: dict[str, Any]) -> Path:
        return Path(self.painel._chamar(lambda: self.n.sessoes.ler(str(dados.get("id", "")))).onde)

    def arquivos(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self.painel._onde(dados)
        pasta = str(dados.get("pasta", ""))
        return {"pasta": pasta, "itens": self.painel._chamar(lambda: arquivos.listar(onde, pasta))}

    def ver_arquivo(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self.painel._onde(dados)
        return dict(self.painel._chamar(lambda: arquivos.ler(onde, str(dados.get("caminho", "")))))

    def buscar_arquivos(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self.painel._onde(dados)
        modo = "conteudo" if dados.get("modo") == "conteudo" else "nomes"
        achados = arquivos.buscar(onde, str(dados.get("termo", "")), modo)
        return {"modo": modo, "achados": achados}

    def criar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        pasta = str(dados.get("pasta", ""))
        if dados.get("novo"):
            projeto = str(dados.get("projeto") or dados.get("nome") or "")
            pasta = str(self.painel._chamar(lambda: self.n.sessoes.criar_projeto(projeto)))
        s = self.painel._chamar(
            lambda: self.n.sessoes.criar(
                str(dados.get("nome", "")),
                pasta,
                str(dados.get("motor", "claude")),
                str(dados.get("modelo", "")),
                bool(dados.get("isolada", False)),
            )
        )
        # Os conectores escolhidos valem antes do agente abrir pela primeira vez.
        if escolhidos := [str(n) for n in dados.get("conectores") or []]:
            self.painel._chamar(
                lambda: conectores.ligar_no_projeto(Path(s.pasta), escolhidos, so_adicionar=True)
            )
        return self.painel._sessao(s)

    def conectores_da_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        s = self.painel._chamar(lambda: self.n.sessoes.ler(str(dados.get("id", ""))))
        return {"conectores": self.painel._chamar(lambda: conectores.do_projeto(Path(s.pasta)))}

    def salvar_conectores_da_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Os conectores do projeto da sessão (valem em todas as sessões daquela pasta)."""
        id_ = str(dados.get("id", ""))
        s = self.painel._chamar(lambda: self.n.sessoes.ler(id_))
        nomes = [str(n) for n in dados.get("nomes") or []]
        valendo = self.painel._chamar(lambda: conectores.ligar_no_projeto(Path(s.pasta), nomes))
        s = self.painel._chamar(lambda: self.n.sessoes.recarregar_conectores(id_, valendo))
        return {
            **self.painel._sessao(s),
            "aviso": f"Conectores: {', '.join(valendo) or 'nenhum'}. A conversa continua.",
        }

    def ler_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        desde = max(0, int(dados.get("desde", 0) or 0))
        s = self.painel._chamar(lambda: self.n.sessoes.ler(id_))
        return {"sessao": self.painel._sessao(s), "mensagens": self.n.sessoes.mensagens(id_, desde)}

    def anexar(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        nome = self.painel._chamar(
            lambda: self.n.sessoes.anexar(consulta.get("id", ""), consulta.get("nome", ""), corpo)
        )
        return {
            "anexo": nome,
            "caminho": str(self.n.sessoes.pasta_de_anexos(consulta.get("id", "")) / nome),
        }

    def criar_arquivo(self, dados: dict[str, Any]) -> dict[str, Any]:
        relativo = self.painel._chamar(
            lambda: self.n.sessoes.criar_arquivo(
                str(dados.get("id", "")),
                str(dados.get("nome", "")),
                str(dados.get("conteudo", "")),
                bool(dados.get("sobrescrever", False)),
            )
        )
        return {"arquivo": relativo}

    def aplicar_copia(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("Confirme a aplicação das mudanças.")
        id_ = str(dados.get("id", ""))
        atividade.PADRAO.origem = "painel"
        aviso = self.painel._chamar(lambda: self.n.sessoes.aplicar_copia(id_))
        atividade.PADRAO.registrar("execucao", f"Juntou a cópia da sessão ao projeto ({id_})")
        return {**self.n.sessoes.copia(id_), "aviso": aviso}

    def descartar_copia(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("Confirme o descarte das mudanças.")
        id_ = str(dados.get("id", ""))
        atividade.PADRAO.origem = "painel"
        aviso = self.painel._chamar(lambda: self.n.sessoes.descartar_copia(id_))
        atividade.PADRAO.registrar("execucao", f"Descartou a cópia da sessão ({id_})")
        return {**self.n.sessoes.copia(id_), "aviso": aviso}

    def tarefa_interrompida(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Continuar (de onde parou) ou dispensar a tarefa que o reinício interrompeu."""
        id_ = str(dados.get("id", ""))
        if dados.get("continuar"):
            s = self.painel._chamar(lambda: self.n.sessoes.continuar_interrompida(id_))
            return {**self.painel._sessao(s), "aviso": "Continuando de onde parou."}
        s = self.painel._chamar(lambda: self.n.sessoes.dispensar_interrompida(id_))
        return {**self.painel._sessao(s), "aviso": "Dispensada."}

    def modelo_da_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O modelo dos próximos pedidos da sessão; o agente reabre nele e a conversa continua."""
        id_, modelo = str(dados.get("id", "")), str(dados.get("modelo", ""))
        s = self.painel._chamar(lambda: self.n.sessoes.ajustar_modelo(id_, modelo))
        nomes = {m["id"]: m["nome"] for m in self.n.sessoes.modelos_da_sessao(s)}
        return {
            **self.painel._sessao(s),
            "aviso": f"Modelo: {nomes.get(modelo, 'padrão da conta')}.",
        }

    def trocar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Troca agente ou conta; com `continuar`, manda de novo o pedido que bateu no limite."""
        with self.n.sessoes._operacoes:
            return self._trocar_sessao(dados)

    def _trocar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        atual = self.painel._chamar(lambda: self.n.sessoes.ler(id_))
        if dados.get("continuar") and not atual.limite:
            raise PedidoInvalido(
                "Não há limite confirmado nesta conta. Troque a conta sem reenviar o pedido."
            )
        trocar = self.n.manutencao.trocar if atual.origem == ORIGEM else self.n.sessoes.trocar
        s, aviso = self.painel._chamar(
            lambda: trocar(id_, str(dados.get("motor", "")), str(dados.get("conta", "")))
        )
        if dados.get("continuar") and s.ultimo_pedido:
            s = self.painel._chamar(lambda: self.n.sessoes.continuar(id_))
            aviso += " Continuando o pedido."
        return {**self.painel._sessao(s), "aviso": aviso}

    def abrir_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        t = self.painel._chamar(
            lambda: self.n.sessoes.abrir_terminal(
                id_, colunas=int(dados.get("colunas", 120)), linhas=int(dados.get("linhas", 32))
            )
        )
        t.redimensionar(int(dados.get("colunas", 120)), int(dados.get("linhas", 32)))
        return {"posicao": t.inicio, "vivo": t.vivo}

    def ler_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Long-poll: espera até 20 s por saída nova a partir de `desde`."""
        id_ = str(dados.get("id", ""))
        t = self.n.sessoes.terminais.get(id_)
        trocando = id_ in self.n.sessoes.fallback.pendentes
        desde = int(dados.get("desde", 0))
        if t is None:
            return {"posicao": desde, "dados": "", "vivo": False, "trocando": trocando}
        reiniciado = bool(dados.get("geracao") and dados["geracao"] != t.pid)
        if reiniciado:
            desde = t.inicio
        posicao, saida, vivo = t.ler(desde, float(dados.get("espera", 20)))
        trocando = id_ in self.n.sessoes.fallback.pendentes or (
            self.n.sessoes.terminais.get(id_) is not t
        )
        return {
            "posicao": posicao,
            "dados": base64.b64encode(saida).decode(),
            "vivo": vivo,
            "geracao": t.pid,
            "reiniciado": reiniciado,
            "trocando": trocando,
        }

    def escrever_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(
            lambda: self.n.sessoes.escrever_terminal(
                str(dados.get("id", "")), str(dados.get("dados", "")).encode()
            )
        )
        return {}

    def tamanho_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        t = self.n.sessoes.terminais.get(str(dados.get("id", "")))
        if t is not None:
            t.redimensionar(int(dados.get("colunas", 120)), int(dados.get("linhas", 32)))
        return {}

    def fechar_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        with self.n.sessoes._operacoes:
            id_ = str(dados.get("id", ""))
            self.n.sessoes.fallback.cancelar(id_)
            s = self.painel._chamar(lambda: self.n.sessoes.ler(id_))
            if id_ in self.n.sessoes._centralizando:
                raise PedidoInvalido("Aguarde a unificação terminar para interromper o agente.")
            if s.origem == ORIGEM and self.n.manutencao.atualizando():
                raise PedidoInvalido("Aguarde a atualização terminar para interromper o agente.")
            self.n.sessoes._consumir_eventos(id_)
            t = self.n.sessoes.terminais.pop(id_, None)
            if t is not None:
                t.encerrar()
            return {"aviso": "Terminal fechado. A conversa continua ao reabrir."}

    def excluir_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self.painel._chamar(lambda: self.n.sessoes.excluir(str(dados.get("id", ""))))
        return {"aviso": aviso, "sessoes": self.painel.sessoes()}
