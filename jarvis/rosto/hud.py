"""O cérebro do JARVIS na tela do Barehands (pedido do usuário, 06/10/2026).

Mesmo contrato do anel e do painel: o JARVIS escreve JSONs pequenos em `state/` e a página lê.
- `decisao.json`: a pergunta que espera o "sim" agora (com o prazo) e as sugestões pendentes.
- `eficiencia.json`: tokens lidos por resposta nos últimos dias e o que saiu sem o cérebro.
- `mapa.json`: o mapa do cérebro (memória, skills, conexões, automações) com as ligações de
  cada correção do usuário ao que ela virou.
- `mapa-abrir.json`: o pedido por voz "mostra o seu cérebro".
- `maos-pedido.json`: o pedido por voz "calibrar as mãos" ou "volta as mãos ao padrão".

O desenho fica no Barehands (AGPL, repositório dele); aqui só os dados. Arquivo velho (JARVIS
parado) some da tela: por isso a reescrita periódica mesmo sem mudança.
"""

import contextlib
import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.automacoes.jobs import Jobs
from jarvis.cerebro.consumo import Consumo
from jarvis.habilidades.diario import EVENTOS, Diario
from jarvis.habilidades.revisao import Pendencias
from jarvis.habilidades.skills import Skills
from jarvis.memoria.curta import Memoria
from jarvis.rosto.pasta import GRUPOS, Conexoes

RENOVAR_S = 30.0
NOVO_S = 48 * 3600.0  # aprendido há menos que isso brilha no mapa
DIAS_NO_MEDIDOR = 7
PALAVRAS_NO_ROTULO = 5
EVENTOS_NA_LINHA = 40
DIAS_NO_GRAFICO = 14


def _lido(d: dict[str, Any]) -> int:
    return int(d.get("entrada", 0)) + int(d.get("cache_lido", 0)) + int(d.get("cache_criado", 0))


def rotulo(texto: str) -> str:
    palavras = texto.split()
    curto = " ".join(palavras[:PALAVRAS_NO_ROTULO])
    return curto + ("…" if len(palavras) > PALAVRAS_NO_ROTULO else "")


def id_memoria(alvo: str, texto: str) -> str:
    """Id estável de uma entrada (o texto é a identidade dela): liga a linha do tempo ao mapa."""
    return f"{alvo}:{hashlib.blake2s(texto.encode(), digest_size=5).hexdigest()}"


def decisao(pergunta: str | None, expira: float | None, pendencias: Pendencias) -> dict[str, Any]:
    return {
        "pergunta": {"texto": pergunta, "expira": expira} if pergunta else None,
        "sugestoes": [{"resumo": p.resumo, "origem": p.origem} for p in pendencias.listar()],
    }


def eficiencia(consumo: Consumo) -> dict[str, Any]:
    hoje = consumo.retrato()
    dias: list[dict[str, Any]] = []
    for d in [*consumo.historico()[-(DIAS_NO_MEDIDOR - 1) :], hoje]:
        respostas = int(d.get("respostas", 0))
        dias.append(
            {
                "dia": datetime.fromisoformat(str(d["dia"])).strftime("%d/%m"),
                "respostas": respostas,
                "media": _lido(d) // respostas if respostas else None,
                "locais": int(d.get("locais", 0)),
            }
        )
    anteriores: list[int] = [d["media"] for d in dias[:-1] if d["media"]]
    atual = dias[-1]["media"]
    tendencia = None
    if anteriores and atual:
        base = sum(anteriores) / len(anteriores)
        tendencia = round(100 * (atual - base) / base)
    lido = _lido(hoje)
    return {
        "dias": dias,
        "hoje": {
            **dias[-1],
            "cache": round(100 * int(hoje.get("cache_lido", 0)) / lido) if lido else None,
        },
        "tendencia": tendencia,  # % da média de hoje contra a dos dias anteriores
    }


