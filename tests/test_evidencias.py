"""Evidências do uso real: o que a rodada de melhoria leva para a sessão de código."""

import json
from pathlib import Path

from zervis.habilidades.evidencias import GUARDAR_S, Evidencias, maos

DIA = 86400.0


def test_resumo_conta_por_tipo_com_exemplos_distintos(tmp_path: Path) -> None:
    ev = Evidencias(tmp_path / "evidencias.jsonl")
    agora = 100 * DIA
    for detalhe in ("abre o guia", "abre o guia", "tema roxo", "mostra o acervo", "dá zoom"):
        ev.registrar("so_tela", detalhe, agora - DIA)
    ev.registrar("nao_achei", "Acervo: planilha", agora - DIA)
    ev.registrar("nao_entendi", "", agora - 10 * DIA)  # fora dos sete dias
    assert ev.resumo(agora) == (
        "Últimos 7 dias: pedido ao cérebro só para mexer na tela (candidato a comando local): "
        '5 vez(es) (ex.: "abre o guia"; "tema roxo"; "mostra o acervo"). '
        'nome que o Núcleo não achou: 1 vez(es) (ex.: "Acervo: planilha").'
    )


def test_sem_nada_diz_que_nao_ha(tmp_path: Path) -> None:
    assert Evidencias(tmp_path / "e.jsonl").resumo(DIA) == (
        "Nenhuma evidência registrada nos últimos 7 dias."
    )


def test_guarda_so_trinta_dias_e_pula_linha_ruim(tmp_path: Path) -> None:
    arquivo = tmp_path / "e.jsonl"
    agora = 100 * DIA
    arquivo.write_text(
        json.dumps({"em": agora - GUARDAR_S - 1, "tipo": "velho"})
        + "\nlixo\n"
        + json.dumps({"em": agora - DIA, "tipo": "nao_entendi"})
        + "\n"
    )
    Evidencias(arquivo).registrar("falha_cerebro", "x" * 500, agora)
    tipos = [json.loads(linha)["tipo"] for linha in arquivo.read_text().splitlines()]
    assert tipos == ["nao_entendi", "falha_cerebro"]
    assert len(json.loads(arquivo.read_text().splitlines()[1])["detalhe"]) == 200


def test_diagnostico_das_maos_em_uma_linha(tmp_path: Path) -> None:
    arquivo = tmp_path / "maos-diagnostico.json"
    arquivo.write_text(
        json.dumps({"origem": "padrao", "contagem": {"abriu": 8, "assinatura": 140}})
    )
    assert (
        maos(arquivo)
        == "Pinças (diagnóstico das mãos, calibração padrao): assinatura 140, abriu 8."
    )
    assert maos(tmp_path / "nao-existe.json") == ""
