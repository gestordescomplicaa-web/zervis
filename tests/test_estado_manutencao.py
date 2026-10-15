"""Manutenção como estado do Zé (ADR 0028): aplicar só nele e sem interromper outras sessões."""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.nucleo.laco import Nucleo
from jarvis.nucleo.servicos.oficina import ServicoOficina
from jarvis.oficina.progresso import Progresso
from jarvis.oficina.sessoes import Sessao, SessaoErro, Sessoes
from jarvis.portal.senha import SO_NO_PC


class _Manutencao:
    def __init__(self, ligado: bool) -> None:
        self.ligado = ligado


class _Sessoes:
    def __init__(self, trabalhando: dict[str, str]) -> None:
        self.ativas = trabalhando  # id -> origem
        self._operacoes = threading.RLock()

    def trabalhando(self) -> list[str]:
        return list(self.ativas)

    def ler(self, id_: str) -> Sessao:
        return Sessao(id_, id_, "~/p", "claude", origem=self.ativas[id_])


class _Nucleo:
    _outras_trabalhando = Nucleo._outras_trabalhando

    def __init__(self, ligado: bool, trabalhando: dict[str, str], pasta: Path) -> None:
        self.manutencao = _Manutencao(ligado)
        self.sessoes = _Sessoes(trabalhando)
        self._aplicar_depois: bool | None = None
        self.aplicados: list[bool] = []
        self.atualizacao = Progresso(pasta)


def test_aplicar_so_no_estado_de_manutencao(tmp_path: Path) -> None:
    n = _Nucleo(False, {}, tmp_path)
    assert Nucleo.aplicar_melhorias(n, False) == "Entre no modo manutenção para aplicar."  # type: ignore[arg-type]


