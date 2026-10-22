"""Pedido de 15/10/2026: confirmar pelo nome e anunciar cada resultado sem ler o prompt."""

import asyncio
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from claude_agent_sdk import PermissionResultAllow, ToolPermissionContext, create_sdk_mcp_server

from zervis.avisos import central
from zervis.avisos.fila import Fila
from zervis.cerebro.base import Resposta
from zervis.cerebro.claude import ClaudeBrain
from zervis.cerebro.codex import CodexBrain
from zervis.cerebro.codex_mcp import FerramentasCodex
from zervis.cerebro.ferramentas import sessoes as ferramentas
from zervis.habilidades import revisao
from zervis.nucleo import estados as e
from zervis.nucleo.servicos.avisos import ServicoAvisos
from zervis.nucleo.servicos.oficina import ServicoOficina
from zervis.oficina.sessoes import Sessao, Sessoes


@pytest.mark.parametrize("motor", ["claude", "codex"])
@pytest.mark.parametrize("confirma", [True, False])
def test_confirmacao_curta_fixa_o_destino_e_envia_o_prompt_so_depois_do_sim(
    tmp_path: Path, motor: str, confirma: bool
) -> None:
    enviados: list[tuple[str, str]] = []

    async def trabalhar(sessoes: Sessoes, sessao: Sessao, texto: str) -> str:
        enviados.append((sessao.id, texto))
        return "Pedido atendido."

    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=trabalhar)
    loja = sessoes.criar("Loja Virtual", str(tmp_path))
    blog = sessoes.criar("Blog", str(tmp_path))
    sessoes.focar(loja.id)
    prompt = "Corrija a busca e prove com testes.\n" + "Restrição importante.\n" * 250 + "Fim."

    async def conferir() -> None:
        consultou = asyncio.Event()
        decisao: asyncio.Future[Resposta] = asyncio.get_running_loop().create_future()
        frases: list[str] = []

        async def aprovar(frase: str) -> Resposta:
            frases.append(frase)
            consultou.set()
            return await decisao

        tipo = CodexBrain if motor == "codex" else ClaudeBrain
        brain = tipo(
            "m",
            [],
            tmp_path / "cerebro",
            prechecar=ferramentas.preparador(sessoes),
            descrever_extra=ferramentas.descritor(sessoes),
        )
        brain.aprovar = aprovar
        tools = ferramentas.ferramentas(sessoes)
        entrada = {"sessao": "", "texto": prompt}
        ponte = None

        async def enviar() -> Any:
            if isinstance(brain, CodexBrain):
                return await brain._atender_codex(
                    "item/tool/call",
                    {
                        "threadId": "fio",
                        "turnId": "turno",
                        "tool": "ze__jarvis__sessao_enviar",
                        "arguments": entrada,
                    },
                )
            permissao = await brain._pode_usar(
                "mcp__jarvis__sessao_enviar", entrada, ToolPermissionContext()
            )
            if isinstance(permissao, PermissionResultAllow):
                assert entrada == {"sessao": loja.id, "texto": prompt}
                ferramenta = next(t for t in tools if t.name == "sessao_enviar")
                return await ferramenta.handler(entrada)
            return permissao

        if isinstance(brain, CodexBrain):
            ponte = FerramentasCodex({"jarvis": create_sdk_mcp_server("jarvis", tools=tools)}, [])
            await ponte.iniciar()
            brain.fio, brain.turno, brain.ponte_mcp = "fio", "turno", ponte
        try:
            tarefa = asyncio.create_task(enviar())
            await asyncio.wait_for(consultou.wait(), 3)
            assert frases == ["Estou enviando sua solicitação à sessão Loja Virtual, confirma?"]
            assert enviados == []
            # Um resultado de outra sessão chega durante a aprovação e muda o foco.
            sessoes.focar(blog.id)
            decisao.set_result(Resposta(confirma, "sim" if confirma else "não"))
            resultado = await asyncio.wait_for(tarefa, 3)
            if confirma:
                for _ in range(100):
                    if enviados and sessoes.ler(loja.id).estado == "parada":
                        break
                    await asyncio.sleep(0.01)
                assert enviados == [(loja.id, prompt)]
                assert sessoes.ler(blog.id).ultimo_pedido == ""
            else:
                assert enviados == []
                assert sessoes.ler(loja.id).estado == "parada"
                assert sessoes.ler(loja.id).ultimo_pedido == ""
                if isinstance(brain, CodexBrain):
                    assert resultado["success"] is False
        finally:
            if not decisao.done():
                decisao.set_result(Resposta(False))
            await brain.close()

    asyncio.run(conferir())


