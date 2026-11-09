"""O Zé descrevendo a si mesmo (ADR 0043): o retrato, as capacidades, o histórico e as
conexões da pasta do Zé, sem segredos. Funções do núcleo, tiradas de `laco.py`."""

import dataclasses
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zervis import __version__, atividade, fuso
from zervis.avisos import modo as modo_fala
from zervis.cerebro import (
    catalogo,
    conectores,
    contas,
    ferramentas,
    rapido,
)
from zervis.memoria import aimemory
from zervis.nucleo import autoconhecimento
from zervis.nucleo.apoio import AJUSTES_DA_TELA as AJUSTES_DA_TELA
from zervis.nucleo.apoio import AVISO_RECENTE_S as AVISO_RECENTE_S
from zervis.nucleo.apoio import BATERIAS_S as BATERIAS_S
from zervis.nucleo.apoio import CHAMADOS_GUARDADOS as CHAMADOS_GUARDADOS
from zervis.nucleo.apoio import CURADORIA_S as CURADORIA_S
from zervis.nucleo.apoio import DADOS as DADOS
from zervis.nucleo.apoio import EM_SEGUNDO_PLANO as EM_SEGUNDO_PLANO
from zervis.nucleo.apoio import ESTADO as ESTADO
from zervis.nucleo.apoio import FALAS_DA_VOLTINHA as FALAS_DA_VOLTINHA
from zervis.nucleo.apoio import FALAS_DE_TONTO as FALAS_DE_TONTO
from zervis.nucleo.apoio import FALHA_NO_CEREBRO as FALHA_NO_CEREBRO
from zervis.nucleo.apoio import JANELA_FALADA as JANELA_FALADA
from zervis.nucleo.apoio import LIMITE_ESCRITO as LIMITE_ESCRITO
from zervis.nucleo.apoio import OFERTA_S as OFERTA_S
from zervis.nucleo.apoio import PASTA_S as PASTA_S
from zervis.nucleo.apoio import PERSONA as PERSONA
from zervis.nucleo.apoio import PERSONA_RAPIDA as PERSONA_RAPIDA
from zervis.nucleo.apoio import PRIMEIRA_FALA_S as PRIMEIRA_FALA_S
from zervis.nucleo.apoio import VENDO_S as VENDO_S
from zervis.nucleo.apoio import Status as Status
from zervis.nucleo.apoio import com_argumento as com_argumento
from zervis.nucleo.apoio import criar_bip as criar_bip
from zervis.nucleo.apoio import criar_toque as criar_toque
from zervis.nucleo.apoio import foto_da_memoria as foto_da_memoria
from zervis.nucleo.apoio import gravar_json as gravar_json
from zervis.nucleo.apoio import ler_json as ler_json
from zervis.nucleo.apoio import nivel_de_pico as nivel_de_pico
from zervis.nucleo.apoio import primeiro_de as primeiro_de
from zervis.nucleo.apoio import versoes_das_skills as versoes_das_skills
from zervis.rosto import pasta
from zervis.sistema import maquina as maquina_atual
from zervis.voz import chamado, espera
from zervis.voz.live import live_ativo

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.nucleo.laco")
# Como o retrato diz cada motor das respostas rápidas (ADR 0043).
NOMES_DOS_MOTORES = {
    "plano": "o Claude pela assinatura",
    "codex": "o Codex pela assinatura",
    "contas": "as contas dos agentes",
    "anthropic": "a API da Anthropic",
    "openai": "a API da OpenAI",
    "openrouter": "o OpenRouter",
    "ponte": "uma ponte compatível com a OpenAI",
    "omniroute": "o OmniRoute",
}

if TYPE_CHECKING:
    from zervis.nucleo.laco import Nucleo


