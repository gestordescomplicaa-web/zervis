"""Ações da página memoria."""

import contextlib
import logging
from typing import Any

from jarvis.habilidades import revisao
from jarvis.habilidades.skills import frente
from jarvis.memoria import aimemory
from jarvis.memoria.curta import Mudanca
from jarvis.portal.acoes.pagina import Pagina
from jarvis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesMemoria(Pagina):
    dependencias = ("diario", "memoria", "pendencias", "skills")

    def skills(self) -> list[dict[str, Any]]:
        sk = self.n.skills
        uso = sk.uso()
        sessoes = {nome for nome, _ in sk.para_sessoes()}
        ligadas = [
            {
                "nome": nome,
                "descricao": descricao,
                "ligada": True,
                "sessoes": nome in sessoes,
                "usos": (uso.get(nome) or {}).get("usos", 0),
            }
            for nome, descricao in sk.listar()
        ]
        desligadas = []
        for nome in sk.arquivadas():
            arquivo = sk.pasta / ".arquivo" / nome / "SKILL.md"
            with contextlib.suppress(OSError):
                descricao = frente(arquivo.read_text()).get("description", "")
                desligadas.append(
                    {"nome": nome, "descricao": descricao, "ligada": False, "usos": 0}
                )
        return sorted(ligadas + desligadas, key=lambda k: k["nome"])

    def skills_sugeridas(self) -> list[dict[str, str]]:
        return [
            {"nome": nome, "descricao": descricao} for nome, descricao in self.n.skills.sugeridas()
        ]

    def memoria(self) -> dict[str, Any]:
        m = self.n.memoria
        return {
            "usuario": m.entradas("usuario"),
            "jarvis": m.entradas("jarvis"),
            "limites": dict(m.limites),
            # O que o Zé aprendeu sozinho numa conversa e espera a pessoa (memória e skill).
            "sugestoes": [revisao.resumo_dict(p) for p in self.n.pendencias.listar()],
            "projetos": aimemory.situacao(),  # a memória das sessões, por projeto (ai-memory)
        }

    def decidir_sugestao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Aprovar ou descartar uma sugestão pelo painel: o mesmo caminho da voz."""
        id_, aprovar = str(dados.get("id", "")), bool(dados.get("aprovar"))
        try:
            proposta = self.n.pendencias.tirar(id_)
        except KeyError:
            raise PedidoInvalido("Sugestão não encontrada.") from None
        if aprovar:
            self.painel._chamar(lambda: revisao.aplicar(proposta, self.n.memoria, self.n.skills))
            self.n.diario.registrar(
                "aprovada",
                proposta.resumo,
                origem=proposta.origem,
                sugerida=round(proposta.criada),
                **revisao.alvo_da_proposta(proposta),
            )
        else:
            self.n.diario.registrar("descartada", proposta.resumo, origem=proposta.origem)
        return {**self.painel.memoria(), "aviso": "Aprovada." if aprovar else "Descartada."}

    def ver_skill(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", ""))
        conteudo = self.painel._chamar(lambda: self.n.skills.atual(nome))
        if not conteudo:
            raise PedidoInvalido("skill desconhecida")
        return {"nome": nome, "conteudo": conteudo}

    def salvar_skill(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O próprio usuário escreve: grava direto (a versão anterior vai para o histórico)."""
        nome, conteudo = str(dados.get("nome", "")).strip(), str(dados.get("conteudo", ""))
        skills = self.n.skills

        def validar() -> str:
            atual = skills.atual(nome)
            if atual:
                return str(skills.novo_conteudo(nome, antigo=atual, novo=conteudo))
            return str(skills.novo_conteudo(nome, conteudo))

        final = self.painel._chamar(validar)
        skills.gravar(nome, final)
        return {"nome": nome, "skills": self.painel.skills()}

    def mudar_memoria(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O próprio usuário adiciona ou tira uma entrada: vale na próxima conversa."""
        acao, alvo, texto = (str(dados.get(k, "")) for k in ("acao", "alvo", "texto"))
        if acao not in ("adicionar", "remover") or alvo not in ("usuario", "jarvis"):
            raise PedidoInvalido("pedido inválido")
        mudanca = (
            Mudanca(acao, alvo, texto=texto)
            if acao == "adicionar"
            else Mudanca(acao, alvo, antigo=texto)
        )
        self.painel._chamar(lambda: self.n.memoria.aplicar(mudanca))
        return self.painel.memoria()

    def ligar_skill(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self.painel._chamar(
            lambda: self.n.skills.ligar(str(dados.get("nome", "")), bool(dados.get("ligada")))
        )
        return self.painel.skills()

    def instalar_skill_sugerida(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self.painel._chamar(lambda: self.n.skills.instalar_sugerida(str(dados.get("nome", ""))))
        return self.painel.skills()

    def excluir_skill(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self.painel._chamar(lambda: self.n.skills.excluir(str(dados.get("nome", ""))))
        return self.painel.skills()
