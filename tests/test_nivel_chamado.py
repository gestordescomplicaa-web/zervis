"""O volume mínimo do "Ei Zé" calibrado pela voz de quem usa (13/11/2026: o som do vídeo no
fone disparava o chamado; 30 de 40 ativações abaixo de -30 dBFS não viraram pedido)."""

from pathlib import Path

from zervis.voz import live
from zervis.voz.nivel_chamado import MINIMO_DE_AMOSTRAS, NivelDoChamado


def test_sem_amostras_vale_o_piso(tmp_path: Path) -> None:
    assert NivelDoChamado(tmp_path / "n.json").minimo(-45.0) == -45.0


def test_com_dez_chamados_o_minimo_sobe_para_perto_da_voz(tmp_path: Path) -> None:
    n = NivelDoChamado(tmp_path / "n.json")
    for i in range(MINIMO_DE_AMOSTRAS):
        n.ativou(-26.0 + (i % 3), agora=float(i))
        n.ouviu("liga a luz da sala", agora=float(i) + 2)
    assert n.minimo(-45.0) == -31.0  # a mediana (-25) menos a margem de 6 dB
    # Reabrir guarda o que aprendeu.
    assert NivelDoChamado(tmp_path / "n.json").minimo(-45.0) == -31.0


def test_so_conta_chamado_que_virou_pedido_com_texto(tmp_path: Path) -> None:
    n = NivelDoChamado(tmp_path / "n.json")
    n.ativou(-40.0, agora=0.0)
    n.ouviu("   ", agora=1.0)  # ninguém falou depois: não conta
    n.ouviu("algo", agora=2.0)  # sem chamado pendente: não conta
    n.ativou(-41.0, agora=10.0)
    n.ouviu("tarde demais", agora=100.0)  # a transcrição não é a do chamado
    assert n.niveis() == []


def test_nunca_desce_do_piso_nem_passa_do_teto(tmp_path: Path) -> None:
    baixo, alto = NivelDoChamado(tmp_path / "b.json"), NivelDoChamado(tmp_path / "a.json")
    for i in range(MINIMO_DE_AMOSTRAS):
        baixo.ativou(-44.0, agora=float(i))
        baixo.ouviu("oi", agora=float(i))
        alto.ativou(-5.0, agora=float(i))
        alto.ouviu("oi", agora=float(i))
    assert baixo.minimo(-45.0) == -45.0
    assert alto.minimo(-45.0) == -25.0


def test_arquivo_estragado_vale_o_piso(tmp_path: Path) -> None:
    (tmp_path / "n.json").write_text("{nao é json")
    assert NivelDoChamado(tmp_path / "n.json").minimo(-45.0) == -45.0


def test_ao_vivo_a_espera_minima_segue_a_escolha_espera() -> None:
    """343 de 969 falas ao vivo fecharam antes da hora com 0,4 s em todas (novembro de 2026)."""
    assert live.tempos_de_fim("rapida") == (0.4, 1.5)
    assert live.tempos_de_fim("normal") == (0.8, 2.0)
    assert live.tempos_de_fim("longa") == (1.2, 3.0)
    assert live.tempos_de_fim("outra") == live.tempos_de_fim("normal")
