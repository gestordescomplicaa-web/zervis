"""Quanto cada tarefa de uma sessão gastou (plano de maturidade, Frente 3): lido da conversa do
próprio agente e registrado na Atividade."""

import json
from pathlib import Path
from typing import Any

import pytest

from zervis import atividade
from zervis.oficina import custo
from zervis.oficina.sessoes import Sessoes


def _jsonl(arquivo: Path, linhas: list[dict[str, Any]]) -> Path:
    arquivo.write_text("".join(json.dumps(d) + "\n" for d in linhas))
    return arquivo


def _resposta(id_: str, entrada: int, lido: int, criado: int, saida: int) -> dict[str, Any]:
    uso = {
        "input_tokens": entrada,
        "cache_read_input_tokens": lido,
        "cache_creation_input_tokens": criado,
        "output_tokens": saida,
    }
    return {"type": "assistant", "message": {"id": id_, "model": "claude-x", "usage": uso}}


def _pedido(texto: str) -> dict[str, Any]:
    return {"type": "user", "message": {"role": "user", "content": texto}}


FERRAMENTA = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def test_claude_soma_o_turno_desde_o_ultimo_pedido_sem_repetir_a_resposta(
    tmp_path: Path,
) -> None:
    conversa = _jsonl(
        tmp_path / "c.jsonl",
        [
            _pedido("liste as frutas"),
            _resposta("m0", 9, 9000, 900, 90),  # o turno anterior não conta
            _pedido("agora rode os testes"),
            _resposta("m1", 2, 1000, 500, 10),
            _resposta("m1", 2, 1000, 500, 10),  # o mesmo id, outro bloco: conta uma vez
            FERRAMENTA,  # o resultado de uma ferramenta não é um pedido novo
            _resposta("m2", 3, 2000, 0, 40),
        ],
    )
    gasto = custo.do_turno(conversa, "claude")
    assert gasto == {
        "entrada": 5,
        "cache_lido": 3000,
        "cache_criado": 500,
        "saida": 50,
        "modelo": "claude-x",
    }
    assert custo.total(gasto) == 3555


def _total(entrada: int, lido: int, saida: int) -> dict[str, Any]:
    info = {
        "total_token_usage": {
            "input_tokens": entrada,
            "cached_input_tokens": lido,
            "output_tokens": saida,
        }
    }
    return {"type": "event_msg", "payload": {"type": "token_count", "info": info}}


def _mensagem(texto: str) -> dict[str, Any]:
    return {"type": "event_msg", "payload": {"type": "user_message", "message": texto}}


def test_codex_e_o_total_no_fim_menos_o_total_antes_do_pedido(tmp_path: Path) -> None:
    conversa = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "turn_context", "payload": {"model": "gpt-x"}},
            _mensagem("liste as frutas"),
            _total(1000, 800, 50),
            _mensagem("agora o bacuri"),
            _total(1500, 1200, 70),
            _total(3000, 2500, 120),
        ],
    )
    assert custo.do_turno(conversa, "codex") == {
        "entrada": 300,  # (3000 - 2500) - (1000 - 800)
        "cache_lido": 1700,
        "cache_criado": 0,
        "saida": 70,
        "modelo": "gpt-x",
    }


def test_sem_o_pedido_na_parte_lida_nao_inventa_o_gasto(tmp_path: Path) -> None:
    """Somar a conversa inteira como se fosse o turno seria pior do que não mostrar nada."""
    sem_pedido = _jsonl(tmp_path / "rollout.jsonl", [_total(3000, 2500, 120)])
    assert custo.do_turno(sem_pedido, "codex") is None
    assert (
        custo.do_turno(_jsonl(tmp_path / "c.jsonl", [_resposta("m", 1, 1, 1, 1)]), "claude") is None
    )
    assert custo.do_turno(tmp_path / "nao-existe.jsonl", "claude") is None
    assert custo.do_turno(None, "claude") is None


def test_o_fim_da_tarefa_vai_para_a_atividade_com_o_gasto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registro = atividade.Atividade(tmp_path / "atividade.db")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    projeto = tmp_path / "casa" / "projetos" / "loja"
    projeto.mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), lambda *_: None)
    s = sessoes.criar("Loja", str(projeto), "claude")
    conversa = _jsonl(
        tmp_path / "c.jsonl", [_pedido("rode os testes"), _resposta("m1", 4, 80000, 700, 250)]
    )
    eventos = [
        {"hook_event_name": "UserPromptSubmit", "prompt": "rode os testes"},
        {
            "hook_event_name": "Stop",
            "last_assistant_message": "Testes verdes.",
            "transcript_path": str(conversa),
        },
    ]
    sessoes.eventos(s.id).write_text("".join(json.dumps(e) + "\n" for e in eventos))
    sessoes._ler_eventos(s.id)
    (item,) = [i for i in registro.listar() if i["titulo"] == "Sessão Loja: tarefa terminada"]
    assert item["origem"] == "sessao" and item["entrada"] == "rode os testes"
    assert item["consumo"] == 80954
    assert item["consumo_partes"] == "claude-x · lido do cache 80,0 mil · novo 704 · escrito 250"
