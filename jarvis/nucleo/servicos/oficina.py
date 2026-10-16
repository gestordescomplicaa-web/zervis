"""Serviço de oficina; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import contextlib
import logging
import queue
import subprocess
import threading
import time
from typing import Any, Protocol

from jarvis import atividade, diagnostico
from jarvis.avisos import central
from jarvis.avisos import modo as modo_fala
from jarvis.cerebro import ferramentas
from jarvis.habilidades import evidencias
from jarvis.nucleo import estados as e
from jarvis.nucleo.apoio import ESTADO, Status
from jarvis.oficina.manutencao import ORIGEM as ORIGEM_MANUTENCAO
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.progresso import Progresso
from jarvis.oficina.sessoes import Sessao, SessaoErro, Sessoes
from jarvis.rosto import tela

log = logging.getLogger(__name__)


MARCO_DO_DIAGNOSTICO = "diagnostico-desde"


class ContextoOficina(Protocol):
    _aplicar_depois: bool | None
    atualizacao: Progresso
    eventos: queue.Queue[e.Evento]
    evidencias: evidencias.Evidencias
    manutencao: Manutencao
    modo_fala: Any
    sessoes: Sessoes
    status: Status
    tela: tela.Tela

    def _aviso_da_oficina(
        self, texto: str, tipo: modo_fala.Tipo, id_: str = "", titulo: str = "", detalhe: str = ""
    ) -> None: ...
    def _comando_especial(self, nome: str, argumento: str) -> str: ...
    def _contexto_da_manutencao(self) -> str: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...
    async def _narrar_fim(
        self, id_: str, nome: str, resposta: str, titulo: str, detalhe: str, pedido: str = ""
    ) -> None: ...
    def _outras_trabalhando(self) -> list[str]: ...
    def _ultima_resposta(self, id_: str) -> str: ...
    def aplicar_melhorias(self, revisado: bool = False) -> str: ...
    def vendo(self, id_: str) -> bool: ...


class ServicoOficina:
    def __init__(self, contexto: ContextoOficina) -> None:
        self.n = contexto

    def _contexto_da_manutencao(self) -> str:
        partes = [self.n.tela.resumo()]
        if self.n.status.ultimo_erro and time.time() - self.n.status.erro_em < 3600:
            partes.append(f"Último erro do JARVIS: {self.n.status.ultimo_erro}.")
        return " ".join(partes)

    @staticmethod
    def _descrever_manutencao(nome: str, entrada: dict[str, Any]) -> str | None:
        """A frase da aprovação do modo manutenção (pelo cérebro, quando a frase escapou)."""
        if nome != f"mcp__{ferramentas.SERVIDOR}__modo_manutencao":
            return None
        if entrada.get("acao") == "entrar":
            agente = "Codex" if entrada.get("agente") == "codex" else "Claude"
            return (
                f"Vou ligar o modo manutenção com o {agente}; "
                "seus pedidos vão para a sessão de código."
            )
        return "Vou desligar o modo manutenção." if entrada.get("acao") == "sair" else None

    def diagnosticar(self, registro: list[str]) -> tuple[str, str]:
        """Monta o diagnóstico (atividade e registro técnico), guarda o último e o entrega à
        sessão de autodesenvolvimento; só no estado de manutenção (ADR 0025, 0026 e 0028)."""
        if not self.n.manutencao.ligado:
            return "", "Entre no modo manutenção para diagnosticar."
        relatorio = diagnostico.montar(
            atividade.PADRAO.listar(5000), registro, desde=self.marco_do_diagnostico()
        )
        arquivo = ESTADO / "diagnostico.md"
        arquivo.write_text(relatorio)
        arquivo.chmod(0o600)
        m = self.n.manutencao
        m.abrir_sessao()
        aviso = m.encaminhar(
            "diagnóstico",
            self.n._contexto_da_manutencao(),
            time.time(),
            diagnostico.PEDIDO + relatorio,
        )
        atividade.PADRAO.registrar(
            "execucao", "Diagnóstico enviado ao autodesenvolvimento", autorizacao="painel"
        )
        return relatorio, aviso

    @staticmethod
    def marco_do_diagnostico() -> float:
        """Quando a pessoa recomeçou o diagnóstico (0: nunca)."""
        try:
            return float((ESTADO / MARCO_DO_DIAGNOSTICO).read_text().strip() or 0)
        except (OSError, ValueError):
            return 0.0

    def recomecar_diagnostico(self) -> str:
        """Daqui em diante, o diagnóstico só conta o que vier depois. A Atividade e o registro
        técnico continuam guardados: tudo o que o Zé executou fica registrado (essência, 6)."""
        arquivo = ESTADO / MARCO_DO_DIAGNOSTICO
        arquivo.write_text(f"{time.time():.0f}\n")
        arquivo.chmod(0o600)
        atividade.PADRAO.registrar("execucao", "Diagnóstico recomeçado", autorizacao="painel")
        return "Diagnóstico recomeçado."

    def _outras_trabalhando(self) -> list[str]:
        """As sessões de outros projetos no meio de um trabalho (o reinício as interromperia)."""
        ids = []
        for id_ in self.n.sessoes.trabalhando():
            with contextlib.suppress(SessaoErro):
                if self.n.sessoes.ler(id_).origem != ORIGEM_MANUTENCAO:
                    ids.append(id_)
        return ids

    def mudar_manutencao(self, ligar: bool) -> str:
        """Entra ou sai do estado de manutenção pelo painel (ADR 0028), igual à voz."""
        if not ligar:
            self.n._comando_especial("manutencao_sair", "")
            return "Manutenção desligada."
        texto = self.n.manutencao.entrar()
        return texto if texto.startswith("Não entrei") else "Manutenção ligada."

    def _aplicar_quando_livre(self) -> None:
        """A atualização esperando as outras sessões terminarem: sai assim que ficarem livres."""
        # Este ciclo roda no laço da voz: uma operação de sessão demorada fica para a
        # próxima volta, sem prender o microfone esperando a trava.
        if not self.n.sessoes._operacoes.acquire(blocking=False):
            return
        try:
            if not self.n.manutencao.ligado:
                self.n._aplicar_depois = None
                self.n.atualizacao.cancelar_espera()
            elif self.n._aplicar_depois is not None and not self.n._outras_trabalhando():
                revisado, self.n._aplicar_depois = self.n._aplicar_depois, None
                self.n.aplicar_melhorias(revisado)
        finally:
            self.n.sessoes._operacoes.release()

    def aplicar_melhorias(self, revisado: bool = False) -> str:
        """Testa a cópia, junta as melhorias e reinicia, em segundo plano (os testes demoram);
        o resultado chega como aviso e fica na atividade. Só no estado de manutenção e sem
        interromper ninguém: com outras sessões trabalhando, espera elas terminarem (ADR 0028)."""
        # A mesma trava do envio e do terminal: ninguém começa entre conferir as sessões
        # livres e reservar a atualização. Os testes rodam fora dela, em segundo plano.
        with self.n.sessoes._operacoes:
            if not self.n.manutencao.ligado:
                return "Entre no modo manutenção para aplicar."
            if outras := self.n._outras_trabalhando():
                if not self.n.atualizacao.aguardar():
                    return "Atualização em andamento."
                self.n._aplicar_depois = revisado
                if len(outras) == 1:
                    return "Uma sessão está trabalhando. Aplico quando ela terminar."
                return f"{len(outras)} sessões estão trabalhando. Aplico quando terminarem."
            if not self.n.atualizacao.comecar():
                return "Atualização em andamento."
            self.n._aplicar_depois = None

        def aplicar() -> None:
            try:
                ok, texto = self.n.manutencao.aplicar(revisado)
            except (OSError, subprocess.SubprocessError, SessaoErro) as erro:
                ok, texto = False, f"Não consegui aplicar as melhorias: {erro}"
            except Exception:
                log.exception("atualização: falha ao aplicar melhorias")
                ok, texto = (
                    False,
                    "Não foi possível aplicar as melhorias. Consulte o registro técnico.",
                )
            if not ok:
                self.n.atualizacao.falhou(texto)
                atividade.PADRAO.registrar("falha", "Mudanças não aplicadas", motivo=texto)
            self.n._na_linha("manutencao", texto)
            self.n.eventos.put(e.Aviso(texto))

        threading.Thread(target=aplicar, name="aplicar-melhorias", daemon=True).start()
        return "Aplicando as melhorias: primeiro os testes na cópia, depois eu reinicio."

    def _rodada_de_melhoria(self) -> str:
        """Junta as evidências do uso real e pede à sessão de código uma lista curta, sem fazer."""
        m = self.n.manutencao
        if not m.ligado:
            entrou = m.entrar("")
            if not m.ligado:
                return entrou
        agora = time.time()
        provas = self.n.evidencias.resumo(agora)
        if maos := evidencias.maos(self.n.tela.pasta / "maos-diagnostico.json"):
            provas += " " + maos
        corpo = (
            "Rodada de melhoria pedida pelo usuário. Evidências do uso real do JARVIS: "
            f"{provas} Proponha até cinco melhorias numeradas, da mais útil para a menos, cada "
            "uma com o problema que resolve e o risco. Não implemente nada ainda: o usuário "
            "aprova por voz quais fazer, e então faça uma por vez."
        )
        return m.encaminhar("rodada de melhoria", self.n._contexto_da_manutencao(), agora, corpo)

    def _manutencao_chegou(self, agora: float) -> None:
        """O que a sessão de código respondeu vira um aviso falado (na hora, se estiver livre)."""
        try:
            chegadas = self.n.manutencao.verificar(agora)
        except OSError as erro:
            log.warning("manutenção: %s", erro)
            return
        # O script do reinício seguro escreve o resultado depois que este processo já subiu.
        if (voltou := self.n.manutencao.resultado_do_reinicio()) is not None:
            self.n.eventos.put(e.Aviso(voltou))
        agente = self.n.manutencao.nome_do_agente
        for c in chegadas:
            if c.tipo == "pergunta":
                texto = f"O {agente} pergunta: {c.texto}"
                if not self.n.manutencao.ligado:
                    texto += " Entre no modo manutenção para responder."
            elif c.tipo == "demora":
                texto = (
                    "O pedido de manutenção passou de quarenta e cinco minutos; veja a sessão "
                    "no painel."
                )
            else:
                # Uma frase, nunca o conteúdo (ADR 0027): a resposta fica na sessão, na tela.
                texto = "A sessão de autodesenvolvimento terminou."
                if c.protegidos:
                    texto += " A mudança mexeu na zona protegida: revise antes de aplicar."
                if c.mudou_codigo:
                    texto += " Há mudanças para aprovar em Autodesenvolvimento."
                else:
                    texto += " Veja a resposta em Autodesenvolvimento."
            log.info("manutenção: %s do pedido %s", c.tipo, c.pedido)
            self.n.eventos.put(e.Aviso(texto))

    def _sessao_terminou(self, sessao: Sessao, resumo: str) -> None:
        """Cada sessão informa o resultado em Normal e Mãos livres. A de manutenção tem seu
        próprio resumo falado, salvo se falhar."""
        if sessao.estado == "trabalhando":
            self.n._aviso_da_oficina(
                f"Sessão {sessao.nome}: {resumo}",
                "notificacao",
                sessao.id,
                f"a sessão {sessao.nome} continua em outra conta",
            )
            return
        if sessao.limite and sessao.estado == "erro" and "bateu o limite" not in resumo:
            self.n._aviso_da_oficina(
                f"Sessão {sessao.nome}: {resumo}",
                "urgente",
                sessao.id,
                f"a sessão {sessao.nome} precisa de uma conta disponível",
            )
            return
        if sessao.origem == ORIGEM_MANUTENCAO and sessao.estado != "erro":
            return
        nome = sessao.nome
        if sessao.estado == "erro" and "bateu o limite" in resumo:
            texto = f"Créditos esgotados na sessão {nome}. Troque de conta para continuar."
            self.n._aviso_da_oficina(texto, "urgente", sessao.id, f"a sessão {nome} sem créditos")
            return
        if sessao.estado == "erro":
            titulo = f"a sessão {nome} falhou"
            self.n._aviso_da_oficina(f"A sessão {nome} falhou.", "urgente", sessao.id, titulo)
            return
        resposta = self.n._ultima_resposta(sessao.id) or resumo
        detalhe = modo_fala.para_ouvir(resposta)
        titulo = f"a sessão {nome} terminou"
        ponte = getattr(self.n, "ponte", None)
        if ponte is None or not resposta.strip() or self.n.modo_fala == "silencioso":
            texto = central.narrar(nome, None, resposta)
            self.n._aviso_da_oficina(texto, "notificacao", sessao.id, titulo, detalhe)
            return
        asyncio.run_coroutine_threadsafe(
            self.n._narrar_fim(sessao.id, nome, resposta, titulo, detalhe, sessao.ultimo_pedido),
            ponte.laco,
        )

    def _sessao_pede(self, sessao: Sessao, mensagem: str) -> None:
        """O agente parou esperando a aprovação da pessoa."""
        self.n._aviso_da_oficina(
            f"A sessão {sessao.nome} está esperando sua aprovação.",
            "urgente",
            sessao.id,
            f"a sessão {sessao.nome} pede aprovação",
        )

    def _avisar_interrompidas(self) -> None:
        """Depois de um reinício: cada sessão que estava no meio de um pedido vira um aviso, com
        a oferta de continuar (a conversa dela está intacta)."""
        for s in getattr(self.n.sessoes, "interrompidas_ao_subir", []):
            if s.origem == ORIGEM_MANUTENCAO:
                continue
            texto = (
                f"A sessão {s.nome} foi interrompida pelo reinício no meio de um pedido. "
                "Posso mandá-la continuar de onde parou."
            )
            atividade.PADRAO.registrar("falha", f"Tarefa interrompida: sessão {s.nome}",
                                       origem="sistema", pedido=s.interrompida[:300])  # fmt: skip
            self.n._aviso_da_oficina(
                texto, "notificacao", s.id, f"a sessão {s.nome} foi interrompida"
            )
        self.n.sessoes.interrompidas_ao_subir = []
