"""A pergunta do Claude Code antes de retomar uma conversa longa parada (06/11/2026).

Retomar gasta uma parte do limite de 5 horas da pessoa, e o Enter de um pedido colado pelo Zé
escolheria "retomar" por ela. O Zé reconhece a tela, avisa e não cola nada até a resposta.
"""

from pathlib import Path

import pytest

from zervis.oficina.sessoes import (
    ESPERA_RETOMAR,
    RETOMAR_CONVERSA,
    SessaoErro,
    Sessoes,
)
from zervis.oficina.terminal import Colagem

# A tela de verdade (Claude Code 2.1.319), partida em dois quadros no meio da pergunta.
TELA = (
    b"\r\x1b[2C\x1b[1B\x1b[1mResume this conver",
    b"sation?\x1b[29G\x1b[22m\x1b[39m\x1b[K\r\x1b[2B \x1b[3GThis conversation has been inactive"
    b"\x1b[39Gfor\x1b[43G2h\x1b[46G53m\x1b[50Gand\x1b[54Gis\x1b[57G537.8k\x1b[64Gtokens\x1b[71Glong."
    b"\x1b[77GResuming\x1b[86Git\x1b[89Gwill\x1b[94Guse\x1b[98Gabout\x1b[104G\x1b[1m10%"
    b"\x1b[108G\x1b[22mof\x1b[111Gyour\r\x1b[2C\x1b[1B5-hour\x1b[10Gusage\x1b[16Glimit.\r\n"
    b"  \x1b[38;2;177;185;249m\xe2\x9d\xaf\x1b[5G\x1b[38;2;153;153;153m1. \x1b[38;2;177;185;249m"
    b"Resume\r\n    \x1b[38;2;153;153;153m2. \x1b[39mStart a new conversation\r\n"
    b"\x1b[3mEnter to confirm \xc2\xb7 Esc to resume\x1b[23m",
)


class TerminalFalsoRetomar(Colagem):
    pid = 1

    def __init__(self) -> None:
        self.escrito: list[bytes] = []

    @property
    def fim(self) -> int:
        return 0

    @property
    def vivo(self) -> bool:
        return True

    def escrever(self, dados: bytes) -> None:
        self.escrito.append(dados)


def _sessao(tmp_path: Path) -> tuple[Sessoes, str, TerminalFalsoRetomar, list[str]]:
    raiz = tmp_path / "projetos"
    (raiz / "loja").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,))
    s = sessoes.criar("Loja", str(raiz / "loja"), "claude")
    terminal = TerminalFalsoRetomar()
    sessoes.terminais[s.id] = terminal  # type: ignore[assignment]
    avisos: list[str] = []
    sessoes.ao_avisar = lambda sessao, mensagem: avisos.append(mensagem)
    return sessoes, s.id, terminal, avisos


def test_a_pergunta_vira_um_aviso_so(tmp_path: Path) -> None:
    sessoes, id_, _, avisos = _sessao(tmp_path)
    for quadro in TELA:
        sessoes._olhar_saida(id_, quadro)
    for quadro in TELA:  # o Claude redesenha a tela: o mesmo aviso não se repete
        sessoes._olhar_saida(id_, quadro)
    assert avisos == [RETOMAR_CONVERSA]
    assert id_ in sessoes.retomada_pendente


def test_pedido_nao_e_colado_por_cima_da_pergunta(tmp_path: Path) -> None:
    sessoes, id_, terminal, _ = _sessao(tmp_path)
    for quadro in TELA:
        sessoes._olhar_saida(id_, quadro)
    with pytest.raises(SessaoErro, match="retomar a conversa ou começar outra"):
        sessoes.enviar(id_, "rode os testes")
    assert terminal.escrito == []  # nem o texto nem o Enter
    s = sessoes.ler(id_)
    assert s.estado != "trabalhando" and s.ultimo_pedido != "rode os testes"
    assert ESPERA_RETOMAR.endswith("Responda no terminal da sessão.")


def test_a_resposta_no_terminal_libera_os_pedidos(tmp_path: Path) -> None:
    sessoes, id_, terminal, _ = _sessao(tmp_path)
    for quadro in TELA:
        sessoes._olhar_saida(id_, quadro)
    sessoes.escrever_terminal(id_, b"2")  # a pessoa escolheu no painel
    sessoes.enviar(id_, "rode os testes")
    assert b"rode os testes" in b"".join(terminal.escrito)


def test_a_conversa_que_andou_tambem_libera(tmp_path: Path) -> None:
    sessoes, id_, _, avisos = _sessao(tmp_path)
    for quadro in TELA:
        sessoes._olhar_saida(id_, quadro)
    sessoes._evento(id_, {"hook_event_name": "UserPromptSubmit", "prompt": "oi"})
    assert id_ not in sessoes.retomada_pendente
    for quadro in TELA:  # perguntou de novo mais tarde: novo aviso
        sessoes._olhar_saida(id_, quadro)
    assert avisos == [RETOMAR_CONVERSA, RETOMAR_CONVERSA]
