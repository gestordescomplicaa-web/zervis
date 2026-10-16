"""O primeiro acesso a um Zé num servidor, sem túnel SSH: endereço seguro e convite de uso único.

Num servidor não há o "próprio PC" para criar a senha do painel. O instalador chama este módulo
no fim: ele gera um convite (vale uma hora, só enquanto não há senha), liga o acesso de qualquer
lugar (Cloudflare) e reinicia o Zé, que sobe o túnel por causa do convite. Depois espera o
endereço e mostra os dois. Quem abre o endereço com o convite cria a senha; a página Voz pede, em
seguida, o código do autenticador.

    python -m jarvis.portal.primeiro_acesso
"""

import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from jarvis.portal import tunel
from jarvis.portal.senha import Acesso

ESPERA_S = 90.0  # o cloudflared costuma dar o endereço em menos de 10 s


def reiniciar_servico() -> None:
    subprocess.run(
        ["systemctl", "--user", "restart", "zervis"],  # noqa: S607
        check=False,
        timeout=60,
    )


def esperar_endereco(
    registro: Path,
    espera_s: float = ESPERA_S,
    agora: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    fim = agora() + espera_s
    while agora() < fim:
        if endereco := tunel.ultimo_endereco(registro):
            return endereco
        dormir(1.0)
    return ""


def preparar(
    acesso: Acesso,
    reiniciar: Callable[[], None] = reiniciar_servico,
    registro: Path = tunel.REGISTRO,
    escolha: Path = tunel.ESCOLHA,
    espera_s: float = ESPERA_S,
    dormir: Callable[[float], None] = time.sleep,
    tunel_no_ar: Callable[[], bool] | None = None,
) -> list[str]:
    """As linhas para o fim da instalação."""
    if acesso.tem_senha:
        endereco = tunel.ultimo_endereco(registro) if tunel.escolhido(escolha) else ""
        return [
            "O acesso ao painel já foi criado.",
            f"Abra {endereco} e entre com a senha." if endereco else _tunel_ssh(),
        ]
    convite = acesso.criar_convite()
    tunel.escolher(True, escolha)
    registro.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    no_ar = tunel_no_ar() if tunel_no_ar is not None else tunel.lancador_padrao().ativo()
    if not no_ar:
        registro.write_bytes(b"")  # um endereço antigo anotado não vale: o Zé sobe um novo
    reiniciar()
    endereco = esperar_endereco(registro, espera_s, dormir=dormir)
    if not endereco:
        return [
            "O endereço seguro não respondeu. Acesse pelo túnel SSH e use o código abaixo.",
            _tunel_ssh(),
            f"Código de primeiro acesso: {convite} (vale 1 hora)",
        ]
    return [
        f"Abra no navegador: {endereco}",
        f"Código de primeiro acesso: {convite} (vale 1 hora)",
        "Crie a senha e, em seguida, ligue o código do autenticador na página Voz.",
    ]


def _tunel_ssh() -> str:
    return "Do seu computador: ssh -N -L 8795:127.0.0.1:8795 <usuário>@<servidor> e abra http://localhost:8795"


def main() -> int:
    for linha in preparar(Acesso()):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
