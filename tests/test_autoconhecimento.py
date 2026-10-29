"""O Zé por ele mesmo (ADR 0043): o retrato, a ferramenta `ze_sobre` e a nota "Quem sou"."""

import asyncio
from types import SimpleNamespace
from typing import Any

from zervis.cerebro import ferramentas
from zervis.cerebro.ferramentas import sobre
from zervis.nucleo import autoconhecimento as a
from zervis.nucleo.servicos.cerebro import ServicoCerebro
from zervis.rosto import pasta

RETRATO = a.Retrato(
    cerebro="Codex, com o GPT-6 Luna",
    reserva="Claude",
    rapidas="o Claude pela assinatura, com o Sonnet 5.5, só no Live; respondendo agora",
    rapidas_agora=True,
    rapidas_modelo="Sonnet 5.5",
    voz="Fish Audio (Gojo), com o Cadu de reserva",
    escuta="Deepgram nova-3, em português",
    live="conectado agora, pelo navegador",
    modo="Live",
    acesso="pelo celular no endereço https://ze.exemplo.invalid, com senha e código",
    versao="0.1.0",
)


def test_quem_responde_diz_a_via_rapida_e_o_completo() -> None:
    assert a.quem_responde(RETRATO) == (
        "Na conversa, quem responde é a via rápida, com o Sonnet 5.5; o que pede ferramenta ou "
        "ação vai ao cérebro completo (Codex, com o GPT-6 Luna)."
    )
    sem = a.Retrato(cerebro="Claude, com o Sonnet 5.5")
    assert a.quem_responde(sem) == "Quem responde é o cérebro completo: Claude, com o Sonnet 5.5."


def test_texto_traz_o_agora_e_onde_mudar_cada_coisa() -> None:
    t = a.texto(RETRATO)
    assert "## Agora" in t and "## Onde mudar" in t
    assert "Fish Audio (Gojo)" in t and "Live" in t and "0.1.0" in t
    assert "Voz → Voz do Zé" in t and "Modelos → Respostas rápidas" in t
    assert "Reserva do cérebro" in t and "Contas dos agentes" not in t  # campo vazio não entra


def test_resumo_para_a_via_rapida_e_curto_e_manda_nao_inventar() -> None:
    r = a.resumo(RETRATO)
    assert r.startswith("## Você agora")
    assert "Sonnet 5.5" in r and "Gojo" in r and "sem inventar" in r
    assert len(r) < 800  # entra em toda resposta rápida


def test_a_ferramenta_ze_sobre_le_o_retrato_na_hora_e_passa_sem_perguntar() -> None:
    chamadas: list[int] = []

    def ler() -> str:
        chamadas.append(1)
        return a.texto(RETRATO)

    [ferramenta] = sobre.ferramentas(ler)

    async def chamar() -> Any:
        return await ferramenta.handler({})

    resposta = asyncio.run(chamar())
    assert "## Agora" in resposta["content"][0]["text"] and chamadas == [1]
    assert f"mcp__{ferramentas.SERVIDOR}__ze_sobre" in ferramentas.LIVRES
    assert sobre.ferramentas(None) == []


def test_a_nota_quem_sou_usa_o_retrato() -> None:
    nota = pasta.quem_sou(pasta.Conexoes(cerebro="x", agora=a.texto(RETRATO)))
    assert "## Agora" in nota and "## Cérebro agora" not in nota
    antiga = pasta.quem_sou(pasta.Conexoes(cerebro="Codex"))
    assert "## Cérebro agora" in antiga  # sem retrato, o resumo de antes


def test_a_via_rapida_sobe_sabendo_que_e_ela_quem_responde() -> None:
    nucleo = SimpleNamespace(
        retrato=lambda: a.Retrato(cerebro="Codex, com o GPT-6 Luna", voz="Cadu"),
        cfg={"via_rapida": {"ligada": True, "motor": "plano", "modelo": "claude-sonnet-5-5"}},
    )
    voce = ServicoCerebro(nucleo)._voce_agora()
    assert "via rápida, com o Sonnet 5.5" in voce and "Voz: Cadu." in voce
    assert ServicoCerebro(SimpleNamespace())._voce_agora() == ""


