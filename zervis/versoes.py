"""Atualizações do Zé pelo painel e pela voz: procurar e aplicar sem decorar comando (26/10/2026).

Procurar busca a origem e compara com o que está instalado, no canal escolhido: "versoes" (as
etiquetas `v*`, o padrão) ou "desenvolvimento" (a master). O que mudou vem do CHANGELOG, as
entradas novas entre o instalado e o destino, não da lista de commits. O Zé procura sozinho uma
vez por dia e só avisa; nunca instala sem a pessoa pedir.

Aplicar roda o mesmo `zervis update` (`zervis/cli.py`) fora do serviço, numa unidade própria do
systemd (`zervis-atualizar`): o update reinicia o Zé, e um filho do serviço morreria junto, no
meio da troca. O resultado fica em `<estado>/atualizar.json`; o painel mostra, e o Zé, ao subir,
avisa uma vez.
"""

import contextlib
import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis import ambiente, cli, lugares

log = logging.getLogger(__name__)
CANAIS = ("versoes", "desenvolvimento")
UNIDADE = "zervis-atualizar"
DIA_S = 24 * 3600
PRIMEIRA_S = 120.0  # a primeira procura, depois de subir: sem disputar o início
RODANDO_MAXIMO_S = 15 * 60  # um "rodando" mais velho que isso morreu sem escrever o fim
MAXIMO_NOVIDADES = 12
# O systemd não passa o ambiente de quem chama: sem estas, a unidade acharia outras pastas.
REPASSAR = (*ambiente.nomes("PERFIL", "RAIZ"), "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")

# Os casos em que não há o que aplicar, ditos para quem está no painel (sem comandos).
TEXTOS = {
    "alteracoes": "Há alterações locais no código do Zé. A atualização não mexe nelas.",
    "sem_origem": "Esta instalação não segue o repositório de origem: reinstale pelo git clone.",
    "sem_conexao": "Sem conexão com o repositório de origem agora.",
    "sem_versao": "Ainda não há versão publicada. Para receber tudo o que entra, use o canal "
    "Desenvolvimento.",
    "em_dia": "O Zé está na versão mais nova ({rotulo}).",
    "a_frente": "O Zé está à frente da versão publicada mais nova ({rotulo}), no código em "
    "desenvolvimento. Para seguir recebendo, use o canal Desenvolvimento.",
    "commits_locais": "Há melhorias locais que ainda não estão na origem (do autodesenvolvimento, "
    "por exemplo). Junte-as antes de atualizar.",
}
RESULTADOS = {
    "ok": "Atualizei o Zé para {para}.",
    "nada": "O Zé já estava na versão mais nova.",
    "voltou": "A versão nova não subiu: voltei para a anterior, nada foi perdido.",
    "falhou": "A atualização não foi feita. Veja os detalhes em Atualizações.",
}

Rodar = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _rodar(comando: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (comandos fixos deste módulo)
        comando, capture_output=True, text=True, timeout=30, check=False
    )


