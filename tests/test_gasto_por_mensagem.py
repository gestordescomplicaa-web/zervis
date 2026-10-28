"""O gasto de tokens de cada mensagem na Conversa (pedido de 27/10/2026: "quero entender como
ele está gastando esses tokens"): por parte, com a via rápida que passa a vez, o Codex que chama
o modelo várias vezes e a pesquisa que gasta por fora."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.test_latencia_nucleo import NucleoCronometrado
from tests.test_via_rapida import MotorFalso, Servidor, falar, gerar_tudo, roteado
from zervis.automacoes.agenda import FUSO
from zervis.cerebro import rapido
from zervis.cerebro.codex_rpc import uso_do_codex
from zervis.cerebro.consumo import Consumo, gasto, somar_usos
from zervis.memoria.conversas import Conversas
from zervis.nucleo.servicos.cerebro import ServicoCerebro
from zervis.portal.acoes import Acoes

RAPIDA = {"input_tokens": 900, "cache_read_input_tokens": 3000, "output_tokens": 5}
COMPLETO = {"input_tokens": 10}


def test_a_parte_e_a_soma_nos_nomes_do_consumo() -> None:
    assert gasto(None, "rapida") is None
    assert gasto(RAPIDA, "rapida", "haiku") == {
        "rotulo": "rapida",
        "modelo": "haiku",
        "entrada": 900,
        "cache_lido": 3000,
        "cache_criado": 0,
        "saida": 5,
    }
    assert somar_usos(RAPIDA, None, COMPLETO) == {
        "input_tokens": 910,
        "cache_read_input_tokens": 3000,
        "cache_creation_input_tokens": 0,
        "output_tokens": 5,
    }


def test_o_consumo_do_dia_separa_por_origem(tmp_path: Path) -> None:
    consumo = Consumo(tmp_path / "consumo.db")
    consumo.somar(RAPIDA, "codex")
    consumo.somar(COMPLETO, "aviso")
    consumo.somar(COMPLETO, "aviso")
    origens = consumo.hoje["origens"]
    assert origens["codex"]["respostas"] == 1 and origens["codex"]["cache_lido"] == 3000
    assert origens["aviso"] == {
        "respostas": 2,
        "entrada": 20,
        "cache_lido": 0,
        "cache_criado": 0,
        "saida": 0,
    }


def test_a_via_rapida_que_passa_a_vez_tambem_conta() -> None:
    class MotorComUso(MotorFalso):
        uso: Any = RAPIDA

    r, _ = roteado(MotorComUso([["Oi!"], ["[completo]"]]))
    falar(r, "Oi Zé")
    assert [g["rotulo"] for g in r.gastos] == ["rapida"]
    falar(r, "Me ajuda numa coisa")  # a via rápida leu, decidiu passar, e o completo respondeu
    assert [(g["rotulo"], g["modelo"]) for g in r.gastos] == [
        ("rapida", "rapido-1"),
        ("completo", "claude-sonnet-5-5"),
    ]
    assert r.uso is not None and r.uso["input_tokens"] == 910  # o consumo do dia vê as duas
    falar(r, "Abre o mapa")  # direto ao completo: só ele gastou
    assert [g["rotulo"] for g in r.gastos] == ["completo"]


def test_o_codex_conta_o_turno_inteiro_e_nao_so_a_ultima_chamada() -> None:
    antes = {"inputTokens": 5000, "cachedInputTokens": 4000, "outputTokens": 100}
    depois = {"inputTokens": 21000, "cachedInputTokens": 15000, "outputTokens": 400}
    assert uso_do_codex(depois, antes) == {
        "input_tokens": 5000,
        "cache_read_input_tokens": 11000,
        "cache_creation_input_tokens": 0,
        "output_tokens": 300,
    }
    assert uso_do_codex(depois)["cache_read_input_tokens"] == 15000


def test_os_motores_por_chave_trazem_o_uso() -> None:
    sse = [
        'data: {"choices":[{"delta":{"content":"Oi."}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":1200,"completion_tokens":7,'
        '"prompt_tokens_details":{"cached_tokens":1000}}}',
        "data: [DONE]",
    ]
    servidor = Servidor(sse)
    try:
        motor = rapido.MotorOpenAI("openai", servidor.endereco, "k", "gpt-5.4-mini")
        assert gerar_tudo(motor) == ["Oi."]
        assert motor.uso == {
            "input_tokens": 200,
            "cache_read_input_tokens": 1000,
            "output_tokens": 7,
        }
    finally:
        servidor.parar()
    sse = [
        'data: {"type":"message_start","message":{"usage":{"input_tokens":40,'
        '"cache_read_input_tokens":2000,"output_tokens":1}}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Certo."}}',
        'data: {"type":"message_delta","usage":{"output_tokens":12}}',
    ]
    servidor = Servidor(sse)
    try:
        motor_a = rapido.MotorAnthropic("k", "claude-haiku-4-5", servidor.endereco)
        assert gerar_tudo(motor_a) == ["Certo."]
        assert motor_a.uso == {
            "input_tokens": 40,
            "cache_read_input_tokens": 2000,
            "output_tokens": 12,
        }
    finally:
        servidor.parar()
    assert "stream_options" in rapido.MotorOpenAI(
        "openai", "https://api.openai.com/v1", "k", "m"
    ).corpo("S", [])
    assert "stream_options" not in rapido.MotorOpenAI(
        "ponte", "http://127.0.0.1:1/v1", "", "m"
    ).corpo("S", [])


def test_a_troca_e_gravada_com_o_gasto_e_a_busca_nao_ve_o_gasto(tmp_path: Path) -> None:
    n: Any = NucleoCronometrado(tmp_path)
    quando = datetime.now(FUSO).replace(microsecond=0, second=0)
    n.turnos = [{"pessoa": "Qual o dólar hoje?", "jarvis": "R$ 5,34."}]
    n.cerebro = SimpleNamespace(
        uso={"input_tokens": 300, "cache_read_input_tokens": 9000, "output_tokens": 40},
        modelo_usado="gpt-5.6-luna",
        ferramentas_usadas=["ze__internet_pesquisar"],
    )
    n.provedor = "codex"
    n._gastos_extras = [gasto(RAPIDA, "pesquisa", "Codex gpt-5.6")]
    g = ServicoCerebro(n)._gasto_do_turno()
    assert g is not None
    assert [p["rotulo"] for p in g["partes"]] == ["completo", "pesquisa"]
    assert g["ferramentas"] == ["internet_pesquisar"] and g["provedor"] == "codex"
    conversas = Conversas(tmp_path / "c")
    conversas.registrar("Qual o dólar hoje?", "R$ 5,34.", quando, g)
    conversas.registrar("Oi", "Oi!", quando.replace(second=30))
    turnos = {t.pessoa: t for t in conversas.do_dia(quando.date())}
    assert turnos["Qual o dólar hoje?"].gasto == g and turnos["Oi"].gasto is None
    assert conversas.buscar("gpt") == [] and conversas.buscar("cache_lido") == []


def test_o_fio_da_conversa_traz_o_gasto_e_o_dia(tmp_path: Path) -> None:
    agora = datetime.now(FUSO).replace(microsecond=0)
    conversas = Conversas(tmp_path / "c")
    conversas.registrar(
        "Oi", "Oi!", agora.replace(hour=0, minute=1), {"partes": [gasto(RAPIDA, "rapida") or {}]}
    )
    consumo = Consumo(tmp_path / "consumo.db")
    consumo.somar(COMPLETO, "nota do dia")
    consumo.somar_local()
    nucleo: Any = SimpleNamespace(
        conversas=conversas, linha=SimpleNamespace(entre=lambda *a: []), consumo=consumo
    )
    fio = Acoes(nucleo, tmp_path, tmp_path).conversa()
    (ze,) = [i for i in fio["itens"] if i["tipo"] == "ze"]
    assert ze["gasto"]["partes"][0]["cache_lido"] == 3000
    assert fio["consumo"]["locais"] == 1 and fio["consumo"]["fundo_vezes"] == 1
    assert fio["consumo"]["fundo"]["entrada"] == 10


def test_sem_consumo_o_fio_continua(tmp_path: Path) -> None:
    nucleo: Any = SimpleNamespace(
        conversas=Conversas(tmp_path / "c"), linha=SimpleNamespace(entre=lambda *a: [])
    )
    assert Acoes(nucleo, tmp_path, tmp_path).conversa()["consumo"] == {}
