"""O terminal de cada sessão e o que o agente conta por ele: abrir e reencontrar o terminal,
olhar a saída, ler os eventos (pedido, ferramenta, fim do turno) e o custo da tarefa.
Funções da classe `Sessoes`, tiradas de `sessoes.py`; a classe repassa a chamada."""

import contextlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zervis import atividade
from zervis.cerebro import contas
from zervis.cerebro.consumo import mil
from zervis.memoria import aimemory
from zervis.oficina import continuidade, custo, fallback
from zervis.oficina import sessoes as ses
from zervis.oficina.permissoes import PRAZO_CODEX_S, assinatura, resumo
from zervis.oficina.supervisor import TerminalRemoto
from zervis.oficina.terminal import Terminal

if TYPE_CHECKING:
    from zervis.oficina.sessoes import Sessoes


def _retomar_terminais(n: "Sessoes") -> set[str]:
    """Os agentes que continuaram no supervisor: voltam para `terminais` com a chave de
    permissão e a posição dos eventos de antes. Devolve as sessões ainda vivas."""
    if n.oficina is None:
        return set()
    try:
        achados = n.oficina.listar()
    except OSError as erro:
        ses.log.warning("supervisor das sessões não respondeu à lista: %s", erro)
        return set()
    vivas: set[str] = set()
    for info in achados:
        id_ = str(info.get("nome", ""))
        bruto = info.get("meta")
        meta: dict[str, Any] = bruto if isinstance(bruto, dict) else {}
        try:
            n.ler(id_)
        except ses.SessaoErro:  # a sessão não existe mais (excluída noutra instalação)
            with contextlib.suppress(OSError, TimeoutError):
                n.oficina.encerrar(id_)
            continue
        chave = str(meta.get("chave", ""))
        if chave:
            prazo = meta.get("prazo")
            n.permissoes.adotar(id_, chave, float(prazo) if prazo else None)
        lidos = n._dados.ler(ses.LIDOS, id_)
        if lidos is not None:
            n._lidos[id_] = int(lidos.get("posicao", 0))
        else:
            with contextlib.suppress(OSError):
                n._lidos[id_] = n.eventos(id_).stat().st_size
        n.fallback.inicios[id_] = float(info.get("criado") or time.time())
        ao_sair, ao_ler = n._avisos_do_terminal(id_, chave)
        n.terminais[id_] = n.oficina.retomar(info, ao_sair=ao_sair, ao_ler=ao_ler)
        if info.get("vivo"):
            vivas.add(id_)
    if vivas:
        ses.log.info("sessões que continuaram durante o reinício: %s", ", ".join(sorted(vivas)))
    return vivas


def _avisos_do_terminal(
    n: "Sessoes", id_: str, resumo_chave: str
) -> tuple[Callable[[int], None], Callable[[bytes], None]]:
    def ao_sair(codigo: int) -> None:
        n._terminal_saiu(id_, codigo, resumo_chave=resumo_chave)

    def ao_ler(dados: bytes) -> None:
        n._olhar_saida(id_, dados)

    return ao_sair, ao_ler


def _novo_terminal(
    n: "Sessoes",
    id_: str,
    comando: list[str],
    pasta: Path,
    ambiente: dict[str, str],
    chave: str,
    prazo: float | None,
    colunas: int,
    linhas: int,
) -> Terminal | TerminalRemoto:
    """O terminal no supervisor (sobrevive ao reinício do Zé); sem ele, um filho do Zé."""
    resumo_chave = resumo(chave) if chave else ""
    ao_sair, ao_ler = n._avisos_do_terminal(id_, resumo_chave)
    if n.oficina is not None:
        meta = {"chave": resumo_chave, "prazo": prazo}
        try:
            return n.oficina.abrir(
                id_, comando, pasta, ambiente, ao_sair, ao_ler, colunas, linhas, meta
            )
        except FileNotFoundError:
            raise
        except OSError as erro:
            ses.log.warning("supervisor das sessões falhou (%s): terminal no próprio Zé", erro)
    return Terminal(
        comando, pasta, ambiente, ao_sair=ao_sair, ao_ler=ao_ler, colunas=colunas, linhas=linhas
    )


