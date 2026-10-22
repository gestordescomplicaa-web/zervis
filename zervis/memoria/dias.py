"""A nota do dia (08/10/2026; ideia do ai-memory-vault, notas diárias que se escrevem sozinhas).

Uma vez por dia, depois das cinco da manhã, o Zé resume os dias que tiveram conversa ou evento e
ainda não têm nota: o que foi feito, decidido e ficou pendente, e os marcos dos próximos dias.
Um modelo menor faz o resumo só com o material do dia (as falas com a hora e os eventos da linha
do tempo), sem inventar; a nota vai para `~/.local/share/zervis/dias/AAAA-MM-DD.md`, para o
ai-memory (busca) e para a linha do tempo. É o que responde "o que fizemos terça?" sem reler
tudo, e o que o Foco usa para "ontem você parou em…".
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path

from zervis import usuario
from zervis.memoria.conversas import FUSO, Conversas, nome_do_dia, publicar
from zervis.memoria.linha import LinhaDoTempo

MATERIAL_MAX = 24_000  # caracteres do dia que o modelo lê (o resto dos dias longos fica de fora)
HORA_DA_NOTA = time(5, 0)

SISTEMA = (
    "Você escreve notas diárias curtas em markdown, em português do Brasil, só com fatos do "
    "registro que recebe. Nunca responda em JSON nem com blocos de código."
)

PROMPT = """Você escreve a nota do dia do Zé, o assistente de voz do usuário, a partir do registro
abaixo: as conversas de {dia} (cada fala com a hora) e os eventos do dia. Escreva em português,
em markdown, curto (no máximo 15 linhas no total), só com fatos que estão no registro:

## Feito
(o que foi feito ou resolvido, uma linha cada)
## Decidido
(decisões e preferências que o usuário firmou; se não houver, "nada")
## Pendente
(o que ficou começado, travado ou prometido para depois; se não houver, "nada")

Não invente, não repita o registro, não cumprimente. Nomes de projetos como estão.

REGISTRO
{material}
"""


def _curta(texto: str, limite: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


class Dias:
    def __init__(self, pasta: Path, conversas: Conversas, linha: LinhaDoTempo) -> None:
        self.pasta = pasta
        self.conversas = conversas
        self.linha = linha

    def arquivo(self, dia: date) -> Path:
        return self.pasta / f"{dia:%Y-%m-%d}.md"

    def nota(self, dia: date) -> str | None:
        try:
            return self.arquivo(dia).read_text()
        except OSError:
            return None

    def material(self, dia: date) -> str:
        inicio = datetime.combine(dia, time(0), FUSO)
        # Cada fala encurtada: um dia longo cabe inteiro, da manhã à noite, no que o modelo lê.
        partes = [
            f"[{t.em:%H:%M}] {usuario.PERFIL.rotulo}: {_curta(t.pessoa, 220)}\n"
            f"[{t.em:%H:%M}] Zé: {_curta(t.ze, 220)}"
            for t in self.conversas.do_dia(dia)
        ]
        partes += [
            f"[evento] {e.resumo()}"
            for e in self.linha.entre(inicio, inicio + timedelta(days=1))
            if e.tipo != "nota"
        ]
        texto = "\n".join(partes)
        return texto[:MATERIAL_MAX]

    def faltando(self, agora: datetime, ate_dias: int = 3) -> list[date]:
        """Dias passados (até `ate_dias` atrás) com material e sem nota, só depois das 5h."""
        if agora.astimezone(FUSO).time() < HORA_DA_NOTA:
            return []
        hoje = agora.astimezone(FUSO).date()
        dias = [hoje - timedelta(days=n) for n in range(ate_dias, 0, -1)]
        return [d for d in dias if self.nota(d) is None and self.material(d)]

    def prompt(self, dia: date) -> str:
        return PROMPT.format(dia=nome_do_dia(dia), material=self.material(dia))

    def guardar(self, dia: date, resumo: str) -> str:
        proximos = self.linha.proximos(7, datetime.combine(dia + timedelta(days=1), time(0), FUSO))
        linhas = resumo.strip().splitlines()
        while linhas and (linhas[0].startswith("# ") or not linhas[0].strip()):
            linhas.pop(0)  # o modelo às vezes repete o título
        corpo = f"# Nota do dia — {nome_do_dia(dia)}\n\n" + "\n".join(linhas) + "\n"
        if proximos:
            corpo += "\n## Marcos dos próximos dias\n" + "\n".join(
                f"- {e.resumo()}" for e in proximos
            )
            corpo += "\n"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo(dia).write_text(corpo)
        publicar(f"dias/{dia:%Y-%m-%d}.md", corpo, ("nota-do-dia",))
        self.linha.registrar(
            "nota", f"Nota do dia {dia:%d/%m/%Y} escrita", datetime.combine(dia, time(23, 59), FUSO)
        )
        return corpo
