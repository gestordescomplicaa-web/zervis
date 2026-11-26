"""O histórico inteiro no chat do Início e o sino com visto e lido (ADR 0139).

Pedido de 25/11/2026: a conversa ficava só no dia (à meia-noite o chat esvaziava e, num dia com
mais de 200 falas, as primeiras sumiam), e o sino contava as pendências sem nunca baixar o número.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos import lidos
from zervis.memoria.conversas import FUSO, Conversas
from zervis.nucleo import precisa
from zervis.portal.acoes import Acoes, inicio
from zervis.portal.servidor import PedidoInvalido


def _em(dia: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, dia, hora, minuto, tzinfo=FUSO)


def _acoes(tmp_path: Path, conversas: Conversas, eventos: list[Any] | None = None) -> Acoes:
    def entre(de: datetime, ate: datetime, tipos: set[str] | None = None) -> list[Any]:
        return [e for e in eventos or [] if de <= e.quando < ate]

    nucleo = SimpleNamespace(conversas=conversas, linha=SimpleNamespace(entre=entre))
    return Acoes(nucleo, tmp_path, tmp_path)


def test_os_ultimos_nunca_separam_o_pedido_da_resposta() -> None:
    itens = [{"quando": q} for q in ("a", "b", "b", "c", "c")]
    assert inicio._ultimos(itens, 2) == itens[3:]
    assert inicio._ultimos(itens, 3) == itens[1:]  # o "b" da resposta puxa o pedido junto
    assert inicio._ultimos(itens, 10) == itens


def test_rolando_para_cima_vem_o_que_veio_antes_dia_a_dia_ate_o_comeco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversas = Conversas(tmp_path / "conversas")
    conversas.registrar("Bom dia", "Bom dia!", _em(23, 9))
    conversas.registrar("E a prospecção?", "Duas enviadas.", _em(24, 20, 35))
    conversas.registrar("Suspende o PC", "Pronto.", _em(24, 21, 50))
    conversas.registrar("Tá por aí?", "Tô aqui.", _em(25, 11, 51))
    aviso = SimpleNamespace(quando=_em(24, 16, 36), registrado=_em(24, 16, 36), texto="Lead novo.")
    acoes = _acoes(tmp_path, conversas, [aviso])
    monkeypatch.setattr(inicio, "POR_PAGINA", 3)

    pagina = acoes.conversa_anteriores({"antes": "2026-11-25T11:51:00-03:00"})
    assert [(i["tipo"], i.get("texto")) for i in pagina["itens"]] == [
        ("voce", "E a prospecção?"),  # 4 de ontem, para não cortar o par (o limite é 3)
        ("ze", "Duas enviadas."),
        ("voce", "Suspende o PC"),
        ("ze", "Pronto."),
    ]
    assert pagina["mais"]  # o aviso de ontem e o dia 23 ainda faltam

    pagina = acoes.conversa_anteriores({"antes": pagina["itens"][0]["quando"]})
    assert [i.get("texto") for i in pagina["itens"]] == ["Bom dia", "Bom dia!", "Lead novo."]
    assert not pagina["mais"]
    with pytest.raises(PedidoInvalido):
        acoes.conversa_anteriores({"antes": "ontem"})


def test_o_fio_de_hoje_diz_o_dia_do_ze(tmp_path: Path) -> None:
    conversas = Conversas(tmp_path / "conversas")
    conversas.registrar("Oi", "Oi!", datetime.now(FUSO) - timedelta(seconds=5))
    fio = _acoes(tmp_path, conversas).conversa()
    assert fio["dia"] == datetime.now(FUSO).date().isoformat()
    assert [i["tipo"] for i in fio["itens"]] == ["voce", "ze"]


def test_visto_e_lido_ficam_guardados_e_a_chave_muda_com_o_item(tmp_path: Path) -> None:
    marcas = lidos.Lidos(tmp_path / "lidos.db")
    a, b = (
        lidos.chave("lead:1", "Responder Ana", "Oi"),
        lidos.chave("lead:1", "Responder Ana", "Oi?"),
    )
    assert a != b  # o lead mandou outra mensagem: volta a ser novidade
    marcas.marcar([a, "não é chave"], "visto")
    assert marcas.estado([a, b]) == {a: {"visto"}}
    marcas.marcar([a], "lido")
    assert marcas.estado([a]) == {a: {"visto", "lido"}}
    marcas.marcar([a], "visto")  # abrir o sino de novo não desfaz o lido
    assert marcas.estado([a]) == {a: {"visto", "lido"}}
    with pytest.raises(ValueError):
        marcas.marcar([a], "apagado")


def test_marcas_de_mais_de_30_dias_se_apagam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marcas = lidos.Lidos(tmp_path / "lidos.db")
    velha, nova = lidos.chave("velha"), lidos.chave("nova")
    agora = time.time()
    monkeypatch.setattr(time, "time", lambda: agora - lidos.GUARDA_S - 60)
    marcas.marcar([velha], "lido")
    monkeypatch.setattr(time, "time", lambda: agora)
    marcas.marcar([nova], "visto")
    assert marcas.estado([velha, nova]) == {nova: {"visto"}}


def test_o_sino_conta_so_o_novo_e_o_ponto_some_no_clique(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marcas = lidos.Lidos(tmp_path / "lidos.db")
    monkeypatch.setattr(lidos, "PADRAO", marcas)
    antes = datetime.now(FUSO) - timedelta(hours=2)
    velho = SimpleNamespace(quando=antes, registrado=antes, texto="Sessão terminou.")
    marcas.dados.guardar("inicio", {"em": time.time() - 3600}, "inicio")  # o sino nasceu há 1 h
    agora = datetime.now(FUSO) - timedelta(seconds=30)
    novo = SimpleNamespace(quando=agora, registrado=agora, texto="Lead novo.")
    lista = [precisa.Item("video:v1", "marketing", "Marketing", "Revisar o vídeo", "Tema")]
    monkeypatch.setattr(precisa, "montar", lambda fontes: lista)
    acoes = _acoes(tmp_path, Conversas(tmp_path / "conversas"), [velho, novo])
    monkeypatch.setattr(inicio.AcoesInicio, "_fontes", lambda self: None)

    sino = acoes.precisa()
    (item,) = sino["itens"]
    assert (item["novo"], item["lido"]) == (True, False)
    assert [(a["texto"], a["novo"], a["lido"]) for a in sino["avisos"]] == [
        ("Lead novo.", True, False),
        ("Sessão terminou.", False, True),  # de antes de o sino guardar marcas: já lido
    ]
    assert sino["novos"] == 2

    acoes.marcar_avisos({"chaves": [item["chave"], sino["avisos"][0]["chave"]], "como": "visto"})
    sino = acoes.precisa()
    assert sino["novos"] == 0 and not sino["itens"][0]["lido"]  # visto, o ponto continua
    acoes.marcar_avisos({"chaves": [item["chave"]], "como": "lido"})
    assert acoes.precisa()["itens"][0]["lido"]

    lista[0] = lista[0]._replace(detalhe="Outro tema")  # o item mudou: novidade de novo
    assert acoes.precisa()["novos"] == 1
    with pytest.raises(PedidoInvalido):
        acoes.marcar_avisos({"chaves": "tudo", "como": "lido"})
