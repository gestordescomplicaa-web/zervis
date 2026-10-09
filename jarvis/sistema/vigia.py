"""Avisos do sistema (Fase 5; docs/07-sistema-omarchy.md): eventos do Omarchy e processo pesado.

Eventos: o hook `deploy/omarchy-hooks/zervis-evento`, instalado nas pastas `.d` do Omarchy, só
anota uma linha JSON em `eventos-sistema.jsonl`; aqui cada linha nova vira um aviso (sem polling
do sistema, só do arquivo).

Processo pesado: o `ps` dá a média desde que o processo nasceu, que esconde um pico de agora. Aqui
a CPU é medida pela diferença de `utime + stime` em `/proc/<pid>/stat` entre duas leituras; quem
passa de `LIMITE_CPU` por `AMOSTRAS_SEGUIDAS` leituras seguidas gera um aviso, uma vez por processo.
"""

import json
import os
from pathlib import Path

LIMITE_CPU = 80.0  # % de um núcleo
AMOSTRAS_SEGUIDAS = 5  # com uma leitura por minuto, cinco minutos
IGNORADOS = {"whisper-server", "Hyprland", "pipewire", "wireplumber"}
TICKS = os.sysconf("SC_CLK_TCK")


def texto_do_evento(evento: str, arg: str) -> str | None:
    if evento == "battery-low":
        return f"Bateria fraca: {arg} por cento." if arg else "Bateria fraca."
    if evento == "post-update":
        return "A atualização do Omarchy terminou."
    return None  # tema, fonte, boot: não merecem voz


class Eventos:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        try:
            self.lido = arquivo.stat().st_size  # o que já estava lá ao subir não é novidade
        except OSError:
            self.lido = 0

    def novos(self) -> list[str]:
        try:
            tamanho = self.arquivo.stat().st_size
        except OSError:
            return []
        if tamanho < self.lido:
            self.lido = 0  # arquivo recriado
        if tamanho == self.lido:
            return []
        with self.arquivo.open("rb") as f:
            f.seek(self.lido)
            bruto = f.read()
        self.lido = tamanho
        avisos = []
        for linha in bruto.decode(errors="replace").splitlines():
            try:
                dado = json.loads(linha)
                texto = texto_do_evento(str(dado.get("evento", "")), str(dado.get("arg", "")))
            except ValueError:
                continue
            if texto:
                avisos.append(texto)
        return avisos


def _tempos(proc: Path = Path("/proc")) -> dict[int, tuple[str, int]]:
    """pid -> (nome, ticks de CPU usados até agora)."""
    tempos = {}
    for pasta in proc.iterdir():
        if not pasta.name.isdigit():
            continue
        try:
            stat = (pasta / "stat").read_text()
        except OSError:
            continue
        fecha = stat.rfind(")")
        nome = stat[stat.find("(") + 1 : fecha]
        campos = stat[fecha + 2 :].split()
        tempos[int(pasta.name)] = (nome, int(campos[11]) + int(campos[12]))
    return tempos


class Vigia:
    def __init__(self, ler: object = _tempos) -> None:
        self.ler = ler
        self.anterior: dict[int, tuple[str, int]] = {}
        self.momento = 0.0
        self.seguidas: dict[int, int] = {}
        self.avisados: set[int] = set()

    def amostrar(self, agora: float) -> list[str]:
        atual: dict[int, tuple[str, int]] = self.ler()  # type: ignore[operator]
        intervalo = agora - self.momento
        avisos = []
        if self.anterior and intervalo > 0:
            for pid, (nome, ticks) in atual.items():
                antes = self.anterior.get(pid)
                if antes is None or nome in IGNORADOS:
                    continue
                cpu = 100 * (ticks - antes[1]) / TICKS / intervalo
                self.seguidas[pid] = self.seguidas.get(pid, 0) + 1 if cpu >= LIMITE_CPU else 0
                if self.seguidas[pid] >= AMOSTRAS_SEGUIDAS and pid not in self.avisados:
                    self.avisados.add(pid)
                    avisos.append(
                        f"O processo {nome} está usando {round(cpu)} por cento de CPU há uns "
                        "cinco minutos. Quer que eu veja o que é?"
                    )
        self.anterior, self.momento = atual, agora
        vivos = set(atual)
        self.seguidas = {p: n for p, n in self.seguidas.items() if p in vivos}
        self.avisados &= vivos
        return avisos