def _abrir_terminal(
    n: "Sessoes", id_: str, pedido: str, colunas: int, linhas: int
) -> Terminal | TerminalRemoto:
    n.exigir_editavel(id_)
    terminal = n.terminais.get(id_)
    if terminal is not None and (terminal.vivo or n.reservada()):
        return terminal
    n._exigir_disponivel()
    s = n.ler(id_)
    contexto = rascunho = ""
    if s.passagem and pedido:  # já há um pedido de verdade: vai junto com ele
        pedido = f"{s.passagem}{ses.PEDIDO_AGORA}{pedido}"
    elif s.passagem and s.motor == "codex" and s.sdk_sessao:
        rascunho = f"{s.passagem}{ses.PEDIDO_AGORA}"
    elif s.passagem:
        contexto = s.passagem
    if s.motor == "claude":
        ses.confiar_pasta_claude(s)
        if s.sdk_sessao and not ses.conversa_claude_existe(s):
            # Aberta e fechada sem nenhum pedido: o Claude não salvou a conversa, e retomá-la
            # falha ("No conversation found"). Começa uma nova.
            s = n._mudar(id_, sdk_sessao="")
    else:
        ses.confiar_pasta_codex(s)
    # Os agentes acham skills na pasta do projeto a cada abertura, mesmo ao retomar uma
    # conversa (instruções novas, não: testes de 13/10/2026), e as listam como skills.
    with contextlib.suppress(OSError):
        ses.ligar_skills_no_projeto(Path(s.onde), n.skills)
    n.eventos(id_).touch(mode=0o600)
    n._lidos[id_] = n.eventos(id_).stat().st_size
    n._dados.guardar(ses.LIDOS, {"posicao": n._lidos[id_]}, id_)
    externos = ses.conectores_do_projeto(s)
    arquivo_mcp = (
        ses.arquivo_de_conectores(n._dir(id_) / ses.CONECTORES, externos)
        if s.motor == "claude"
        else None
    )
    permissao = n.permissoes.endereco
    segredos = ses.conectores_codex(externos, bool(permissao))[1] if s.motor == "codex" else {}
    # A chave do gancho de permissão vai no ambiente do terminal, nunca na linha de comando.
    # O Codex só aceita gancho de comando, e o comando precisa ser sempre o mesmo (ele pede
    # para confiar em cada gancho novo): o endereço, o prazo e os eventos vão no ambiente.
    prazo = PRAZO_CODEX_S if s.motor == "codex" else None
    chave = n.permissoes.chave(id_, prazo) if permissao else ""
    if chave:
        segredos = {**segredos, ses.VARIAVEL_PERMISSAO: chave}
        if s.motor == "codex":
            segredos |= {
                "ZE_PERMISSAO_URL": permissao,
                "ZE_PERMISSAO_PRAZO": str(int(PRAZO_CODEX_S) + 5),
                "ZE_EVENTOS": str(n.eventos(id_)),
            }
    try:
        n.fallback.inicios[id_] = time.time()
        terminal = n._novo_terminal(
            id_,
            ses.comando_terminal(
                s,
                pedido,
                n.eventos(id_),
                n._contexto(id_, contexto),
                externos,
                arquivo_mcp,
                permissao,
            ),
            s.onde,
            {**ses.ambiente_da_conta(s), **segredos},
            chave,
            prazo if chave else None,
            colunas,
            linhas,
        )
    except FileNotFoundError:
        raise ses.SessaoErro(
            f"{ses.NOMES_MOTORES[s.motor]} não está instalado nesta máquina."
        ) from None
    n.terminais[id_] = terminal
    if rascunho:
        terminal.rascunho(rascunho)
    if s.passagem:  # entregue: o agente novo já recebeu
        n._mudar(id_, passagem="")
    return terminal


def _contexto(n: "Sessoes", id_: str, texto: str) -> Path | None:
    """A passagem num arquivo de uso único, que o hook do Claude entrega no início."""
    if not texto:
        return None
    arquivo = n._dir(id_) / "contexto.json"
    saida = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texto}}
    arquivo.write_text(json.dumps(saida, ensure_ascii=False))
    arquivo.chmod(0o600)
    return arquivo


def _terminal_saiu(n: "Sessoes", id_: str, codigo: int, *, resumo_chave: str = "") -> None:
    n.retomada_pendente.discard(id_)
    n._cauda.pop(id_, None)
    if resumo_chave:  # só a chave deste terminal: o seguinte, se já abriu, tem a dele
        n.permissoes.esquecer(id_, resumo=resumo_chave)
    with contextlib.suppress(ses.SessaoErro):
        if codigo not in ses.SAIDAS_NORMAIS:  # fechar o terminal é normal; erro fica na conversa
            n.anotar(id_, "sistema", f"O agente saiu ({codigo}).")
        s = n.ler(id_)
        if s.motor == "codex":
            aimemory.capturar_codex(s.sdk_sessao, s.onde, "", "", encerrar=True)
        if s.estado == "trabalhando":  # fechou no meio de um pedido
            n._mudar(id_, estado="parada", interrompida=s.ultimo_pedido)


