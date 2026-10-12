"""O modo de fala: quando o Zé fala sozinho (ADR 0018)."""

from pathlib import Path

import pytest

from jarvis.avisos import modo
from jarvis.nucleo.estados import comando


@pytest.mark.parametrize(
    ("m", "tipo", "vendo", "fala"),
    [
        ("silencioso", "urgente", False, False),
        ("silencioso", "notificacao", False, False),
        ("avisos", "notificacao", False, True),
        ("avisos", "urgente", False, True),
        ("avisos", "resposta", False, False),  # a resposta, só se a pessoa pedir
        ("maos_livres", "resposta", False, True),
        ("maos_livres", "urgente", True, False),  # já está na tela
        ("avisos", "notificacao", True, False),
    ],
)
def test_quem_fala_em_cada_modo(m: str, tipo: modo.Tipo, vendo: bool, fala: bool) -> None:
    assert modo.falar(m, tipo, vendo) is fala


def test_ler_e_gravar(tmp_path: Path) -> None:
    arquivo = tmp_path / "fala.json"
    assert modo.ler(arquivo) == "avisos"  # padrão de quem instala do zero
    modo.gravar("maos_livres", arquivo)
    assert modo.ler(arquivo) == "maos_livres"
    arquivo.write_text('{"modo": "gritando"}')
    assert modo.ler(arquivo) == "avisos"
    with pytest.raises(ValueError):
        modo.gravar("gritando", arquivo)


def test_resposta_pronta_para_ouvir() -> None:
    texto = (
        "## Feito\n"
        "Corrigi o login em `src/auth/login.ts` e rodei os testes:\n"
        "```bash\nnpm test\n```\n"
        "- **12 passaram**\n"
        "Veja [o relatório](https://exemplo.com/r) em /home/ana/projeto/relatorio.html"
    )
    ouvir = modo.para_ouvir(texto)
    assert "src/auth" not in ouvir and "npm test" not in ouvir and "https" not in ouvir
    assert "/home/ana" not in ouvir and "**" not in ouvir and "#" not in ouvir
    assert "Corrigi o login em login.ts" in ouvir and "12 passaram" in ouvir
    assert "o relatório em relatorio.html" in ouvir


def test_resposta_longa_fica_nas_primeiras_frases() -> None:
    texto = " ".join(f"Frase número {i} com algum conteúdo." for i in range(40))
    ouvir = modo.para_ouvir(texto, limite=120)
    assert len(ouvir) <= 120 and ouvir.endswith(".")


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("Zé, modo silencioso", "modo_silencioso"),
        ("Ei Zé, modo mãos livres", "modo_maos_livres"),
        ("modo avisos", "modo_avisos"),
    ],
)
def test_trocar_o_modo_por_voz(fala: str, nome: str) -> None:
    assert comando(fala) == nome


class _Nucleo:
    """O mínimo do núcleo que o fim de sessão usa."""

    def __init__(self, m: str, vendo: bool = False) -> None:
        self.modo_fala, self._vendo_agora = m, vendo
        self.ditos: list[tuple[str, str]] = []

    def vendo(self, id_: str) -> bool:
        return self._vendo_agora

    def _ultima_resposta(self, id_: str) -> str:
        return "Corrigi o login em `src/a.ts`. Os testes passaram."

    def _aviso_da_oficina(self, texto: str, tipo: str, id_: str = "") -> None:
        self.ditos.append((tipo, texto))


def _fim(m: str, estado: str = "parada", resumo: str = "ok") -> list[tuple[str, str]]:
    from jarvis.nucleo.laco import Nucleo
    from jarvis.oficina.sessoes import Sessao

    n = _Nucleo(m)
    s = Sessao("s1", "Loja", "~/projetos/loja", "claude", estado=estado)
    Nucleo._sessao_terminou(n, s, resumo)  # type: ignore[arg-type]
    return n.ditos


def test_fim_de_sessao_em_avisos_e_uma_frase() -> None:
    assert _fim("avisos") == [("notificacao", "A sessão Loja terminou.")]


def test_fim_de_sessao_em_maos_livres_leva_a_resposta_para_ouvir() -> None:
    [(tipo, texto)] = _fim("maos_livres")
    assert tipo == "notificacao"
    assert texto == "A sessão Loja terminou. Corrigi o login em a.ts. Os testes passaram."


def test_creditos_esgotados_sao_urgentes() -> None:
    [(tipo, texto)] = _fim("avisos", "erro", "a conta Padrão do Claude bateu o limite")
    assert tipo == "urgente" and texto.startswith("Créditos esgotados na sessão Loja")
