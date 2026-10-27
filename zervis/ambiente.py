"""As variáveis de ambiente do Zé: `ZERVIS_<NOME>`, com `JARVIS_<NOME>` ainda aceito.

O projeto se chamava JARVIS até 08/10/2026, e as instalações feitas antes de 20/10/2026 têm
`JARVIS_PAINEL_PORTA` na unidade do systemd e `JARVIS_PERFIL` ou `JARVIS_RAIZ` nos scripts de
quem testa. O nome novo vale primeiro; o antigo, quando o novo não existe.
"""

import os

PREFIXO, LEGADO = "ZERVIS_", "JARVIS_"


def nome(variavel: str) -> str:
    """O nome oficial: `PAINEL_PORTA` → `ZERVIS_PAINEL_PORTA`."""
    return PREFIXO + variavel


def ler(variavel: str, padrao: str = "") -> str:
    for completo in (PREFIXO + variavel, LEGADO + variavel):
        if (valor := os.environ.get(completo)) is not None:
            return valor
    return padrao


def nomes(*variaveis: str) -> tuple[str, ...]:
    """Os dois nomes de cada variável (para repassar a um processo filho)."""
    return tuple(p + v for v in variaveis for p in (PREFIXO, LEGADO))