def _conexoes(n: "Nucleo") -> pasta.Conexoes:
    c, r = n.cfg["cerebro"], n.cfg["revisao"]
    opcao = catalogo.OPCOES.get(n.provedor)
    nome = opcao.nome if opcao else n.provedor
    modelo = n.modelos().get(n.provedor, "")
    reserva = catalogo.OPCOES.get(c["reserva"])
    escuta = "Deepgram" if n.deepgram.disponivel else "desligada (sem chave do Deepgram)"
    livres = set(ferramentas.LIVRES)
    revisao = (
        f"{catalogo.rotulo(r['modelo'])}, até {r['max_por_dia']} por dia" if r["ligada"] else ""
    )
    return pasta.Conexoes(
        cerebro=f"{nome}, com o {modelo}" if modelo else nome,
        reserva=reserva.nome if reserva else c["reserva"],
        revisao=revisao,
        voz=f"fala pelo {n._fala_por()}, escuta pelo {escuta}",
        agora=n._agora_para_a_pasta(revisao),
        proprias=[(t.name, f"mcp__{ferramentas.SERVIDOR}__{t.name}" in livres) for t in n.proprias],
        embutidas=list(c["ferramentas"]),
        externos={
            nome: [
                livre.rsplit("__", 1)[-1]
                for livre in n.externos.livres
                if livre.startswith(f"mcp__{nome}__")
            ]
            for nome in n.externos.servidores
        },
    )


def retrato(n: "Nucleo") -> autoconhecimento.Retrato:
    """O Zé agora, para ele mesmo responder e ajudar (ADR 0043). Sem segredos."""
    c = n.cfg["cerebro"]
    opcao = catalogo.OPCOES.get(n.provedor)
    nome = opcao.nome if opcao else n.provedor
    modelo = n.modelos().get(n.provedor, "")
    reserva = catalogo.OPCOES.get(c["reserva"])
    via = rapido.efetiva(n.cfg["via_rapida"])
    cerebro = n.cerebro
    roteado = isinstance(cerebro, rapido.Roteado) and cerebro.motor_ok
    modelo_rapido = str(cerebro.motor.modelo) if isinstance(cerebro, rapido.Roteado) else ""
    if via["ligada"]:
        quando = "só no Live" if via.get("quando", "live") == "live" else "sempre"
        motor = NOMES_DOS_MOTORES.get(str(via["motor"]), str(via["motor"]))
        rapidas = f"{motor}, com o {catalogo.rotulo(str(via['modelo']))}, {quando}"
        rapidas += "; respondendo agora" if roteado else ""
    else:
        rapidas = "desligadas (tudo vai ao cérebro completo)"
    live = live_ativo(n)
    if live is not None:
        onde = "o app do celular" if getattr(live.fonte, "do_app", False) else "o navegador"
        estado_live = (
            f"conectado agora, por {onde}: percebe o fim da fala pelo detector do LiveKit e "
            "dá para cortar o Zé falando por cima"
        )
    elif n.live.disponivel:
        estado_live = 'pronto; liga ao conectar a voz do aparelho (o botão "Conectar voz")'
    else:
        estado_live = f"indisponível ({n.live.erro or 'sem a chave do Deepgram'})"
    m = maquina_atual.detectar()
    endereco = getattr(getattr(n, "tunel", None), "endereco", "")
    cs = contas.Contas()
    return autoconhecimento.Retrato(
        cerebro=f"{nome}, com o {catalogo.rotulo(modelo)}" if modelo else nome,
        modelo=catalogo.rotulo(modelo) if modelo else "",
        provedor=nome,
        modelo_das_rapidas=catalogo.rotulo(str(via["modelo"])) if via["ligada"] else "",
        reserva=reserva.nome if reserva else str(c["reserva"]),
        rapidas=rapidas,
        rapidas_agora=roteado,
        rapidas_modelo=catalogo.rotulo(modelo_rapido) if roteado else "",
        voz=n._fala_por(),
        escuta=(
            "Deepgram nova-3, em português"
            if n.deepgram.disponivel
            else "desligada (sem a chave do Deepgram)"
        ),
        live=estado_live,
        modo=modo_fala.NOMES.get(n.modo_fala, n.modo_fala),
        ativacao=chamado.NOMES.get(n.chamado, n.chamado),
        espera=espera.NOMES.get(n.espera, n.espera),
        acesso=(
            f"pelo celular no endereço {endereco}, com senha e código"
            if endereco
            else "neste computador (o acesso de qualquer lugar está desligado)"
        ),
        contas=f"Claude: {cs.em_uso('claude').nome}; Codex: {cs.em_uso('codex').nome}",
        maquina=("um servidor sem tela" if m.servidor else "este computador")
        + f" ({m.sistema}{', com Omarchy' if m.omarchy else ''})",
        versao=__version__,
    )


