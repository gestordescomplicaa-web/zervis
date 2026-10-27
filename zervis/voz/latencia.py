"""Marcos de cada turno, sem áudio/texto; persistência fora do laço do microfone.

O primeiro token é o primeiro fragmento de texto não vazio recebido do provedor.
O primeiro som é a entrega do primeiro PCM ao reprodutor, não uma medição acústica.
"""

import argparse
import json
import logging
import math
import os
import queue
import statistics
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from zervis import lugares
from zervis.automacoes.agenda import FUSO

log = logging.getLogger(__name__)
ETAPAS = {
    "fim_de_turno": ("fim_fala", "pedido_fechado"),
    "transcricao": ("pedido_fechado", "transcrito"),
    "despacho": ("transcrito", "cerebro_enviado"),
    "cerebro": ("cerebro_enviado", "primeiro_token"),
    "formacao_frase": ("primeiro_token", "primeira_frase"),
    "entrega_fala": ("primeira_frase", "sintese_pedida"),
    "voz": ("sintese_pedida", "primeiro_som"),
    "total": ("fim_fala", "primeiro_som"),
}
MARCOS = {m for par in ETAPAS.values() for m in par} | {"fim_cerebro"}
CAMPOS_GRUPO = (
    "origem",
    "rota",
    "provedor",
    "modelo",
    "transcricao_por",
    "fim_por",
    "aprovacao",
    "primeiro_som_tipo",
    "voz_por",
)


@dataclass
class Turno:
    id: str
    em: str
    inicio: float
    origem: str
    rota: str = "controle"
    provedor: str = ""
    modelo: str = ""
    transcricao_por: str = ""
    fim_por: str = ""
    aprovacao: bool = False
    erro_cerebro: bool = False
    primeiro_som_tipo: str = "resposta"
    voz_por: str = ""  # quem falou a primeira frase: piper ou elevenlabs
    marcos: dict[str, float] = field(default_factory=dict)

    def registro(self, resultado: str) -> dict[str, Any]:
        marcos = {k: round((v - self.inicio) * 1000, 3) for k, v in self.marcos.items()}
        etapas: dict[str, float] = {}
        for nome, (a, b) in ETAPAS.items():
            if nome == "total" and self.origem == "teclado":
                a = "pedido_fechado"
            if nome == "despacho" and self.origem == "teclado":
                a = "pedido_fechado"
            if a in marcos and b in marcos and marcos[b] >= marcos[a]:
                etapas[nome] = round(marcos[b] - marcos[a], 3)
        return {
            "versao": 1,
            "id": self.id,
            "em": self.em,
            "origem": self.origem,
            "rota": self.rota,
            "provedor": self.provedor,
            "modelo": self.modelo,
            "transcricao_por": self.transcricao_por,
            "fim_por": self.fim_por,
            "aprovacao": self.aprovacao,
            "primeiro_som_tipo": self.primeiro_som_tipo,
            "voz_por": self.voz_por,
            "resultado": resultado,
            "marcos_ms": marcos,
            "etapas_ms": etapas,
        }


def ler_turnos(arquivo: Path) -> list[dict[str, Any]]:
    registros = []
    try:
        with arquivo.open(encoding="utf-8", errors="replace") as f:
            for linha in f:
                try:
                    r = json.loads(linha)
                    if (
                        isinstance(r, dict)
                        and r.get("versao") == 1
                        and isinstance(r.get("etapas_ms"), dict)
                    ):
                        registros.append(r)
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return registros


def resumir(registros: list[dict[str, Any]]) -> dict[str, Any]:
    grupos: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for r in registros:
        chave = tuple(str(r.get(k, False if k == "aprovacao" else "")) for k in CAMPOS_GRUPO)
        grupos.setdefault(chave, []).append(r)
    saida = []
    for chave, linhas in sorted(grupos.items()):
        etapas = {}
        for etapa in ETAPAS:
            valores = sorted(
                float(v)
                for r in linhas
                if r.get("resultado") == "concluido"
                and isinstance(r.get("etapas_ms"), dict)
                and isinstance(v := r["etapas_ms"].get(etapa), (int, float))
                and not isinstance(v, bool)
                and math.isfinite(v)
                and v >= 0
            )
            if valores:
                etapas[etapa] = {
                    "n": len(valores),
                    "mediana_ms": round(statistics.median(valores), 3),
                    "p95_ms": valores[math.ceil(len(valores) * 0.95) - 1],
                }
        saida.append(
            {
                **dict(zip(CAMPOS_GRUPO, chave, strict=True)),
                "aprovacao": chave[CAMPOS_GRUPO.index("aprovacao")] == "True",
                "turnos": len(linhas),
                "resultados": {
                    k: sum(r.get("resultado") == k for r in linhas)
                    for k in sorted({str(r.get("resultado")) for r in linhas})
                },
                "etapas": etapas,
            }
        )
    return {"versao": 1, "turnos": len(registros), "grupos": saida}


