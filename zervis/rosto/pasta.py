"""A pasta do Zé no Barehands: ele mesmo escreve, o usuário lê (pedido de 06/10/2026).

Uma pasta de notas em Markdown, apontada por uma bolha do Barehands, com tudo o que é do Zé:
quem ele é e com o que está conectado, a memória, as skills com o uso, as automações, as
sugestões com o diário de aprendizado e o consumo de tokens por dia. Só leitura: mudar continua
passando pela aprovação por voz. Cada nota só é regravada quando o conteúdo muda.
"""

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import Jobs
from zervis.cerebro.consumo import Consumo
from zervis.habilidades.diario import EVENTOS, Diario
from zervis.habilidades.revisao import Pendencias
from zervis.habilidades.skills import Skills
from zervis.memoria.curta import SEPARADOR, Memoria

DIARIO_NA_PASTA = 40  # eventos mais novos mostrados
DIAS_NA_PASTA = 14

# Rótulo de cada grupo de ferramentas próprias, pelo começo do nome.
GRUPOS = {
    "sess": "Sessões de código",
    "sistema": "Máquina (Omarchy)",
    "automac": "Automações",
    "sugest": "Aprendizado",
    "skill": "Skills",
    "memoria": "Memória",
    "historico": "Memória",
}


@dataclass
class Conexoes:
    """O que o laço sabe do cérebro atual e das ferramentas ligadas."""

    cerebro: str = ""
    reserva: str = ""
    revisao: str = ""
    voz: str = ""
    proprias: list[tuple[str, bool]] = field(default_factory=list)  # (ferramenta, livre)
    embutidas: list[str] = field(default_factory=list)
    externos: dict[str, list[str]] = field(default_factory=dict)  # servidor -> livres
    agora: str = ""  # o retrato do autoconhecimento (ADR 0043); vazio: o resumo de antes


def _quando(epoca: float | int | None) -> str:
    if not epoca:
        return "-"
    return datetime.fromtimestamp(epoca, FUSO).strftime("%d/%m %H:%M")


def _mil(n: int) -> str:
    return f"{n / 1000:.1f} mil".replace(".", ",") if n >= 1000 else str(n)


def _celula(texto: str) -> str:
    return " ".join(texto.split()).replace("|", "/")


def quem_sou(c: Conexoes) -> str:
    linhas = [
        "# Quem sou",
        "",
        "Sou o Zé desta máquina. Esta pasta é escrita por mim e serve só para ler: "
        "mudanças passam pela sua aprovação por voz.",
        "",
        *(
            [c.agora.rstrip()]
            if c.agora
            else [
                "## Cérebro agora",
                f"- **Quem responde:** {c.cerebro or '-'}",
                f"- **Reserva:** {c.reserva or '-'}",
                f"- **Revisão em segundo plano:** {c.revisao or 'desligada'}",
                f"- **Voz e escuta:** {c.voz or '-'}",
            ]
        ),
        "",
        "## Conexões",
        "",
        "### Minhas ferramentas",
        "Livre = uso sem perguntar; o resto pede a sua aprovação por voz.",
        "",
    ]
    grupos: dict[str, list[str]] = {}
    for nome, livre in c.proprias:
        grupo = next((g for p, g in GRUPOS.items() if nome.startswith(p)), "Outras")
        grupos.setdefault(grupo, []).append(f"`{nome}`" + (" (livre)" if livre else ""))
    for grupo, nomes in grupos.items():
        linhas.append(f"- **{grupo}:** {', '.join(nomes)}")
    linhas += ["", "### Internet"]
    linhas.append(
        "- " + ", ".join(f"`{n}`" for n in c.embutidas) + " (pede aprovação)"
        if c.embutidas
        else "- nenhuma"
    )
    linhas += ["", "### MCPs externos"]
    if not c.externos:
        linhas.append("- nenhum ligado")
    for servidor, livres in c.externos.items():
        sufixo = f" (livres: {', '.join(livres)})" if livres else " (tudo pede aprovação)"
        linhas.append(f"- **{servidor}**{sufixo}")
    return "\n".join(linhas) + "\n"


def memoria(m: Memoria) -> str:
    linhas = ["# Memória", "", "Vai no começo de toda conversa. Tudo aqui foi aprovado por você."]
    for alvo, titulo in (("usuario", "Sobre você"), ("jarvis", "Minhas notas (ambiente)")):
        entradas = m.entradas(alvo)
        uso = len(SEPARADOR.join(entradas))
        limite = m.limites[alvo]
        linhas += [
            "",
            f"## {titulo}",
            f"{uso} de {limite} caracteres ({100 * uso // limite}%).",
            "",
        ]
        linhas += [f"- {e}" for e in entradas] or ["(vazio)"]
    return "\n".join(linhas) + "\n"


def skills(s: Skills, dias_arquivo: float) -> str:
    linhas = [
        "# Skills",
        "",
        "Como fazer bem uma classe de tarefa, do seu jeito. No prompt vai só uma linha de cada; "
        "o texto é lido quando a tarefa aparece (cada leitura conta um uso). "
        f"Sem uso há {dias_arquivo:.0f} dias, a skill vai para o arquivo.",
        "",
    ]
    lista = s.listar()
    if lista:
        uso = s.uso()
        linhas += ["| Skill | Quando usar | Usos | Último uso |", "|---|---|---|---|"]
        for nome, descricao in lista:
            u = uso.get(nome, {})
            linhas.append(
                f"| {nome} | {_celula(descricao)} | {u.get('usos', 0)} | "
                f"{_quando(u.get('ultimo'))} |"
            )
    else:
        linhas.append("Nenhuma ainda. Elas nascem das suas correções, com a sua aprovação.")
    if arquivadas := s.arquivadas():
        linhas += ["", "## Arquivadas", "", *(f"- {n}" for n in arquivadas)]
    return "\n".join(linhas) + "\n"


