"""Os serviços podem executar com dependências próprias, sem hardware nem Nucleo."""

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.nucleo.servicos.atendimento import ServicoAtendimento
from jarvis.nucleo.servicos.avisos import ServicoAvisos
from jarvis.nucleo.servicos.cerebro import ServicoCerebro
from jarvis.nucleo.servicos.foco import ServicoFoco
from jarvis.nucleo.servicos.memoria import ServicoMemoria
from jarvis.nucleo.servicos.oficina import ServicoOficina
from jarvis.nucleo.servicos.remoto import ServicoRemoto
from jarvis.nucleo.servicos.voz import ServicoVoz


def test_atendimento_entrega_evento_sem_acesso_ao_nucleo() -> None:
    recebidas: list[tuple[str, str]] = []
    contexto: Any = SimpleNamespace(
        mensagens=SimpleNamespace(receber=lambda n, t: recebidas.append((n, t)))
    )
    ServicoAtendimento(contexto)._evento_da_central(
        {"tipo": "mensagem", "nome": "Ana", "texto": "oi"}
    )
    assert recebidas == [("Ana", "oi")]


@pytest.mark.parametrize(
    "fonte,digitado,permitido", [(None, None, True), (object(), None, False), (None, 1.0, False)]
)
def test_acesso_remoto_preserva_origem_do_pedido(
    fonte: Any, digitado: float | None, permitido: bool
) -> None:
    contexto: Any = SimpleNamespace(_fonte=fonte, _digitado_em=digitado)
    assert ServicoRemoto(contexto)._no_proprio_pc() is permitido


def test_avisos_levam_contexto_sem_criar_outro_nucleo() -> None:
    contexto: Any = SimpleNamespace(avisos_falados=[(time.monotonic(), "Tarefa concluída.")])
    assert "Tarefa concluída." in ServicoAvisos(contexto)._com_avisos("mostre")


def test_oficina_distingue_trabalho_de_manutencao() -> None:
    contexto: Any = SimpleNamespace(
        sessoes=SimpleNamespace(
            trabalhando=lambda: ["a", "b"],
            ler=lambda i: SimpleNamespace(origem="manutencao" if i == "a" else "usuario"),
        )
    )
    assert ServicoOficina(contexto)._outras_trabalhando() == ["b"]


def test_cerebro_descarta_latencia_de_outro_pedido() -> None:
    contexto: Any = SimpleNamespace(_turno_cerebro=(7, "turno"), marca=7)
    servico = ServicoCerebro(contexto)
    assert servico._latencia_do_cerebro(7) == "turno"
    assert servico._latencia_do_cerebro(6) is None


def test_voz_preserva_trava_do_silencioso() -> None:
    contexto: Any = SimpleNamespace(modo_fala="silencioso")
    assert ServicoVoz(contexto).microfone_travado


def test_memoria_monta_foto_com_as_skills() -> None:
    contexto: Any = SimpleNamespace(
        memoria=SimpleNamespace(foto=lambda: "Preferências"),
        skills=SimpleNamespace(catalogo=lambda: "Skills"),
    )
    assert ServicoMemoria(contexto)._foto_simples() == "Preferências\n\nSkills"


def test_foco_sem_sessao_nao_altera_pedido() -> None:
    contexto: Any = SimpleNamespace(sessoes=SimpleNamespace(em_foco=("", 0)))
    assert ServicoFoco(contexto)._com_foco("oi") == "oi"


def test_agendador_entrega_lembrete_com_dependencias_proprias() -> None:
    import queue
    from datetime import datetime

    from jarvis.automacoes.jobs import Job
    from jarvis.nucleo import estados as e
    from jarvis.nucleo.servicos.automacoes import ServicoAutomacoes

    agora = time.time()
    anotadas: list[str] = []
    job = Job("Teste", "em 1m", "lembrete", "Reunião.", datetime.now().isoformat())
    contexto: Any = SimpleNamespace(
        jobs=SimpleNamespace(vencidos=lambda _: [job], registrar=lambda *_: None),
        _rodando=set(),
        _meta={},
        _na_linha=lambda _, t: anotadas.append(t),
        eventos=queue.Queue(),
        eventos_sistema=SimpleNamespace(novos=lambda: []),
        _vigia_em=agora,
        _agenda_em=agora,
    )
    ServicoAutomacoes(contexto)._agendador(agora)
    assert anotadas == ["Reunião."]
    assert contexto.eventos.get_nowait() == e.Aviso("Lembrete: Reunião.")


def test_oficina_recomeca_o_diagnostico_sem_apagar_a_atividade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis import atividade
    from jarvis.nucleo.servicos import oficina

    monkeypatch.setattr(oficina, "ESTADO", tmp_path)
    registro = atividade.Atividade(tmp_path / "atividade.db")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    registro.registrar("falha", "Antes do recomeço")
    servico = ServicoOficina(SimpleNamespace())
    assert servico.marco_do_diagnostico() == 0.0
    antes = time.time()
    assert servico.recomecar_diagnostico() == "Diagnóstico recomeçado."
    assert servico.marco_do_diagnostico() >= int(antes)
    assert (tmp_path / oficina.MARCO_DO_DIAGNOSTICO).stat().st_mode & 0o777 == 0o600
    titulos = [i["titulo"] for i in registro.listar()]
    assert "Antes do recomeço" in titulos and "Diagnóstico recomeçado" in titulos