class Latencias:
    def __init__(self, pasta: Path, relogio: Callable[[], float] = time.monotonic) -> None:
        self.pasta, self.relogio = pasta, relogio
        self.trava = threading.Lock()
        self.turnos: dict[str, Turno] = {}
        self.ultimo: dict[str, Any] | None = None
        self.descartados = 0
        self.erro: str | None = None
        self.fila: queue.Queue[dict[str, Any] | threading.Event | None] = queue.Queue(128)
        self.thread = threading.Thread(target=self._gravar, name="latencias", daemon=True)
        self.thread.start()

    def iniciar(self, origem: str, inicio: float | None = None) -> str:
        if origem not in {"voz", "teclado"}:
            raise ValueError("origem de turno inválida")
        id_ = uuid4().hex
        with self.trava:
            self.turnos[id_] = Turno(
                id_,
                datetime.now(FUSO).isoformat(),
                self.relogio() if inicio is None else inicio,
                origem,
            )
        return id_

    def marcar(self, id_: str | None, marco: str, em: float | None = None) -> None:
        if marco not in MARCOS:
            raise ValueError("marco de latência inválido")
        with self.trava:
            if t := self.turnos.get(id_ or ""):
                t.marcos.setdefault(marco, self.relogio() if em is None else em)

    def contexto(self, id_: str | None, **campos: str | bool) -> None:
        permitidos = {
            "rota",
            "provedor",
            "modelo",
            "transcricao_por",
            "fim_por",
            "aprovacao",
            "erro_cerebro",
            "primeiro_som_tipo",
            "voz_por",
        }
        if campos.keys() - permitidos:
            raise ValueError("campo de diagnóstico não permitido")
        for k, v in campos.items():
            if isinstance(v, bool) != (k in {"aprovacao", "erro_cerebro"}):
                raise ValueError("tipo de diagnóstico inválido")
        with self.trava:
            if t := self.turnos.get(id_ or ""):
                for k, v in campos.items():
                    setattr(t, k, v)

    def primeiro_som(self, id_: str | None, em: float, tipo: str) -> None:
        with self.trava:
            if (t := self.turnos.get(id_ or "")) and "primeiro_som" not in t.marcos:
                t.marcos["primeiro_som"] = em
                t.primeiro_som_tipo = tipo

    def finalizar(self, id_: str | None, resultado: str = "concluido") -> None:
        with self.trava:
            if not (t := self.turnos.pop(id_ or "", None)):
                return
            if resultado == "concluido":
                resultado = (
                    "erro_cerebro"
                    if t.erro_cerebro
                    else ("sem_som" if "primeiro_som" not in t.marcos else resultado)
                )
            r = self.ultimo = t.registro(resultado)
        try:
            self.fila.put_nowait(r)
        except queue.Full:
            self.descartados += 1  # observabilidade nunca prende a voz

    def aguardar(self, prazo: float = 5) -> bool:
        pronto = threading.Event()
        try:
            self.fila.put_nowait(pronto)
        except queue.Full:
            return False
        return pronto.wait(prazo)

    def fechar(self) -> None:
        try:
            self.fila.put_nowait(None)
        except queue.Full:
            return
        self.thread.join(timeout=2)

    def _gravar(self) -> None:
        dias: dict[str, list[dict[str, Any]]] = {}
        while True:
            r = self.fila.get()
            if r is None:
                return
            if isinstance(r, threading.Event):
                r.set()
                continue
            try:
                self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
                dia = str(r["em"])[:10]
                arquivo = self.pasta / f"{dia}.jsonl"
                if dia not in dias:
                    dias.clear()  # a memória do coletor fica limitada ao dia ativo
                    dias[dia] = ler_turnos(arquivo)
                # Repare uma última linha incompleta de um encerramento abrupto.
                if arquivo.exists() and arquivo.stat().st_size:
                    with arquivo.open("rb") as f:
                        f.seek(-1, os.SEEK_END)
                        separar = f.read(1) != b"\n"
                else:
                    separar = False
                fd = os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "w") as f:
                    os.fchmod(f.fileno(), 0o600)
                    f.write(("\n" if separar else "") + json.dumps(r, ensure_ascii=False) + "\n")
                dias[dia].append(r)
                resumo = {"dia": dia, **resumir(dias[dia])}
                destino = self.pasta / f"{dia}-resumo.json"
                temp = destino.with_suffix(".next")
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    os.fchmod(f.fileno(), 0o600)
                    json.dump(resumo, f, ensure_ascii=False)
                temp.replace(destino)
                self.erro = None
            except OSError as erro:
                self.erro = type(erro).__name__
                log.warning("diagnóstico de latência indisponível: %s", self.erro)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumo diário de latência da voz, em ms")
    parser.add_argument("--dia", default=datetime.now(FUSO).date().isoformat())
    parser.add_argument("--pasta", type=Path, default=lugares.ESTADO / "latencias")
    args = parser.parse_args()
    dia = datetime.strptime(args.dia, "%Y-%m-%d").date().isoformat()
    print(
        json.dumps(
            {"dia": dia, **resumir(ler_turnos(args.pasta / f"{dia}.jsonl"))},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
