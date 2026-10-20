"""Registro das rotas do painel; cada página recebe apenas os serviços que usa."""

from functools import partial
from pathlib import Path
from typing import Any

from jarvis.automacoes.jobs import JobErro
from jarvis.cerebro.mcp_externo import McpInvalido
from jarvis.habilidades.skills import SkillErro
from jarvis.habilidades.skills import dos_agentes as skills_dos_agentes
from jarvis.memoria.curta import MemoriaErro
from jarvis.oficina import arquivos
from jarvis.oficina.sessoes import SessaoErro
from jarvis.portal.acoes.acesso import AcoesAcesso
from jarvis.portal.acoes.atendimento import AcoesAtendimento
from jarvis.portal.acoes.cerebro import AcoesCerebro
from jarvis.portal.acoes.conectores import AcoesConectores
from jarvis.portal.acoes.configuracao import AcoesConfiguracao
from jarvis.portal.acoes.inicio import AcoesInicio
from jarvis.portal.acoes.melhorias import AcoesMelhorias
from jarvis.portal.acoes.memoria import AcoesMemoria
from jarvis.portal.acoes.pagina import Servicos
from jarvis.portal.acoes.sessoes import AcoesSessoes
from jarvis.portal.acoes.voz import AcoesVoz
from jarvis.portal.servidor import Escrita, Leitura, PedidoInvalido


