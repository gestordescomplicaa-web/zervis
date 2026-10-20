"""Memória contínua: cada fala com a hora, a linha do tempo, a nota do dia e as ferramentas."""

import json
import sqlite3
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from jarvis.memoria import conversas as mc
from jarvis.memoria import dias as md
from jarvis.memoria import historico, tempo
from jarvis.memoria.conversas import FUSO, Conversas, Turno
from jarvis.memoria.dias import Dias
from jarvis.memoria.linha import LinhaDoTempo, interpretar_data


def test_publicacao_usa_binario_embutido_e_mesmos_dados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis.memoria import aimemory

    binario = tmp_path / "binario-embutido" / "ai-memory"
    dados = tmp_path / "memoria-longa"
    chamadas: list[tuple[list[str], dict[str, Any]]] = []

    def executar(comando: list[str], **opcoes: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append((comando, opcoes))
        return subprocess.CompletedProcess(comando, 0, stdout="", stderr="")

    monkeypatch.setattr(aimemory, "binario", lambda: binario)
    monkeypatch.setattr(aimemory, "DADOS", dados)
    monkeypatch.setattr("jarvis.memoria.conversas.subprocess.run", executar)
    assert mc.publicar("conversas/dia.md", "Registro sintético.", ("voz",))
    comando, opcoes = chamadas[0]
    assert comando[:4] == [str(binario), "--data-dir", str(dados), "write-page"]
    assert opcoes["input"] == "Registro sintético." and opcoes["timeout"] == 30
    assert comando[-2:] == ["-t", "voz"]


def quando(dia: int, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime(2026, 10, dia, hora, minuto, tzinfo=FUSO)


def test_cada_fala_fica_com_a_hora_e_o_dia_vira_pagina(tmp_path: Path) -> None:
    c = Conversas(tmp_path)
    c.registrar("Que horas são?", "São dez da manhã.", quando(8, 10, 2))
    c.registrar("E amanhã?", "Quinta.", quando(8, 11, 30))
    c.registrar("Bom dia", "Bom dia!", quando(9, 8))
    assert [t.pessoa for t in c.do_dia(date(2026, 10, 8))] == ["Que horas são?", "E amanhã?"]
    assert c.dias() == [date(2026, 10, 8), date(2026, 10, 9)]
    pagina = c.pagina(date(2026, 10, 8))
    assert pagina.startswith("# Conversas com o Zé — quinta-feira, 08/10/2026")
    assert "## 10:02\n**Usuário:** Que horas são?" in pagina and "**Zé:** Quinta." in pagina


def test_juntar_nao_duplica(tmp_path: Path) -> None:
    c = Conversas(tmp_path)
    t = Turno(quando(8), "Oi", "Olá")
    assert c.juntar([t, t]) == 1
    assert c.juntar([t, Turno(quando(8, 11), "Outra", "Sim")]) == 1
    assert len(c.do_dia(date(2026, 10, 8))) == 2


def test_carimbo_e_contexto_aninhado_saem_do_pedido() -> None:
    conteudo = (
        "[quinta-feira, 08/10/2026, 00:47] (Janela do Zé: aberta; Núcleo recolhido "
        "(Mapa, Guia); o usuário está usando as mãos) (Aviso: algo) Quero o mapa."
    )
    assert mc.pedido_do_carimbo(conteudo) == (quando(8, 0, 47), "Quero o mapa.")
    assert mc.pedido_do_carimbo("Você revisa uma conversa…") is None


def test_importar_a_transcricao_do_sdk(tmp_path: Path) -> None:
    pedido = "[quarta-feira, 07/10/2026, 21:05] (Janela aberta) Abre o guia."
    linhas = [
        {"type": "user", "message": {"content": "Você revisa uma conversa entre…"}},
        {"type": "user", "message": {"content": pedido}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "x"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Guia aberto."}]}},
        {"type": "user", "message": {"content": "[quarta-feira, 07/10/2026, 21:06] Valeu."}},
    ]  # fmt: skip
    turnos = mc.turnos_da_transcricao(json.dumps(x) for x in linhas)
    assert turnos == [
        Turno(quando(7, 21, 5), "Abre o guia.", "Guia aberto."),
        Turno(quando(7, 21, 6), "Valeu.", ""),
    ]
    pasta = tmp_path / "sdk"
    pasta.mkdir()
    (pasta / "a.jsonl").write_text("\n".join(json.dumps(x) for x in linhas))
    c = Conversas(tmp_path / "conversas")
    assert mc.importar_sdk(pasta, c) == 2
    assert mc.importar_sdk(pasta, c) == 0  # de novo: nada duplicado


def test_linha_do_tempo_registra_filtra_e_mostra_os_proximos_marcos(tmp_path: Path) -> None:
    linha = LinhaDoTempo(tmp_path / "linha.jsonl")
    linha.registrar("aprovado", "Vou pedir para um Claude, no projeto X: testes.", quando(8, 9))
    linha.registrar("marco", "Lançamento do Ligatia", interpretar_data("2026-10-20"))
    linha.registrar("marco", "Fechei o contrato", interpretar_data("07/10/2026 15:30"))
    assert [e.texto for e in linha.entre(quando(8, 0), quando(9, 0))] == [
        "Vou pedir para um Claude, no projeto X: testes."
    ]
    assert [e.texto for e in linha.proximos(14, quando(8))] == ["Lançamento do Ligatia"]
    assert linha.todos()[0].resumo() == "07/10/2026 15:30 [marco] Fechei o contrato"
    with pytest.raises(ValueError):
        linha.registrar("fofoca", "x")
    with pytest.raises(ValueError):
        interpretar_data("dia vinte")


def test_nota_do_dia_so_depois_das_cinco_com_material_e_sem_nota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publicadas: list[str] = []
    monkeypatch.setattr(md, "publicar", lambda caminho, corpo, tags=(): publicadas.append(caminho))
    c, linha = Conversas(tmp_path / "c"), LinhaDoTempo(tmp_path / "l.jsonl")
    d = Dias(tmp_path / "dias", c, linha)
    c.registrar("Começa o teste do Foco", "Começado.", quando(7, 14))
    linha.registrar("marco", "Lançamento do Ligatia", quando(10, 0))
    assert d.faltando(quando(8, 4)) == []  # antes das 5h
    assert d.faltando(quando(8, 6)) == [date(2026, 10, 7)]
    assert "[14:00] Usuário: Começa o teste do Foco" in d.prompt(date(2026, 10, 7))
    c.registrar("x" * 900, "y", quando(7, 15))
    assert "x" * 300 not in d.material(date(2026, 10, 7))  # falas longas encurtadas
    corpo = d.guardar(date(2026, 10, 7), "# Nota do dia — Zé\n\n## Feito\n- Teste do Foco começado")
    assert corpo.count("# Nota do dia") == 1
    assert "Nota do dia — quarta-feira, 07/10/2026" in corpo and "Lançamento do Ligatia" in corpo
    assert publicadas == ["dias/2026-10-07.md"] and d.faltando(quando(8, 6)) == []


def test_ferramentas_de_tempo(tmp_path: Path) -> None:
    c, linha = Conversas(tmp_path / "c"), LinhaDoTempo(tmp_path / "l.jsonl")
    d = Dias(tmp_path / "dias", c, linha)
    c.registrar("Abre o mapa", "Mapa aberto.", quando(6, 10))
    c.registrar("Fala do Ligatia", "O Ligatia está parado.", quando(6, 11))
    linha.registrar("aviso", "O Codex terminou no projeto X.", quando(6, 12))
    r = tempo.linha_do_tempo(c, linha, d, date(2026, 10, 5), date(2026, 10, 7))
    assert [x["dia"] for x in r["dias"]] == ["terça-feira, 06/10/2026"]
    assert r["dias"][0]["conversas"] == 2 and "O Codex terminou" in r["dias"][0]["eventos"][0]
    texto = tempo.conversa_do_dia(c, date(2026, 10, 6), "ligatia")
    assert "O Ligatia está parado." in texto and "Mapa aberto" not in texto
    with pytest.raises(ValueError):
        tempo.linha_do_tempo(c, linha, d, date(2026, 1, 1), date(2026, 10, 1))
    assert set(tempo.LIVRES) == {
        "mcp__tempo__linha_do_tempo",
        "mcp__tempo__conversa_do_dia",
        "mcp__tempo__marcar",
    }


def test_a_busca_ve_as_paginas_do_ze_primeiro(tmp_path: Path) -> None:
    banco = tmp_path / "m.sqlite"
    with sqlite3.connect(banco) as con:
        con.executescript(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE sessions (id INTEGER, project_id INTEGER, started_at INTEGER);"
            "CREATE TABLE pages (id INTEGER, project_id INTEGER, updated_at INTEGER);"
            "INSERT INTO projects VALUES (1, 'VIBE-CODING'), (2, 'Zé'), (3, 'Vazio');"
            "INSERT INTO sessions VALUES (1, 1, 900);"
            "INSERT INTO pages VALUES (1, 2, 100);"
        )
    assert historico.projetos(banco) == ["Zé", "VIBE-CODING"]


def test_conversa_gravada_no_formato_antigo_continua_legivel(tmp_path: Path) -> None:
    """Antes de 20/10/2026, a fala de quem usa ficava sob outra chave: ela continua sendo lida, e
    as falas novas vão como "pessoa"."""
    from jarvis.dados.documentos import Documentos

    pasta = tmp_path / "conversas"
    antigo = {
        "em": "2026-10-14T10:00:00-03:00",
        "fala_antiga": "cadê a proposta?",
        "ze": "Em revisão.",
    }
    Documentos(pasta / "conversas.db").guardar("conversas", {**antigo, "dia": "2026-10-14"})
    c = Conversas(pasta)
    (turno,) = c.do_dia(date(2026, 10, 14))
    assert (turno.pessoa, turno.ze) == ("cadê a proposta?", "Em revisão.")
    assert c.buscar("proposta")[0].pessoa == "cadê a proposta?"
    novo = c.registrar("e o contrato?", "Assinado.")
    assert '"pessoa": "e o contrato?"' in novo.para_json()
