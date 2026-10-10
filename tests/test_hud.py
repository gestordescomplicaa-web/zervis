"""O cérebro na tela do Barehands: card de decisão, medidor de eficiência e mapa do cérebro."""

import json
import time
from pathlib import Path
from types import SimpleNamespace

from jarvis.automacoes.jobs import Jobs
from jarvis.cerebro.consumo import Consumo
from jarvis.habilidades import revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import Skills
from jarvis.memoria.curta import Memoria, Mudanca
from jarvis.rosto import hud
from jarvis.rosto.pasta import Conexoes
from jarvis.usuario import Perfil


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
    conexoes = Conexoes(
        cerebro="Claude, com o Sonnet 5.5",
        proprias=[("sistema_estado", True), ("sistema_executar", False), ("memoria", False)],
        embutidas=["WebSearch", "WebFetch"],
    )
    agora = time.time()
    m = hud.mapa(conexoes, memoria, skills, Jobs(tmp_path / "j.json"), diario, agora)
    assert m["centro"] == {"rotulo": "Zé", "sub": "Claude, com o Sonnet 5.5"}
    grupos = {g["id"]: g for g in m["grupos"]}
    # As ferramentas ficam no painel (Conectores): o Mapa mostra o que o Zé sabe e faz.
    assert list(grupos) == ["usuario", "jarvis", "skills", "automacoes"]
    importada, aprendida = grupos["usuario"]["itens"]
    assert importada == {
        "id": hud.id_memoria("usuario", "Se chama Ana."),
        "rotulo": "Se chama Ana.",
        "texto": "Se chama Ana.",
        "novo": False,
    }
    assert aprendida["origem"] == "não, prefiro o seletor" and aprendida["novo"]
    assert aprendida["rotulo"] == "Prefere seletor visual na tela."
    assert m["aprendizado"] == {"aprovadas": 1, "recentes": 1}
    (evento,) = m["linha_do_tempo"]
    assert evento["rotulo"] == "Sugestão aprovada" and evento["item"] == aprendida["id"]
    assert evento["origem"] == "não, prefiro o seletor"
    assert len(m["por_dia"]) == 14 and m["por_dia"][-1]["n"] == 1
    velho = hud.mapa(conexoes, memoria, skills, Jobs(tmp_path / "j.json"), diario, agora + 3e5)
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


def test_o_perfil_abre_o_sobre_voce_do_mapa(tmp_path: Path) -> None:
    conexoes = Conexoes(cerebro="Claude", proprias=[], embutidas=[])
    vazio = Memoria(tmp_path / "m", {"usuario": 900, "jarvis": 900})
    jobs, diario = Jobs(tmp_path / "j.json"), Diario(tmp_path / "d.jsonl")
    m = hud.mapa(
        conexoes, vazio, Skills(tmp_path / "s"), jobs, diario, 0, Perfil("Ana", "Designer.")
    )
    assert m["grupos"][0]["itens"][0] == {
        "id": "perfil",
        "rotulo": "Ana",
        "texto": "Ana. Designer.",
    }
    sem = hud.mapa(conexoes, vazio, Skills(tmp_path / "s"), jobs, diario, 0, Perfil())
    assert sem["grupos"][0]["itens"] == []


def test_so_aparecem_os_orbes_com_conteudo() -> None:
    dia_zero = hud.orbes({"atual": None, "ativas": [], "ideias": []}, 0, False, False)
    assert dia_zero == {"visiveis": ["mapa", "acervo", "guia"], "desenvolvedor": False}
    em_uso = hud.orbes({"atual": {"titulo": "Site"}}, 2, True, False)
    assert em_uso["visiveis"] == ["mapa", "hoje", "trabalho", "acervo", "guia"]
    assert hud.orbes({}, 0, False, True)["visiveis"][1] == "hoje"  # um lembrete ativo basta


def test_o_trabalho_vem_das_sessoes_do_ze_sem_prompt_nem_caminho() -> None:
    s = SimpleNamespace(
        id="a1",
        nome="Loja",
        estado="trabalhando",
        pasta="/x/loja",
        resumo="Testes ok.",
        atualizada="t",
    )
    (item,) = hud.trabalho([s])["sessoes"]
    assert item == {
        "id": "a1",
        "rotulo": "Loja",
        "estado": "trabalhando",
        "pasta": "loja",
        "texto": "Testes ok.",
        "atualizada": "t",
    }
