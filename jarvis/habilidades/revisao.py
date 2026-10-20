"""Revisão em segundo plano: o Zé aprende com a conversa (Fase 6; o que fez o Hermes famoso).

No fim de uma conversa que valha a pena (correção do usuário ou pelo menos `MINIMO_TURNOS`), um
modelo menor relê só aquela conversa, com a memória e as skills atuais, e propõe o que guardar.
Cada proposta passa pelas mesmas checagens da escrita normal e vira **pendência**: nada é gravado
sem o usuário aprovar por voz. Economia e eficácia: ADR 0011 (se aprender menos que o Hermes, a
regra volta a ser a dele).

Os critérios do prompt são adaptados de `agent/background_review.py` do Hermes Agent (Nous
Research, MIT; ver THIRD_PARTY.md): skill é como fazer bem uma classe de tarefa do jeito do
usuário; correção de estilo é sinal de primeira classe; não registrar falha de ambiente,
afirmação negativa sobre ferramenta, erro passageiro, narrativa de tarefa única nem tentativa que
não deu certo.
"""

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jarvis import usuario
from jarvis.habilidades.skills import SkillErro, Skills
from jarvis.memoria.curta import Memoria, MemoriaErro, Mudanca

MINIMO_TURNOS = 4
LIMITE_ORIGEM = 240
LIMITE_SKILLS_NO_PROMPT = 12_000
SINAIS = re.compile(
    r"n[aã]o [eé] (assim|isso)|errad|errou|para de |pare de |n[aã]o fa[cç]a|da pr[oó]xima vez|"
    r"prefiro|n[aã]o gosto|sempre que|nunca mais|eu quero que|quero que voc[eê]|lembr|guard|anot",
    re.IGNORECASE,
)

PROMPT = """Você revisa uma conversa entre o usuário e o Zé, o assistente de voz dele, para \
o Zé aprender. Proponha só o que fará a próxima conversa sair melhor de primeira.

Dois lugares, um fato vai para um só:
- memória "usuario": quem o usuário é, preferências, jeito de trabalhar, o que ele espera do \
Zé;
- memória "jarvis": fatos do ambiente (máquina, projetos, ferramentas, caminhos, convenções);
- skill: como fazer bem uma CLASSE de tarefa, do jeito do usuário (procedimento na ordem, \
armadilhas como regra geral + o porquê em uma frase). Nome no nível da classe, nunca de uma \
tarefa de hoje.

Sinais que pedem ação: o usuário corrigiu estilo, tom, tamanho ou formato da resposta (sinal de \
primeira classe); corrigiu o jeito ou a ordem de fazer algo; apareceu uma técnica que vale \
repetir; uma skill usada estava errada ou incompleta (corrija o trecho, não acrescente \
"atualização" embaixo).

NÃO proponha: falha de ambiente (programa faltando, credencial não configurada); afirmação \
negativa sobre ferramenta ("X não funciona"); erro passageiro que se resolveu; narrativa de \
tarefa única; tentativas que não deram certo apresentadas como método; nada que já esteja na \
memória ou nas skills abaixo; nada que veio da internet ou de outro agente sem o usuário \
confirmar.

Correção de estilo ou do jeito de responder vale para tudo: além de ajustar a skill da \
tarefa, se houver, ponha a regra geral na memória "usuario" em uma frase.

Prefira, nesta ordem: corrigir uma skill existente; trocar uma entrada de memória; criar memória \
nova; criar skill nova. Memória: uma frase curta e duradoura. Se nada vale, devolva listas \
vazias.

Responda SÓ com JSON, sem texto em volta:
{{"memoria": [{{"acao": "adicionar|trocar|remover", "alvo": "usuario|jarvis", "texto": "...", \
"antigo": "trecho único da entrada, para trocar/remover"}}],
"skills": [{{"acao": "criar|corrigir", "nome": "minusculas-com-hifen", "conteudo": "SKILL.md \
inteiro com front matter name/description (só para criar)", "trecho_antigo": "...", \
"trecho_novo": "... (só para corrigir)"}}]}}

{memoria}

## Skills atuais (conteúdo)
{skills}

## Conversa
{conversa}
"""


