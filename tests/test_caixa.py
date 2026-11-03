"""O arquivo do WhatsApp do Zé (ADR 0054 e 0056): o que entra, o que sai, grupos e a busca."""

import json
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis.avisos import caixa as cx
from zervis.nucleo.servicos.atendimento import ServicoAtendimento

ANA = "134230663237656@lid"
GRUPO = "120363000000000000@g.us"
T = 1_000_000.0  # o relógio dos testes


class Relogio:
    t = T

    def __call__(self) -> float:
        return self.t


def _caixa(tmp_path: Path, antigo: Path | None = None) -> tuple[cx.Caixa, Relogio]:
    relogio = Relogio()
    return cx.Caixa(tmp_path / "arquivo.db", relogio, antigo), relogio


def test_guarda_a_conversa_dos_dois_lados_e_sabe_quem_espera(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Ana", "quanto custa?", "", ANA)
    [conversa] = caixa.conversas()
    assert conversa.sem_resposta and conversa.nome == "Ana"
    relogio.t += 30
    caixa.enviada(ANA, "Custa 200.")
    assert not caixa.conversas()[0].sem_resposta
    relogio.t += 30
    caixa.enviada("558100000000@s.whatsapp.net", "oi")  # a quem nunca escreveu: também guarda
    assert [c.nome for c in caixa.conversas()] == ["558100000000", "Ana"]
    assert stat.S_IMODE((tmp_path / "arquivo.db").stat().st_mode) == 0o600


def test_grupo_com_quem_falou_mas_sem_cobrar_resposta(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Bia", "reunião às 15h", "558199990000", GRUPO, grupo=True, grupo_nome="Equipe")
    relogio.t += 10
    caixa.receber("Caio", "", "", GRUPO, midia="audio", grupo=True)
    [g] = caixa.conversas()
    assert (g.nome, g.grupo, g.sem_resposta) == ("Equipe", True, False)
    assert [(m["autor"], cx.descrever(m)) for m in caixa.mensagens(GRUPO)] == [
        ("Bia", "reunião às 15h"),
        ("Caio", "[um áudio]"),
    ]
    assert caixa.conversas(grupos=False) == []


def test_a_mais_recente_primeiro_e_a_midia_pelo_tipo(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Bia", "bom dia", "558199990000", "558199990000@s.whatsapp.net")
    relogio.t += 60
    caixa.receber("Ana", "", "", ANA, midia="audio")
    relogio.t += 1
    caixa.receber("Ana", "o orçamento", "", ANA, midia="image")
    assert [c.nome for c in caixa.conversas()] == ["Ana", "Bia"]
    descritas = [cx.descrever(m) for m in caixa.mensagens(ANA)]
    assert descritas == ["[um áudio]", "[uma foto] o orçamento"]


def test_para_sempre_sem_repetir_e_na_ordem_em_que_aconteceu(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    assert caixa.receber("Ana", "quanto custa?", "", ANA, quando=T, evento="s:1")
    assert not caixa.receber("Ana", "quanto custa?", "", ANA, quando=T, evento="s:1")  # repassada
    caixa.receber("Ana", "antes", "", ANA, quando=T - 60, evento="s:0")  # chegou atrasada
    relogio.t += 400 * 86400  # mais de um ano depois
    depois = cx.Caixa(tmp_path / "arquivo.db", relogio, None)
    assert [m["texto"] for m in depois.mensagens(ANA)] == ["antes", "quanto custa?"]


def test_busca_por_palavra_sem_acento_por_contato_e_periodo(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Ana", "Pode mandar o orçamento da automação?", "", ANA)
    caixa.receber("Bia", "o orçamento ficou alto", "", "2@lid")
    relogio.t += 10 * 86400
    caixa.receber("Ana", "e o prazo de entrega?", "", ANA)
    caixa.receber("Caio", "orçamento aprovado", "", GRUPO, grupo=True, grupo_nome="Equipe")
    achados = caixa.buscar("orcamento")  # sem acento, como a voz transcreve
    assert {c.nome for c, _ in achados} == {"Ana", "Bia", "Equipe"}
    assert len(caixa.buscar("orçamento entrega", chat=ANA)) == 2
    recentes = caixa.buscar("orçamento", desde=relogio.t - 86400)
    assert [c.nome for c, _ in recentes] == ["Equipe"]
    ultima = [m["texto"] for _, m in caixa.buscar("", chat=ANA, limite=1)]
    assert ultima == ["e o prazo de entrega?"]
    assert caixa.buscar("xyzw") == []


def test_acha_pelo_nome_quem_espera_primeiro(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("João Silva", "oi", "", "1@lid")
    relogio.t += 1
    caixa.enviada("1@lid", "oi, João")
    relogio.t += 1
    caixa.receber("João Pedro", "oi", "", "2@lid")
    achado = caixa.achar("João")  # o Silva já foi respondido: o Pedro é quem espera
    assert achado is not None and achado.chat == "2@lid"
    assert (por_id := caixa.achar(cx.ident("1@lid"))) is not None and por_id.chat == "1@lid"
    relogio.t += 1
    caixa.receber("João Silva", "e aí?", "", "1@lid")
    assert caixa.achar("João") is None  # dois esperando: o Zé pergunta qual


def test_esquecer_apaga_a_conversa_e_a_busca(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Ana", "meu endereço é rua das flores", "", ANA)
    relogio.t += 1
    caixa.receber("Bia", "oi", "", "2@lid")
    assert caixa.esquecer(ANA) == 1
    assert caixa.buscar("endereço") == [] and caixa.achar("Ana") is None
    assert [c.nome for c in caixa.conversas()] == ["Bia"]


def test_a_caixa_de_7_dias_entra_no_arquivo_uma_vez(tmp_path: Path) -> None:
    antigo = tmp_path / "whatsapp-caixa.json"
    conversa = {"chat": ANA, "nome": "Ana", "telefone": "", "mensagens": [
        {"de_mim": False, "texto": "quanto custa?", "midia": "", "quando": T - 100},
        {"de_mim": True, "texto": "Custa 200.", "midia": "", "quando": T - 50},
    ]}  # fmt: skip
    antigo.write_text(json.dumps([conversa]))
    caixa, _ = _caixa(tmp_path, antigo)
    assert [m["texto"] for m in caixa.mensagens(ANA)] == ["quanto custa?", "Custa 200."]
    assert not antigo.exists() and antigo.with_suffix(".importado").exists()


def _servico(tmp_path: Path) -> tuple[ServicoAtendimento, Any, list[tuple[str, ...]]]:
    julgadas: list[tuple[str, ...]] = []
    caixa, _ = _caixa(tmp_path)
    n: Any = SimpleNamespace(
        caixa=caixa,
        mensagens=SimpleNamespace(receber=lambda *dados: julgadas.append(dados)),
        leads=SimpleNamespace(
            responder=lambda chat, quando=0.0: None, dispensada_ha_pouco=lambda chat: False
        ),
    )
    return ServicoAtendimento(n), n, julgadas


def test_a_central_alimenta_o_arquivo_e_so_o_texto_privado_novo_e_julgado(tmp_path: Path) -> None:
    servico, n, julgadas = _servico(tmp_path)
    base = {"tipo": "mensagem", "nome": "Ana", "telefone": "", "chat": ANA, "quando": T + 9}
    servico._evento_da_central(
        {**base, "texto": "quanto custa?", "midia": "", "evento": "s:1", "hora": T + 1}
    )
    servico._evento_da_central(
        {**base, "texto": "", "midia": "audio", "evento": "s:2", "hora": T + 2}
    )
    servico._evento_da_central(
        {**base, "texto": "antiga", "repassado": True, "evento": "s:0", "hora": T + 0.5}
    )
    servico._evento_da_central(
        {**base, "texto": "reunião", "chat": GRUPO, "grupo": True, "grupo_nome": "Equipe",
         "evento": "g:1", "hora": T + 3}
    )  # fmt: skip
    servico._evento_da_central(
        {"tipo": "respondida", "chat": ANA, "texto": "Custa 200.", "evento": "s:3", "quando": T + 4}
    )
    assert julgadas == [("Ana", "quanto custa?", "", ANA)]  # nem áudio, nem repassada, nem grupo
    textos = [m["texto"] for m in n.caixa.mensagens(ANA)]
    assert textos == ["antiga", "quanto custa?", "", "Custa 200."]  # a hora do WhatsApp manda
    assert [m["texto"] for m in n.caixa.mensagens(GRUPO)] == ["reunião"]
