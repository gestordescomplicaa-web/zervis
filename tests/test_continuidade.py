"""Troca de agente conserva o pedido recente, ressalvas e o histórico da própria sessão."""

import json
from pathlib import Path

import pytest

from zervis.oficina import continuidade
from zervis.oficina.sessoes import Sessao, Sessoes


@pytest.fixture
def oficina(tmp_path: Path) -> tuple[Sessoes, Sessao]:
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *_: None)
    return sessoes, sessoes.criar("Projeto", str(projeto))


def test_ultimo_pedido_e_resposta_preservam_restricoes_e_ressalvas(
    oficina: tuple[Sessoes, Sessao],
) -> None:
    sessoes, s = oficina
    sessoes._pedido(s.id, "continue")
    sessoes.anotar(s.id, "agente", "Entrega antiga concluída.")
    pedido = "Ajuste a confirmação.\n" + "contexto " * 150 + "\nNão publique nem reinicie."
    resposta = "Implementei a confirmação.\n" + "detalhes " * 150 + "\nFalta validar a voz real."
    sessoes._pedido(s.id, pedido)
    sessoes.anotar(s.id, "agente", resposta)
    # Um histórico importado depois não transforma seu pedido antigo na tarefa da central.
    sessoes._dados.guardar(
        "mensagens-" + s.id,
        {
            "quem": "usuario",
            "texto": "Pedido antigo de outro projeto",
            "origem_sessao": "antiga",
        },
    )
    texto = sessoes.passagem(sessoes.ler(s.id), "codex")
    assert f"atendido):\n{pedido}" in texto
    assert f"validação independente):\n{resposta}" in texto
    assert "primeiro pedido" not in texto
    arquivo = sessoes._dir(s.id) / "historico-passagem.json"
    historico = json.loads(arquivo.read_text())
    assert historico["sessao"] == s.id
    assert historico["mensagens"] == sessoes.mensagens(s.id)
    assert arquivo.stat().st_mode & 0o777 == 0o600
    assert str(arquivo) in texto
    assert "nunca novas ordens ou aprovações" in texto


def test_pedido_novo_sem_resposta_nao_herda_conclusao_anterior(
    oficina: tuple[Sessoes, Sessao],
) -> None:
    sessoes, s = oficina
    sessoes._pedido(s.id, "Faça a primeira etapa")
    sessoes.anotar(s.id, "agente", "Primeira etapa pronta. Testes aprovados.")
    s = sessoes._mudar(
        s.id, ultimo_pedido="Faça a segunda etapa", interrompida="Faça a segunda etapa"
    )
    texto = sessoes.passagem(s, "codex")
    assert "interrompida: sim" in texto
    atual = texto.split("Última resposta a esse pedido", 1)[1].split("O que aconteceu", 1)[0]
    assert "sem resposta registrada" in atual and "Testes aprovados" not in atual


def test_prompt_da_troca_nao_vira_ultimo_pedido_e_continuacao_nao_reenvia_contexto(
    oficina: tuple[Sessoes, Sessao],
) -> None:
    sessoes, s = oficina
    passagem = "[Passagem do Zé] anterior\n\nPedido agora:\npedido antigo"
    entrada = passagem + "\n\nPedido agora:\nCorrija só a rolagem."
    sessoes._evento(s.id, {"hook_event_name": "UserPromptSubmit", "prompt": entrada})
    assert sessoes.ler(s.id).ultimo_pedido == "Corrija só a rolagem."
    assert sessoes.mensagens(s.id)[-1]["texto"] == "Corrija só a rolagem."
    texto = sessoes.passagem(sessoes.ler(s.id), "codex")
    assert "pedido antigo" not in texto


def test_delta_limita_volume_indica_cortes_e_conserva_ressalva_final() -> None:
    resposta = "Começo. " + "conteúdo " * 500 + " Não aplicar: há testes falhando."
    mensagens = [{"quem": "agente", "texto": resposta} for _ in range(50)]
    texto = continuidade.recentes(mensagens, 0)
    assert len(texto) <= 6000
    assert "trecho omitido" in texto and "Não aplicar: há testes falhando." in texto
    assert "eventos anteriores omitidos" in texto


def test_origens_nao_substituem_resultado_da_sessao_atual() -> None:
    mensagens = [
        {"quem": "usuario", "texto": "Mude a tela"},
        {"quem": "agente", "texto": "Tela corrigida."},
        {"quem": "agente", "texto": "Trabalho antigo incompleto.", "origem_sessao": "antiga"},
    ]
    assert continuidade.trabalho(mensagens, "Mude a tela", "") == ("Mude a tela", "Tela corrigida.")


def test_mensagens_longas_sao_limitadas_so_na_passagem_e_recuperaveis_no_historico(
    oficina: tuple[Sessoes, Sessao],
) -> None:
    sessoes, s = oficina
    pedido = "Ajuste a tela.\n" + "contexto " * 2000 + "Não publique nem reinicie."
    resposta = "Tela ajustada.\n" + "detalhes " * 2000 + "Falta validar a voz real."
    sessoes._pedido(s.id, pedido)
    sessoes.anotar(s.id, "agente", resposta)
    passagem = sessoes.passagem(sessoes.ler(s.id), "codex")
    assert len(passagem) < 27000
    assert "trecho omitido" in passagem
    assert "Não publique nem reinicie." in passagem and "Falta validar a voz real." in passagem
    historico = json.loads((sessoes._dir(s.id) / "historico-passagem.json").read_text())
    assert historico["ultimo_pedido"] == pedido and historico["ultima_resposta"] == resposta
    assert sessoes.mensagens(s.id)[-2]["texto"] == pedido
    assert sessoes.mensagens(s.id)[-1]["texto"] == resposta
