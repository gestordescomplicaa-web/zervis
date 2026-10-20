"""O registro das conversas do Zé, com data e hora de cada fala (08/10/2026).

As conversas de voz não entravam no ai-memory: os ganchos dele são do Claude Code de terminal e
o
cérebro do Zé roda pelo Agent SDK, sem ganchos. Agora o próprio Zé registra cada pedido e a
resposta em `<dados>/conversas/conversas.db` (a fonte da verdade, com a hora local) e publica
uma página por dia no ai-memory (projeto "Zé", camada episódica), onde a
busca por texto e por significado acha. As conversas anteriores a isto vêm das transcrições do
Agent SDK pela `importar_sdk`, uma vez.
"""

import json
import logging
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from zervis import fuso, usuario
from zervis.dados.documentos import Documentos, linhas_json
from zervis.memoria import aimemory

log = logging.getLogger(__name__)
FUSO = fuso.local()
PROJETO = "Zé"  # o projeto do ai-memory onde ficam as páginas do Zé
DIAS_DA_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado",
    "domingo",
]  # fmt: skip
_CARIMBO = re.compile(r"^\[[^\]]*?(\d{2})/(\d{2})/(\d{4}), (\d{2}):(\d{2})\]\s*")


@dataclass(frozen=True)
class Turno:
    em: datetime
    pessoa: str  # o que quem usa disse
    ze: str

    def para_json(self) -> str:
        return json.dumps(
            {"em": self.em.isoformat(timespec="seconds"), "pessoa": self.pessoa, "ze": self.ze},
            ensure_ascii=False,
        )


_CAMPOS = {"em", "ze", "dia", "pessoa"}


def _turno(d: dict[str, Any]) -> Turno:
    """Um turno gravado. Nos registros de antes de 20/10/2026, a fala de quem usa ficava sob
    outra chave (o nome de uma pessoa, que não pode estar no código): a que não é conhecida."""
    fala = d.get("pessoa")
    if fala is None:
        fala = next((v for k, v in d.items() if k not in _CAMPOS), "")
    return Turno(datetime.fromisoformat(d["em"]), str(fala), str(d["ze"]))


def nome_do_dia(dia: date) -> str:
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia:%d/%m/%Y}"


class Conversas:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self._dados = Documentos(pasta / "conversas.db")
        for arquivo in sorted(pasta.glob("????-??-??.jsonl")):
            try:
                date.fromisoformat(arquivo.stem)
            except ValueError:
                continue

            def ler(texto: str, dia: str = arquivo.stem) -> list[dict[str, Any]]:
                return [{**dado, "dia": dia} for dado in linhas_json(texto)]

            self._dados.importar(arquivo, ler, "conversas")

    def _arquivo(self, dia: date) -> Path:
        return self.pasta / f"{dia:%Y-%m-%d}.jsonl"

    def registrar(self, pessoa: str, ze: str, em: datetime | None = None) -> Turno:
        turno = Turno((em or datetime.now(FUSO)).astimezone(FUSO), pessoa.strip(), ze.strip())
        self._dados.guardar(
            "conversas", {**json.loads(turno.para_json()), "dia": turno.em.date().isoformat()}
        )
        return turno

    def do_dia(self, dia: date) -> list[Turno]:
        dados = self._dados.filtrar("conversas", "dia", [dia.isoformat()], -1)
        return sorted((_turno(d) for d in dados), key=lambda t: t.em)

    def dias(self) -> list[date]:
        return sorted({date.fromisoformat(d["dia"]) for d in self._dados.listar("conversas")})

    def buscar(self, texto: str, limite: int = 50) -> list[Turno]:
        return [_turno(d) for d in self._dados.buscar(texto, "conversas", limite)]

    def juntar(self, turnos: Iterable[Turno]) -> int:
        """Importa só os turnos novos dentro de uma transação entre processos."""
        novos = 0
        por_dia: dict[date, list[Turno]] = {}
        for t in turnos:
            por_dia.setdefault(t.em.date(), []).append(t)
        with self._dados.banco.transacao():
            for dia, lista in por_dia.items():
                vistos = {(t.em.isoformat(timespec="minutes"), t.pessoa) for t in self.do_dia(dia)}
                for t in sorted(lista, key=lambda x: x.em):
                    chave = (t.em.isoformat(timespec="minutes"), t.pessoa)
                    if chave not in vistos:
                        vistos.add(chave)
                        self.registrar(t.pessoa, t.ze, t.em)
                        novos += 1
        return novos

    def pagina(self, dia: date) -> str:
        """O dia como página do ai-memory: cada fala com a hora."""
        partes = [f"# Conversas com o Zé — {nome_do_dia(dia)}", ""]
        for t in self.do_dia(dia):
            partes += [
                f"## {t.em:%H:%M}",
                f"**{usuario.PERFIL.rotulo}:** {t.pessoa}",
                "",
                f"**Zé:** {t.ze}",
                "",
            ]
        return "\n".join(partes)


