"""O eco pelo texto (ADR 0062): a fala do Zé que volta transcrita não vira pedido; a pessoa
repetindo poucas palavras dele, sim."""

from pathlib import Path
from types import SimpleNamespace

from zervis.nucleo import estados as e
from zervis.voz.eco_texto import JANELA_S, EcoDeTexto


class Relogio:
    t = 100.0

    def __call__(self) -> float:
        return self.t


FALA = "Achei cinco fornecedores de embalagens sustentáveis em São Paulo. O mais perto é a G6."


def test_trecho_longo_da_propria_fala_e_eco() -> None:
    eco = EcoDeTexto(Relogio())
    eco.falou(FALA)
    assert eco.eco("achei cinco fornecedores de embalagens sustentaveis")  # sem acento, sem caixa
    assert eco.eco(
        "Sustentáveis em São Paulo. O mais perto"
    )  # o fim de uma frase e o começo da outra
    assert eco.eco("é... fornecedores de embalagens sustentáveis em São Paulo")  # quase toda


def test_a_pessoa_repetindo_pouco_ou_pedindo_outra_coisa_nao_e_eco() -> None:
    eco = EcoDeTexto(Relogio())
    eco.falou("Quer que eu detalhe os concorrentes da Magazine Luiza?")
    assert not eco.eco("sim, detalha os concorrentes")  # 3 palavras iguais: um pedido
    assert not eco.eco("detalhe os concorrentes, mas só os do Nordeste e com preço")
    assert not eco.eco("manda um oi para a G6 no WhatsApp")
    assert not eco.eco("")


def test_fala_antiga_nao_conta() -> None:
    relogio = Relogio()
    eco = EcoDeTexto(relogio)
    eco.falou(FALA)
    relogio.t += JANELA_S + 1
    assert not eco.eco("achei cinco fornecedores de embalagens sustentáveis")


def test_o_nucleo_descarta_o_eco_e_segue_com_o_pedido(tmp_path: Path) -> None:
    from tests.test_latencia_nucleo import NucleoCronometrado

    n = NucleoCronometrado(tmp_path)
    n._pedidos_ao_vivo = 0
    n.live = SimpleNamespace(  # type: ignore[assignment]
        ativo=True, parar=lambda: None, acompanhar=lambda *a: None, falar=lambda *a: None
    )
    n.eco_texto.falou(FALA)
    n.tratar(e.FalaAoVivo("Achei cinco fornecedores de embalagens sustentáveis em São Paulo"))
    assert n._pedidos_ao_vivo == 0  # a própria fala: nada
    n.tratar(e.FalaAoVivo("Zé, manda um oi para a G6"))
    assert n._pedidos_ao_vivo == 1
