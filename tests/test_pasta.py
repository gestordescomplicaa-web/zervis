"""A pasta do Zé: diário de aprendizado, curadoria das skills e as notas do Barehands."""

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from zervis.automacoes.jobs import Jobs
from zervis.cerebro import ferramentas
from zervis.cerebro.consumo import Consumo
from zervis.habilidades import revisao
from zervis.habilidades.diario import Diario
from zervis.habilidades.skills import Skills
from zervis.memoria.curta import Memoria, Mudanca
from zervis.rosto import pasta

SKILL = "---\nname: {nome}\ndescription: Faz {nome}.\n---\n# {nome}\n"


def _skill(s: Skills, nome: str) -> None:
    s.gravar(nome, s.novo_conteudo(nome, conteudo=SKILL.format(nome=nome)))


def test_diario_guarda_mais_novo_primeiro_e_pula_linha_ruim(tmp_path: Path) -> None:
    d = Diario(tmp_path / "diario.jsonl")
    assert d.ultimos() == []
    d.registrar("aprovada", "guardar X", origem="prefiro X", vazio="")
    with d.arquivo.open("a") as f:
        f.write("{quebrada\n")
    d.registrar("descartada", "guardar Y")
    eventos = d.ultimos()
    assert [e["evento"] for e in eventos] == ["descartada", "aprovada"]
    assert eventos[1]["origem"] == "prefiro X" and "vazio" not in eventos[1]
    assert oct(d.arquivo.stat().st_mode & 0o777) == "0o600"


def test_curadoria_arquiva_so_skill_parada_e_nada_se_perde(tmp_path: Path) -> None:
    s = Skills(tmp_path / "skills")
    for nome in ("usada", "parada", "nova"):
        _skill(s, nome)
    agora = time.time()
    velho = agora - 40 * 86_400
    os.utime(s.pasta / "parada" / "SKILL.md", (velho, velho))
    os.utime(s.pasta / "usada" / "SKILL.md", (velho, velho))
    s.ver("usada")  # lida agora: conta como uso recente
    assert s.arquivar_paradas(30, agora) == ["parada"]
    assert [n for n, _ in s.listar()] == ["nova", "usada"]
    assert s.arquivadas() == ["parada"]
    assert (s.pasta / ".arquivo" / "parada" / "SKILL.md").is_file()
    assert "parada" not in s.catalogo()


def test_origem_da_sugestao_e_a_fala_com_correcao() -> None:
    turnos = [
        {"pessoa": "abre os temas", "jarvis": "..."},
        {"pessoa": "não é assim, prefiro o seletor na tela", "jarvis": "..."},
    ]
    assert revisao.origem(turnos) == "não é assim, prefiro o seletor na tela"
    assert revisao.origem(turnos[:1]) == "abre os temas"
    antiga = revisao.Proposta(tipo="memoria", dados={}, resumo="r", id="a", criada=1.0)
    assert antiga.origem == ""  # pendências gravadas antes do campo continuam abrindo


def _ferramentas(tmp_path: Path, memoria: Memoria, skills: Skills) -> dict[str, Any]:
    lista = ferramentas.montar(
        None,
        memoria,
        skills,
        revisao.Pendencias(tmp_path / "p.json"),
        diario=Diario(tmp_path / "diario.jsonl"),
    )
    return {t.name: t.handler for t in lista}


def test_aprovar_descartar_e_memoria_vao_para_o_diario(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path / "m", {"usuario": 500, "jarvis": 500})
    skills = Skills(tmp_path / "s")
    pendencias = revisao.Pendencias(tmp_path / "p.json")
    dados = {"acao": "adicionar", "alvo": "usuario", "texto": "Prefere seletor visual."}
    aprovar = revisao.Proposta("memoria", dados, "guardar A", id="a1", origem="prefiro o seletor")
    descartar = revisao.Proposta("memoria", dados, "guardar B", id="b2")
    pendencias.adicionar([aprovar, descartar])
    f = _ferramentas(tmp_path, memoria, skills)
    asyncio.run(f["sugestao_aprovar"]({"id": "a1"}))
    asyncio.run(f["sugestao_descartar"]({"id": "b2"}))
    asyncio.run(f["memoria"]({"acao": "adicionar", "alvo": "jarvis", "texto": "Usa Omarchy 4."}))
    eventos = Diario(tmp_path / "diario.jsonl").ultimos()
    assert [(e["evento"], e["resumo"]) for e in eventos] == [
        ("memoria", "guardar na memória nas minhas notas: Usa Omarchy 4."),
        ("descartada", "guardar B"),
        ("aprovada", "guardar A"),
    ]
    assert eventos[2]["origem"] == "prefiro o seletor"
    assert memoria.entradas("usuario") == ["Prefere seletor visual."]


def test_notas_e_regravacao_so_quando_muda(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path / "m", {"usuario": 500, "jarvis": 500})
    memoria.aplicar(Mudanca("adicionar", "usuario", "Se chama Ana.", ""))
    skills = Skills(tmp_path / "s")
    _skill(skills, "fala-natural")
    skills.ver("fala-natural")
    diario = Diario(tmp_path / "diario.jsonl")
    diario.registrar("aprovada", "guardar X", origem="prefiro X")
    consumo = Consumo(tmp_path / "consumo.json")
    consumo.somar({"input_tokens": 10, "cache_read_input_tokens": 1990}, "claude")
    conexoes = pasta.Conexoes(
        cerebro="Claude, com o Sonnet 5.5",
        proprias=[("sessoes_listar", True), ("sistema_executar", False)],
        embutidas=["WebSearch"],
        externos={"tempo": ["get_current_time"]},
    )
    notas = pasta.notas(
        conexoes,
        memoria,
        skills,
        30,
        Jobs(tmp_path / "jobs.json"),
        revisao.Pendencias(tmp_path / "p.json"),
        diario,
        consumo,
    )
    assert list(notas) == [
        "1 Quem sou.md",
        "2 Memória.md",
        "3 Skills.md",
        "4 Automações.md",
        "5 Aprendizado.md",
        "6 Consumo.md",
    ]
    assert "**Sessões de código:** `sessoes_listar` (livre)" in notas["1 Quem sou.md"]
    assert "**Máquina (Omarchy):** `sistema_executar`\n" in notas["1 Quem sou.md"]
    assert "**tempo** (livres: get_current_time)" in notas["1 Quem sou.md"]
    assert "- Se chama Ana." in notas["2 Memória.md"]
    assert "| fala-natural | Faz fala-natural. | 1 |" in notas["3 Skills.md"]
    assert "Sugestão aprovada: guardar X" in notas["5 Aprendizado.md"]
    assert "“prefiro X”" in notas["5 Aprendizado.md"]
    assert "| 1 | 2.0 mil | 99% | 0 | 2.0 mil |".replace(".", ",") in notas["6 Consumo.md"]

    p = pasta.Pasta(tmp_path / "pasta")
    assert len(p.gravar(notas)) == 6
    assert p.gravar(notas) == []
    assert p.gravar({**notas, "2 Memória.md": "outra"}) == ["2 Memória.md"]
    assert sorted(x.name for x in p.pasta.iterdir()) == sorted(notas)  # sem temporários
