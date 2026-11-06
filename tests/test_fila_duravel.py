"""A fila durável das automações (ADR 0069): matar o Zé no meio de uma automação não a perde.

O aceite da Frente 1 do plano de maturidade. O "Zé" que cai é um processo de verdade, morto com
SIGKILL depois de marcar a execução como rodando, sem chance de arrumar nada.
"""

import json
import os
import queue
import signal
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import GUARDADAS, Execucao, Jobs
from zervis.avisos.fila import Fila
from zervis.nucleo.servicos.automacoes import ServicoAutomacoes

AGORA = datetime(2099, 1, 2, 16, 0, tzinfo=FUSO)


def _vencida(jobs: Jobs, tipo: str, texto: str, agenda: str = "em 1m") -> str:
    return jobs.criar(f"Teste {tipo}", agenda, tipo, texto, AGORA - timedelta(minutes=2)).id


def test_vencer_grava_a_execucao_e_avanca_a_agenda_juntas(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    unica = _vencida(jobs, "lembrete", "Reunião.")
    repete = _vencida(jobs, "pergunta", "Como está o dólar?", "a cada 1m")
    novas = jobs.disparar(AGORA)
    assert sorted(x.job for x in novas) == sorted([unica, repete])
    por_id = {j.id: j for j in jobs.listar()}
    assert por_id[unica].proxima == "" and not por_id[unica].ativo  # de uma vez só
    assert por_id[repete].proxima == (AGORA + timedelta(minutes=1)).isoformat()
    # Ainda aberta, a automação que repete não acumula outra execução.
    assert jobs.disparar(AGORA + timedelta(minutes=5)) == []
    assert len(jobs.pendentes()) == 2


def test_concluir_registra_o_resultado_na_automacao(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    id_ = _vencida(jobs, "pergunta", "Como está o dólar?")
    (x,) = jobs.disparar(AGORA)
    assert jobs.iniciar(x.id, AGORA).tentativas == 1
    feita = jobs.concluir(x.id, "erro", AGORA, "TimeoutError")
    assert feita.estado == "falhou" and feita.erro == "TimeoutError"
    job = jobs.listar()[0]
    assert job.id == id_ and job.ultimo_status == "erro" and job.ultimo_erro == "TimeoutError"


def test_historico_tem_limite(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    _vencida(jobs, "lembrete", "Água.", "a cada 1m")
    momento = AGORA
    for _ in range(GUARDADAS + 5):
        (x,) = jobs.disparar(momento)
        jobs.concluir(x.id, "ok", momento)
        momento += timedelta(minutes=1)
    assert len(jobs.execucoes()) == GUARDADAS


def test_ao_subir_cada_tipo_tem_seu_destino(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    _vencida(jobs, "lembrete", "Reunião.")
    _vencida(jobs, "pergunta", "Como está o dólar?")
    _vencida(jobs, "ligacao", json.dumps({"t": "5581999990040", "n": "Marta", "r": "Oi."}))
    _vencida(jobs, "pergunta", "Vai chover?", "em 2m")
    execucoes = {x.texto: x for x in jobs.disparar(AGORA)}
    for x in execucoes.values():
        jobs.iniciar(x.id, AGORA)
    jobs.iniciar(execucoes["Vai chover?"].id, AGORA)  # já na segunda tentativa
    interrompidas = jobs.retomar_ao_subir(AGORA)
    estados = {x.texto: x.estado for x in jobs.execucoes()}
    assert estados["Reunião."] == "pendente"  # repetir um lembrete é melhor que perdê-lo
    assert estados["Como está o dólar?"] == "pendente"  # só lê: roda de novo
    assert estados["Vai chover?"] == "interrompida"  # esgotou as tentativas
    ligacao = next(t for t in estados if t.startswith("{"))
    assert estados[ligacao] == "interrompida"  # pode ter ligado: não liga de novo sozinho
    assert sorted(x.tipo for x in interrompidas) == ["ligacao", "pergunta"]
    assert jobs.retomar_ao_subir(AGORA) == []  # só uma vez


ZE_QUE_CAI = textwrap.dedent(
    """
    import sys, time
    from datetime import datetime, timedelta
    from pathlib import Path
    from zervis.automacoes.agenda import FUSO
    from zervis.automacoes.jobs import Jobs
    jobs = Jobs(Path(sys.argv[1]))
    agora = datetime.now(FUSO)
    antes = agora - timedelta(minutes=2)
    jobs.criar("Dólar", "em 1m", "pergunta", "Como está o dólar?", antes)
    jobs.criar("Marta", "em 1m", "ligacao", '{"t": "5581999990040", "n": "Marta", "r": "Oi."}',
               antes)
    for x in jobs.disparar(agora):
        jobs.iniciar(x.id, agora)
    print("rodando", flush=True)
    time.sleep(60)
    """
)


def _contexto(jobs: Jobs, fila: Fila, perguntas: list[Execucao]) -> Any:
    agora = 1e18  # os vigias e a procura de versão acabaram de rodar: só as automações

    async def rodar_pergunta(x: Execucao) -> None:
        perguntas.append(x)
        contexto.jobs.concluir(x.id, "ok", datetime.now(FUSO))
        contexto._rodando.discard(x.id)

    laco = __import__("asyncio").new_event_loop()
    threading.Thread(target=laco.run_forever, daemon=True).start()
    contexto: Any = SimpleNamespace(
        jobs=jobs,
        fila=fila,
        _rodando=set(),
        _meta={},
        _na_linha=lambda *_: None,
        _rodar_pergunta=rodar_pergunta,
        ponte=SimpleNamespace(laco=laco),
        eventos=queue.Queue(),
        eventos_sistema=SimpleNamespace(novos=lambda: []),
        _vigia_em=agora,
        _agenda_em=agora,
        _n8n_em=agora,
        _n8n_conferindo=threading.Event(),
        _versoes_em=agora,
        _versoes_procurando=threading.Event(),
        versoes=SimpleNamespace(resultado_novo=lambda: None),
    )
    return contexto


def test_matar_o_ze_no_meio_de_uma_automacao_nao_a_perde(tmp_path: Path) -> None:
    arquivo = tmp_path / "jobs.json"
    ze = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", ZE_QUE_CAI, str(arquivo)], stdout=subprocess.PIPE, text=True
    )
    assert ze.stdout is not None and ze.stdout.readline().strip() == "rodando"
    os.kill(ze.pid, signal.SIGKILL)
    ze.wait(5)

    jobs = Jobs(arquivo)
    fila = Fila(tmp_path / "avisos.json")
    perguntas: list[Execucao] = []
    servico = ServicoAutomacoes(_contexto(jobs, fila, perguntas))
    servico.retomar_execucoes()  # o Zé novo sobe
    # A ligação não é refeita sozinha: vira aviso, guardado na fila durável.
    avisos = [a.texto for a in fila.validos()]
    assert len(avisos) == 1 and "ligação agendada Marta foi interrompida" in avisos[0]
    # A pergunta roda de novo, uma vez, e termina.
    servico._agendador(time.time())
    fim = time.monotonic() + 3
    while not perguntas and time.monotonic() < fim:
        time.sleep(0.01)
    assert [x.texto for x in perguntas] == ["Como está o dólar?"]
    assert perguntas[0].tentativas == 2
    estados = sorted((x.tipo, x.estado) for x in jobs.execucoes())
    assert estados == [("ligacao", "interrompida"), ("pergunta", "concluida")]


def test_ligacao_que_nao_saiu_fica_como_erro(tmp_path: Path) -> None:
    """Antes, a ligação agendada era marcada "ok" antes de discar."""
    jobs = Jobs(tmp_path / "jobs.json")
    _vencida(jobs, "ligacao", json.dumps({"t": "5581999990040", "n": "Marta", "r": "Oi."}))
    contexto = _contexto(jobs, Fila(tmp_path / "avisos.json"), [])

    def nao_liga(*_: str) -> str:
        raise RuntimeError("WhatsApp desconectado")

    contexto.fazer_ligacao = nao_liga
    ServicoAutomacoes(contexto)._agendador(AGORA.timestamp())
    fim = time.monotonic() + 3
    while jobs.listar()[0].ultimo_status == "nunca" and time.monotonic() < fim:
        time.sleep(0.01)
    assert jobs.listar()[0].ultimo_status == "erro"
    assert [x.estado for x in jobs.execucoes()] == ["falhou"]
