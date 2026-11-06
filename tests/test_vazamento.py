"""Antes de publicar uma melhoria: a mudança não leva dados de quem usa (06/11/2026). Os dados são
inventados aqui: uma agenda falsa, chaves falsas, uma pasta pessoal falsa."""

import json
import sqlite3
from pathlib import Path

import pytest

from zervis.oficina import vazamento as v

CHAVE_FALSA = "zx81Kq0pLm2Nb7Vc4Xs9Hd3Fg6Jt5Ry"


@pytest.fixture
def sensiveis(tmp_path: Path) -> v.Sensiveis:
    banco = tmp_path / "wacalls.db"
    db = sqlite3.connect(banco)
    db.execute("CREATE TABLE whatsmeow_contacts (their_jid, full_name, first_name, push_name)")
    db.execute("CREATE TABLE whatsmeow_lid_map (lid, pn)")
    db.execute("CREATE TABLE whatsmeow_device (jid)")
    db.executemany(
        "INSERT INTO whatsmeow_contacts VALUES (?, ?, ?, ?)",
        [
            ("5571988887777@s.whatsapp.net", "Gertrudes Valadão", "", ""),
            ("246813579024680@lid", "", "Bento", ""),
            ("5571933334444@s.whatsapp.net", "", "", "Só perfil"),
        ],
    )
    db.execute("INSERT INTO whatsmeow_lid_map VALUES ('135792468013579', '5571922221111')")
    db.execute("INSERT INTO whatsmeow_device VALUES ('5571900001111:7@s.whatsapp.net')")
    db.commit()
    db.close()
    config = tmp_path / "config"
    (config / "chaves").mkdir(parents=True)
    (config / "deepgram.key").write_text(CHAVE_FALSA + "\n")
    (config / "chaves" / "oauth.json").write_text(
        json.dumps({"token": "tk_9f8e7d6c5b4a3210fedcba"})
    )
    (config / "painel.json").write_text(json.dumps({"tema": "escuro", "porta": "8795"}))
    (config / "perfil.json").write_text(json.dumps({"nome": "Ernesto Pilar"}))
    return v.coletar(config=config, whatsapp=banco, casa=Path("/home/fulano"))


def _diff(arquivo: str, *linhas: str) -> str:
    corpo = "\n".join(f"+{linha}" for linha in linhas)
    cabeca = f"diff --git a/{arquivo} b/{arquivo}\n--- a/{arquivo}\n+++ b/{arquivo}\n"
    return f"{cabeca}@@ -0,0 +10,{len(linhas)} @@\n{corpo}\n"


@pytest.mark.parametrize(
    ("linha", "tipo"),
    [
        ('TEL = "5571988887777"', "número de telefone da sua agenda"),
        ('tel = "(71) 98888-7777"', "número de telefone da sua agenda"),  # formatado
        ('tel = "557188887777"', "número de telefone da sua agenda"),  # sem o nono dígito
        ('tel = "71922221111"', "número de telefone da sua agenda"),  # veio do mapa do LID
        ('eu = "5571900001111"', "número de telefone da sua agenda"),  # o número conectado
        ('jid = "246813579024680@lid"', "identificador de um contato do WhatsApp"),
        ('nome = "Gertrudes Valadao"', "nome de um contato seu"),  # sem o acento
        ('quem = "ERNESTO PILAR"', "nome de um contato seu"),  # o perfil
        (f"chave = '{CHAVE_FALSA}'", "chave ou token desta máquina"),
        ('{"t": "tk_9f8e7d6c5b4a3210fedcba"}', "chave ou token desta máquina"),
        ("caminho = '/home/fulano/Work/x'", "caminho da sua pasta pessoal"),
        ("k = 'sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123'", "chave da Anthropic"),
        ("t = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'", "token do GitHub"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----", "chave privada"),
    ],
)
def test_acha_dados_reais_nas_linhas_novas(sensiveis: v.Sensiveis, linha: str, tipo: str) -> None:
    achados = v.conferir(_diff("tests/test_x.py", "ok = 1", linha), "", sensiveis)
    assert [str(a) for a in achados] == [f"{tipo} em tests/test_x.py:11"]


def test_dados_de_exemplo_passam(sensiveis: v.Sensiveis) -> None:
    exemplo = _diff(
        "tests/test_x.py",
        'ANA = "5581999990000"',  # número de exemplo, fora da agenda
        'nome = "Marta Quintela"',
        'so_perfil = "5571933334444"',  # só o nome de perfil não é agenda, mas o número é
        "porta = 8795",
        "Gertrudes",  # um primeiro nome sozinho não basta
    )
    achados = v.conferir(exemplo, "Corrige a busca", sensiveis)
    assert [a.tipo for a in achados] == ["número de telefone da sua agenda"]  # o "só perfil"


def test_mensagem_do_commit_e_arquivos_proibidos(sensiveis: v.Sensiveis) -> None:
    diff = _diff("dados/conversas.db", "x") + _diff(".env", "A=1")
    achados = v.conferir(diff, "Testado com a Gertrudes Valadão", sensiveis)
    assert {str(a) for a in achados} == {
        "arquivo que não vai para o repositório em dados/conversas.db",
        "arquivo que não vai para o repositório em .env",
        "nome de um contato seu em mensagem do commit",
    }


def test_nada_vaza_no_texto_do_achado(sensiveis: v.Sensiveis) -> None:
    achados = v.conferir(_diff("a.py", f"k = '{CHAVE_FALSA}' # 5571988887777"), "", sensiveis)
    texto = " ".join(str(a) for a in achados)
    assert CHAVE_FALSA not in texto and "88887777" not in texto


def test_sem_agenda_nem_configuracao_so_os_formatos(tmp_path: Path) -> None:
    s = v.coletar(config=tmp_path / "nada", whatsapp=tmp_path / "nada.db", casa=Path("/home/x"))
    assert not s.telefones and not s.nomes and not s.segredos
    assert v.conferir(_diff("a.py", "AKIAABCDEFGHIJKLMNOP"), "", s)[0].tipo == "chave da AWS"
