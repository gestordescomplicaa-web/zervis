"""Nenhum módulo acima de 800 linhas (plano de maturidade, Frente 5).

Os que ainda passam disso estão na lista com o tamanho de hoje: não podem crescer, e quem os
dividir abaixa o número aqui (ou tira da lista). Módulo novo nasce abaixo do limite.
"""

from pathlib import Path

LIMITE = 800
RAIZ = Path(__file__).resolve().parents[1] / "zervis"
# Os que falta dividir, com o teto de hoje (09/11/2026).
GRANDES = {
    "oficina/sessoes.py": 2222,  # com o custo das tarefas (#135)
}


def test_nenhum_modulo_passa_do_limite_e_os_grandes_nao_crescem() -> None:
    acima = {}
    for arquivo in RAIZ.rglob("*.py"):
        nome = arquivo.relative_to(RAIZ).as_posix()
        linhas = len(arquivo.read_text().splitlines())
        if linhas > GRANDES.get(nome, LIMITE):
            acima[nome] = linhas
    assert not acima, f"acima do limite ({LIMITE} linhas, ou o teto em GRANDES): {acima}"


def test_a_lista_dos_grandes_so_tem_quem_ainda_e_grande() -> None:
    """Dividiu? Tira da lista, para o teto não ficar folgado."""
    folgados = [
        nome
        for nome in GRANDES
        if not (RAIZ / nome).is_file() or len((RAIZ / nome).read_text().splitlines()) <= LIMITE
    ]
    assert not folgados, f"já estão abaixo de {LIMITE} linhas; tire de GRANDES: {folgados}"