def capacidades(n: "Nucleo") -> autoconhecimento.Capacidades:
    """O que o Zé sabe fazer agora (ADR 0045). Cada parte que falhar fica vazia: a pergunta
    "o que você faz?" nunca cai por causa de um arquivo ilegível."""

    def tentar(fazer: Callable[[], Any], padrao: Any) -> Any:
        try:
            return fazer()
        except Exception:
            log.debug("autoconhecimento: parte das capacidades falhou", exc_info=True)
            return padrao

    livres = {nome.rsplit("__", 1)[-1] for nome in ferramentas.LIVRES}
    por_grupo = {g: [f.name for f in fs] for g, fs in n.ferramentas_por_grupo.items()}

    def skills() -> tuple[autoconhecimento.Skill, ...]:
        uso = n.skills.uso()
        lista = [
            autoconhecimento.Skill(nome, descricao, int((uso.get(nome) or {}).get("usos", 0)))
            for nome, descricao in n.skills.listar()
        ]
        return tuple(sorted(lista, key=lambda s: -s.usos))

    def externos() -> tuple[autoconhecimento.Conector, ...]:
        return tuple(
            autoconhecimento.Conector(
                str(c["nome"]), len(c.get("livres") or []), len(c.get("bloqueadas") or [])
            )
            for c in conectores.listar()
        )

    def sessoes() -> tuple[autoconhecimento.Sessao, ...]:
        ativas = set(n.sessoes.trabalhando())
        return tuple(
            autoconhecimento.Sessao(
                s.nome,
                contas.NOMES.get(s.motor, s.motor),
                "trabalhando" if s.id in ativas else s.estado,
            )
            for s in n.sessoes.listar()
            if s.origem != "manutencao"
        )

    def automacoes() -> tuple[autoconhecimento.Automacao, ...]:
        return tuple(autoconhecimento.Automacao(j.nome, j.agenda, j.ativo) for j in n.jobs.listar())

    lembrancas = tentar(
        lambda: len(n.memoria.entradas("usuario")) + len(n.memoria.entradas("jarvis")),
        0,
    )
    central = getattr(n, "central", None)
    return autoconhecimento.Capacidades(
        grupos=autoconhecimento.grupos(por_grupo, livres),
        skills=tentar(skills, ()),
        conectores=tentar(externos, ()),
        sessoes=tentar(sessoes, ()),
        automacoes=tentar(automacoes, ()),
        lembrancas=lembrancas,
        paginas=tentar(aimemory.paginas, None),
        whatsapp=(("conectado" if central.whatsapp_ativo else "desligado") if central else ""),
    )


def historico(n: "Nucleo", dias: int = 7) -> autoconhecimento.Historico:
    """O que o Zé fez nos últimos dias, da Atividade (ADR 0045)."""
    try:
        b = atividade.PADRAO.balanco(dias, fuso.local())
        recentes = atividade.PADRAO.listar(5)
    except Exception:
        log.debug("autoconhecimento: a atividade não abriu", exc_info=True)
        return autoconhecimento.Historico(dias=dias)
    return autoconhecimento.Historico(
        dias=dias,
        contagem=b["contagem"],
        por_dia=tuple(autoconhecimento.Dia(*d) for d in b["por_dia"]),
        mais_usadas=tuple(b["mais_usadas"]),
        recentes=tuple(
            (float(i.get("quando", 0)), str(i.get("tipo", "")), str(i.get("titulo", "")))
            for i in recentes
        ),
    )


def _agora_para_a_pasta(n: "Nucleo", revisao: str) -> str:
    try:
        r = n.retrato()
    except Exception:  # a nota não pode derrubar a pasta: sem retrato, o resumo de antes
        log.debug("retrato do Zé falhou", exc_info=True)
        return ""
    extras = [f"**Revisão em segundo plano:** {revisao or 'desligada'}"]
    return autoconhecimento.texto(
        dataclasses.replace(r, extras=extras), n.capacidades(), n.historico()
    )


def _fala_por(n: "Nucleo") -> str:
    ativo = n.motor_voz.ativo
    if ativo is None:
        return "Piper (Cadu)"
    nome = n.motor_voz.escolha.voz(ativo).get("nome", "")
    titulo = n.motor_voz.titulo(ativo)
    return f"{titulo} ({nome}), com o Cadu de reserva" if nome else titulo
