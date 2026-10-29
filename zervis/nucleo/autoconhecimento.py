"""O Zé por ele mesmo (ADR 0043 e 0045): como está configurado, o que sabe fazer e o que fez.

Pedido da pessoa em 27/10/2026, depois de o Zé não saber dizer qual modelo respondia no Live:
ele precisa se entender como um sistema independente do modelo que estiver por trás, para
responder e ajudar quem usa, também por voz. Um retrato só, de onde saem as três leituras:
- a ferramenta `ze_sobre`, que o cérebro completo consulta (Claude, Codex ou outro);
- o resumo que a via rápida recebe ao subir, para responder sem passar a vez;
- a nota "Quem sou" da pasta do Zé.

Desde 29/10/2026 (ADR 0045) o retrato vai além da configuração: o que o Zé sabe fazer (as
próprias ferramentas por grupo, as skills, os conectores, as sessões, as automações, a memória) e o
que ele fez nos últimos dias (a Atividade). A mesma fonte vira texto para os modelos e dados para a
tela (`dados`), de onde saem as apresentações da Imersão: a tela só mostra o que o Zé sabe de si.

Sem segredo nenhum: chaves, senhas e tokens nunca entram, só se existem.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, NamedTuple


@dataclass(frozen=True)
class Retrato:
    """O momento: cada campo já em português falado, pronto para ler ou dizer."""

    cerebro: str  # quem responde os pedidos com ação: "Codex, com o GPT-6 Luna"
    modelo: str = ""  # só o modelo do cérebro ("GPT-6 Luna"), para a tela
    provedor: str = ""  # só quem o serve ("Codex"), para a tela
    modelo_das_rapidas: str = ""  # o modelo das respostas rápidas quando ligadas, para a tela
    reserva: str = ""
    rapidas: str = ""  # as respostas rápidas: motor, modelo e quando valem
    rapidas_agora: bool = False  # se é a via rápida que está respondendo a conversa agora
    rapidas_modelo: str = ""  # o modelo dela, para "qual modelo está me respondendo?"
    voz: str = ""
    escuta: str = ""
    live: str = ""  # o Live: conectado, disponível ou o motivo de estar indisponível
    modo: str = ""  # Silencioso, Normal ou Live
    ativacao: str = ""
    espera: str = ""
    acesso: str = ""  # de onde dá para falar com o Zé: o PC, o endereço, o app
    contas: str = ""
    maquina: str = ""
    versao: str = ""
    extras: list[str] = field(default_factory=list)


# O que cada grupo de ferramentas do servidor `jarvis` faz, em uma linha (as chaves são os módulos
# de `zervis/cerebro/ferramentas`). Grupo novo sem linha aqui entra com o nome do módulo.
GRUPOS = {
    "sessoes": ("Sessões de código", "abre, acompanha e conduz sessões com os agentes"),
    "tela": ("Tela", "vê e mexe na própria tela e abre ou fecha a janela"),
    "sistema": ("Sistema", "consulta o estado da máquina e roda as ações do sistema"),
    "automacoes": ("Automações", "agenda lembretes e perguntas e muda as automações"),
    "aprendizado": ("Aprendizado", "guarda memória, busca no histórico e cria ou corrige skills"),
    "manutencao": ("Manutenção", "melhora o próprio código numa cópia isolada"),
    "navegador": ("Navegador", "continua a leitura de uma página da internet"),
    "conectores": ("Conectores", "lista, testa e cadastra integrações com outros sistemas"),
    "atualizacoes": ("Atualizações", "verifica se há versão nova do Zé"),
    "sobre": ("Autoconhecimento", "descreve a própria configuração, capacidades e atividade"),
    "pesquisa": ("Pesquisa na internet", "pesquisa notícias e assuntos, com as fontes"),
}


class Grupo(NamedTuple):
    chave: str
    nome: str
    faz: str
    ferramentas: tuple[str, ...]
    livres: int  # quantas passam sem perguntar (só leem ou são reversíveis)


class Skill(NamedTuple):
    nome: str
    descricao: str
    usos: int


class Conector(NamedTuple):
    nome: str
    livres: int  # ferramentas liberadas para o Zé
    bloqueadas: int


class Sessao(NamedTuple):
    nome: str
    agente: str
    estado: str


class Automacao(NamedTuple):
    nome: str
    agenda: str
    ativa: bool


@dataclass(frozen=True)
class Capacidades:
    """O que o Zé sabe fazer agora: as próprias ferramentas e o que está ligado a ele."""

    grupos: tuple[Grupo, ...] = ()
    skills: tuple[Skill, ...] = ()
    conectores: tuple[Conector, ...] = ()
    sessoes: tuple[Sessao, ...] = ()
    automacoes: tuple[Automacao, ...] = ()
    lembrancas: int = 0  # entradas da memória curta (sobre a pessoa e sobre o próprio Zé)
    paginas: int | None = None  # páginas da memória das sessões (ai-memory); None sem ela
    whatsapp: str = ""  # "conectado" ou "desligado"; vazio sem a Central

    @property
    def ferramentas(self) -> int:
        return sum(len(g.ferramentas) for g in self.grupos)


class Dia(NamedTuple):
    dia: str  # AAAA-MM-DD, no fuso de quem usa
    registros: int
    falhas: int


@dataclass(frozen=True)
class Historico:
    """O que o Zé fez nos últimos dias, da Atividade (ADR 0025)."""

    dias: int = 7
    contagem: Mapping[str, int] = field(default_factory=dict)  # pedido, execucao, falha…
    por_dia: tuple[Dia, ...] = ()
    mais_usadas: tuple[tuple[str, int], ...] = ()  # ferramenta, vezes
    recentes: tuple[tuple[float, str, str], ...] = ()  # quando (época), tipo, título


def grupos(por_grupo: Mapping[str, Sequence[str]], livres: Collection[str]) -> tuple[Grupo, ...]:
    """Os grupos das ferramentas do Zé, com o que cada um faz e quantas passam sem perguntar."""
    return tuple(
        Grupo(chave, *GRUPOS.get(chave, (chave, "")), tuple(nomes), sum(n in livres for n in nomes))
        for chave, nomes in por_grupo.items()
        if nomes
    )


def nome_da_ferramenta(nome: str) -> str:
    """`mcp__n8n__criar` vira "n8n · criar"; as do próprio Zé ficam só com o nome."""
    if nome.startswith("mcp__"):
        servidor, _, ferramenta = nome[5:].partition("__")
        return ferramenta if servidor == "jarvis" else f"{servidor} · {ferramenta}"
    return nome


# A pesquisa vale com qualquer cérebro (ADR 0044): o Zé dizia "não tenho a ferramenta de pesquisa"
# com o Codex e, minutos antes, "consigo acessar a internet" (caso real de 27/10/2026).
PESQUISA = (
    "sim, direto, sem abrir sessão (internet_pesquisar): notícias, fatos recentes, preços, um "
    "assunto resumido; as fontes vão para a tela. Vai pela conta do Codex e, sem ela, pelo Claude."
)


def quem_responde(r: Retrato) -> str:
    """A frase de "qual modelo você está usando?", agora."""
    if r.rapidas_agora and r.rapidas_modelo:
        return (
            f"Na conversa, quem responde é a via rápida, com o {r.rapidas_modelo}; o que pede "
            f"ferramenta ou ação vai ao cérebro completo ({r.cerebro})."
        )
    return f"Quem responde é o cérebro completo: {r.cerebro}."


def texto(r: Retrato, cap: Capacidades | None = None, hist: Historico | None = None) -> str:
    """O retrato inteiro, em Markdown curto (a ferramenta `ze_sobre` e a nota "Quem sou")."""
    linhas = [
        "## Agora",
        f"- **Quem responde:** {quem_responde(r)}",
        *([f"- **Reserva do cérebro:** {r.reserva}"] if r.reserva else []),
        *([f"- **Respostas rápidas:** {r.rapidas}"] if r.rapidas else []),
        f"- **Pesquisa na internet:** {PESQUISA}",
        *([f"- **Modo de fala:** {r.modo}"] if r.modo else []),
        *([f"- **Live (conversa em tempo real):** {r.live}"] if r.live else []),
        *([f"- **Voz:** {r.voz}"] if r.voz else []),
        *([f"- **Escuta:** {r.escuta}"] if r.escuta else []),
        *([f"- **Ativação:** {r.ativacao}"] if r.ativacao else []),
        *([f"- **Espera (fim da fala):** {r.espera}"] if r.espera else []),
        *([f"- **Acesso:** {r.acesso}"] if r.acesso else []),
        *([f"- **Contas dos agentes:** {r.contas}"] if r.contas else []),
        *([f"- **Esta máquina:** {r.maquina}"] if r.maquina else []),
        *([f"- **Versão do Zé:** {r.versao}"] if r.versao else []),
        *(f"- {x}" for x in r.extras),
    ]
    partes = ["\n".join(linhas)]
    if cap is not None:
        partes.append(texto_das_capacidades(cap))
    if hist is not None:
        partes.append(texto_do_historico(hist))
    return "\n\n".join(partes) + "\n\n" + MAPA


def _lista(itens: Sequence[str], maximo: int) -> str:
    resto = len(itens) - maximo
    return "; ".join(itens[:maximo]) + (f"; e mais {resto}" if resto > 0 else "")


def texto_das_capacidades(c: Capacidades) -> str:
    """O que o Zé sabe fazer, para ele responder "o que você faz?" sem inventar."""
    linhas = [f"## O que eu sei fazer ({c.ferramentas} ferramentas próprias)"]
    linhas += [f"- **{g.nome}** ({len(g.ferramentas)}): {g.faz}." for g in c.grupos]
    if c.skills:
        usadas = [f"{s.nome} ({s.usos} usos)" if s.usos else s.nome for s in c.skills]
        linhas.append(f"- **Skills ({len(c.skills)}):** {_lista(usadas, 8)}.")
    if c.conectores:
        conectores = [f"{x.nome} ({x.livres} ferramentas liberadas)" for x in c.conectores]
        linhas.append(f"- **Conectores:** {_lista(conectores, 6)}.")
    if c.sessoes:
        sessoes = [f"{x.nome} ({x.agente}, {x.estado})" for x in c.sessoes]
        linhas.append(f"- **Sessões de código ({len(c.sessoes)}):** {_lista(sessoes, 6)}.")
    if c.automacoes:
        autos = [f"{x.nome} ({x.agenda}{'' if x.ativa else ', pausada'})" for x in c.automacoes]
        linhas.append(f"- **Automações ({len(c.automacoes)}):** {_lista(autos, 6)}.")
    memoria = f"{c.lembrancas} lembranças"
    if c.paginas is not None:
        memoria += f"; {c.paginas} páginas na memória das sessões"
    linhas.append(f"- **Memória:** {memoria}.")
    if c.whatsapp:
        linhas.append(f"- **WhatsApp:** {c.whatsapp}.")
    return "\n".join(linhas)


def texto_do_historico(h: Historico) -> str:
    """O que o Zé fez nos últimos dias, em números."""
    q = h.contagem
    linhas = [
        f"## O que eu fiz (últimos {h.dias} dias)",
        f"- {q.get('pedido', 0)} pedidos atendidos, {q.get('execucao', 0)} ações executadas, "
        f"{q.get('falha', 0)} falhas, {q.get('negada', 0)} negadas, "
        f"{q.get('nao_entendi', 0)} não entendidos, {q.get('correcao', 0)} correções.",
    ]
    if h.mais_usadas:
        usadas = [f"{nome_da_ferramenta(n)} ({v} vezes)" for n, v in h.mais_usadas]
        linhas.append(f"- **Mais executadas:** {_lista(usadas, 6)}.")
    if h.por_dia:
        dias = [
            f"{date.fromisoformat(d.dia):%d/%m}: {d.registros}"
            + (f" ({d.falhas} falhas)" if d.falhas else "")
            for d in h.por_dia
        ]
        linhas.append(f"- **Por dia:** {'; '.join(dias)}.")
    return "\n".join(linhas)


def dados(r: Retrato, cap: Capacidades, hist: Historico) -> dict[str, Any]:
    """O mesmo retrato para a tela (as apresentações da Imersão, ADR 0045): só dados, sem
    segredo, e sem o acesso nem as contas, que a tela não precisa mostrar."""
    return {
        "agora": {
            "quem_responde": quem_responde(r),
            "cerebro": r.cerebro,
            "modelo": r.modelo,
            "provedor": r.provedor,
            "reserva": r.reserva,
            "rapidas": r.rapidas,
            "rapidas_agora": r.rapidas_agora,
            "modelo_das_rapidas": r.modelo_das_rapidas,
            "voz": r.voz,
            "escuta": r.escuta,
            "live": r.live,
            "modo": r.modo,
            "ativacao": r.ativacao,
            "espera": r.espera,
            "maquina": r.maquina,
            "versao": r.versao,
        },
        "capacidades": {
            "ferramentas": cap.ferramentas,
            "grupos": [g._asdict() | {"ferramentas": list(g.ferramentas)} for g in cap.grupos],
            "skills": [s._asdict() for s in cap.skills],
            "conectores": [x._asdict() for x in cap.conectores],
            "sessoes": [x._asdict() for x in cap.sessoes],
            "automacoes": [x._asdict() for x in cap.automacoes],
            "lembrancas": cap.lembrancas,
            "paginas": cap.paginas,
            "whatsapp": cap.whatsapp,
        },
        "historico": {
            "dias": hist.dias,
            "contagem": dict(hist.contagem),
            "por_dia": [d._asdict() for d in hist.por_dia],
            "mais_usadas": [
                {"ferramenta": nome_da_ferramenta(n), "vezes": v} for n, v in hist.mais_usadas
            ],
            "recentes": [{"quando": q, "tipo": t, "titulo": x} for q, t, x in hist.recentes],
        },
    }


def resumo(r: Retrato) -> str:
    """O que a via rápida recebe ao subir: o bastante para responder sobre si sem passar a vez."""
    partes = [quem_responde(r)]
    for rotulo, valor in (
        ("Modo de fala", r.modo),
        ("Voz", r.voz),
        ("Escuta", r.escuta),
        ("Live", r.live),
    ):
        if valor:
            partes.append(f"{rotulo}: {valor}.")
    return (
        "## Você agora (configuração do Zé)\n"
        + " ".join(partes)
        + " Pesquisa na internet: sim, pelo cérebro completo; para pesquisar, passe a vez."
        + "\nPerguntas sobre você (modelo, voz, modos, configurações): responda com isto, sem "
        "inventar. Para mudar alguma coisa ou para o que não estiver aqui, passe a vez."
    )


# Onde se muda cada coisa: o Zé ajuda quem usa a encontrar, por voz ou pelo painel.
MAPA = """## Onde mudar
- **Modo de fala** (Silencioso, Normal, Live): página Voz, o atalho Alt+M ou por voz ("modo
  silencioso", "modo normal", "modo live").
- **Live:** o modo Live, com a voz do aparelho conectada: no navegador, o botão "Conectar voz"
  (embaixo do menu, ao lado de "Falar"); no app do celular, "Ao vivo" na notificação. Sem a
  chave do Deepgram ou o detector de fim de fala baixado, a voz ao vivo segue sem o tempo real.
- **Voz do Zé** (Cadu, ElevenLabs, Fish Audio e a voz de cada um): página Voz → Voz do Zé.
- **Espera e ativação** ("Ei Zé" ou só o botão): página Voz.
- **Cérebro** (Claude, Codex ou outro): página Modelos, ou por voz ("troca para o Claude").
- **Respostas rápidas** (motor, modelo, só no Live ou sempre): Modelos → Respostas rápidas, com o
  botão Testar mostrando a primeira palavra.
- **Contas** (as assinaturas e as chaves dos provedores): Modelos → Contas.
- **Escuta** (a chave do Deepgram): Modelos → Reconhecimento de fala.
- **Celular:** Voz → Acesso pelo celular (senha, código do autenticador e o endereço) e o app de
  voz. Desligar o código desliga também o acesso de qualquer lugar.
- **Atualizações do Zé:** página Atualizações.
"""