# ADR 0045: o Zé se conhece por inteiro (o que sabe fazer e o que fez), e a tela lê o mesmo retrato.
CAPACIDADES = a.Capacidades(
    grupos=a.grupos(
        {"sessoes": ["sessoes_listar", "sessao_criar"], "novo": ["x_fazer"], "vazio": []},
        {"sessoes_listar"},
    ),
    skills=(a.Skill("checar-leads", "Vê os leads", 3), a.Skill("resumo", "Resume", 0)),
    conectores=(a.Conector("n8n", 31, 15),),
    sessoes=(a.Sessao("Site", "Claude", "trabalhando"),),
    automacoes=(a.Automacao("Bom dia", "todo dia 08:00", False),),
    lembrancas=5,
    paginas=161,
    whatsapp="conectado",
)
HISTORICO = a.Historico(
    contagem={"pedido": 12, "execucao": 7, "falha": 2, "negada": 1},
    por_dia=(a.Dia("2026-10-28", 9, 2), a.Dia("2026-10-29", 4, 0)),
    mais_usadas=(("sessoes_listar", 5), ("mcp__n8n__criar_fluxo", 2)),
    recentes=((1793276414.0, "falha", "Chave recusada"),),
)


def test_grupos_contam_as_livres_e_explicam_cada_area() -> None:
    sessoes, novo = CAPACIDADES.grupos  # grupo sem ferramenta fica de fora
    assert sessoes.nome == "Sessões de código" and sessoes.livres == 1
    assert len(sessoes.ferramentas) == 2 and sessoes.faz
    assert novo.nome == "novo" and novo.faz == ""  # módulo novo sem linha em GRUPOS
    assert CAPACIDADES.ferramentas == 3


def test_texto_traz_o_que_sabe_fazer_e_o_que_fez() -> None:
    t = a.texto(RETRATO, CAPACIDADES, HISTORICO)
    assert t.index("## Agora") < t.index("## O que eu sei fazer") < t.index("## O que eu fiz")
    assert t.index("## O que eu fiz") < t.index("## Onde mudar")
    assert "**Sessões de código** (2)" in t and "checar-leads (3 usos)" in t and "resumo;" not in t
    assert "n8n (31 ferramentas liberadas)" in t and "Site (Claude, trabalhando)" in t
    assert "Bom dia (todo dia 08:00, pausada)" in t and "161 páginas" in t
    assert "12 pedidos atendidos, 7 ações executadas, 2 falhas" in t
    assert "sessoes_listar (5 vezes)" in t and "n8n · criar_fluxo (2 vezes)" in t
    assert "28/10: 9 (2 falhas); 29/10: 4." in t
    assert "## O que eu sei fazer" not in a.texto(RETRATO)  # sem as partes, como antes


def test_a_lista_longa_diz_quantos_faltam() -> None:
    muitas = a.Capacidades(skills=tuple(a.Skill(f"s{i}", "", 0) for i in range(11)))
    assert "s7; e mais 3." in a.texto_das_capacidades(muitas)


def test_dados_para_a_tela_sao_json_sem_acesso_nem_contas() -> None:
    import json

    d = json.loads(json.dumps(a.dados(RETRATO, CAPACIDADES, HISTORICO)))
    assert d["agora"]["cerebro"] == RETRATO.cerebro and "acesso" not in d["agora"]
    assert "contas" not in d["agora"] and "ze.exemplo.invalid" not in json.dumps(d)
    assert d["capacidades"]["ferramentas"] == 3
    assert d["capacidades"]["grupos"][0]["ferramentas"] == ["sessoes_listar", "sessao_criar"]
    assert d["capacidades"]["conectores"] == [{"nome": "n8n", "livres": 31, "bloqueadas": 15}]
    assert d["historico"]["mais_usadas"][1] == {"ferramenta": "n8n · criar_fluxo", "vezes": 2}
    assert d["historico"]["por_dia"][0] == {"dia": "2026-10-28", "registros": 9, "falhas": 2}
    assert d["historico"]["recentes"][0]["titulo"] == "Chave recusada"


def test_as_ferramentas_por_grupo_sao_as_mesmas_do_servidor(tmp_path: Any) -> None:
    from zervis.habilidades.skills import Skills
    from zervis.memoria.curta import Memoria

    memoria, skills = (
        Memoria(tmp_path / "m", {"usuario": 500, "jarvis": 500}),
        Skills(tmp_path / "s"),
    )
    grupos = ferramentas.por_grupo(None, memoria, skills, sobre=lambda: "")
    planas = ferramentas.montar(None, memoria, skills, sobre=lambda: "")
    assert [f.name for fs in grupos.values() for f in fs] == [f.name for f in planas]
    assert "sobre" in grupos and "sessoes" not in grupos  # sem o serviço, o grupo some
    assert set(grupos) <= set(a.GRUPOS)  # todo grupo de verdade tem a sua linha