def publicar(caminho: str, corpo: str, tags: tuple[str, ...] = (), tier: str = "episodic") -> bool:
    """Escreve (ou substitui) uma página do Zé no ai-memory; falha só registra, nunca derruba."""
    comando = aimemory.comando(
        "write-page", "--project", PROJETO, "--path", caminho, "--body", "-",
        "--tier", tier, *(a for tag in tags for a in ("-t", tag)),
    )  # fmt: skip
    try:
        feito = subprocess.run(  # noqa: S603 (binário fixo, argumentos em lista)
            comando, input=corpo, capture_output=True, text=True, timeout=30, check=False,
            cwd="/tmp",  # noqa: S108 (fora de qualquer projeto: o projeto vai explícito)
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as erro:
        log.warning("ai-memory não recebeu %s: %s", caminho, erro)
        return False
    if feito.returncode != 0:
        log.warning("ai-memory recusou %s: %s", caminho, feito.stderr.strip()[-200:])
        return False
    return True


def publicar_dia(conversas: Conversas, dia: date) -> bool:
    return publicar(f"conversas/{dia:%Y-%m-%d}.md", conversas.pagina(dia), ("conversa", "voz"))


def _sem_contexto(texto: str) -> str:
    """Tira os parênteses de contexto do começo ("(Janela do Zé: …)"), mesmo aninhados."""
    texto = texto.strip()
    while texto.startswith("("):
        nivel = 0
        for i, c in enumerate(texto):
            nivel += (c == "(") - (c == ")")
            if nivel == 0:
                texto = texto[i + 1 :].strip()
                break
        else:
            return texto
    return texto


def pedido_do_carimbo(conteudo: str) -> tuple[datetime, str] | None:
    """`[quinta-feira, 08/10/2026, 00:47] (contexto) texto` -> (data e hora, texto)."""
    m = _CARIMBO.match(conteudo)
    if not m:
        return None
    dia, mes, ano, hora, minuto = (int(x) for x in m.groups())
    try:
        quando = datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)
    except ValueError:
        return None
    return quando, _sem_contexto(conteudo[m.end() :])


def turnos_da_transcricao(linhas: Iterable[str]) -> list[Turno]:
    """Os pedidos com carimbo e as respostas em texto de uma transcrição do Agent SDK."""
    turnos: list[Turno] = []
    atual: tuple[datetime, str] | None = None
    respostas: list[str] = []
    for linha in linhas:
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        conteudo = (d.get("message") or {}).get("content")
        if d.get("type") == "user" and isinstance(conteudo, str):
            if (pedido := pedido_do_carimbo(conteudo)) is not None:
                if atual and atual[1]:
                    turnos.append(Turno(atual[0], atual[1], " ".join(respostas).strip()))
                atual, respostas = pedido, []
        elif d.get("type") == "assistant" and isinstance(conteudo, list) and atual:
            respostas += [str(b.get("text", "")) for b in conteudo if b.get("type") == "text"]
    if atual and atual[1]:
        turnos.append(Turno(atual[0], atual[1], " ".join(respostas).strip()))
    return turnos


def importar_sdk(pasta_sdk: Path, conversas: Conversas) -> int:
    """As conversas de antes do registro, das transcrições do Agent SDK (só pedidos com carimbo:
    a revisão e as consultas internas não são conversa com o usuário)."""
    turnos: list[Turno] = []
    for arquivo in sorted(pasta_sdk.glob("*.jsonl")):
        try:
            turnos += turnos_da_transcricao(arquivo.read_text().splitlines())
        except OSError:
            continue
    return conversas.juntar(turnos)
