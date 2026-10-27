"""Onde o Zé guarda tudo: três raízes no padrão XDG, decididas só aqui (docs/plano-distribuicao.md).

- CONFIG (`~/.config/zervis`): `config.toml`, chaves (0600), conectores MCP;
- DADOS (`~/.local/share/zervis`): memória curta, skills, conversas, Foco, sessões, automações;
- ESTADO (`~/.local/state/zervis`): o momento (status, tempos, consumo, avisos).

`ZERVIS_PERFIL=teste` troca as três de uma vez (`zervis-teste`), para testar uma instalação do
zero ao lado da de sempre. `ZERVIS_RAIZ=<pasta>` põe as três dentro de uma pasta só (testes,
instalação portátil). Os `XDG_*_HOME` do sistema são respeitados.
"""

import os
import re
from pathlib import Path

from zervis import ambiente


def _base(variavel: str, padrao: str) -> Path:
    valor = os.environ.get(variavel, "").strip()
    return Path(valor).expanduser() if valor else Path.home() / padrao


def _nome() -> str:
    perfil = ambiente.ler("PERFIL").strip()
    if perfil and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", perfil):
        raise ValueError(f"ZERVIS_PERFIL inválido: {perfil!r} (minúsculas, números e hífen)")
    return f"zervis-{perfil}" if perfil else "zervis"


def raizes() -> tuple[Path, Path, Path]:
    """(config, dados, estado), lidas do ambiente agora."""
    if raiz := ambiente.ler("RAIZ").strip():
        base = Path(raiz).expanduser()
        return base / "config", base / "dados", base / "estado"
    nome = _nome()
    return (
        _base("XDG_CONFIG_HOME", ".config") / nome,
        _base("XDG_DATA_HOME", ".local/share") / nome,
        _base("XDG_STATE_HOME", ".local/state") / nome,
    )


CONFIG, DADOS, ESTADO = raizes()
PERFIL = ambiente.ler("PERFIL").strip() or "padrão"
