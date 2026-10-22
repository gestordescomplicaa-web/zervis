"""O cérebro do Zé na tela do Barehands (pedido do usuário, 06/10/2026).

Mesmo contrato do anel e do painel: o Zé escreve JSONs pequenos em `state/` e a página lê.
- `decisao.json`: a pergunta que espera o "sim" agora (com o prazo) e as sugestões pendentes.
- `eficiencia.json`: tokens lidos por resposta nos últimos dias e o que saiu sem o cérebro.
- `mapa.json`: o Mapa (perfil, memória, skills e automações) com as ligações de cada correção
  do usuário ao que ela virou.
- `trabalho.json`: as sessões de agentes de código do Zé (a vista Trabalho e o orbe Trabalho).
- `orbes.json`: quais orbes aparecem (só os que têm conteúdo) e se o modo desenvolvedor está
  ligado (medidores de CPU, GPU, baterias dos modelos e tokens).
- `mapa-abrir.json`: o pedido por voz "mostra o seu cérebro".
- `maos-pedido.json`: o pedido por voz "calibrar as mãos" ou "volta as mãos ao padrão".

O desenho fica em `jarvis/imersivo/web/` (ADR 0014); aqui só os dados. Arquivo velho (Zé
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
from jarvis.rosto.pasta import Conexoes
from jarvis.usuario import Perfil

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
    agora: float,
    perfil: Perfil | None = None,
) -> dict[str, Any]:
    """O que o Zé sabe e faz, para o Mapa do modo imersivo: quem você é, memória, skills e
    automações. As ferramentas (conexões) ficam no painel: são configuração, não visualização."""
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
        if alvo == "usuario" and perfil is not None and (perfil.nome or perfil.sobre):
            texto = ". ".join(t for t in (perfil.nome, perfil.sobre) if t)
            itens.insert(0, {"id": "perfil", "rotulo": perfil.nome or "Perfil", "texto": texto})
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
        "centro": {"rotulo": "Zé", "sub": conexoes.cerebro},
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


def trabalho(sessoes: list[Any]) -> dict[str, Any]:
    """As sessões de agentes de código do Zé, no formato da vista Trabalho."""
    return {
        "disponivel": True,
        "sessoes": [
            {
                "id": s.id,
                "rotulo": s.nome,
                "estado": s.estado,
                "pasta": Path(s.pasta).name,
                "texto": s.resumo,
                "atualizada": s.atualizada,
            }
            for s in sessoes
        ],
    }


def orbes(
    foco: dict[str, Any],
    sessoes: int,
    desenvolvedor: bool,
    tem_automacao: bool,
    tem_acervo: bool = False,
) -> dict[str, Any]:
    """Os orbes que aparecem: Mapa e Guia sempre; Hoje, Trabalho e Acervo só com conteúdo."""
    visiveis = ["mapa"]
    if foco.get("atual") or foco.get("ativas") or foco.get("ideias") or tem_automacao:
        visiveis.append("hoje")
    if sessoes:
        visiveis.append("trabalho")
    if tem_acervo:
        visiveis.append("acervo")
    visiveis.append("guia")
    return {"visiveis": visiveis, "desenvolvedor": desenvolvedor}
