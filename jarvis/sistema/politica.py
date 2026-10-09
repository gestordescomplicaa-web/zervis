"""Executar ações do Omarchy com a política de risco (Fase 5; docs/07-sistema-omarchy.md).

O cérebro chama `sistema_executar(acao, argumentos)`; o `ClaudeBrain` consulta esta política
antes da pergunta falada:
- risco 0 e 1: liberado sem perguntar (o JARVIS diz o que fez);
- risco 2: confirmação falada;
- risco 3: confirmação com a frase exata ("confirmo reiniciar"); "sim" não basta;
- risco 4, ação desconhecida ou argumento estranho: recusado antes de perguntar.

Executa sem shell, com tempo limite e saída cortada; o ambiente gráfico é relido do systemd a cada
vez (o Hyprland reiniciado troca a assinatura, lição de 06/10/2026). Nunca simula teclado.
"""

import re
import subprocess
import unicodedata
from typing import Any

from jarvis.sistema.catalogo import NIVEIS, Acao

FERRAMENTA = "mcp__jarvis__sistema_executar"
VERBOS = {
    "system-reboot": "reiniciar",
    "system-shutdown": "desligar",
    "system-logout": "sair",
    "system-suspend": "suspender",
    "system-hibernate": "hibernar",
}
ARGUMENTO = re.compile(r"[\w .,:%+\-/=@#'\"À-ÿ]{1,200}")
# O navegador abre um endereço (08/10/2026: "pesquisa no navegador" abria a página inicial,
# porque `?` e `&` são recusados acima). Só http(s), sem espaço, aspas nem caracteres de shell;
# executa sem shell de qualquer jeito, então o endereço chega inteiro como um argumento.
ENDERECO = re.compile(r"https?://[\w.-]+(:\d+)?(/[\w\-./%~+=,:@!*()?&#À-ÿ]*)?")
ACEITAM_ENDERECO = {"launch-browser", "launch-webapp"}
VARIAVEIS_GRAFICAS = (
    "WAYLAND_DISPLAY",
    "DISPLAY",
    "HYPRLAND_INSTANCE_SIGNATURE",
    "XDG_RUNTIME_DIR",
)


def _palavras(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", limpo)


def _ambiente() -> dict[str, str]:
    import os

    env = dict(os.environ)
    try:
        saida = subprocess.run(
            ["/usr/bin/systemctl", "--user", "show-environment"],
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return env
    for linha in saida.splitlines():
        chave, _, valor = linha.partition("=")
        if chave in VARIAVEIS_GRAFICAS:
            env[chave] = valor
    return env


class Sistema:
    def __init__(self, acoes: dict[str, Acao], tempo_limite_s: float = 30.0) -> None:
        self.acoes = acoes
        self.tempo_limite_s = tempo_limite_s

    def _alvo(self, entrada: dict[str, Any]) -> tuple[Acao | None, list[str]]:
        nome = str(entrada.get("acao", "")).removeprefix("omarchy-")
        argumentos = entrada.get("argumentos") or []
        if not isinstance(argumentos, list):
            argumentos = [str(argumentos)]
        return self.acoes.get(nome), [str(a) for a in argumentos]

    # --- ganchos do ClaudeBrain -----------------------------------------------------------------

    def prechecar(self, nome: str, entrada: dict[str, Any]) -> str | None:
        if nome != FERRAMENTA:
            return None
        acao, argumentos = self._alvo(entrada)
        if acao is None:
            return "Ação desconhecida: busque no catálogo com sistema_buscar e use o nome exato."
        if acao.risco == 4:
            motivo = "usa sudo" if acao.usa_sudo else "é proibida por voz"
            return f"Recusado: a ação {acao.nome} {motivo}. Diga ao usuário que isso é pela tela."
        if acao.nome in ACEITAM_ENDERECO:  # nada ou um endereço web; nunca file: nem javascript:
            valido = not argumentos or (
                len(argumentos) == 1
                and len(argumentos[0]) <= 2000
                and ENDERECO.fullmatch(argumentos[0]) is not None
            )
        else:
            valido = len(argumentos) <= 6 and all(ARGUMENTO.fullmatch(a) for a in argumentos)
        if not valido:
            return "Argumentos inválidos: use só os valores que a ação documenta."
        return None

    def autoaprovar(self, nome: str, entrada: dict[str, Any]) -> bool:
        acao, _ = self._alvo(entrada)
        return nome == FERRAMENTA and acao is not None and acao.risco <= 1

    def frase_exata(self, nome: str, entrada: dict[str, Any]) -> str | None:
        acao, _ = self._alvo(entrada)
        if nome != FERRAMENTA or acao is None or acao.risco != 3:
            return None
        return f"confirmo {VERBOS.get(acao.nome, 'executar')}"

    def descrever(self, nome: str, entrada: dict[str, Any]) -> str | None:
        acao, argumentos = self._alvo(entrada)
        if nome != FERRAMENTA or acao is None:
            return None
        if acao.risco == 3:
            frase = self.frase_exata(nome, entrada)
            verbo = VERBOS.get(acao.nome, "mexer no sistema")
            return f"Isso vai {verbo} o computador. Para confirmar, diga: {frase}."
        detalhe = f" {' '.join(argumentos)}" if argumentos else ""
        return f"Vou executar {acao.nome.replace('-', ' ')}{detalhe}."

    # --- execução ---------------------------------------------------------------------------------

    def executar(self, entrada: dict[str, Any]) -> dict[str, Any]:
        acao, argumentos = self._alvo(entrada)
        if acao is None or acao.risco == 4:
            raise ValueError("ação não permitida")
        try:
            feito = subprocess.run(  # noqa: S603 (binário do catálogo, sem shell)
                [str(acao.caminho), *argumentos],
                capture_output=True,
                text=True,
                timeout=self.tempo_limite_s,
                env=_ambiente(),
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"acao": acao.nome, "ok": False, "saida": "tempo esgotado"}
        saida = (feito.stdout + feito.stderr).strip()[-1500:]
        return {
            "acao": acao.nome,
            "ok": feito.returncode == 0,
            "saida": saida,
            "nivel": NIVEIS[acao.risco],
        }


def frase_confere(fala: str, frase: str) -> bool:
    """ "confirmo reiniciar" precisa estar dito, nessa ordem, com as duas palavras."""
    ditas, exigidas = _palavras(fala), _palavras(frase)
    texto = " ".join(ditas)
    return " ".join(exigidas) in texto