class _SkillsDoRetrato:
    def listar(self) -> list[tuple[str, str]]:
        return [("pouco", "a"), ("muito", "b")]

    def uso(self) -> dict[str, dict[str, int]]:
        return {"muito": {"usos": 9}, "pouco": {"usos": 1}}


class _SessoesDoRetrato:
    def trabalhando(self) -> list[str]:
        return ["s1"]

    def listar(self) -> list[Any]:
        s = SimpleNamespace(id="s1", nome="Site", motor="claude", estado="parada", origem="")
        ze = SimpleNamespace(
            id="s2", nome="Zé", motor="codex", estado="parada", origem="manutencao"
        )
        return [s, ze]


class _JobsQueQuebram:
    def listar(self) -> list[Any]:
        raise OSError("jobs.json ilegível")


def test_o_nucleo_monta_as_capacidades_e_uma_parte_quebrada_nao_derruba(monkeypatch: Any) -> None:
    from zervis.cerebro import conectores
    from zervis.memoria import aimemory
    from zervis.nucleo.laco import Nucleo

    monkeypatch.setattr(conectores, "listar", lambda: [{"nome": "n8n", "livres": ["a", "b"]}])
    monkeypatch.setattr(aimemory, "paginas", lambda: 42)
    falso = SimpleNamespace(
        ferramentas_por_grupo={"sobre": [SimpleNamespace(name="ze_sobre")]},
        skills=_SkillsDoRetrato(),
        sessoes=_SessoesDoRetrato(),
        jobs=_JobsQueQuebram(),
        memoria=SimpleNamespace(entradas=lambda alvo: ["x", "y"] if alvo == "usuario" else ["z"]),
        central=SimpleNamespace(whatsapp_ativo=False),
    )
    c = Nucleo.capacidades(falso)  # type: ignore[arg-type]
    assert c.grupos[0].nome == "Autoconhecimento" and c.grupos[0].livres == 1
    assert [s.nome for s in c.skills] == ["muito", "pouco"]  # a mais usada primeiro
    assert c.conectores == (a.Conector("n8n", 2, 0),)
    assert c.sessoes == (a.Sessao("Site", "Claude", "trabalhando"),)  # a do Zé fica de fora
    assert c.automacoes == () and c.lembrancas == 3 and c.paginas == 42
    assert c.whatsapp == "desligado"


def test_o_nucleo_le_o_historico_da_atividade(tmp_path: Any, monkeypatch: Any) -> None:
    from zervis import atividade
    from zervis.nucleo.laco import Nucleo

    registro = atividade.Atividade(tmp_path / "atividade.jsonl")
    registro.registrar("execucao", "Listou as sessões", ferramenta="sessoes_listar")
    registro.registrar("pedido", "quantas sessões?")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    h = Nucleo.historico(SimpleNamespace())  # type: ignore[arg-type]
    assert h.contagem["execucao"] == 1 and h.contagem["pedido"] == 1
    assert h.mais_usadas == (("sessoes_listar", 1),) and len(h.por_dia) == 7
    assert [t for _, t, _ in h.recentes] == ["pedido", "execucao"]


def test_o_painel_entrega_o_autoconhecimento_do_nucleo(tmp_path: Any) -> None:
    """Regressão de 29/10/2026: a rota respondia 500 no Zé de verdade porque a página Início não
    declarava o serviço; o teste do painel usa respostas de exemplo e não passava pelo núcleo."""
    from zervis.portal.acoes import Acoes

    retrato = {"agora": {"modelo": "GPT-6 Luna"}}
    acoes = Acoes(SimpleNamespace(autoconhecimento=lambda: retrato), tmp_path, tmp_path)
    assert acoes.leituras()["autoconhecimento"]() == retrato


def test_a_nota_quem_sou_traz_o_que_sabe_fazer_e_o_que_fez() -> None:
    from zervis.nucleo.laco import Nucleo

    falso = SimpleNamespace(
        retrato=lambda: RETRATO, capacidades=lambda: CAPACIDADES, historico=lambda: HISTORICO
    )
    nota = Nucleo._agora_para_a_pasta(falso, "ligada")  # type: ignore[arg-type]
    assert "## O que eu sei fazer" in nota and "## O que eu fiz" in nota
    assert "Revisão em segundo plano:** ligada" in nota