def test_com_outra_sessao_trabalhando_espera_e_aplica_quando_livre(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    n = _Nucleo(True, {"loja": "", "ze": "manutencao"}, tmp_path)
    aviso = Nucleo.aplicar_melhorias(n, True)  # type: ignore[arg-type]
    assert aviso == "Uma sessão está trabalhando. Aplico quando ela terminar."
    assert n._aplicar_depois is True
    aplicados: list[bool] = []
    monkeypatch.setattr(
        _Nucleo,
        "aplicar_melhorias",
        lambda self, revisado=False: aplicados.append(revisado),
        raising=False,
    )
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert aplicados == []  # a loja ainda trabalha
    del n.sessoes.ativas["loja"]  # a sessão do próprio Zé não conta
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert aplicados == [True] and n._aplicar_depois is None


def test_sair_da_manutencao_cancela_a_espera(tmp_path: Path) -> None:
    n = _Nucleo(True, {"loja": ""}, tmp_path)
    Nucleo.aplicar_melhorias(n, False)  # type: ignore[arg-type]
    n.manutencao.ligado = False
    n._aplicar_depois = None  # a saída por voz já limpa o pedido antes do próximo ciclo
    Nucleo._aplicar_quando_livre(n)  # type: ignore[arg-type]
    assert n._aplicar_depois is None
    assert n.atualizacao.foto() is None


def test_conferir_a_espera_nao_prende_o_laco_da_voz(tmp_path: Path) -> None:
    n = _Nucleo(True, {"loja": ""}, tmp_path)
    Nucleo.aplicar_melhorias(n, False)  # type: ignore[arg-type]
    # Uma operação de outra tela pode estar encerrando um processo demorado.
    with ThreadPoolExecutor(max_workers=1) as pool, n.sessoes._operacoes:
        consulta = pool.submit(Nucleo._aplicar_quando_livre, n)  # type: ignore[arg-type]
        consulta.result(timeout=1)
    assert n._aplicar_depois is False


@pytest.mark.parametrize("inesperada", [False, True])
def test_duas_telas_nao_aplicam_duas_vezes_e_a_falha_chega_ao_painel(
    tmp_path: Path, inesperada: bool
) -> None:
    iniciou, liberar = threading.Event(), threading.Event()
    chamadas: list[bool] = []
    progresso = Progresso(tmp_path)

    def aplicar(revisado: bool) -> tuple[bool, str]:
        chamadas.append(revisado)
        progresso.etapa("testes_copia")
        iniciou.set()
        assert liberar.wait(3)
        if inesperada:
            raise RuntimeError("falha inesperada")
        return False, "Os testes falharam."

    contexto: Any = SimpleNamespace(
        manutencao=SimpleNamespace(ligado=True, aplicar=aplicar),
        sessoes=_Sessoes({}),
        _outras_trabalhando=lambda: [],
        _aplicar_depois=None,
        atualizacao=progresso,
        _na_linha=lambda *_: None,
        eventos=queue.Queue(),
    )
    servico = ServicoOficina(contexto)
    try:
        assert servico.aplicar_melhorias(True).startswith("Aplicando")
        assert iniciou.wait(3)
        assert servico.aplicar_melhorias(True) == "Atualização em andamento."
        assert chamadas == [True]
    finally:
        liberar.set()
    contexto.eventos.get(timeout=3)  # a falha terminou, sem ficar girando na tela
    f = progresso.foto()
    assert f is not None and f["estado"] == "falhou"


@pytest.mark.parametrize("origem", ["painel", "manutencao"])
def test_sessao_reservada_recusa_trabalho_novo_inclusive_a_do_ze(
    tmp_path: Path, origem: str
) -> None:
    sessoes = Sessoes(tmp_path, (tmp_path,), rodar=lambda *_: "ok")
    loja = sessoes.criar("Loja", str(tmp_path), origem=origem)
    sessoes.reservada = lambda: "Atualização do Zé em andamento. Tente em instantes."
    with pytest.raises(SessaoErro, match="Atualização do Zé"):
        sessoes.enviar(loja.id, "rode os testes")


def test_aplicar_reserva_antes_de_outro_pedido_poder_comecar(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *_: "não deve rodar")
    loja = sessoes.criar("Loja", str(tmp_path))
    progresso = Progresso(tmp_path / "atualizacao")
    sessoes.reservada = progresso.reserva
    verificou, reservar, enviando, enviado, terminar = (threading.Event() for _ in range(5))

    def outras() -> list[str]:
        verificou.set()
        assert reservar.wait(3)
        return []

    def aplicar(revisado: bool) -> tuple[bool, str]:
        assert terminar.wait(3)
        return False, "Falha simulada."

    def enviar() -> None:
        enviando.set()
        try:
            sessoes.enviar(loja.id, "não interromper com um reinício")
        finally:
            enviado.set()

    contexto: Any = SimpleNamespace(
        sessoes=sessoes,
        manutencao=SimpleNamespace(ligado=True, aplicar=aplicar),
        atualizacao=progresso,
        _aplicar_depois=None,
        _outras_trabalhando=outras,
        _na_linha=lambda *_: None,
        eventos=queue.Queue(),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        atualizacao = pool.submit(ServicoOficina(contexto).aplicar_melhorias)
        try:
            assert verificou.wait(3)
            pedido = pool.submit(enviar)
            assert enviando.wait(3)
            assert not enviado.wait(0.05)  # o envio usa a mesma seção crítica do Aplicar
            reservar.set()
            assert atualizacao.result(timeout=3).startswith("Aplicando")
            with pytest.raises(SessaoErro, match="Atualização em andamento"):
                pedido.result(timeout=3)
            assert sessoes.ler(loja.id).estado == "parada"
        finally:
            reservar.set()
            terminar.set()
    contexto.eventos.get(timeout=3)
    assert progresso.reserva() is None


def test_entrar_e_sair_da_manutencao_so_pelo_pc() -> None:
    assert "ze/manutencao" in SO_NO_PC


class _Voz:
    """O núcleo só com o que o pedido falado de reiniciar usa."""

    def __init__(self, fonte: object = None, digitado: float | None = None) -> None:
        self._fonte = fonte
        self._digitado_em = digitado
        self.aplicados: list[bool] = []
        self.ditos: list[str] = []
        self.manutencao = self
        self.eventos = self

    def mudancas(self) -> dict[str, Any]:
        return {"commits": ["abc muda"]}

    def aplicar_melhorias(self, revisado: bool = False) -> str:
        self.aplicados.append(revisado)
        return "aplicando"

    def _no_proprio_pc(self) -> bool:
        return Nucleo._no_proprio_pc(self)  # type: ignore[arg-type]

    def put(self, evento: Any) -> None:
        if hasattr(evento, "texto"):
            self.ditos.append(evento.texto)


@pytest.mark.parametrize(
    ("voz", "aplicados", "dito"),
    [
        (_Voz(), [False], "aplicando"),  # "eu revisei" pela voz não vale como revisão
        (_Voz(fonte=object()), [], "Aplique no computador."),  # celular
        (_Voz(digitado=1.0), [], "Aplique no computador."),  # digitado no painel
    ],
)
def test_pela_voz_so_no_pc_e_nunca_a_zona_protegida(
    voz: _Voz, aplicados: list[bool], dito: str
) -> None:
    Nucleo._responder_depois(voz, "reiniciar", "revisado")  # type: ignore[arg-type]
    assert voz.aplicados == aplicados and voz.ditos == [dito]
