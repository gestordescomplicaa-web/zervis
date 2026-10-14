"""A memória que muda no meio da conversa chega ao cérebro no próximo pedido (auditoria 3)."""

from pathlib import Path
from types import SimpleNamespace

from jarvis.memoria.curta import Memoria, Mudanca
from jarvis.nucleo.laco import Nucleo


def test_mudou_no_meio_vai_junto_e_depois_nao_repete(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path, {"usuario": 2000, "jarvis": 2000})
    n = SimpleNamespace(memoria=memoria, _memoria_vista=None)
    assert Nucleo._com_memoria(n, "oi") == "oi"  # type: ignore[arg-type]  # começo: a foto basta
    memoria.aplicar(Mudanca("adicionar", "usuario", texto="Prefiro respostas curtas."))
    pedido = Nucleo._com_memoria(n, "o que você sabe sobre mim?")  # type: ignore[arg-type]
    assert "Memória atualizada" in pedido and "Prefiro respostas curtas." in pedido
    assert Nucleo._com_memoria(n, "e agora?") == "e agora?"  # type: ignore[arg-type]


def test_sessao_nova_le_a_foto_sem_repetir(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path, {"usuario": 2000, "jarvis": 2000})
    n = SimpleNamespace(memoria=memoria, _memoria_vista="foto velha")
    n._memoria_vista = None  # o que acontece depois de reiniciar ou trocar o cérebro
    assert Nucleo._com_memoria(n, "oi") == "oi"  # type: ignore[arg-type]
