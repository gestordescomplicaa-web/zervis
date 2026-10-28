"""O Zé por ele mesmo (ADR 0043): como ele está configurado agora, em texto que qualquer modelo lê.

Pedido da pessoa em 27/10/2026, depois de o Zé não saber dizer qual modelo respondia no Live:
ele precisa se entender como um sistema independente do modelo que estiver por trás, para
responder e ajudar quem usa, também por voz. Um retrato só, de onde saem as três leituras:
- a ferramenta `ze_sobre`, que o cérebro completo consulta (Claude, Codex ou outro);
- o resumo que a via rápida recebe ao subir, para responder sem passar a vez;
- a nota "Quem sou" da pasta do Zé.

Sem segredo nenhum: chaves, senhas e tokens nunca entram, só se existem.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Retrato:
    """O momento: cada campo já em português falado, pronto para ler ou dizer."""

    cerebro: str  # quem responde os pedidos com ação: "Codex, com o GPT-6 Luna"
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


def texto(r: Retrato) -> str:
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
    return "\n".join(linhas) + "\n\n" + MAPA


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