class Acoes:
    def __init__(self, nucleo: Any, pasta_latencias: Path, pasta_teste: Path) -> None:
        self.n = nucleo
        self.pasta_latencias = pasta_latencias
        self.pasta_teste = pasta_teste
        self.conectores_pendentes = False
        self._registrar(nucleo)

    def _registrar(self, nucleo: Any) -> None:
        self._funcoes: dict[str, Any] = {}
        for tipo in (
            AcoesAtendimento,
            AcoesAcesso,
            AcoesMelhorias,
            AcoesVoz,
            AcoesCerebro,
            AcoesConfiguracao,
            AcoesSessoes,
            AcoesMemoria,
            AcoesConectores,
            AcoesInicio,
        ):
            pagina = tipo(
                self, Servicos({nome: partial(getattr, nucleo, nome) for nome in tipo.dependencias})
            )
            for nome, membro in tipo.__dict__.items():
                if callable(membro) or isinstance(membro, staticmethod):
                    self._funcoes[nome] = getattr(pagina, nome)

    def __getattr__(self, nome: str) -> Any:
        if nome == "_funcoes" or "n" not in self.__dict__:
            raise AttributeError(nome)
        if "_funcoes" not in self.__dict__:
            self._registrar(self.n)
        try:
            return self._funcoes[nome]
        except KeyError:
            raise AttributeError(nome) from None

    def leituras(self) -> dict[str, Leitura]:
        return {
            "estado": self.estado,
            "conversa": self.conversa,
            "remoto": self.remoto,
            "atividade": self.atividade,
            "configuracao": self.configuracao,
            "contas": self.contas,
            "inicio": self.inicio,
            "cerebro": self.cerebro,
            "escuta": self.escuta,
            "skills": self.skills,
            "skills/sugeridas": self.skills_sugeridas,
            "memoria": self.memoria,
            "skills/agentes": skills_dos_agentes,
            "automacoes": self.automacoes,
            "foco": self.foco,
            "sessoes": self.sessoes,
            "pastas": self.pastas,
            "conectores": self.conectores,
            "atendimento": self.atendimento,
        }

    def escritas(self) -> dict[str, Escrita]:
        return {
            "cerebro": self.mudar_cerebro,
            "fala/modo": self.mudar_modo_fala,
            "escuta/modo": self.mudar_escuta,
            "voz/token": self.token_voz,
            "voz/apertar": self.apertar,
            "voz/soltar": self.soltar,
            "voz/chamado": self.mudar_chamado,
            "voz/espera": self.mudar_espera,
            "remoto/ativar": self.ativar_remoto,
            "voz/evento": self.evento_voz,
            "atividade/registro": self.registro_tecnico,
            "ze/melhorias": self.melhorias,
            "ze/diagnosticar": self.diagnosticar,
            "ze/manutencao": self.manutencao,
            "conversa/escrever": self.escrever,
            "ze/diagnostico": self.diagnostico,
            "ze/diagnostico/recomecar": self.recomecar_diagnostico,
            "ze/sessao": self.sessao_de_melhorias,
            "ze/central": self.central_de_melhorias,
            "ze/unificar": self.unificar_melhorias,
            "ze/aplicar": self.aplicar_melhorias,
            "ze/descartar": self.descartar_melhorias,
            "acesso/senha": self.definir_senha,
            "acesso/encerrar": self.encerrar_acessos,
            "acesso/desconectar": self.desconectar_aparelho,
            "acesso/codigo/preparar": self.preparar_codigo,
            "acesso/codigo/confirmar": self.confirmar_codigo,
            "acesso/codigo/desligar": self.desligar_codigo,
            "remoto/desativar": self.desativar_remoto,
            "tunel/ativar": self.ativar_tunel,
            "tunel/desativar": self.desativar_tunel,
            "mensagens/whatsapp": self.mudar_mensagens,
            "whatsapp/conectar": self.conectar_whatsapp,
            "whatsapp/desconectar": self.desconectar_whatsapp,
            "atendente/salvar": self.salvar_atendente,
            "atendente/testar": self.testar_atendente,
            "atendente/devolver": self.devolver_atendimento,
            "atendente/publicar": self.publicar_atendente,
            "atendente/sessao": self.sessao_do_atendente,
            "atendente/esquecer": self.esquecer_atendimento,
            "atendente/chave": self.chave_do_atendente,
            "atendente/chave/apagar": self.apagar_chave_do_atendente,
            "painel/vendo": self.painel_vendo,
            "chave": self.guardar_chave,
            "chave/apagar": self.apagar_chave,
            "testar": self.testar,
            "escuta/chave": self.guardar_chave_escuta,
            "escuta/apagar": self.apagar_chave_escuta,
            "escuta/testar": self.testar_chave_escuta,
            "perfil": self.salvar_perfil,
            "acesso/chave": self.guardar_chave_claude,
            "acesso/chave-codex": self.guardar_chave_codex,
            "acesso/remover": self.remover_acesso,
            "acesso/testar": self.testar_acesso,
            "conta/adicionar": self.adicionar_conta,
            "conta/remover": self.remover_conta,
            "conta/usar": self.usar_conta,
            "conta/entrar": self.entrar_conta,
            "conta/login/ler": self.ler_login,
            "conta/login/codigo": self.codigo_login,
            "conta/login/fechar": self.fechar_login,
            "sessao/criar": self.criar_sessao,
            "sessao/ler": self.ler_sessao,
            "sessao/trocar": self.trocar_sessao,
            "sessao/modelo": self.modelo_da_sessao,
            "sessao/conectores": self.conectores_da_sessao,
            "sessao/conectores/salvar": self.salvar_conectores_da_sessao,
            "sessao/interrompida": self.tarefa_interrompida,
            "sessao/copia": lambda d: self._chamar(
                lambda: self.n.sessoes.copia(str(d.get("id", "")))
            ),
            "sessao/copia/aplicar": self.aplicar_copia,
            "sessao/copia/descartar": self.descartar_copia,
            "terminal/abrir": self.abrir_terminal,
            "terminal/ler": self.ler_terminal,
            "terminal/escrever": self.escrever_terminal,
            "terminal/tamanho": self.tamanho_terminal,
            "terminal/fechar": self.fechar_terminal,
            "sessao/arquivo": self.criar_arquivo,
            "sessao/arquivos": self.arquivos,
            "sessao/ver": self.ver_arquivo,
            "sessao/buscar": self.buscar_arquivos,
            "skill/ver": self.ver_skill,
            "skill/salvar": self.salvar_skill,
            "conector/salvar": self.salvar_conector,
            "conector/importar": self.importar_conector,
            "conector/remover": self.remover_conector,
            "conector/ligar": self.ligar_conector,
            "conector/segredo": self.segredo_conector,
            "conector/testar": self.testar_conector,
            "conectores/aplicar": self.aplicar_conectores,
            "conector/entrar": self.entrar_conector,
            "conector/entrar/concluir": self.concluir_conector,
            "conector/sair": self.sair_conector,
            "conector/cliente": self.guardar_cliente_conector,
            "conector/cliente/apagar": self.apagar_cliente_conector,
            "foco/acao": self.acao_no_foco,
            "automacao/ativar": self.ativar_automacao,
            "automacao/remover": self.remover_automacao,
            "memoria/mudar": self.mudar_memoria,
            "sugestao/decidir": self.decidir_sugestao,
            "skill/ligar": self.ligar_skill,
            "skill/instalar-sugerida": self.instalar_skill_sugerida,
            "skill/excluir": self.excluir_skill,
            "sessao/excluir": self.excluir_sessao,
            "cerebro/escolher": self.escolher_cerebro,
            "cerebro/modelo": self.modelo_do_cerebro,
            "omniroute/salvar": self.salvar_omniroute,
        }

    def envios(self) -> dict[str, Any]:
        return {"sessao/anexo": self.anexar}

    def _chamar(self, fazer: Any) -> Any:
        try:
            return fazer()
        except (
            SessaoErro,
            arquivos.ArquivoErro,
            SkillErro,
            McpInvalido,
            JobErro,
            MemoriaErro,
        ) as erro:
            raise PedidoInvalido(str(erro)) from None
