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


def test_o_que_saiu_e_dito_para_nao_juntar_o_velho_e_o_novo(tmp_path: Path) -> None:
    memoria = Memoria(tmp_path, {"usuario": 2000, "jarvis": 2000})
    memoria.aplicar(Mudanca("adicionar", "usuario", texto="Minha fruta preferida é banana."))
    n = SimpleNamespace(memoria=memoria, _memoria_vista=None)
    Nucleo._com_memoria(n, "oi")  # type: ignore[arg-type]
    memoria.aplicar(Mudanca("remover", "usuario", antigo="Minha fruta preferida é banana."))
    memoria.aplicar(Mudanca("adicionar", "usuario", texto="Minha fruta preferida é morango."))
    pedido = Nucleo._com_memoria(n, "qual minha fruta?")  # type: ignore[arg-type]
    saiu, _, depois = pedido.partition("### ")
    assert "Saiu da memória" in saiu and "banana" in saiu
    assert "morango" in depois and "banana" not in depois


def test_vale_o_que_o_cerebro_recebeu_ao_conectar(tmp_path: Path) -> None:
    """O cérebro conecta ao subir e tira a foto ali: apagar depois disso, antes do primeiro
    pedido, também precisa chegar (13/10/2026)."""
    memoria = Memoria(tmp_path, {"usuario": 2000, "jarvis": 2000})
    memoria.aplicar(Mudanca("adicionar", "usuario", texto="Minha fruta preferida é morango."))
    n = SimpleNamespace(
        memoria=memoria, _memoria_vista=None, skills=SimpleNamespace(catalogo=lambda: "")
    )
    n._foto_simples = lambda: Nucleo._foto_simples(n)  # type: ignore[arg-type]
    Nucleo._foto_do_cerebro(n)  # type: ignore[arg-type]  # o cérebro conectou ao subir
    memoria.aplicar(Mudanca("remover", "usuario", antigo="Minha fruta preferida é morango."))
    pedido = Nucleo._com_memoria(n, "qual minha fruta?")  # type: ignore[arg-type]
    assert "Saiu da memória" in pedido and "morango" in pedido.split("###")[0]
