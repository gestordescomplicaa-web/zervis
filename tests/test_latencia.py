"""Cronômetros independentes por turno e resumo diário, sem dados da conversa."""

import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from zervis.automacoes.agenda import FUSO
from zervis.voz.latencia import Latencias, ler_turnos, resumir


def test_marcos_sao_unicos_e_atrasados_nao_contaminam_proximo_turno(tmp_path: Path) -> None:
    latencias = Latencias(tmp_path)
    try:
        a = latencias.iniciar("voz", 10)
        latencias.marcar(a, "fim_fala", 10)
        latencias.marcar(a, "pedido_fechado", 10.64)
        latencias.marcar(a, "transcrito", 10.84)
        latencias.marcar(a, "cerebro_enviado", 10.86)
        latencias.marcar(a, "primeiro_token", 11.86)
        latencias.marcar(a, "primeiro_token", 12)
        latencias.marcar(a, "primeira_frase", 12.06)
        latencias.marcar(a, "sintese_pedida", 12.07)
        latencias.primeiro_som(a, 12.3, "resposta")
        latencias.primeiro_som(a, 13, "confirmacao")
        latencias.finalizar(a)
        b = latencias.iniciar("teclado", 20)
        latencias.marcar(a, "primeiro_token", 30)
        latencias.primeiro_som(a, 30, "resposta")
        latencias.finalizar(a)
        assert latencias.turnos[b].marcos == {}
        assert latencias.ultimo is not None
        assert latencias.ultimo["primeiro_som_tipo"] == "resposta"
        assert latencias.ultimo["etapas_ms"] == {
            "fim_de_turno": 640,
            "transcricao": 200,
            "despacho": 20,
            "cerebro": 1000,
            "formacao_frase": 200,
            "entrega_fala": 10,
            "voz": 230,
            "total": 2300,
        }
        assert latencias.aguardar()
    finally:
        latencias.fechar()


def test_teclado_nao_inventa_transcricao_e_omite_marcos_ausentes(tmp_path: Path) -> None:
    latencias = Latencias(tmp_path)
    try:
        t = latencias.iniciar("teclado", 5)
        latencias.marcar(t, "pedido_fechado", 5)
        latencias.marcar(t, "cerebro_enviado", 5.01)
        latencias.primeiro_som(t, 6, "resposta")
        latencias.finalizar(t)
        assert latencias.ultimo is not None
        assert latencias.ultimo["etapas_ms"] == {"despacho": 10, "total": 1000}
        with pytest.raises(ValueError):
            latencias.contexto(t, texto="conteúdo privado")
        with pytest.raises(ValueError):
            latencias.marcar(t, "texto privado")
        with pytest.raises(ValueError):
            latencias.contexto(t, aprovacao="sim")
        with pytest.raises(ValueError):
            latencias.iniciar("qualquer coisa")
    finally:
        latencias.fechar()


def test_resumo_separa_origem_rota_e_confirmacao_e_exclui_parciais() -> None:
    voz: list[dict[str, Any]] = [
        {
            "origem": "voz",
            "rota": "cerebro",
            "resultado": "concluido",
            "etapas_ms": {"total": i * 100},
        }
        for i in range(1, 21)
    ]
    outros: list[dict[str, Any]] = [
        {**voz[0], "resultado": "interrompido", "etapas_ms": {"total": 90000}},
        {**voz[0], "etapas_ms": {}},
        {**voz[0], "etapas_ms": {"total": float("nan")}},
        {**voz[0], "etapas_ms": {"total": True}},
        {**voz[0], "etapas_ms": None},
        {**voz[0], "origem": "teclado"},
        {**voz[0], "rota": "comando"},
        {**voz[0], "aprovacao": True},
    ]
    r = resumir(voz + outros)
    assert r["turnos"] == 28 and len(r["grupos"]) == 4
    grupo = next(g for g in r["grupos"] if g["turnos"] == 25)
    assert grupo["etapas"]["total"] == {"n": 20, "mediana_ms": 1050, "p95_ms": 1900}
    assert "transcricao" not in grupo["etapas"]
    assert grupo["resultados"]["interrompido"] == 1


def test_persistencia_privada_recupera_dia_anterior_e_cauda_incompleta(tmp_path: Path) -> None:
    dia = datetime.now(FUSO).date().isoformat()
    arquivo = tmp_path / f"{dia}.jsonl"
    for i in range(2):
        latencias = Latencias(tmp_path)
        try:
            t = latencias.iniciar("voz", 10)
            latencias.marcar(t, "fim_fala", 10)
            latencias.primeiro_som(t, 11 + i, "resposta")
            latencias.finalizar(t)
            assert latencias.aguardar()
        finally:
            latencias.fechar()
        if i == 0:
            with arquivo.open("a") as f:
                f.write('{"versao":1,"id":"incompleto"')
    linhas = ler_turnos(arquivo)
    assert len(linhas) == 2
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    resumo = tmp_path / f"{dia}-resumo.json"
    assert stat.S_IMODE(resumo.stat().st_mode) == 0o600
    r = json.loads(resumo.read_text())
    assert r["grupos"][0]["etapas"]["total"]["mediana_ms"] == 1500
    assert "texto" not in linhas[0] and "audio" not in linhas[0]


def test_falha_de_disco_e_fila_cheia_nao_derrubam_o_coletor(tmp_path: Path) -> None:
    arquivo = tmp_path / "arquivo"
    arquivo.touch()
    latencias = Latencias(arquivo)  # é um arquivo; mkdir deve falhar na thread de escrita
    try:
        t = latencias.iniciar("voz")
        latencias.finalizar(t)
        assert latencias.aguardar() and latencias.thread.is_alive()
        assert latencias.erro == "FileExistsError"
        assert latencias.ultimo is not None and latencias.ultimo["resultado"] == "sem_som"
    finally:
        latencias.fechar()
    # Um escritor parado simula disco travado, sem sleeps nem esperar IO no laço.
    for _ in range(130):
        t = latencias.iniciar("voz")
        latencias.finalizar(t, "interrompido")
    assert latencias.descartados == 2


def test_erro_do_cerebro_nao_entra_como_resposta_simples(tmp_path: Path) -> None:
    latencias = Latencias(tmp_path)
    try:
        t = latencias.iniciar("voz", 1)
        latencias.marcar(t, "fim_fala", 1)
        latencias.contexto(t, erro_cerebro=True)
        latencias.primeiro_som(t, 2, "resposta")
        latencias.finalizar(t)
        assert latencias.ultimo is not None and latencias.ultimo["resultado"] == "erro_cerebro"
        assert resumir([latencias.ultimo])["grupos"][0]["etapas"] == {}
    finally:
        latencias.fechar()