def test_criar_com_prompt_longo_tem_uma_unica_pergunta_curta(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *_: "")
    frase = ferramentas.descritor(sessoes)(
        "mcp__jarvis__sessao_criar",
        {"nome": "Site", "pasta": str(tmp_path), "tarefa": "Prompt técnico. " * 500},
    )
    assert frase is not None
    assert frase == "Estou enviando sua solicitação à sessão Site, confirma?"
    frase_projeto_novo = ferramentas.descritor(sessoes)(
        "mcp__jarvis__sessao_criar",
        {"nome": "", "projeto_novo": "Projeto novo", "tarefa": "Faça a tarefa."},
    )
    assert frase_projeto_novo == "Estou enviando sua solicitação à sessão Projeto-novo, confirma?"
    maquina = e.Maquina(estado=e.Estado.PENSANDO)
    assert maquina.tratar(e.PedidoAprovacao(frase), 1) == [e.Falar(frase)]
    maquina.tratar(e.FalaOcioso(), 2)
    assert maquina.tratar(e.FimDeFala("sim"), 3) == [e.ResponderAprovacao(True, "sim")]


def test_destino_ambiguo_nao_pede_aprovacao_nem_escolhe_outra_sessao(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *_: "não deve rodar")
    sessoes.criar("Site principal", str(tmp_path))
    sessoes.criar("Site novo", str(tmp_path))
    entrada = {"sessao": "Site", "texto": "Conserte o menu."}
    erro = ferramentas.preparador(sessoes)("mcp__jarvis__sessao_enviar", entrada)
    assert erro and "mais de uma" in erro
    assert entrada["sessao"] == "Site"
    assert not sessoes.trabalhando()


class AmbienteDeAvisos:
    """Máquina e fila reais; som e sessões sintéticos para não operar contas nem hardware."""

    def __init__(self, pasta: Path, modo: str) -> None:
        self.modo_fala, self.chamado = modo, "voz"
        self.maquina = e.Maquina(estado=e.Estado.PENSANDO, em_conversa=True)
        self.fila = Fila(pasta / "avisos.json")
        self.eventos: queue.Queue[e.Aviso] = queue.Queue()
        self.segmentador = SimpleNamespace(em_fala=False)
        self.transcrevendo = None
        self.cfg = {"revisao": {"modelo": "sintetico"}}
        self.consumo = SimpleNamespace(somar=lambda *args: None)
        self._meta: dict[str, Any] = {}
        self.linha: list[str] = []
        self.focadas: list[str] = []
        self.sessoes = SimpleNamespace(focar=self.focadas.append)
        self.servico = ServicoAvisos(self)  # type: ignore[arg-type]

    def _na_linha(self, tipo: str, texto: str) -> None:
        self.linha.append(texto)

    def _pessoa_falando(self) -> bool:
        return self.servico._pessoa_falando()

    def _sair_da_fila(self) -> None:
        self.servico._sair_da_fila()

    def _ultima_resposta(self, id_: str) -> str:
        return "Corrigi a busca e os testes passaram."

    def _aviso_da_oficina(self, *args: Any) -> None:
        self.servico._aviso_da_oficina(*args)

    def vendo(self, id_: str) -> bool:
        return True  # estar com a sessão aberta não deve ocultar seu resultado falado

    def consumir(self) -> list[str]:
        falas = []
        while not self.eventos.empty():
            aviso = self.eventos.get_nowait()
            for efeito in self.maquina.tratar(aviso, time.monotonic()):
                if isinstance(efeito, e.ReterAviso):
                    self.servico._guardar(efeito.texto)
                elif isinstance(efeito, e.Falar):
                    falas.append(efeito.texto)
        return falas


@pytest.mark.parametrize("modo", ["avisos", "maos_livres"])
def test_tres_sessoes_avisam_uma_por_vez_sem_pedir_proximo(tmp_path: Path, modo: str) -> None:
    ambiente = AmbienteDeAvisos(tmp_path, modo)
    oficina = ServicoOficina(ambiente)  # type: ignore[arg-type]
    for nome in ("Loja", "Blog", "Site"):
        oficina._sessao_terminou(Sessao(nome, nome, str(tmp_path), "claude"), "feito")
    assert ambiente.consumir() == []  # chegam durante outra resposta, ficam guardados
    assert len(ambiente.fila.validos()) == 3
    ambiente.fila = Fila(tmp_path / "avisos.json")  # a espera continua depois de recarregar
    ambiente.maquina.tratar(e.RespostaFim(), 1)
    for nome in ("Loja", "Blog", "Site"):
        ambiente.servico._aviso_ao_vivo()
        assert ambiente.consumir() == [
            f"Resultado da sessão {nome}. Ela informou: Corrigi a busca e os testes passaram."
        ]
        ambiente.servico._aviso_ao_vivo()
        assert ambiente.eventos.empty()  # a próxima não fala por cima da atual
        ambiente.maquina.tratar(e.FalaOcioso(), 2)
    assert not ambiente.fila.validos()
    assert len(ambiente.linha) == 3


