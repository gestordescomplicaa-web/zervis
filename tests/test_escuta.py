"""Recorte do pedido e leitura da saída do Voxtype."""

import numpy as np

from jarvis.voz.escuta import Segmentador

Q = b"\x00" * 2560


def _alimentar(s: Segmentador, padrao: str) -> list[bytes]:
    """'v' = quadro com voz, '.' = silêncio. Devolve os trechos fechados."""
    saidas = []
    for i, c in enumerate(padrao):
        trecho = s.quadro(bytes([i % 256]) * 2560, c == "v")
        if trecho is not None:
            saidas.append(trecho)
    return saidas


def test_fecha_depois_de_tres_segundos_de_silencio_com_o_preambulo() -> None:
    s = Segmentador()
    assert _alimentar(s, "......" + "vvvv" + "." * 37) == []  # 2,96 s: ainda pensando
    trechos = _alimentar(s, ".")
    assert len(trechos) == 1
    # 5 quadros antes da voz + 4 de voz + 38 de silêncio
    assert len(trechos[0]) == (5 + 4 + 38) * 2560
    assert trechos[0][:1] == bytes([1])  # o primeiro quadro guardado é o 2º de silêncio
    assert not s.em_fala


def test_pausa_curta_no_meio_nao_corta_o_pedido() -> None:
    trechos = _alimentar(Segmentador(), "vvv" + "." * 35 + "vvv" + "." * 38)
    assert len(trechos) == 1


def test_estalo_de_um_quadro_e_descartado() -> None:
    s = Segmentador()
    assert _alimentar(s, "v" + "." * 38) == []
    assert not s.em_fala


def test_teto_de_sessenta_segundos() -> None:
    trechos = _alimentar(Segmentador(maximo_quadros=10), "v" * 12)
    assert len(trechos) == 1
    assert len(trechos[0]) == 10 * 2560


class VadFalso:
    def __init__(self, voz: set[int]) -> None:
        self.voz, self.i = voz, 0

    def prever(self, pedaco: np.ndarray, tamanho: int = 480) -> float:
        nota = 1.0 if self.i in self.voz else 0.0
        self.i += 1
        return nota


def test_fim_de_turno_fecha_na_primeira_pausa_quando_o_modelo_tem_certeza() -> None:
    consultas: list[int] = []

    def modelo(pcm: bytes) -> float:
        consultas.append(len(pcm) // 2560)
        return 0.9

    s = Segmentador(fim_de_turno=modelo)
    assert _alimentar(s, "vvvv" + ".......") == []  # 0,56 s: ainda pode ser uma respiração
    trechos = _alimentar(s, ".")
    assert len(trechos) == 1
    assert consultas == [12]  # 4 de voz + 8 de pausa: fechou em 0,64 s, não em 3 s
    assert len(trechos[0]) == 12 * 2560
    assert s.fechou_pelo_modelo


def test_fim_de_turno_incerto_espera_o_silencio_fixo() -> None:
    s = Segmentador(fim_de_turno=lambda pcm: 0.5)
    trechos = _alimentar(s, "vvvv" + "." * 38)
    assert len(trechos) == 1
    assert len(trechos[0]) == (4 + 38) * 2560
    assert not s.fechou_pelo_modelo
    assert s.notas_do_ultimo == (0.5,)


def test_fim_de_turno_consulta_uma_vez_por_pausa() -> None:
    """Pausa longa para pensar não dá ao modelo várias chances de cortar o usuário."""
    consultas: list[int] = []

    def modelo(pcm: bytes) -> float:
        consultas.append(len(pcm) // 2560)
        return 0.3

    s = Segmentador(fim_de_turno=modelo)
    trechos = _alimentar(s, "vvvv" + "." * 30 + "vvvv" + "." * 38)
    assert len(trechos) == 1
    assert consultas == [12, 46]  # uma na pausa do meio, outra na do fim
    assert s.notas_do_ultimo == (0.3, 0.3)


def test_nota_abaixo_do_limiar_nao_fecha() -> None:
    s = Segmentador(fim_de_turno=lambda pcm: 0.65)  # fechava com o limiar antigo de 0,6
    assert _alimentar(s, "vvvv" + "." * 8) == []