def _olhar_saida(n: "Sessoes", id_: str, dados: bytes) -> None:
    """A tela só dispara conferência. Histórico e prompts nunca comprovam limite."""
    junto = n._saida_limite.get(id_, b"")[-64:] + dados  # pode vir partido em dois
    cauda = n._cauda.get(id_, b"")[-64:] + dados
    n._cauda[id_] = cauda[-64:]
    if id_ not in n.retomada_pendente and ses.TELA_RETOMAR in cauda:
        n.retomada_pendente.add(id_)
        n._cauda.pop(id_, None)
        if n.ao_avisar is not None:
            with contextlib.suppress(ses.SessaoErro):
                n.ao_avisar(n.ler(id_), ses.RETOMAR_CONVERSA)
    if id_ not in n._ganchos_avisados and b"Hooks need review" in junto:
        # O Codex quer que a pessoa confie nos ganchos do Zé (uma vez por conta): sem isso,
        # a aprovação pela voz e pelo painel não funciona nesta sessão.
        n._ganchos_avisados.add(id_)
        if n.ao_avisar is not None:
            with contextlib.suppress(ses.SessaoErro):
                n.ao_avisar(n.ler(id_), ses.GANCHOS_DO_CODEX)
    if id_ in n._limite_visto:
        return
    recente = (n._saida_limite.get(id_, b"") + dados)[-8192:]
    n._saida_limite[id_] = recente
    texto = ses.ANSI.sub("", recente.decode(errors="replace"))
    if not ses.LIMITE_TERMINAL.search(texto):
        return
    n._saida_limite.pop(id_, None)
    n.fallback.agendar(id_)


def _vigiar_eventos(n: "Sessoes") -> None:
    while True:
        time.sleep(0.7)
        for id_ in list(n.terminais):
            try:
                n._ler_eventos(id_)
            except Exception:
                ses.log.exception("eventos da sessão %s", id_)


def _consumir_eventos(n: "Sessoes", id_: str) -> None:
    arquivo = n.eventos(id_)
    try:
        tamanho = arquivo.stat().st_size
    except OSError:
        return
    inicio = n._lidos.get(id_, 0)
    if tamanho <= inicio:
        return
    with arquivo.open("rb") as f:
        f.seek(inicio)
        novo = f.read(tamanho - inicio)
    corte = novo.rfind(b"\n") + 1  # só linhas completas
    n._lidos[id_] = inicio + corte
    if corte:  # guardada: um reinício do Zé continua daqui, sem repetir nem perder evento
        n._dados.guardar(ses.LIDOS, {"posicao": n._lidos[id_]}, id_)
    for linha in novo[:corte].splitlines():
        with contextlib.suppress(ValueError):
            if isinstance(evento := json.loads(linha), dict):
                n._evento(id_, evento)


def _evento(n: "Sessoes", id_: str, e: dict[str, Any]) -> None:
    """O que os agentes contam pelos hooks (Claude) e pelo notify (Codex)."""
    nome = str(e.get("hook_event_name") or e.get("type") or "")
    if nome == "SessionStart" and e.get("session_id"):
        # Só uma conversa que já existe em disco: a nova o Claude só salva no primeiro pedido.
        if Path(str(e.get("transcript_path") or "")).is_file():
            n._mudar(id_, sdk_sessao=str(e["session_id"]))
    elif nome == "UserPromptSubmit":
        n.retomada_pendente.discard(id_)  # a conversa andou: a pergunta foi respondida
        # Um pedido novo: o que esperava de um turno anterior ficou para trás.
        n.permissoes.retirar(id_, fora_do_turno=str(e.get("prompt_id", "")))
        if e.get("session_id"):
            n._mudar(id_, sdk_sessao=str(e["session_id"]))
        pedido = n._pedido(id_, str(e.get("prompt", "")))
        if not pedido:
            return
        if id_ in n.fallback.pendentes and n.ler(id_).limite:
            # O hook pode chegar depois do aviso de limite do mesmo turno. Não apaga
            # o erro nem anuncia conclusão enquanto a evidência nativa é conferida.
            n._mudar(id_, ultimo_pedido=pedido, interrompida="")
            return
        n._limite_visto.discard(id_)
        n._saida_limite.pop(id_, None)
        n._mudar(
            id_,
            estado="trabalhando",
            limite=False,
            ultimo_pedido=pedido,
            interrompida="",  # um pedido novo: o interrompido ficou para trás
        )
    elif nome == "PostToolUse":
        # A ferramenta rodou: se esperava permissão, a pessoa aprovou no terminal. O gancho
        # enxuto (MCP) já manda a assinatura; o completo (comandos, arquivos), a entrada.
        rodou = str(e.get("assinatura") or "") or assinatura(
            str(e.get("tool_name", "")), e.get("tool_input")
        )
        n.permissoes.retirar(id_, rodou=rodou)
        if acao := ses._acao_do_claude(e):
            n.anotar(id_, "ferramenta", acao)
    elif nome == "Interrupt":
        # O Codex foi interrompido (Esc) com o gancho esperando: o gancho não é encerrado, e
        # o pedido daquele turno sai do painel e da voz.
        n.permissoes.retirar(id_, do_turno=str(e.get("turn_id", "")))
    elif nome == "Notification" and "permission" in str(e.get("message", "")).lower():
        if n.ao_avisar is not None:
            n.ao_avisar(n.ler(id_), str(e.get("message", "")))
    elif nome == "Stop":
        # O turno parou: um "não" no terminal termina aqui.
        n.permissoes.retirar(id_, do_turno=str(e.get("prompt_id", "")))
        if e.get("session_id"):
            n._mudar(id_, sdk_sessao=str(e["session_id"]))
        resposta = str(e.get("last_assistant_message") or "")  # o hook já traz a resposta
        if not resposta:
            resposta = ses._ultima_resposta_claude(str(e.get("transcript_path", "")))
        n._fim_do_turno(id_, resposta, str(e.get("transcript_path") or ""))
    elif nome == "agent-turn-complete":
        if ses._turno_auxiliar_do_codex(e):
            return  # o Codex gerando o título da conversa, noutro fio: não é o turno
        if n.ler(id_).estado != "trabalhando":
            return  # evento repetido depois de a conclusão já ter sido consumida
        if e.get("thread-id"):
            n._mudar(id_, sdk_sessao=str(e["thread-id"]))
        entrada = e.get("input-messages")  # todos os pedidos da conversa; o do turno é o último
        if isinstance(entrada, list) and entrada:
            n._pedido(id_, str(entrada[-1]))
        n._fim_do_turno(id_, str(e.get("last-assistant-message") or ""))


