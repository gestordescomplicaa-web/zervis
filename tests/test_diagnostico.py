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


def test_pedido_mantem_o_agente_longe_dos_dados_da_pessoa() -> None:
    assert "não leia as pastas de dados do Zé" in diagnostico.PEDIDO
    assert "~/.local/state/zervis" in diagnostico.PEDIDO


def test_traceback_agrupa_pela_excecao_final_e_onde_nasceu() -> None:
    p = "2026-10-13T11:24:19-03:00 pc python[12]: "

    def erro(n: int, msg: str) -> list[str]:
        return [
            f"{p}Traceback (most recent call last):",
            f'{p}  File "/usr/lib/python3/threading.py", line {n}, in run',
            f"{p}    self._target()",
            f'{p}  File "/home/x/jarvis/nucleo/laco.py", line {n + 9}, in _ouvir',
            f"{p}    texto = fila.get()",
            f"{p}{msg}",
        ]

    registro = [
        *erro(10, "KeyError: 'voz'"),
        *erro(20, "KeyError: 'voz'"),
        f"{p}Traceback (most recent call last):",
        f'{p}  File "/a/b/portal/acoes.py", line 3, in f',
        f"{p}ValueError: x",
        f"{p}",
        f"{p}During handling of the above exception, another exception occurred:",
        f"{p}",
        f"{p}Traceback (most recent call last):",
        f'{p}  File "/a/b/portal/acoes.py", line 5, in g',
        f"{p}RuntimeError: quebrou 3 vezes",
        f"{p}INFO jarvis: seguiu",
    ]
    texto = diagnostico.montar([], registro, agora=1.0)
    assert "- Erro não tratado: KeyError: 'voz' (laco.py, _ouvir): 2 vez(es)" in texto
    assert "- Erro não tratado: RuntimeError: quebrou # vezes (acoes.py, g): 1 vez(es)" in texto
    assert "most recent call last" not in texto and "seguiu" not in texto
