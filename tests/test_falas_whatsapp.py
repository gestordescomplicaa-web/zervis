"""As leituras do WhatsApp que o Zé fala sem o cérebro (ADR 0056): zero token, na hora."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from zervis.avisos import falas_whatsapp as f
from zervis.avisos.caixa import Caixa
from zervis.avisos.prioridade import Prioridade
from zervis.nucleo import estados

FUSO = ZoneInfo("America/Sao_Paulo")
T = datetime(2026, 11, 3, 10, 42, tzinfo=FUSO).timestamp()


class Relogio:
    t = T

    def __call__(self) -> float:
        return self.t


@pytest.mark.parametrize(
    ("frase", "comando"),
    [
        ("Zérvis, quem foi a última pessoa que me mandou mensagem no WhatsApp?", "whatsapp_quem"),
        ("Quem me mandou mensagem?", "whatsapp_quem"),
        ("De quem foi a última mensagem no WhatsApp?", "whatsapp_quem"),
        ("Tem mensagem nova no zap?", "whatsapp_quem"),
        ("Tem alguém esperando resposta?", "whatsapp_esperando"),
        ("Quem eu preciso responder no WhatsApp?", "whatsapp_esperando"),
        ("Quem está na lista de prioridade?", "whatsapp_lista"),
        ("Quem você está monitorando?", "whatsapp_lista"),
        ("Lê a mensagem da Ana", "whatsapp_ler:ana"),
        ("Zé, lê a última mensagem da Ana Souza", "whatsapp_ler:ana souza"),
        ("me lê as mensagens do João no WhatsApp", "whatsapp_ler:joao"),
        # O que pede busca, resumo ou ação vai ao cérebro.
        ("O que a Ana disse sobre o orçamento?", None),
        ("Responde pra Ana: pode ser amanhã", None),
        ("Quem é você?", None),
        ("Lê a mensagem da Ana e responde que sim", None),
        ("Lê a mensagem da Ana e responde", None),
        ("Lê a mensagem do João e resume", None),
    ],
)
def test_frases_que_o_ze_responde_sozinho(frase: str, comando: str | None) -> None:
    assert estados.comando(frase) == comando


def _caixa(tmp_path: Path) -> tuple[Caixa, Relogio]:
    relogio = Relogio()
    return Caixa(tmp_path / "arquivo.db", relogio, None), relogio


def test_quem_mandou_e_quem_espera(tmp_path: Path) -> None:
    caixa, _ = _caixa(tmp_path)
    assert f.quem(caixa, FUSO) == "Nenhuma mensagem no WhatsApp ainda."
    caixa.receber("Bia", "bom dia", "", "2@lid", quando=T - 86400)  # ontem
    caixa.receber("Caio", "oi", "", "3@lid", quando=T - 3600)
    caixa.enviada("3@lid", "oi, Caio", quando=T - 3500)
    caixa.receber("Ana", "quanto custa a automação?", "", "1@lid", quando=T)
    caixa.enviada("1@lid", "já te respondo", quando=T - 10)  # antes da dela: não conta
    assert f.quem(caixa, FUSO) == (
        "A última foi de Ana, às 10:42: quanto custa a automação? Também esperam resposta: Bia."
    )
    assert f.esperando(caixa, FUSO) == (
        "2 pessoas esperam a sua resposta: Ana, às 10:42; Bia, ontem às 10:42."
    )
    caixa.enviada("1@lid", "Custa 200.", quando=T + 5)
    caixa.enviada("2@lid", "bom dia!", quando=T + 6)
    assert f.esperando(caixa, FUSO) == "Ninguém esperando a sua resposta no WhatsApp."
    assert f.quem(caixa, FUSO).endswith("Você já respondeu.")


def test_le_as_ultimas_dele_e_grupo_nao_entra_em_quem(tmp_path: Path) -> None:
    caixa, _ = _caixa(tmp_path)
    for i, texto in enumerate(["oi", "tudo bem?", "quanto custa?", "e o prazo?"]):
        caixa.receber("Ana", texto, "", "1@lid", quando=T - 300 + i * 60)
    caixa.receber("Caio", "reunião", "", "9@g.us", quando=T + 1, grupo=True, grupo_nome="Equipe")
    assert f.ler(caixa, "ana", FUSO) == (
        "De Ana, às 10:38: tudo bem? às 10:39: quanto custa? às 10:40: e o prazo?"
    )
    assert f.ler(caixa, "carla", FUSO) == "Não achei uma conversa só com carla no WhatsApp."
    assert f.quem(caixa, FUSO).startswith("A última foi de Ana")  # grupo não conta
    assert f.ler(caixa, "equipe", FUSO).startswith("No grupo Equipe, às")


def test_lista_de_prioridade_falada(tmp_path: Path) -> None:
    lista = Prioridade(tmp_path / "prioridade.json", Relogio())
    assert f.lista(lista) == "A lista de prioridade está vazia."
    lista.monitorar("Ana", chat="1@lid")
    lista.esperar_resposta("Bia", "2@lid")
    assert f.lista(lista) == (
        "Na lista de prioridade: Ana. Esperando a resposta ao que mandei por você: Bia."
    )