def _pedido(n: "Sessoes", id_: str, texto: str) -> str:
    """O que a pessoa digitou no terminal entra na conversa do Zé (é dela que sai a passagem
    e a memória). Da passagem que o Zé colou, fica só o pedido que veio junto."""
    texto = continuidade.pedido_sem_contexto(texto)
    if texto.startswith(fallback.RETOMADA):
        texto = texto[len(fallback.RETOMADA) :]
    elif texto.strip():
        n._dados.remover("fallback-tentativas", id_)
    if texto.strip():
        texto = texto.strip()
        n.anotar(id_, "usuario", texto)
        n._mudar(id_, ultimo_pedido=texto)
    return texto.strip()


def _fim_do_turno(n: "Sessoes", id_: str, resposta: str, conversa: str = "") -> None:
    atual = n.ler(id_)
    if atual.estado != "trabalhando":
        return  # uma notificação repetida não registra nem anuncia o mesmo turno de novo
    if resposta.strip():
        n.anotar(id_, "agente", resposta)
    if atual.limite:
        return
    resumo = ses._resumo_de(resposta) if resposta.strip() else "terminou"
    final = n._mudar(
        id_,
        estado="parada",
        resumo=resumo[:300],
        fios={**atual.fios, atual.motor: atual.sdk_sessao} if atual.sdk_sessao else atual.fios,
        vistos={**atual.vistos, atual.motor: len(n.mensagens(id_))},
    )
    if final.motor == "codex":
        aimemory.capturar_codex(final.sdk_sessao, final.onde, final.ultimo_pedido, resposta)
    n._registrar_custo(final, conversa)
    if n.ao_terminar is not None:
        try:
            n.ao_terminar(final, resumo)
        except Exception:
            ses.log.exception("aviso do fim da sessão falhou")


def _registrar_custo(n: "Sessoes", s: "ses.Sessao", conversa: str) -> None:
    """Quanto a tarefa gastou, na Atividade (plano de maturidade, Frente 3): lido da conversa
    do próprio agente, sem gastar nada. Sem a conversa, nada se registra."""
    arquivo = Path(conversa) if conversa else None
    if (arquivo is None or not arquivo.is_file()) and s.sdk_sessao:
        try:
            cs = contas.Contas()
            conta = cs.achar(s.conta) if s.conta else cs.em_uso(s.motor)
        except contas.ContaErro:
            return
        arquivo = ses._arquivo_da_conversa(s.motor, s.sdk_sessao, conta.onde)
    gasto = custo.do_turno(arquivo, s.motor)
    if gasto is None:
        return
    total = custo.total(gasto)
    partes = (
        f"{gasto['modelo'] or ses.NOMES_MOTORES.get(s.motor, s.motor)} · lido do cache "
        f"{mil(gasto['cache_lido'])} · novo {mil(gasto['entrada'] + gasto['cache_criado'])} "
        f"· escrito {mil(gasto['saida'])}"
    )
    atividade.PADRAO.registrar(
        "execucao",
        f"Sessão {s.nome}: tarefa terminada",
        origem="sessao",
        entrada=s.ultimo_pedido,
        consumo=total,
        consumo_partes=partes,
    )
