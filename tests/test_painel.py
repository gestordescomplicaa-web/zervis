"""Painel de cérebros no Barehands: lista com baterias e o clique de volta, uma vez só."""

import json
from pathlib import Path

from zervis.cerebro.baterias import Bateria
from zervis.rosto.painel import Painel


def test_mostra_os_cinco_com_o_ativo_e_as_baterias(tmp_path: Path) -> None:
    Painel(tmp_path).mostrar("gpt", {"gpt": Bateria(12, "semana")}, {"gpt": "GPT-6 Luna"}, 100.0)
    dados = json.loads((tmp_path / "cerebros.json").read_text())
    assert [c["id"] for c in dados["lista"]] == ["claude", "codex", "gpt", "gemini", "auto"]
    gpt = dados["lista"][2]
    assert gpt["ativo"] and gpt["bateria"]["restante"] == 12
    assert gpt["modelo"] == "GPT-6 Luna"
    assert dados["lista"][0]["bateria"] is None
    assert dados["ts"] == 100.0


def test_escolha_vale_uma_vez_e_so_se_recente_e_conhecida(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    arquivo = tmp_path / "escolha.json"
    arquivo.write_text(json.dumps({"id": "gemini", "ts": 100.0}))
    assert painel.escolha(110.0) == "gemini"
    assert painel.escolha(110.0) is None
    arquivo.write_text(json.dumps({"id": "gemini", "ts": 100.0}))
    assert painel.escolha(200.0) is None  # velha: o Zé estava parado na hora do clique
    arquivo.write_text(json.dumps({"id": "rm -rf", "ts": 100.0}))
    assert painel.escolha(101.0) is None


def test_autoconhecimento_para_a_imersao_uma_vez_por_minuto(tmp_path: Path) -> None:
    """ADR 0045: as apresentações da Imersão leem só o retrato que o Zé grava aqui."""
    painel, chamadas = Painel(tmp_path), []

    def montar() -> dict[str, object]:
        chamadas.append(1)
        return {"agora": {"modelo": "GPT-6 Luna"}}

    painel.autoconhecimento(montar, 100.0)
    painel.autoconhecimento(montar, 130.0)  # antes de um minuto: não remonta (lê a Atividade)
    dados = json.loads((tmp_path / "autoconhecimento.json").read_text())
    assert dados == {"agora": {"modelo": "GPT-6 Luna"}, "ts": 100.0} and chamadas == [1]

    def quebrado() -> dict[str, object]:
        raise OSError("atividade ilegível")

    painel.autoconhecimento(quebrado, 200.0)  # a falha deixa o arquivo anterior
    assert json.loads((tmp_path / "autoconhecimento.json").read_text())["ts"] == 100.0
