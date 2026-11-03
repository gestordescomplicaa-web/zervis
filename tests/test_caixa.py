"""A caixa de entrada do WhatsApp do Zé (ADR 0054): o que entra, o que sai, por quanto tempo."""

import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis.avisos import caixa as cx
from zervis.nucleo.servicos.atendimento import ServicoAtendimento

ANA = "134230663237656@lid"
T = 1_000_000.0  # o relógio dos testes


class Relogio:
    t = T

    def __call__(self) -> float:
        return self.t


def _caixa(tmp_path: Path) -> tuple[cx.Caixa, Relogio]:
    relogio = Relogio()
    return cx.Caixa(tmp_path / "caixa.json", relogio), relogio


def test_guarda_a_conversa_dos_dois_lados_e_sabe_quem_espera(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Ana", "quanto custa?", "", ANA)
    [conversa] = caixa.conversas()
    assert conversa.sem_resposta and conversa.nome == "Ana"
    relogio.t += 30
    caixa.enviada(ANA, "Custa 200.")
    assert not caixa.conversas()[0].sem_resposta
    caixa.enviada("558100000000@s.whatsapp.net", "oi")  # a quem nunca escreveu: fora da caixa
    assert len(caixa.conversas()) == 1


def test_a_mais_recente_primeiro_e_a_midia_pelo_tipo(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Bia", "bom dia", "558199990000", "558199990000@s.whatsapp.net")
    relogio.t += 60
    caixa.receber("Ana", "", "", ANA, midia="audio")
    caixa.receber("Ana", "o orçamento", "", ANA, midia="image")
    assert [c.nome for c in caixa.conversas()] == ["Ana", "Bia"]
    ana = caixa.conversas()[0]
    assert [cx.descrever(m) for m in ana.mensagens] == ["[um áudio]", "[uma foto] o orçamento"]


def test_sobrevive_ao_reinicio_privada_sem_repetir_e_esquece_em_7_dias(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    caixa.receber("Ana", "quanto custa?", "", ANA, quando=relogio.t)
    caixa.receber("Ana", "quanto custa?", "", ANA, quando=relogio.t)  # a Central repassou
    arquivo = tmp_path / "caixa.json"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    depois = cx.Caixa(arquivo, relogio)
    assert len(depois.conversas()[0].mensagens) == 1
    relogio.t += cx.VALIDADE_S + 1
    assert depois.conversas() == []


def test_limites_de_conversas_e_mensagens(tmp_path: Path) -> None:
    caixa, relogio = _caixa(tmp_path)
    for i in range(cx.MENSAGENS + 5):
        relogio.t += 1
        caixa.receber("Ana", f"m{i}", "", ANA)
    assert len(caixa.conversas()[0].mensagens) == cx.MENSAGENS
    for i in range(cx.CONVERSAS + 3):
        relogio.t += 1
        caixa.receber(f"C{i}", "oi", "", f"{1000 + i}@lid")
    assert len(caixa.conversas()) == cx.CONVERSAS


def test_acha_pelo_nome_quem_espera_primeiro(tmp_path: Path) -> None:
    caixa, _ = _caixa(tmp_path)
    caixa.receber("João Silva", "oi", "", "1@lid")
    caixa.enviada("1@lid", "oi, João")
    caixa.receber("João Pedro", "oi", "", "2@lid")
    achado = caixa.achar("João")  # o Silva já foi respondido: o Pedro é quem espera
    assert achado is not None and achado.chat == "2@lid"
    assert (por_id := caixa.achar(cx.ident("1@lid"))) is not None and por_id.chat == "1@lid"
    caixa.receber("João Silva", "e aí?", "", "1@lid")
    assert caixa.achar("João") is None  # dois esperando: o Zé pergunta qual


def _servico(tmp_path: Path) -> tuple[ServicoAtendimento, Any, list[tuple[str, ...]]]:
    julgadas: list[tuple[str, ...]] = []
    caixa, _ = _caixa(tmp_path)
    n: Any = SimpleNamespace(
        caixa=caixa,
        mensagens=SimpleNamespace(receber=lambda *dados: julgadas.append(dados)),
        leads=SimpleNamespace(responder=lambda chat, quando=0.0: None),
    )
    return ServicoAtendimento(n), n, julgadas


def test_a_central_alimenta_a_caixa_e_so_o_texto_novo_e_julgado(tmp_path: Path) -> None:
    servico, n, julgadas = _servico(tmp_path)
    base = {"tipo": "mensagem", "nome": "Ana", "telefone": "", "chat": ANA, "quando": T + 1}
    servico._evento_da_central({**base, "texto": "quanto custa?", "midia": ""})
    servico._evento_da_central({**base, "texto": "", "midia": "audio", "quando": T + 2})
    servico._evento_da_central({**base, "texto": "antiga", "repassado": True, "quando": T + 0.5})
    servico._evento_da_central(
        {"tipo": "respondida", "chat": ANA, "texto": "Custa 200.", "quando": T + 3}
    )
    assert julgadas == [("Ana", "quanto custa?", "", ANA)]  # nem o áudio nem a repassada
    textos = [m["texto"] for m in n.caixa.conversas()[0].mensagens]
    assert textos == ["antiga", "quanto custa?", "", "Custa 200."]  # na ordem em que aconteceram
