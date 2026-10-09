"""O cérebro na tela do Barehands: card de decisão, medidor de eficiência e mapa do cérebro."""

import json
import time
from pathlib import Path

from jarvis.automacoes.jobs import Jobs
from jarvis.cerebro.consumo import Consumo, UsoDeFerramentas
from jarvis.habilidades import revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import Skills
from jarvis.memoria.curta import Memoria, Mudanca
from jarvis.rosto import hud
from jarvis.rosto.pasta import Conexoes


def test_decisao_com_pergunta_prazo_e_sugestoes(tmp_path: Path) -> None:
    pendencias = revisao.Pendencias(tmp_path / "p.json")
    assert hud.decisao(None, None, pendencias) == {"pergunta": None, "sugestoes": []}
    pendencias.adicionar([revisao.Proposta("memoria", {}, "guardar X", origem="prefiro X")])
    d = hud.decisao("Vou reiniciar o computador.", 1234, pendencias)
    assert d["pergunta"] == {"texto": "Vou reiniciar o computador.", "expira": 1234}
    assert d["sugestoes"] == [{"resumo": "guardar X", "origem": "prefiro X"}]


def test_eficiencia_media_por_resposta_tendencia_e_locais(tmp_path: Path) -> None:
    (tmp_path / "consumo-dias.json").write_text(
        json.dumps(
            [
                {"dia": "2026-10-04", "respostas": 10, "entrada": 0, "cache_lido": 300_000},
                {"dia": "2026-10-05", "respostas": 0, "entrada": 0, "cache_lido": 0},
            ]
        )
    )
    consumo = Consumo(tmp_path / "consumo.json")
    consumo.somar({"input_tokens": 1_000, "cache_read_input_tokens": 23_000}, "claude")
    consumo.somar_local()
    consumo.somar_local()
    e = hud.eficiencia(consumo)
    assert [d["media"] for d in e["dias"]] == [30_000, None, 24_000]
    assert e["hoje"]["locais"] == 2 and e["hoje"]["cache"] == 96
    assert e["tendencia"] == -20  # 24 mil contra 30 mil: gastou menos


def test_mapa_liga_a_correcao_ao_que_ela_virou(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path / "m", {"usuario": 900, "jarvis": 900})
    memoria.aplicar(Mudanca("adicionar", "usuario", "Se chama Ana.", ""))
    memoria.aplicar(Mudanca("adicionar", "usuario", "Prefere seletor visual na tela.", ""))
    diario = Diario(tmp_path / "d.jsonl")
    diario.registrar(
        "aprovada",
        "guardar…",
        origem="não, prefiro o seletor",
        alvo="usuario",
        texto="Prefere seletor visual na tela.",
    )
    skills = Skills(tmp_path / "s")
    uso = UsoDeFerramentas(tmp_path / "uso.json")
    uso.somar(["mcp__jarvis__sistema_executar", "mcp__jarvis__sistema_estado", "WebSearch"], 50)
    conexoes = Conexoes(
        cerebro="Claude, com o Sonnet 5.5",
        proprias=[("sistema_estado", True), ("sistema_executar", False), ("memoria", False)],
        embutidas=["WebSearch", "WebFetch"],
    )
    agora = time.time()
    m = hud.mapa(conexoes, memoria, skills, Jobs(tmp_path / "j.json"), diario, uso.ler(), agora)
    assert m["centro"] == {"rotulo": "JARVIS", "sub": "Claude, com o Sonnet 5.5"}
    grupos = {g["id"]: g for g in m["grupos"]}
    assert list(grupos) == ["usuario", "jarvis", "skills", "conexoes", "automacoes"]
    importada, aprendida = grupos["usuario"]["itens"]
    assert importada == {
        "id": hud.id_memoria("usuario", "Se chama Ana."),
        "rotulo": "Se chama Ana.",
        "texto": "Se chama Ana.",
        "novo": False,
    }
    assert aprendida["origem"] == "não, prefiro o seletor" and aprendida["novo"]
    assert aprendida["rotulo"] == "Prefere seletor visual na tela."
    conexoes_por_nome = {i["rotulo"]: i for i in grupos["conexoes"]["itens"]}
    assert conexoes_por_nome["Máquina (Omarchy)"]["usos"] == 2
    assert conexoes_por_nome["Internet"]["usos"] == 1
    assert conexoes_por_nome["Memória"]["usos"] == 0
    assert m["aprendizado"] == {"aprovadas": 1, "recentes": 1}
    (evento,) = m["linha_do_tempo"]
    assert evento["rotulo"] == "Sugestão aprovada" and evento["item"] == aprendida["id"]
    assert evento["origem"] == "não, prefiro o seletor"
    assert len(m["por_dia"]) == 14 and m["por_dia"][-1]["n"] == 1
    velho = hud.mapa(conexoes, memoria, skills, Jobs(tmp_path / "j.json"), diario, {}, agora + 3e5)
    assert not velho["grupos"][0]["itens"][1]["novo"]  # depois de 48 h para de brilhar


def test_rotulo_curto_para_o_no() -> None:
    assert hud.rotulo("Ao mudar configurações visuais, guardar o estado") == (
        "Ao mudar configurações visuais, guardar…"
    )


def test_hud_so_regrava_quando_muda_ou_vai_envelhecer(tmp_path: Path) -> None:
    h = hud.Hud(tmp_path)
    assert h.gravar("decisao", {"pergunta": None}, 100)
    assert not h.gravar("decisao", {"pergunta": None}, 110)
    assert h.gravar("decisao", {"pergunta": {"texto": "x"}}, 111)
    assert h.gravar("decisao", {"pergunta": {"texto": "x"}}, 150)  # renovação
    gravado = json.loads((tmp_path / "decisao.json").read_text())
    assert gravado == {"pergunta": {"texto": "x"}, "ts": 150}
    h.abrir_mapa()
    assert json.loads((tmp_path / "mapa-abrir.json").read_text())["pedido"] > 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["decisao.json", "mapa-abrir.json"]
    h.pedir_maos("padrao")
    assert json.loads((tmp_path / "maos-pedido.json").read_text())["acao"] == "padrao"
