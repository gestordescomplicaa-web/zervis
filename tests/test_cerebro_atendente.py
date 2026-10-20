"""O cérebro do agente de atendimento (escolha na página Atendimento) e o pré-aquecimento."""

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from zervis.atendimento import agente as ag
from zervis.atendimento import cerebro as c
from zervis.atendimento import ligacao as lg
from zervis.cerebro import rapido


def test_opcoes_mostram_api_so_com_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zervis.atendimento.cerebro.shutil.which", lambda _: None)
    monkeypatch.setattr(c, "tem_chave", lambda motor: motor == "anthropic")
    grupos = c.opcoes()
    assert [g["titulo"] for g in grupos] == ["Claude · assinatura", "Anthropic · chave de API"]
    assert grupos[1]["itens"][0]["valor"] == "anthropic|claude-haiku-4-5-20251001"
    assert all("|" in i["valor"] for g in grupos for i in g["itens"])


def test_escolha_validada_e_com_nome_de_produto() -> None:
    assert c.validar("plano|claude-haiku-4-5-20251001") == c.PADRAO
    assert c.validar({"motor": "openai", "modelo": "gpt-5.4-mini"})["motor"] == "openai"
    for ruim in ("", "plano|", "qualquer|x", "plano|" + "x" * 200):
        with pytest.raises(ValueError):
            c.validar(ruim)
    assert c.nome(c.PADRAO) == "Haiku 4.5 · Claude (assinatura)"
    assert c.nome({"motor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}) == (
        "Haiku 4.5 · Anthropic (API)"
    )
    assert c.rapido_nas_ligacoes({"motor": "openai", "modelo": "gpt-5.4-mini"})
    assert not c.rapido_nas_ligacoes(c.PADRAO)


def test_sem_chave_a_api_cai_no_padrao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rapido, "criar_motor", lambda via, pasta: None)
    motor = c.criar({"motor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}, tmp_path)
    assert isinstance(motor, rapido.MotorPlano) and motor._modelo == c.PADRAO["modelo"]


def test_cerebro_e_um_ajuste_do_agente(tmp_path: Path) -> None:
    p = ag.validar({"cerebro": "anthropic|claude-haiku-4-5-20251001"}, ag.Perfil())
    ag.gravar(p, tmp_path)
    assert ag.ler(tmp_path).cerebro == {"motor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}
    assert ag.Perfil().cerebro == c.PADRAO
    with pytest.raises(ag.AgenteErro):
        ag.validar({"cerebro": "nada"}, ag.Perfil())


class MotorFalso:
    com_estado = False

    def __init__(self) -> None:
        self.iniciado = ""
        self.fechado = False

    async def iniciar(self, sistema: str) -> None:
        self.iniciado = sistema

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        self.aquecimento = mensagens[-1]["content"]
        yield "Olá!"

    async def fechar(self) -> None:
        self.fechado = True


def test_central_pre_aquece_e_troca_a_reserva_quando_a_persona_muda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.atendimento import central as ce

    monkeypatch.setattr(lg, "voz_pronta", lambda: True)
    monkeypatch.setattr(lg, "falar_com_piper", lambda texto: b"voz:" + texto.encode())
    perfil = ag.Perfil(nome="Bia", ligacoes=True)
    criados: list[MotorFalso] = []

    def novo() -> Any:
        criados.append(MotorFalso())
        return criados[-1]

    atendente = ag.Atendente(lambda: None, lambda *_: "", lambda *_: None, tmp_path,  # type: ignore[arg-type, return-value]
                             perfil=lambda: perfil)  # fmt: skip
    central = ce.Central(lambda: None, wa=object(), atendente=atendente,  # type: ignore[arg-type, return-value]
                         avisos_ligados=lambda: False, motor_de_voz=novo)  # fmt: skip
    try:
        atendente.executar(central.aquecer())
        texto = "Olá! Aqui é Bia. Como posso ajudar?"
        assert central.saudacao == (lg.saudacao(perfil), b"voz:" + texto.encode())
        assert len(criados) == 1 and "Você é Bia" in criados[0].iniciado
        assert texto in criados[0].aquecimento  # aquecido com a própria saudação
        atendente.executar(central.aquecer())  # nada mudou: a mesma reserva
        assert len(criados) == 1
        motor, iniciado = central._tomar_reserva(perfil)
        assert motor is criados[0] and iniciado and central.reserva is None

        atendente.executar(central.aquecer())
        perfil.nome = "Carla"  # a persona mudou: a reserva antiga não serve
        motor, iniciado = central._tomar_reserva(perfil)
        assert not iniciado
        fim = time.monotonic() + 2  # a reserva antiga fecha em segundo plano
        while not criados[1].fechado:
            assert time.monotonic() < fim
            time.sleep(0.01)
    finally:
        atendente.parar()