def automacoes(jobs: Jobs) -> str:
    linhas = ["# Automações", ""]
    lista = jobs.listar()
    if not lista:
        return "\n".join([*linhas, "Nenhuma. Peça por voz: “me lembra daqui a…”."]) + "\n"
    linhas += [
        "| Nome | Tipo | Agenda | Próxima | Última | Status |",
        "|---|---|---|---|---|---|",
    ]
    for j in lista:
        proxima = datetime.fromisoformat(j.proxima).strftime("%d/%m %H:%M") if j.proxima else "-"
        ultima = datetime.fromisoformat(j.ultima).strftime("%d/%m %H:%M") if j.ultima else "-"
        status = j.ultimo_status + ("" if j.ativo else " (pausada)")
        linhas.append(
            f"| {_celula(j.nome)} | {j.tipo} | {_celula(j.agenda)} | {proxima} | {ultima} | "
            f"{status} |"
        )
    linhas += ["", "## O que cada uma faz", ""]
    linhas += [f"- **{_celula(j.nome)}:** {_celula(j.texto)}" for j in lista]
    return "\n".join(linhas) + "\n"


def aprendizado(pendencias: Pendencias, diario: Diario) -> str:
    linhas = [
        "# Aprendizado",
        "",
        "## Sugestões esperando você",
        "Diga “quais são as sugestões?” para ouvir e aprovar.",
        "",
    ]
    lista = pendencias.listar()
    linhas += [
        f"- **{_quando(p.criada)}** · {p.resumo}"
        + (f"  \n  _de:_ “{_celula(p.origem)}”" if p.origem else "")
        for p in lista
    ] or ["Nenhuma."]
    linhas += ["", "## Diário", ""]
    eventos = diario.ultimos(DIARIO_NA_PASTA)
    for ev in eventos:
        rotulo = EVENTOS.get(str(ev.get("evento")), str(ev.get("evento")))
        linha = f"- **{_quando(ev.get('em'))}** · {rotulo}: {_celula(str(ev.get('resumo', '')))}"
        if ev.get("origem"):
            linha += f"  \n  _de:_ “{_celula(str(ev['origem']))}”"
        linhas.append(linha)
    if not eventos:
        linhas.append("Nada ainda: o diário começou em 06/10/2026.")
    return "\n".join(linhas) + "\n"


def _lido(d: dict[str, Any]) -> int:
    return int(d.get("entrada", 0)) + int(d.get("cache_lido", 0)) + int(d.get("cache_criado", 0))


def consumo(c: Consumo) -> str:
    hoje = c.retrato()
    linhas = [
        "# Consumo",
        "",
        "Na assinatura não se paga por token, mas tudo gasta as janelas de uso (as baterias). "
        "A meta é a média por resposta cair conforme eu aprendo, sem perder capacidade.",
        "",
        "| Dia | Respostas | Lidos | Do cache | Escritos | Lidos por resposta |",
        "|---|---|---|---|---|---|",
    ]
    for d in [*c.historico()[-(DIAS_NA_PASTA - 1) :], hoje][::-1]:
        respostas = int(d.get("respostas", 0))
        lido = _lido(d)
        cache = f"{100 * int(d.get('cache_lido', 0)) // lido}%" if lido else "-"
        media = _mil(lido // respostas) if respostas else "-"
        dia = datetime.fromisoformat(str(d.get("dia"))).strftime("%d/%m")
        linhas.append(
            f"| {dia} | {respostas} | {_mil(lido)} | {cache} | {_mil(int(d.get('saida', 0)))} | "
            f"{media} |"
        )
    return "\n".join(linhas) + "\n"


class Pasta:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def gravar(self, notas: dict[str, str]) -> list[str]:
        """Grava as notas que mudaram (escrita atômica); devolve os nomes regravados."""
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        mudadas = []
        for nome, texto in notas.items():
            arquivo = self.pasta / nome
            with contextlib.suppress(OSError):
                if arquivo.read_text() == texto:
                    continue
            temporario = arquivo.with_name(f".{nome}.next")
            temporario.write_text(texto)
            temporario.chmod(0o600)
            temporario.replace(arquivo)
            mudadas.append(nome)
        return mudadas


def notas(
    conexoes: Conexoes,
    m: Memoria,
    s: Skills,
    dias_arquivo: float,
    jobs: Jobs,
    pendencias: Pendencias,
    diario: Diario,
    c: Consumo,
) -> dict[str, str]:
    """As notas da pasta; o número na frente dá a ordem no Barehands."""
    return {
        "1 Quem sou.md": quem_sou(conexoes),
        "2 Memória.md": memoria(m),
        "3 Skills.md": skills(s, dias_arquivo),
        "4 Automações.md": automacoes(jobs),
        "5 Aprendizado.md": aprendizado(pendencias, diario),
        "6 Consumo.md": consumo(c),
    }
