"""O Zé dentro da imagem Docker (ADR 0096): a entrada do contêiner e o que muda nele.

No servidor de sempre (`deploy/instalar-servidor.sh`) o systemd do usuário cuida do serviço, do
túnel e da atualização. No contêiner não há systemd: o `tini` é o processo 1 (recolhe os zumbis
das sessões), esta entrada vira o Zé, e o Docker reinicia o contêiner quando o Zé cai. O que mora
no volume (modelos de som, Codex, ai-memory) o próprio Zé baixa ao subir, como em qualquer
máquina. A atualização é pela imagem, não pelo git.

    python -m zervis.conteiner   # a entrada da imagem (ENTRYPOINT)
"""

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from zervis import ambiente

if TYPE_CHECKING:
    from zervis.portal.senha import Acesso

log = logging.getLogger(__name__)
# A imagem é construída do repositório (docs/vps.md, "Pelo Docker"): atualizar é trazer o
# código novo e construir de novo. Os dados ficam no volume.
ATUALIZAR = "git pull && docker compose up -d --build"
LOGS = "docker compose logs -f"
TEXTO_ATUALIZAR = (
    "Neste contêiner, o Zé se atualiza pela imagem, não pelo painel. No servidor, na pasta do "
    f"Zé: {ATUALIZAR}"
)


def em_conteiner() -> bool:
    """A imagem do Zé declara `ZERVIS_CONTEINER=1` (o Dockerfile): sem adivinhar pelo cgroup."""
    return ambiente.ler("CONTEINER") == "1"


def primeiro_acesso_pelo_tunel(acesso: "Acesso | None" = None, escolha: Path | None = None) -> bool:
    """Sem senha ainda, o endereço seguro (Cloudflare) sobe com o Zé. Ao subir, ele só abre o
    túnel com a senha ou com um convite válido (`nucleo/ciclo.py`); no servidor de sempre, o
    `primeiro_acesso` cria o convite e reinicia o serviço pelo systemctl, que aqui não existe.
    Então a entrada cria um convite antes de virar o Zé, e o `primeiro_acesso`, rodado depois
    por `docker compose exec`, troca por um convite novo (que ele mostra) e espera o endereço."""
    from zervis.portal import tunel
    from zervis.portal.senha import Acesso

    acesso = acesso or Acesso()
    if acesso.tem_senha:
        return False
    tunel.escolher(True, escolha or tunel.ESCOLHA)
    acesso.criar_convite()  # este ninguém vê: só abre o túnel na subida
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if primeiro_acesso_pelo_tunel():
        log.info("contêiner: sem senha ainda, o endereço seguro sobe com o Zé")
    os.execv(sys.executable, [sys.executable, "-m", "zervis"])  # noqa: S606 (o próprio Zé)
    return 0  # pragma: no cover (o execv não volta)


if __name__ == "__main__":
    sys.exit(main())
