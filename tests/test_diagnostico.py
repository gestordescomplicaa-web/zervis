"""O diagnóstico do Zé (ADR 0025, camada 2): o que deu errado, agrupado por causa."""

from jarvis import diagnostico


def test_agrupa_falhas_nao_entendi_correcoes_e_o_registro() -> None:
    agora = 1_000_000.0
    itens = [
        {
            "quando": agora - 10,
            "tipo": "falha",
            "titulo": "O cérebro falhou",
            "erro": "limite_de_uso",
        },
        {
            "quando": agora - 20,
            "tipo": "falha",
            "titulo": "O cérebro falhou",
            "erro": "limite_de_uso",
        },
        {"quando": agora - 30, "tipo": "nao_entendi", "titulo": 'Ouviu "Eis é"'},
        {"quando": agora - 40, "tipo": "correcao", "titulo": "Não, eu disse suspender"},
        {
            "quando": agora - 50,
            "tipo": "negada",
            "titulo": "Omarchy: system-shutdown",
            "motivo": "sem a frase exata",
        },
        {"quando": agora - 60, "tipo": "pedido", "titulo": "Que horas são?"},
        {"quando": agora - 30 * 86400, "tipo": "falha", "titulo": "Antiga demais"},
    ]
    registro = [
        "2026-10-13T11:24:19-03:00 omarchy python[1088527]: ERROR livekit: data channel 3 closed",
        "2026-10-13T12:00:00-03:00 omarchy python[2000]: ERROR livekit: data channel 7 closed",
        "2026-10-13T12:00:01-03:00 omarchy python[2000]: INFO tudo certo",
    ]
    texto = diagnostico.montar(itens, registro, agora=agora)
    assert "Falhas: 2" in texto and "Pedidos atendidos: 1" in texto
    assert "- O cérebro falhou: 2 vez(es) (ex.: limite_de_uso)" in texto
    assert 'Ouviu "Eis é"' in texto and '"Não, eu disse suspender"' in texto
    assert "system-shutdown (sem a frase exata)" in texto
    assert "ERROR livekit: data channel # closed: 2 vez(es)" in texto
    assert "Antiga demais" not in texto and "tudo certo" not in texto


def test_sem_problemas_diz_que_nao_ha_o_que_corrigir() -> None:
    assert "Nada a corrigir" in diagnostico.montar([], [], agora=1.0)


def test_assinatura_ignora_o_que_muda_a_cada_vez() -> None:
    a = diagnostico.assinatura(
        "2026-10-13T11:24:19-03:00 pc python[12]: WARNING porta 7880 em /home/x/y/z.py"
    )
    b = diagnostico.assinatura(
        "2026-10-13T11:25:00-03:00 pc python[99]: WARNING porta 8796 em /home/q/r/s.py"
    )
    assert a == b
