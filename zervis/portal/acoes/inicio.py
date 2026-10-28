"""Ações da página inicio."""

import logging
import os
from pathlib import Path
from typing import Any

from zervis import atividade
from zervis.avisos import mensagens
from zervis.cerebro import rapido
from zervis.portal.acoes.apoio import _latencia_de_hoje, linhas_do_registro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


def _item(atual: dict[str, str], tipo: str) -> dict[str, str]:
    return {
        "quando": atual["quando"],
        "tipo": tipo,
        "texto": atual["pessoa"] if tipo == "voce" else atual["ze"],
    }


class AcoesInicio(Pagina):
    dependencias = (
        "_aplicar_depois",
        "_fonte",
        "atualizacao",
        "central",
        "cerebro",
        "cfg",
        "chamado",
        "consumo",
        "conversa_em_andamento",
        "conversas",
        "escrever",
        "espera",
        "foco",
        "jobs",
        "linha",
        "manutencao",
        "maquina",
        "mensagens",
        "modo_escuta",
        "modo_fala",
        "provedor",
        "sessoes",
        "tem_janela",
        "ultimo_na_tela",
        "ver_sessao",
        "versoes",
    )

    def estado(self) -> dict[str, Any]:
        from zervis.memoria.linha import agora

        via = self.painel._via()
        cerebro = self.n.cerebro
        return {
            "ze": self.n.maquina.estado.value,
            "cerebro": {"provedor": self.n.provedor, "modelo": getattr(cerebro, "modelo", "")},
            "via_rapida": {
                "ativa": isinstance(cerebro, rapido.Roteado),
                "motor": via["motor"],
                "modelo": via["modelo"],
            },
            "consumo": self.n.consumo.resumo_falado(),
            "latencia": _latencia_de_hoje(self.painel.pasta_latencias, agora().date().isoformat()),
            "foco": self.n.foco.onde_estava(),
            "tela_ts": self.painel._tela_ts(),
            "modo_fala": self.n.modo_fala,
            "escuta": {"modo": self.n.modo_escuta, "janela": self.n.tem_janela},
            "chamado": self.n.chamado,
            "espera": self.n.espera,
            "whatsapp": {
                "ligado": self.n.mensagens.ativo,
                "disponivel": mensagens.disponivel() or self.n.central.whatsapp_ativo,
            },
            "voz_remota": {"conectada": self.n._fonte is not None},
            "manutencao": {
                "ligada": self.n.manutencao.ligado,
                "aguardando": self.n._aplicar_depois is not None,
            },
            "atualizacao": self.n.atualizacao.foto(),
            "versao": self.n.versoes.foto(),  # a bolinha de "tem atualização" no menu
            "tela": self.n.ultimo_na_tela,  # [quando, texto]: o painel mostra no Silencioso
            "inicio": os.getpid(),  # muda a cada reinício: o painel recarrega sozinho
        }

    def conversa(self) -> dict[str, Any]:
        """O fio de hoje com o Zé: o que a pessoa disse ou escreveu, as respostas e os avisos."""
        from zervis.memoria.linha import agora

        hoje = agora()
        itens: list[dict[str, str]] = []
        for t in self.n.conversas.do_dia(hoje.date()):
            quando = t.em.isoformat(timespec="seconds")
            itens.append({"quando": quando, "tipo": "voce", "texto": t.pessoa})
            if t.ze:
                itens.append({"quando": quando, "tipo": "ze", "texto": t.ze})
        inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        for ev in self.n.linha.entre(inicio, hoje, {"aviso", "lembrete", "manutencao"}):
            # Um lembrete é gravado ao ser criado, com a hora em que vai tocar.
            momento = max(ev.quando, ev.registrado)
            if momento <= hoje:
                itens.append(
                    {
                        "quando": momento.isoformat(timespec="seconds"),
                        "tipo": "aviso",
                        "texto": ev.texto,
                    }
                )
        itens.sort(key=lambda i: i["quando"])  # estável: o pedido antes da resposta
        andamento = getattr(self.n, "conversa_em_andamento", None)
        if andamento is not None and (atual := andamento()) is not None:
            # A troca em curso ainda não está no histórico: vai no fim, marcada, com o que o Zé
            # já respondeu até aqui.
            itens.append({**_item(atual, "voce"), "pendente": "1"})
            if atual["ze"]:
                itens.append({**_item(atual, "ze"), "pendente": "1"})
        fila = getattr(self.n, "fila", None)
        esperando = [a.titulo or a.texto for a in fila.validos()] if fila is not None else []
        return {"itens": itens[-200:], "esperando": esperando}

    def escrever(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Um pedido escrito no painel: o mesmo caminho da fala."""
        return {"aviso": self.n.escrever(str(dados.get("texto", "")))}

    def atividade(self) -> dict[str, Any]:
        """O que o Zé fez e onde tropeçou (ADR 0025), do mais recente ao mais antigo."""
        return {"itens": atividade.PADRAO.listar(300), "resumo": atividade.PADRAO.resumo()}

    def registro_tecnico(self, dados: dict[str, Any]) -> dict[str, Any]:
        """As últimas linhas do registro do serviço, sem segredos; `nivel`: erros, avisos, tudo.
        O nível sai do texto da linha: o journal guarda tudo o que o Zé escreve num nível só."""
        marcas = {
            "erros": ("ERROR", "CRITICAL", "Traceback"),
            "avisos": ("WARNING", "ERROR", "CRITICAL", "Traceback"),
        }
        linhas = linhas_do_registro()
        if linhas is None:
            return {"linhas": [], "aviso": "Registro do sistema indisponível."}
        if filtro := marcas.get(str(dados.get("nivel", ""))):
            linhas = [x for x in linhas if any(m in x for m in filtro)]
        return {"linhas": linhas[-400:]}

    def painel_vendo(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O painel está com esta sessão aberta e à vista: o Zé não fala o que ela já mostra."""
        self.n.ver_sessao(str(dados.get("sessao", ""))[:40])
        return {}

    def _tela_ts(self) -> float:
        """Quando o Zé mandou algo para o modo imersivo pela última vez (o painel abre a aba)."""
        try:
            pasta: Path = self.n.cfg.caminho("barehands", "pasta_estado")
            return float((pasta / "tela-comando.json").stat().st_mtime)
        except (OSError, KeyError):
            return 0.0

    def inicio(self) -> dict[str, Any]:
        from zervis.memoria.linha import agora

        hoje = self.n.consumo.retrato()
        lido = sum(int(hoje.get(k) or 0) for k in ("entrada", "cache_lido", "cache_criado"))
        totais = [
            g["total_ms"]
            for g in _latencia_de_hoje(self.painel.pasta_latencias, agora().date().isoformat())
            if g.get("origem") == "voz" and g.get("total_ms")
        ]
        trabalhando = set(self.n.sessoes.trabalhando())
        sessoes = self.n.sessoes.listar()
        proximas = sorted(
            (j for j in self.n.jobs.listar() if j.ativo and j.proxima), key=lambda j: j.proxima
        )[:3]
        atual = self.n.foco.atual()
        return {
            "ze": self.n.maquina.estado.value,
            "foco": {"titulo": atual.titulo, "passo": atual.proximo_passo} if atual else None,
            "sessoes": {
                "total": len(sessoes),
                "trabalhando": [s.nome for s in sessoes if s.id in trabalhando],
            },
            "proximas": [{"nome": j.nome, "quando": j.proxima} for j in proximas],
            "hoje": {
                "respostas": int(hoje.get("respostas") or 0) + int(hoje.get("locais") or 0),
                "tokens_mil": round(lido / 1000),
                "voz_s": round(min(totais) / 1000, 1) if totais else None,
            },
        }

    def automacoes(self) -> list[dict[str, Any]]:
        return [
            {
                "id": j.id,
                "nome": j.nome,
                "tipo": j.tipo,
                "agenda": j.agenda,
                "proxima": j.proxima,
                "ativo": j.ativo,
                "ultimo_status": j.ultimo_status,
            }
            for j in self.n.jobs.listar()
        ]

    def foco(self) -> dict[str, Any]:
        return dict(self.n.foco.quadro())

    def acao_no_foco(self, dados: dict[str, Any]) -> dict[str, Any]:
        from zervis.foco.frentes import FocoErro

        foco, id_, acao = self.n.foco, str(dados.get("id", "")), str(dados.get("acao", ""))
        try:
            f = foco.por_id(id_)
            if acao == "passo":
                foco.passo_feito(f.id)
            elif acao == "concluir":
                foco.concluir(f.id)
            elif acao == "pausar":
                foco.atualizar(f.id, estado="pausada")
            elif acao == "focar":
                foco.focar(f.id)
            elif acao == "descartar":
                foco.atualizar(f.id, estado="descartada")
            elif acao == "passo_novo":
                foco.atualizar(f.id, proximo_passo=str(dados.get("texto", "")))
            else:
                raise PedidoInvalido("ação desconhecida")
        except FocoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.painel.foco()

    def ativar_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        from zervis.memoria.linha import agora

        id_ = str(dados.get("id", ""))
        if dados.get("ativo"):
            self.painel._chamar(lambda: self.n.jobs.retomar(id_, agora()))
        else:
            self.painel._chamar(lambda: self.n.jobs.pausar(id_))
        return self.painel.automacoes()

    def remover_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self.painel._chamar(lambda: self.n.jobs.remover(str(dados.get("id", ""))))
        return self.painel.automacoes()
