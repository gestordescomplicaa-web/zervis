"""Catálogo das ações do Omarchy, gerado dos cabeçalhos `# omarchy:*` (docs/07-sistema-omarchy.md).

Nada escrito à mão: cada `/usr/bin/omarchy-*` traz `summary`, `args`, `examples`, `hidden`; o
catálogo se atualiza sozinho a cada atualização do Omarchy. Cada ação ganha um nível de risco:

0 leitura (estado da máquina)        livre
1 reversível (volume, abrir app...)  executa e diz o que fez
2 efeito durável ou não classificado confirmação falada
3 sistema (reiniciar, desligar)      confirmação com a frase exata ("confirmo reiniciar")
4 proibido                           nunca: reset de fábrica, remoções, qualquer script com sudo

Comando novo que nenhuma regra cobre cai no 2. Ocultos (`hidden=true`) são peças internas do
Omarchy e não entram no catálogo.
"""

import re
from dataclasses import dataclass
from pathlib import Path

PASTA = Path("/usr/bin")
PREFIXO = "omarchy-"
NIVEIS = {0: "leitura", 1: "reversível", 2: "confirmação", 3: "frase exata", 4: "proibido"}

# Regras na ordem: a primeira que casar decide.
REGRAS: list[tuple[int, re.Pattern[str]]] = [
    (
        4,
        re.compile(
            r"factory-reset|(^|-)remove|uninstall|reinstall|^dev-|refresh-|^debug|snapshot-restore"
        ),
    ),
    (3, re.compile(r"^system-(reboot|shutdown|logout|suspend|hibernate)$|^update(-|$)|^restart-")),
    (
        0,
        re.compile(
            r"(-status|-stats|-current|-list|-available|-state|-branch|-channel|-pkgs)$|^version$|"
            r"^agent-usage-(claude|codex)$"
        ),
    ),
    (
        1,
        re.compile(
            r"^menu$|^audio-|^brightness-|^launch-|^toggle-|^notification-|^capture-(screenshot|region|"
            r"text|windows)|^theme-(set|bg-next)$|^hyprland-(focus-app|window-pop)|^reminder$|"
            r"^weather-"
        ),
    ),
]


@dataclass(frozen=True)
class Acao:
    nome: str  # sem o prefixo: "audio-output-volume"
    resumo: str
    argumentos: str
    exemplos: str
    risco: int
    usa_sudo: bool
    caminho: Path  # o script de onde o catálogo foi lido (nunca remontado a partir do nome)


def _cabecalho(texto: str) -> dict[str, str]:
    campos = {}
    for linha in texto.splitlines()[:40]:
        achado = re.match(r"#\s*omarchy:([a-z]+)=(.*)", linha)
        if achado:
            campos[achado[1]] = achado[2].strip()
    return campos


def classificar(nome: str, usa_sudo: bool, forcados: dict[str, int] | None = None) -> int:
    if forcados and nome in forcados:
        return forcados[nome]
    if usa_sudo:
        return 4  # sem terminal, pediria senha e travaria; e sudo por voz é proibido (doc 07)
    for nivel, padrao in REGRAS:
        if padrao.search(nome):
            return nivel
    return 2


def carregar(pasta: Path = PASTA, forcados: dict[str, int] | None = None) -> dict[str, Acao]:
    acoes = {}
    for arquivo in sorted(pasta.glob(f"{PREFIXO}*")):
        try:
            texto = arquivo.read_text(errors="replace")
        except OSError:
            continue
        campos = _cabecalho(texto)
        if "summary" not in campos or campos.get("hidden") == "true":
            continue
        nome = arquivo.name.removeprefix(PREFIXO)
        usa_sudo = bool(re.search(r"(^|[\s;&|(])sudo\s", texto, re.MULTILINE))
        acoes[nome] = Acao(
            nome,
            campos["summary"],
            campos.get("args", ""),
            campos.get("examples", ""),
            classificar(nome, usa_sudo, forcados),
            usa_sudo,
            arquivo,
        )
    return acoes


# As do dia a dia: vão na descrição da ferramenta para o cérebro executar sem buscar antes (uma
# ida a menos ao modelo por ação; teste de 06/10/2026: buscar e executar relia ~14 mil tokens).
COMUNS = [
    "audio-output-volume", "audio-input-mute", "brightness-display", "capture-screenshot",
    "launch-browser", "launch-or-focus", "menu", "theme-list", "theme-set", "theme-current",
    "toggle-nightlight", "toggle-notification-silencing", "system-reboot", "system-shutdown",
]  # fmt: skip


def resumo_comuns(acoes: dict[str, Acao]) -> str:
    linhas = []
    for nome in COMUNS:
        a = acoes.get(nome)
        if a is not None and a.risco < 4:
            args = f" {a.argumentos}" if a.argumentos else ""
            linhas.append(f"{nome}{args}: {a.resumo}")
    return "; ".join(linhas)


def buscar(acoes: dict[str, Acao], termos: str, limite: int = 8) -> list[Acao]:
    palavras = [p for p in re.findall(r"[\w-]+", termos.casefold()) if len(p) > 1]

    def nota(a: Acao) -> int:
        alvo = f"{a.nome} {a.resumo}".casefold()
        return sum(3 if p in a.nome else 1 for p in palavras if p in alvo)

    achadas = sorted((a for a in acoes.values() if a.risco < 4), key=nota, reverse=True)
    return [a for a in achadas if nota(a) > 0][:limite]