def mapa(
    conexoes: Conexoes,
    memoria: Memoria,
    skills: Skills,
    jobs: Jobs,
    diario: Diario,
    uso_ferramentas: dict[str, dict[str, int]],
    agora: float,
) -> dict[str, Any]:
    # O diário diz de onde veio cada coisa aprendida: memória pelo texto, skill pelo nome.
    origens: dict[tuple[str, str], dict[str, Any]] = {}
    for ev in reversed(diario.ultimos(500)):  # do mais velho ao mais novo: o último vence
        if ev.get("evento") not in ("aprovada", "memoria", "skill"):
            continue
        chave = ("skill", ev["nome"]) if ev.get("nome") else (ev.get("alvo", ""), ev.get("texto"))
        origens[chave] = {"origem": ev.get("origem", ""), "em": ev.get("em")}

    def aprendido(chave: tuple[str, Any]) -> dict[str, Any]:
        o = origens.get(chave)
        if not o:
            return {"novo": False}
        em = o.get("em") or 0
        return {"origem": o["origem"], "em": em, "novo": agora - em < NOVO_S}

    grupos: list[dict[str, Any]] = []
    for alvo, titulo in (("usuario", "Sobre você"), ("jarvis", "Ambiente")):
        itens = [
            {"id": id_memoria(alvo, e), "rotulo": rotulo(e), "texto": e, **aprendido((alvo, e))}
            for e in memoria.entradas(alvo)
        ]
        grupos.append({"id": alvo, "rotulo": titulo, "itens": itens})

    uso_skills = skills.uso()
    grupos.append(
        {
            "id": "skills",
            "rotulo": "Skills",
            "itens": [
                {
                    "id": f"skill:{nome}",
                    "rotulo": nome,
                    "texto": descricao,
                    "usos": uso_skills.get(nome, {}).get("usos", 0),
                    **aprendido(("skill", nome)),
                }
                for nome, descricao in skills.listar()
            ],
        }
    )

    por_grupo: dict[str, dict[str, Any]] = {}
    for nome, _ in conexoes.proprias:
        grupo = next((g for p, g in GRUPOS.items() if nome.startswith(p)), "Outras")
        item = por_grupo.setdefault(grupo, {"rotulo": grupo, "nomes": [], "usos": 0, "ultimo": 0})
        uso = uso_ferramentas.get(f"mcp__jarvis__{nome}", {})
        item["nomes"].append(nome)
        item["usos"] += uso.get("usos", 0)
        item["ultimo"] = max(item["ultimo"], uso.get("ultimo", 0))
    if conexoes.embutidas:
        usos = [uso_ferramentas.get(n, {}) for n in conexoes.embutidas]
        por_grupo["Internet"] = {
            "rotulo": "Internet",
            "nomes": list(conexoes.embutidas),
            "usos": sum(u.get("usos", 0) for u in usos),
            "ultimo": max((u.get("ultimo", 0) for u in usos), default=0),
        }
    for servidor in conexoes.externos:
        usos = [u for n, u in uso_ferramentas.items() if n.startswith(f"mcp__{servidor}__")]
        por_grupo[servidor] = {
            "rotulo": f"MCP {servidor}",
            "nomes": [servidor],
            "usos": sum(u.get("usos", 0) for u in usos),
            "ultimo": max((u.get("ultimo", 0) for u in usos), default=0),
        }
    grupos.append(
        {
            "id": "conexoes",
            "rotulo": "Conexões",
            "itens": [
                {
                    "id": f"conexao:{g['rotulo']}",
                    "texto": ", ".join(g["nomes"]),
                    **g,
                    "novo": False,
                }
                for g in por_grupo.values()
            ],
        }
    )
    grupos.append(
        {
            "id": "automacoes",
            "rotulo": "Automações",
            "itens": [
                {
                    "id": f"automacao:{j.id}",
                    "rotulo": j.nome,
                    "texto": j.texto,
                    "ativo": j.ativo,
                    "novo": False,
                }
                for j in jobs.listar()
            ],
        }
    )
    eventos = diario.ultimos(500)
    ids = {it["id"] for g in grupos for it in g["itens"]}
    return {
        "centro": {"rotulo": "JARVIS", "sub": conexoes.cerebro},
        "grupos": grupos,
        "linha_do_tempo": [_evento(ev, ids) for ev in eventos[:EVENTOS_NA_LINHA]],
        "por_dia": _por_dia(eventos, agora),
        "aprendizado": {
            "aprovadas": sum(1 for ev in eventos if ev.get("evento") == "aprovada"),
            "recentes": sum(
                1
                for ev in eventos
                if ev.get("evento") in ("aprovada", "memoria", "skill")
                and agora - (ev.get("em") or 0) < NOVO_S
            ),
        },
    }


def _evento(ev: dict[str, Any], ids: set[str]) -> dict[str, Any]:
    """Uma linha da história do aprendizado, ligada ao item do mapa se ele ainda existir."""
    if ev.get("nome"):
        alvo = f"skill:{ev['nome']}"
    elif ev.get("alvo") and ev.get("texto"):
        alvo = id_memoria(str(ev["alvo"]), str(ev["texto"]))
    else:
        alvo = ""
    evento = str(ev.get("evento", ""))
    return {
        "em": ev.get("em"),
        "evento": evento,
        "rotulo": EVENTOS.get(evento, evento),
        "resumo": ev.get("resumo", ""),
        "origem": ev.get("origem", ""),
        "item": alvo if alvo in ids else None,
    }


def _por_dia(eventos: list[dict[str, Any]], agora: float) -> list[dict[str, Any]]:
    """Aprendizados por dia (aprovados e gravados a pedido): o cérebro crescendo."""
    contagem: dict[str, int] = {}
    for ev in eventos:
        if ev.get("evento") in ("aprovada", "memoria", "skill") and ev.get("em"):
            dia = datetime.fromtimestamp(ev["em"]).date().isoformat()
            contagem[dia] = contagem.get(dia, 0) + 1
    hoje = datetime.fromtimestamp(agora).date()
    dias = [hoje.fromordinal(hoje.toordinal() - i) for i in range(DIAS_NO_GRAFICO - 1, -1, -1)]
    return [{"dia": d.strftime("%d/%m"), "n": contagem.get(d.isoformat(), 0)} for d in dias]


class Hud:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self.trava = threading.Lock()  # o laço (decisão) e a thread da pasta (o resto) escrevem
        self.mostrado: dict[str, tuple[Any, float]] = {}

    def gravar(self, nome: str, dados: dict[str, Any], agora: float) -> bool:
        """Grava `state/<nome>.json` se mudou ou se está para envelhecer; True se gravou."""
        with self.trava:
            anterior = self.mostrado.get(nome)
            if anterior and anterior[0] == dados and agora - anterior[1] < RENOVAR_S:
                return False
            self.mostrado[nome] = (dados, agora)
        with contextlib.suppress(OSError):
            arquivo = self.pasta / f"{nome}.json"
            temporario = arquivo.with_name(f".{nome}.next")
            temporario.write_text(json.dumps({**dados, "ts": agora}, ensure_ascii=False))
            temporario.replace(arquivo)
        return True

    def abrir_mapa(self) -> None:
        self.gravar("mapa-abrir", {"pedido": time.time()}, time.time())

    def pedir_maos(self, acao: str) -> None:
        """`maos-pedido.json`: calibrar as mãos ou voltar ao padrão, pedido por voz."""
        self.gravar("maos-pedido", {"pedido": time.time(), "acao": acao}, time.time())