def vale_revisar(turnos: list[dict[str, str]]) -> bool:
    if not turnos:
        return False
    if len(turnos) >= MINIMO_TURNOS:
        return True
    return any(SINAIS.search(t.get("pessoa", "")) for t in turnos)


def origem(turnos: list[dict[str, str]]) -> str:
    """De onde a sugestão veio, para o diário: as falas do usuário com correção, ou a primeira."""
    falas = [t.get("pessoa", "").strip() for t in turnos]
    com_sinal = [f for f in falas if SINAIS.search(f)] or falas[:1]
    return " / ".join(com_sinal)[:LIMITE_ORIGEM]


def montar_prompt(turnos: list[dict[str, str]], memoria: Memoria, skills: Skills) -> str:
    corpos, tamanho = [], 0
    for nome, _ in skills.listar():
        corpo = skills.atual(nome)
        if tamanho + len(corpo) > LIMITE_SKILLS_NO_PROMPT:
            corpos.append(f"(skill {nome} omitida por tamanho)")
            continue
        corpos.append(f"### {nome}\n{corpo}")
        tamanho += len(corpo)
    conversa = "\n".join(
        f"{usuario.PERFIL.rotulo}: {t.get('pessoa', '')}\nJARVIS: {t.get('jarvis', '')}"
        for t in turnos
    )
    return PROMPT.format(
        memoria=memoria.foto(), skills="\n\n".join(corpos) or "(nenhuma)", conversa=conversa
    )


@dataclass
class Proposta:
    tipo: str  # memoria, skill
    dados: dict[str, str]
    resumo: str  # falável
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:6])
    criada: float = field(default_factory=time.time)
    origem: str = ""  # a fala do usuário que gerou a sugestão (diário de aprendizado)


def resumo_da_memoria(m: Mudanca) -> str:
    return _resumo(
        "memoria", {"acao": m.acao, "alvo": m.alvo, "texto": m.texto, "antigo": m.antigo}
    )


def _resumo(tipo: str, d: dict[str, str]) -> str:
    if tipo == "memoria":
        dono = "sobre você" if d.get("alvo") == "usuario" else "nas minhas notas"
        if d.get("acao") == "remover":
            return f"tirar da memória {dono}: {d.get('antigo', '')}"
        return f"guardar na memória {dono}: {d.get('texto', '')}"
    verbo = "criar" if d.get("acao") == "criar" else "corrigir"
    return f"{verbo} a skill {d.get('nome', '')}"


def interpretar(saida: str, memoria: Memoria, skills: Skills) -> list[Proposta]:
    """Só as propostas que passariam na escrita de verdade; o resto é descartado em silêncio."""
    achado = re.search(r"\{.*\}", saida, re.DOTALL)
    if not achado:
        return []
    try:
        dados = json.loads(achado.group(0))
    except ValueError:
        return []
    propostas = []
    for item in dados.get("memoria") or []:
        if not isinstance(item, dict):
            continue
        d = {k: str(item.get(k, "")) for k in ("acao", "alvo", "texto", "antigo")}
        try:
            memoria.resultado(Mudanca(d["acao"], d["alvo"], d["texto"], d["antigo"]))
        except MemoriaErro:
            continue
        propostas.append(Proposta("memoria", d, _resumo("memoria", d)))
    for item in dados.get("skills") or []:
        if not isinstance(item, dict):
            continue
        d = {
            k: str(item.get(k, ""))
            for k in ("acao", "nome", "conteudo", "trecho_antigo", "trecho_novo")
        }
        try:
            conteudo = skills.novo_conteudo(
                d["nome"],
                conteudo=d["conteudo"] if d["acao"] == "criar" else "",
                antigo=d["trecho_antigo"] if d["acao"] == "corrigir" else "",
                novo=d["trecho_novo"],
            )
        except SkillErro:
            continue
        propostas.append(Proposta("skill", {**d, "final": conteudo}, _resumo("skill", d)))
    return propostas


