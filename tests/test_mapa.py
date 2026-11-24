"""O Zé conhece todas as suas páginas e os seus eventos (ADR 0128).

Caso de 24/11/2026: perguntado sobre a Prospecção, o Zé disse que não conhecia a aba. Ela entrou
no painel sem ferramenta e sem linha no autoconhecimento. Estes testes fazem uma página nova sem
lugar no mapa (ou com uma ferramenta que não existe) falhar no `make check`.
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from zervis import atividade, empresas
from zervis.cerebro import ferramentas, rapido
from zervis.cerebro.ferramentas import paginas
from zervis.cerebro.ferramentas import prospeccao as g_prospeccao
from zervis.nucleo import autoconhecimento, mapa
from zervis.prospeccao import funil

RAIZ = Path(__file__).resolve().parent.parent
MENU = RAIZ / "zervis" / "portal" / "web" / "index.html"


def _secoes_do_menu() -> list[str]:
    return re.findall(r'data-secao="([a-z0-9]+)"', MENU.read_text())


def _ferramentas_existentes() -> set[str]:
    """Os nomes de todas as ferramentas que o cérebro pode ter (servidor `jarvis` e o Foco)."""
    nomes: set[str] = set()
    fontes = [*(RAIZ / "zervis" / "cerebro" / "ferramentas").glob("*.py")]
    fontes.append(RAIZ / "zervis" / "foco" / "ferramentas.py")
    for fonte in fontes:
        nomes |= set(re.findall(r'@tool\(\s*"([a-z0-9_]+)"', fonte.read_text()))
    return nomes


def test_toda_pagina_do_menu_esta_no_mapa_com_ferramenta_que_existe() -> None:
    secoes = _secoes_do_menu()
    assert secoes and set(secoes) == set(mapa.PAGINAS), (
        "Página do painel sem linha em zervis/nucleo/mapa.py (ou linha de página que saiu): "
        f"{sorted(set(secoes) ^ set(mapa.PAGINAS))}"
    )
    existentes = _ferramentas_existentes()
    for secao, pagina in mapa.PAGINAS.items():
        assert pagina.consultar, f"{secao}: sem ferramenta para o Zé consultar"
        faltam = set(pagina.consultar) - existentes
        assert not faltam, f"{secao}: ferramentas que não existem: {faltam}"


def test_o_retrato_leva_o_mapa_e_toda_ferramenta_nova_tem_grupo() -> None:
    texto = autoconhecimento.texto(autoconhecimento.Retrato(cerebro="Claude"))
    assert "## As minhas páginas (o painel)" in texto
    assert "**Prospecção** (prospeccao_situacao)" in texto and "atividade_buscar" in texto
    for chave in ("prospeccao", "paginas"):
        assert chave in autoconhecimento.GRUPOS
    livres = {n.rsplit("__", 1)[-1] for n in ferramentas.LIVRES}
    leitura = {"prospeccao_situacao", "empresas_listar", "redes_situacao", "atividade_buscar"}
    assert leitura <= livres  # ler não pergunta
    escrita = {"prospeccao_aprovar", "prospeccao_buscar", "prospeccao_ajustar"}
    assert not escrita & livres  # o que muda o envio pede o sim
    for nome in ("prospeccao_situacao", "redes_situacao", "atividade_buscar"):
        assert ferramentas.de_fora(f"mcp__jarvis__{nome}")  # texto de terceiros


def _chamar(ferramenta: Any, args: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(ferramenta.handler(args))


def _por_nome(lista: list[Any]) -> dict[str, Any]:
    return {f.name: f for f in lista}


@pytest.fixture
def funil_de_teste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> funil.Funil:
    config = tmp_path / "prospeccao.json"
    f = funil.Funil(
        tmp_path / "prospeccao-dados.json",
        config,
        agora=lambda: datetime(2026, 11, 25, 10, 0).timestamp(),
        chave_apify=lambda: "",
        sortear=lambda inicio, fim: inicio,
    )
    funil.salvar_config(funil.Config(ligada=True, cidade="Caruaru, PE", ramos=["dentista"]), config)
    monkeypatch.setattr(funil, "_PADRAO", f)
    with f._empresas.transacao():
        sorrir = f._nova("Sorrir Clínica", "maps", status="aprovar", dono="Carlos Lima")
        sorrir.update(cargo="Sócio-Administrador", nota=78, mensagem="Oi, Carlos!")
        centro = f._nova("Imobiliária Centro", "maps", status="enviada", enviado=f.agora())
        centro["telefone_enviado"] = "558199990000"
        f._empresas.gravar([sorrir, centro])
    return f


def test_prospeccao_pela_voz_diz_o_que_acontece_e_age_pelo_nome(
    funil_de_teste: funil.Funil,
) -> None:
    t = _por_nome(g_prospeccao.ferramentas())
    situacao = json.loads(_chamar(t["prospeccao_situacao"], {})["content"][0]["text"])
    assert situacao["estado"] == "Ligada" and situacao["hoje"] == "1 de 2 enviadas"
    assert situacao["agora"] == "nada em andamento"
    [espera] = situacao["aguardando_aprovacao"]
    assert espera["empresa"] == "Sorrir Clínica" and espera["mensagem"] == "Oi, Carlos!"
    uma = json.loads(_chamar(t["prospeccao_situacao"], {"empresa": "carlos"})["content"][0]["text"])
    assert uma["empresa"]["quem_decide"] == "Carlos Lima (Sócio-Administrador)"
    feito = _chamar(t["prospeccao_aprovar"], {"empresa": "sorrir"})
    assert "Sorrir Clínica aprovada" in feito["content"][0]["text"]
    assert funil_de_teste.achar("sorrir")["status"] == "fila"
    nada = _chamar(t["prospeccao_descartar"], {"empresa": "padaria"})
    assert nada.get("is_error") and "Nenhuma empresa" in nada["content"][0]["text"]
    ajuste = _chamar(t["prospeccao_ajustar"], {"ligada": False, "por_dia": 3})
    assert (
        "desligada" in ajuste["content"][0]["text"]
        and "até 3 por dia" in ajuste["content"][0]["text"]
    )
    assert _chamar(t["prospeccao_ajustar"], {"por_dia": 50}).get("is_error")  # acima do teto


def test_atividade_empresas_e_funil_pela_voz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = atividade.Atividade(tmp_path / "atividade.db")
    monkeypatch.setattr(atividade, "PADRAO", base)
    base.registrar("execucao", "Prospecção: 8 empresa(s) novas (dentista)")
    base.registrar("falha", "WhatsApp: conversa nova com Ana", erro="não conectado")
    t = _por_nome(paginas.ferramentas())
    achou = json.loads(
        _chamar(t["atividade_buscar"], {"busca": "prospeccao"})["content"][0]["text"]
    )
    assert achou["total"] == 1 and achou["registros"][0]["o_que"].startswith("Prospecção")
    falhas = json.loads(_chamar(t["atividade_buscar"], {"tipo": "falha"})["content"][0]["text"])
    assert [r["tipo"] for r in falhas["registros"]] == ["falha"]

    monkeypatch.setattr(
        empresas,
        "PADRAO",
        empresas.Empresas(tmp_path / "e.json", tmp_path / "e", tmp_path / "g.json"),
    )
    vazio = json.loads(_chamar(t["empresas_listar"], {})["content"][0]["text"])
    assert vazio["empresas"] == [] and "Nenhuma" in vazio["aviso"]
    funil_ig = json.loads(_chamar(t["redes_situacao"], {})["content"][0]["text"])
    assert funil_ig["comentarios_viram_conversa"] in ("ligado", "desligado")


def test_pergunta_sobre_uma_pagina_vai_ao_cerebro_que_tem_as_ferramentas() -> None:
    """Caso real: a pergunta ficou na via rápida, que não tem ferramentas nem sabe o estado."""
    for pedido in (
        "veja se tá acontecendo algum disparo de prospecção no momento na aba prospecção",
        "como está a prospecção?",
        "quem comentou no instagram hoje?",
        "o que aconteceu com o envio de ontem?",
        "quais empresas eu tenho?",
    ):
        assert rapido.precisa_do_completo(pedido), pedido
    assert not rapido.precisa_do_completo("tudo bem com você?")
    so_retrato = {"ze_sobre", "historico_buscar", "atividade_buscar"}
    for secao, pagina in mapa.PAGINAS.items():
        if not set(pagina.consultar) <= so_retrato:
            assert pagina.assuntos, f"{secao}: sem palavras que levem o pedido ao cérebro completo"
    resumo = autoconhecimento.resumo(autoconhecimento.Retrato(cerebro="Claude"))
    assert "Prospecção" in resumo and "nunca diga que não conhece" in resumo