def _ler(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(arquivo: Path, dados: dict[str, Any]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps(dados, ensure_ascii=False))
    temporario.chmod(0o600)
    temporario.replace(arquivo)


def novidades(alvo: str, rodar: cli.Rodar = cli.rodar) -> list[str]:
    """As entradas que o CHANGELOG ganha entre o instalado e `alvo`, cada uma num texto só (as
    linhas de continuação juntas), sem o Markdown da lista."""
    diff = rodar(
        ["git", "-C", str(cli.REPO), "diff", "--unified=0", "HEAD", alvo, "--", "CHANGELOG.md"]
    ).stdout
    entradas: list[str] = []
    for linha in diff.splitlines():
        if linha.startswith("+++") or not linha.startswith("+"):
            continue
        texto = linha[1:]
        if texto.startswith("- "):
            entradas.append(texto[2:].strip())
        elif texto.startswith("  ") and entradas:
            entradas[-1] += " " + texto.strip()
    return entradas


class Versoes:
    """O que o painel e a voz sabem das atualizações; uma por processo do Zé."""

    def __init__(
        self,
        estado: Path | None = None,
        config: Path | None = None,
        rodar: cli.Rodar = cli.rodar,
        lancar: Rodar = _rodar,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self.resultado = (estado or lugares.ESTADO) / "atualizar.json"
        self.ajuste = (config or lugares.CONFIG) / "atualizacoes.json"
        self.rodar, self.lancar, self.agora = rodar, lancar, agora
        self._ultima: dict[str, Any] = {}
        self._trava = threading.Lock()
        self._procurando = threading.Lock()
        self._avisado = ""  # o destino que a procura diária já avisou

    # --- canal ---

    @property
    def canal(self) -> str:
        canal = _ler(self.ajuste).get("canal")
        return canal if canal in CANAIS else CANAIS[0]

    def mudar_canal(self, canal: str) -> None:
        if canal not in CANAIS:
            raise ValueError(f"canal desconhecido: {canal}")
        _gravar(self.ajuste, {**_ler(self.ajuste), "canal": canal})
        with self._trava:
            self._ultima = {}  # a procura de antes era de outro canal

    # --- procurar ---

    def procurar(self) -> dict[str, Any]:
        """Busca a origem agora e guarda o que achou (o painel e a voz leem a última)."""
        with self._procurando:
            canal = self.canal
            plano = cli.planejar(self.rodar, desenvolvimento=canal == "desenvolvimento")
            achado: dict[str, Any] = {
                "canal": canal,
                "instalada": cli.versao(self.rodar),
                "destino": plano.rotulo,
                "alvo": plano.alvo[:12],
                "disponivel": not plano.motivo,
                "motivo": plano.motivo,
                "texto": TEXTOS.get(plano.motivo, "").format(rotulo=plano.rotulo),
                "mudancas": 0,
                "novidades": [],
                "procurado": self.agora(),
            }
            if not plano.motivo:
                commits = cli._git(self.rodar, "rev-list", "--count", f"HEAD..{plano.alvo}")
                achado["mudancas"] = int(commits.stdout.strip() or 0)
                lista = novidades(plano.alvo, self.rodar)
                achado["novidades"] = lista[:MAXIMO_NOVIDADES]
                achado["mais"] = max(0, len(lista) - MAXIMO_NOVIDADES)
                achado["texto"] = (
                    f"Há uma versão nova ({plano.rotulo}), com {achado['mudancas']} mudanças."
                    if canal == "versoes"
                    else f"Há {achado['mudancas']} mudanças novas no código em desenvolvimento."
                )
            with self._trava:
                self._ultima = achado
            return achado

    def ultima(self) -> dict[str, Any]:
        with self._trava:
            return dict(self._ultima)

    def foto(self) -> dict[str, Any]:
        """O resumo para o menu do painel: a bolinha de "tem atualização" e se está rodando."""
        ultima = self.ultima()
        return {"disponivel": bool(ultima.get("disponivel")), "rodando": self.rodando()}

    def procurar_do_dia(self) -> str | None:
        """A procura diária: o que avisar, só quando aparece um destino novo (nunca instala)."""
        try:
            achado = self.procurar()
        except (OSError, subprocess.SubprocessError, ValueError) as erro:
            log.warning("atualizações: não consegui procurar: %s", erro)
            return None
        if not achado["disponivel"] or achado["alvo"] == self._avisado:
            return None
        self._avisado = achado["alvo"]
        if achado["canal"] == "versoes":
            return f"Tem versão nova do Zé, a {achado['destino']}. Está em Atualizações."
        return f"Tem atualização do Zé: {achado['mudancas']} mudanças. Está em Atualizações."

    # --- aplicar ---

    def rodando(self) -> bool:
        r = _ler(self.resultado)
        return r.get("estado") == "rodando" and self.agora() - r.get("inicio", 0) < RODANDO_MAXIMO_S

    def aplicar(self) -> str:
        """Começa a atualização numa unidade própria e devolve na hora (o Zé vai reiniciar)."""
        if self.rodando():
            return "Já há uma atualização em andamento."
        canal = self.canal
        _gravar(
            self.resultado,
            {"estado": "rodando", "canal": canal, "inicio": self.agora(), "avisado": False},
        )
        self.lancar(["systemctl", "--user", "reset-failed", UNIDADE])
        lancado = self.lancar(
            [
                "systemd-run",
                "--user",
                "--collect",
                f"--unit={UNIDADE}",
                *(f"--setenv={k}={os.environ[k]}" for k in REPASSAR if os.environ.get(k)),
                "--",
                sys.executable,
                "-m",
                "zervis.versoes",
                canal,
            ]
        )
        if lancado.returncode != 0:
            erro = (lancado.stderr or lancado.stdout).strip()
            self._terminar("falhou", canal, f"O systemd não começou a atualização: {erro}")
            return "Não consegui começar a atualização. Veja os detalhes em Atualizações."
        return "Atualizando: o Zé reinicia e volta em alguns segundos."

    def _terminar(
        self, estado: str, canal: str, registro: str, de: str = "", para: str = ""
    ) -> None:
        anterior = _ler(self.resultado)
        _gravar(
            self.resultado,
            {
                "estado": estado,
                "canal": canal,
                "inicio": anterior.get("inicio", self.agora()),
                "fim": self.agora(),
                "de": de,
                "para": para,
                "registro": registro[-4000:],
                "avisado": False,
            },
        )

    def executar(self, canal: str) -> int:
        """Dentro da unidade `zervis-atualizar`: o `zervis update`, com o resultado guardado."""
        antes = cli._git(self.rodar, "rev-parse", "HEAD").stdout.strip()
        de = cli.versao(self.rodar)
        saida = io.StringIO()
        try:
            with contextlib.redirect_stdout(saida):
                codigo = cli.update(self.rodar, desenvolvimento=canal == "desenvolvimento")
        except Exception as erro:  # o registro precisa do fim, qualquer que seja
            print(f"{type(erro).__name__}: {erro}", file=saida)
            codigo = 1
        depois = cli._git(self.rodar, "rev-parse", "HEAD").stdout.strip()
        texto = saida.getvalue()
        if codigo == 0:
            estado = "ok" if depois != antes else "nada"
        else:
            estado = "voltou" if "voltando para a anterior" in texto else "falhou"
        self._terminar(estado, canal, texto, de, cli.versao(self.rodar))
        return codigo

    def ultimo_resultado(self) -> dict[str, Any]:
        """A última atualização, para a página (sem o `avisado`)."""
        r = _ler(self.resultado)
        if not r:
            return {}
        r.pop("avisado", None)
        r["rodando"] = self.rodando()
        r["texto"] = RESULTADOS.get(r.get("estado", ""), "").format(para=r.get("para", ""))
        return r

    def resultado_novo(self) -> str | None:
        """O que dizer, uma vez, sobre uma atualização que terminou (o Zé acabou de subir)."""
        r = _ler(self.resultado)
        if r.get("avisado", True) or r.get("estado") not in RESULTADOS:
            return None
        _gravar(self.resultado, {**r, "avisado": True})
        return RESULTADOS[r["estado"]].format(para=r.get("para", ""))


PADRAO = Versoes()


def main(argv: list[str] | None = None) -> int:
    canal = (argv if argv is not None else sys.argv[1:] or [CANAIS[0]])[0]
    if canal not in CANAIS:
        print(f"canal desconhecido: {canal}", file=sys.stderr)
        return 2
    return PADRAO.executar(canal)


if __name__ == "__main__":
    sys.exit(main())