def test_resultado_espera_a_pessoa_parar_de_falar(tmp_path: Path) -> None:
    ambiente = AmbienteDeAvisos(tmp_path, "avisos")
    ambiente.fila.guardar("Resultado da sessão Loja.", sessao="loja")
    ambiente.maquina.estado = e.Estado.OUVINDO
    ambiente.segmentador.em_fala = True
    ambiente.servico._aviso_ao_vivo()
    assert ambiente.eventos.empty() and len(ambiente.fila.validos()) == 1
    ambiente.segmentador.em_fala = False
    ambiente.servico._aviso_ao_vivo()
    assert ambiente.consumir() == ["Resultado da sessão Loja."]


def test_silencioso_registra_os_resultados_sem_falar(tmp_path: Path) -> None:
    ambiente = AmbienteDeAvisos(tmp_path, "silencioso")
    oficina = ServicoOficina(ambiente)  # type: ignore[arg-type]
    for nome in ("Loja", "Blog", "Site"):
        oficina._sessao_terminou(Sessao(nome, nome, str(tmp_path), "claude"), "feito")
    assert ambiente.eventos.empty() and len(ambiente.linha) == 3


def test_fila_preserva_tres_resultados_publicados_simultaneamente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Fila._ler
    barreira = threading.Barrier(3)
    arquivo = tmp_path / "avisos.json"

    def ler_lento(self: Fila) -> Any:
        dados = original(self)
        time.sleep(0.01)  # amplia a janela em que uma escrita podia apagar outra
        return dados

    monkeypatch.setattr(Fila, "_ler", ler_lento)

    def publicar(nome: str) -> None:
        fila = Fila(arquivo)
        barreira.wait(timeout=3)
        fila.guardar(f"Resultado da sessão {nome}.", sessao=nome)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(publicar, ["Loja", "Site", "Blog"]))
    assert {a.sessao for a in Fila(arquivo).validos()} == {"Loja", "Site", "Blog"}
    assert arquivo.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("modelo_falha", [False, True])
def test_resumo_preserva_pedido_e_pendencia_mesmo_se_o_modelo_falhar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modelo_falha: bool
) -> None:
    ambiente = AmbienteDeAvisos(tmp_path, "avisos")
    pedidos: list[str] = []
    resposta = "## Feito\nCorrigi a busca. Testes não executados por falta de acesso."

    async def resumir(prompt: str, *args: Any) -> tuple[str, None]:
        pedidos.append(prompt)
        if modelo_falha:
            raise RuntimeError("provedor indisponível")
        return "Ela corrigiu a busca, mas os testes ficaram pendentes por falta de acesso.", None

    monkeypatch.setattr(revisao, "perguntar_ao_modelo", resumir)
    asyncio.run(
        ambiente.servico._narrar_fim(
            "loja",
            "Loja",
            resposta,
            "a sessão Loja terminou",
            resposta,
            "Corrija a busca e execute os testes.",
        )
    )
    assert "Corrija a busca e execute os testes." in pedidos[0]
    assert "Testes não executados por falta de acesso." in pedidos[0]
    aviso = ambiente.eventos.get_nowait()
    assert aviso.sequencial and "sessão Loja" in aviso.texto
    if modelo_falha:
        assert aviso.texto.endswith("Ela informou: Testes não executados por falta de acesso.")
    else:
        assert "testes ficaram pendentes" in aviso.texto


def test_resposta_longa_mantem_as_ressalvas_do_fim_no_pedido_de_resumo() -> None:
    resposta = "Correção feita.\n" + "Detalhes intermediários.\n" * 400 + "Publicação pendente."
    prompt = central.pedido_de_resumo(resposta, "Corrija e publique.")
    assert "Corrija e publique." in prompt and "Publicação pendente." in prompt
    assert "Só afirme conclusão" in prompt