class Pendencias:
    """Propostas esperando o usuário; sobrevivem a reinícios."""

    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo

    def listar(self) -> list[Proposta]:
        try:
            brutas = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return []
        return [Proposta(**p) for p in brutas if isinstance(p, dict)]

    def _gravar(self, propostas: list[Proposta]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps([asdict(p) for p in propostas], ensure_ascii=False))
        temporario.chmod(0o600)
        temporario.replace(self.arquivo)

    def adicionar(self, novas: list[Proposta]) -> None:
        self._gravar([*self.listar(), *novas])

    def tirar(self, id_: str) -> Proposta:
        todas = self.listar()
        achada = next((p for p in todas if p.id == id_), None)
        if achada is None:
            raise KeyError(id_)
        self._gravar([p for p in todas if p.id != id_])
        return achada

    def achar(self, id_: str) -> Proposta | None:
        return next((p for p in self.listar() if p.id == id_), None)


def aplicar(proposta: Proposta, memoria: Memoria, skills: Skills) -> None:
    d = proposta.dados
    if proposta.tipo == "memoria":
        memoria.aplicar(Mudanca(d["acao"], d["alvo"], d.get("texto", ""), d.get("antigo", "")))
        return
    # A skill pode ter mudado desde a proposta: recalcula e revalida antes de gravar.
    conteudo = skills.novo_conteudo(
        d["nome"],
        conteudo=d["conteudo"] if d["acao"] == "criar" else "",
        antigo=d["trecho_antigo"] if d["acao"] == "corrigir" else "",
        novo=d.get("trecho_novo", ""),
    )
    skills.gravar(d["nome"], conteudo)


def alvo_da_proposta(p: Proposta) -> dict[str, str]:
    """O que a proposta muda, para o diário ligar a origem ao que ela virou (mapa do cérebro)."""
    d = p.dados
    if p.tipo == "memoria":
        return {"alvo": d.get("alvo", ""), "texto": d.get("texto", "")}
    return {"nome": d.get("nome", "")}


def resumo_dict(p: Proposta) -> dict[str, Any]:
    return {"id": p.id, "tipo": p.tipo, "resumo": p.resumo}


SISTEMA = "Você revisa conversas para um assistente aprender. Responda só com o JSON pedido."


async def perguntar_ao_modelo(
    prompt: str, modelo: str, pasta: Path, pensamento: int = 1500, sistema: str = ""
) -> tuple[str, dict[str, Any] | None]:
    """Uma consulta só, sem ferramentas, pela assinatura do Claude Code (ADR 0011: modelo menor)."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    opcoes = ClaudeAgentOptions(
        system_prompt=sistema or SISTEMA,  # outra consulta (a nota do dia) traz a sua
        tools=[],
        allowed_tools=[],
        permission_mode="default",
        setting_sources=[],
        strict_mcp_config=True,
        model=modelo,
        cwd=str(pasta),
        max_turns=1,
        # Prova de 06/10/2026 na mesma conversa: pensamento livre gastou 2.744 tokens em 27 s;
        # sem pensar (4 s) perdeu a correção de estilo; 1.500 de orçamento pegou estilo na
        # memória e a regra numa skill de classe, como o Hermes, em 11 s com o Haiku.
        thinking={"type": "enabled", "budget_tokens": pensamento}
        if pensamento
        else {"type": "disabled"},
    )
    texto, uso = "", None
    async for msg in query(prompt=prompt, options=opcoes):
        if isinstance(msg, AssistantMessage):
            texto += "".join(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            uso = msg.usage
    return texto, uso
