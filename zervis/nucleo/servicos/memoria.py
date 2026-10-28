"""Serviço de memoria; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import concurrent.futures
import logging
import threading
import time
from datetime import datetime
from typing import Any, Protocol

from zervis import atividade, usuario
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import Jobs
from zervis.cerebro.base import Ponte
from zervis.cerebro.consumo import Consumo
from zervis.config import Config
from zervis.foco.frentes import Foco
from zervis.habilidades import revisao
from zervis.habilidades.diario import Diario
from zervis.habilidades.skills import Skills
from zervis.imersivo import Imersivo, tem_acervo
from zervis.memoria.conversas import Conversas, publicar_dia
from zervis.memoria.curta import Memoria
from zervis.memoria.dias import SISTEMA as SISTEMA_DA_NOTA
from zervis.memoria.dias import Dias
from zervis.memoria.linha import LinhaDoTempo
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import CURADORIA_S, DADOS, PASTA_S, foto_da_memoria, versoes_das_skills
from zervis.oficina.sessoes import Sessoes
from zervis.rosto import hud, pasta
from zervis.rosto import pasta as pasta_modulo
from zervis.voz.saida import Voz

log = logging.getLogger(__name__)


class ContextoMemoria(Protocol):
    _conversa_suja: Any
    _curadoria_em: Any
    _memoria_vista: str | None
    _turno_gravado: Any
    _gasto_do_turno: Any
    _na_tela: dict[str, None]
    _notas_em_curso: Any
    _pasta_em: Any
    _pasta_exec: concurrent.futures.ThreadPoolExecutor
    _pasta_rodando: concurrent.futures.Future[None] | None
    _pedido_em: Any
    _pedido_quando: Any
    _proxima_nota: Any
    _skills_vistas: dict[str, float]
    cfg: Config
    consumo: Consumo
    conversas: Conversas
    diario: Diario
    dias: Dias
    foco: Foco
    hud: hud.Hud
    imersivo: Imersivo
    jobs: Jobs
    linha: LinhaDoTempo
    maquina: e.Maquina
    memoria: Memoria
    pasta: pasta_modulo.Pasta
    pendencias: revisao.Pendencias
    ponte: Ponte
    sessoes: Sessoes
    skills: Skills
    voz: Voz

    def _conexoes(self) -> pasta_modulo.Conexoes: ...
    async def _escrever_notas(self, dias: list[Any]) -> None: ...
    def _escrever_pasta(self, conexoes: pasta_modulo.Conexoes, curar: bool) -> None: ...
    def _fim_da_conversa(self) -> None: ...
    def _foto_simples(self) -> str: ...
    def _mostrar(self, texto: str) -> None: ...


class ServicoMemoria:
    def __init__(self, contexto: ContextoMemoria) -> None:
        self.n = contexto

    def _na_linha(self, tipo: str, texto: str) -> None:
        """Um evento na linha do tempo; falha de disco não derruba nada."""
        if tipo == "aviso":
            self.n._na_tela[texto] = None
            while len(self.n._na_tela) > 50:
                del self.n._na_tela[next(iter(self.n._na_tela))]
        try:
            self.n.linha.registrar(tipo, texto)
        except (OSError, ValueError) as erro:
            log.warning("linha do tempo: %s", erro)

    def _foto_simples(self) -> str:
        return foto_da_memoria(self.n.memoria, getattr(self.n, "skills", None))

    def _foto_do_cerebro(self) -> str:
        """A foto que o cérebro põe no começo de cada sessão dele, guardada para comparar: o
        cérebro conecta ao subir, antes do primeiro pedido (13/10/2026: a pessoa apagou a memória
        depois do reinício e o Zé ainda respondia com o que estava lá)."""
        self.n._memoria_vista = self.n._foto_simples()
        self.n._skills_vistas = versoes_das_skills(getattr(self.n, "skills", None))
        return self.n._memoria_vista

    def _com_memoria(self, pedido: str) -> str:
        """A memória curta ou as skills mudaram no meio da conversa (painel, aprovação, voz): o
        pedido leva a versão nova, porque a foto do começo da conversa ficou velha (13/10/2026: a
        pessoa adicionou uma preferência e o Zé disse que a memória estava vazia; criou uma skill e
        ele não a leu)."""
        memoria = getattr(self.n, "memoria", None)
        if memoria is None:
            return pedido
        atual = foto_da_memoria(memoria, getattr(self.n, "skills", None))
        vista, self.n._memoria_vista = getattr(self.n, "_memoria_vista", None), atual
        # Skill editada (o conteúdo, não só a descrição): o que o cérebro leu antes ficou velho.
        versoes = versoes_das_skills(getattr(self.n, "skills", None))
        antes, self.n._skills_vistas = getattr(self.n, "_skills_vistas", None) or {}, versoes
        mudou = sorted(n for n, v in versoes.items() if n in antes and antes[n] != v)
        if vista is None or (vista == atual and not mudou):
            return pedido

        # O que saiu precisa ser dito: sem isso, o cérebro junta o velho e o novo (13/10/2026:
        # trocou "banana" por "morango" e o Zé disse que a pessoa gostava das duas).
        def itens(foto: str) -> set[str]:
            return {linha for linha in foto.splitlines() if linha.startswith("- ")}

        saiu = sorted(itens(vista) - itens(atual))
        aviso = (
            "Saiu (não vale mais, mesmo que apareça antes nesta conversa):\n"
            + "\n".join(saiu)
            + "\n\n"
            if saiu
            else ""
        )
        if mudou:
            aviso += (
                "Skills que mudaram desde o começo da conversa (leia de novo antes de usar): "
                + ", ".join(mudou)
                + "\n\n"
            )
        return (
            "[Memória e skills atualizadas agora: valem no lugar da foto do começo da conversa]\n"
            f"{aviso}{atual}\n\n{pedido}"
        )

    def _registrar_turno(self, turno: dict[str, str]) -> None:
        """O pedido e a resposta, com a hora do pedido; a página do dia sai em segundo plano."""
        self.n._turno_gravado = turno  # a Conversa deixa de mostrá-lo como em andamento
        pedido = turno["pessoa"]
        if self.n.voz.muda and turno["jarvis"]:
            self.n._mostrar(turno["jarvis"])
        atividade.PADRAO.registrar("pedido", pedido, resposta=turno["jarvis"])
        if atividade.e_correcao(pedido):
            atividade.PADRAO.registrar("correcao", pedido)
        try:
            gasto, self.n._gasto_do_turno = getattr(self.n, "_gasto_do_turno", None), None
            feito = self.n.conversas.registrar(
                turno["pessoa"], turno["jarvis"], self.n._pedido_quando, gasto
            )
        except OSError as erro:
            log.warning("conversas: %s", erro)
            return
        threading.Thread(
            target=publicar_dia, args=(self.n.conversas, feito.em.date()), daemon=True
        ).start()

    def _nota_do_dia(self, agora: float) -> None:
        """Depois das 5h, os dias sem nota ganham a nota (um modelo menor, uma vez por dia)."""
        if self.n._notas_em_curso or agora < self.n._proxima_nota:
            return
        self.n._proxima_nota = agora + 600
        faltando = self.n.dias.faltando(datetime.fromtimestamp(agora, FUSO))
        if faltando:
            self.n._notas_em_curso = True
            asyncio.run_coroutine_threadsafe(self.n._escrever_notas(faltando), self.n.ponte.laco)

    async def _escrever_notas(self, dias: list[Any]) -> None:
        try:
            r = self.n.cfg["revisao"]
            for dia in dias:
                resumo, uso = await revisao.perguntar_ao_modelo(
                    self.n.dias.prompt(dia), r["modelo"], DADOS / "cerebro", 0, SISTEMA_DA_NOTA
                )
                self.n.consumo.somar(uso, "nota do dia")
                if resumo.strip():
                    await asyncio.to_thread(self.n.dias.guardar, dia, resumo)
                    log.info("nota do dia %s escrita", dia)
        except Exception:
            log.exception("nota do dia falhou")
        finally:
            self.n._notas_em_curso = False

    def _conversa_parada(self) -> None:
        """Muito tempo sem falar: a próxima pergunta começa uma sessão nova, com a memória."""
        limite_min = self.n.cfg["cerebro"]["nova_conversa_apos_min"]
        parado = time.monotonic() - self.n._pedido_em
        if (
            limite_min > 0
            and self.n._conversa_suja
            and parado > limite_min * 60
            and self.n.maquina.estado is e.Estado.ATIVO
        ):
            log.info("conversa parada há %.0f min: a próxima começa do zero", parado / 60)
            self.n._fim_da_conversa()
            self.n.ponte.reiniciar()
            self.n._conversa_suja = False

    def _atualizar_pasta(self, agora: float) -> None:
        """Fora da thread do laço: lê memória, skills, jobs e diário do disco."""
        if self.n._pasta_rodando is not None and not self.n._pasta_rodando.done():
            return
        if agora - self.n._pasta_em < PASTA_S:
            return
        self.n._pasta_em = agora
        curar = agora - self.n._curadoria_em >= CURADORIA_S
        if curar:
            self.n._curadoria_em = agora
        self.n._pasta_rodando = self.n._pasta_exec.submit(
            self.n._escrever_pasta, self.n._conexoes(), curar
        )

    def _escrever_pasta(self, conexoes: pasta.Conexoes, curar: bool) -> None:
        dias = self.n.cfg["skills"]["arquivar_apos_dias"]
        try:
            if curar and dias > 0:
                for nome in self.n.skills.arquivar_paradas(dias, time.time()):
                    log.info("curadoria: skill %s arquivada (sem uso há %.0f dias)", nome, dias)
                    self.n.diario.registrar(
                        "arquivada", f"a skill {nome}, sem uso há {dias:.0f} dias"
                    )
            notas = pasta.notas(
                conexoes,
                self.n.memoria,
                self.n.skills,
                dias,
                self.n.jobs,
                self.n.pendencias,
                self.n.diario,
                self.n.consumo,
            )
            if mudadas := self.n.pasta.gravar(notas):
                log.info("pasta do Zé: %s", ", ".join(mudadas))
            agora = time.time()
            self.n.hud.gravar("eficiencia", hud.eficiencia(self.n.consumo), agora)
            self.n.hud.gravar(
                "mapa",
                hud.mapa(
                    conexoes,
                    self.n.memoria,
                    self.n.skills,
                    self.n.jobs,
                    self.n.diario,
                    agora,
                    usuario.PERFIL,
                ),
                agora,
            )
            sessoes = self.n.sessoes.listar()
            self.n.hud.gravar("trabalho", hud.trabalho(sessoes), agora)
            self.n.hud.gravar(
                "orbes",
                hud.orbes(
                    self.n.foco.quadro(),
                    len(sessoes),
                    bool(self.n.cfg["barehands"]["desenvolvedor"]),
                    any(j.ativo for j in self.n.jobs.listar()),
                    tem_acervo(self.n.imersivo.acervo),
                ),
                agora,
            )
        except Exception:
            log.exception("pasta do Zé falhou")
