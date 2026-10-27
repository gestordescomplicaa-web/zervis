"""Escolha conservadora de outra conta; evidência vem do registro nativo do agente."""

import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zervis import atividade
from zervis.cerebro import contas, modelos
from zervis.oficina import continuidade

if TYPE_CHECKING:
    from zervis.oficina.sessoes import Sessao, Sessoes

log = logging.getLogger(__name__)
RETOMADA = (
    "O trabalho foi interrompido pelo limite da conta. Confira o histórico e "
    "os arquivos, preserve o que já foi feito e continue apenas o que falta. "
    "Não repita ações já concluídas. Pedido atual:\n\n"
)


@dataclass
class Interrupcao:
    pedido: str = ""
    modelo: str = ""
    esforco: str = ""
    limite: bool = False
    fio: str = ""
    limite_em: float = 0.0


def ler_registro(arquivo: Path, motor: str) -> Interrupcao:
    """Só campos estruturados confirmam limite; textos de ferramentas não autorizam troca.

    A leitura é limitada. Se o pedido ficou fora da cauda, a retomada exige intervenção.
    """
    resultado = Interrupcao()
    with arquivo.open("rb") as entrada:
        entrada.seek(max(0, arquivo.stat().st_size - 2 * 1024 * 1024))
        for linha in entrada:
            try:
                d = json.loads(linha)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(d, dict):
                continue
            try:
                momento = datetime.fromisoformat(str(d.get("timestamp", ""))).timestamp()
            except ValueError:
                momento = 0.0
            p = d.get("payload") or {}
            if not isinstance(p, dict):
                continue
            confirmou = False
            if motor == "codex":
                if d.get("type") == "session_meta":
                    resultado.fio = str(p.get("id") or "")
                elif d.get("type") == "turn_context":
                    resultado.modelo = str(p.get("model") or "")
                    resultado.esforco = str(p.get("effort") or "")
                elif d.get("type") == "event_msg":
                    tipo = p.get("type")
                    if tipo == "user_message":
                        resultado.pedido = str(p.get("message") or "")
                        resultado.limite = False
                    elif tipo == "turn_aborted" or (
                        tipo in ("task_complete", "turn_complete") and p.get("last_agent_message")
                    ):
                        resultado.limite = False
                    elif tipo == "error":
                        resultado.limite = p.get("codex_error_info") == "usage_limit_exceeded"
                        confirmou = resultado.limite
                    elif tipo == "token_count":
                        limites = p.get("rate_limits") or {}
                        if isinstance(limites, dict):
                            # Cem por cento pode vir depois de um turno bem-sucedido.
                            # Só a indicação explícita de bloqueio autoriza a retomada.
                            confirmou = limites.get("rate_limit_reached_type") in (
                                "rate_limit_reached",
                                "workspace_owner_credits_depleted",
                                "workspace_member_credits_depleted",
                                "workspace_owner_usage_limit_reached",
                                "workspace_member_usage_limit_reached",
                            )
                            resultado.limite = resultado.limite or confirmou
            else:
                if d.get("type") == "user" and not d.get("isMeta"):
                    conteudo = (d.get("message") or {}).get("content")
                    if isinstance(conteudo, str):
                        resultado.pedido = conteudo
                        resultado.limite = False
                    elif isinstance(conteudo, list):
                        textos = [b.get("text", "") for b in conteudo if b.get("type") == "text"]
                        if textos:
                            resultado.pedido = "\n".join(textos)
                            resultado.limite = False
                elif d.get("type") == "assistant":
                    mensagem = d.get("message") or {}
                    modelo = str(mensagem.get("model") or "")
                    if modelo and modelo != "<synthetic>":
                        resultado.modelo = modelo
                    resultado.limite = d.get("error") in ("rate_limit", "billing_error")
                    confirmou = resultado.limite
            if confirmou:
                resultado.limite_em = momento
    return resultado


def candidatas(
    cs: contas.Contas, motor: str, modelo: str, esforco: str, excluidas: set[str]
) -> list[contas.Conta]:
    """Plano ordena tentativas, nunca comprova saldo nem disponibilidade de modelo."""
    if not modelo or not esforco:
        return []
    elegiveis: list[tuple[int, contas.Conta]] = []
    pastas: set[Path] = set()
    for conta in cs.listar(motor):
        if conta.id in excluidas or conta.onde.resolve() in pastas:
            continue
        identidade = contas.quem(conta)
        if not identidade.get("logado"):
            continue
        opcoes = {m["id"]: m for m in modelos.da_conta(conta)}
        if modelo not in opcoes or (motor == "codex" and esforco not in opcoes[modelo]["esforcos"]):
            continue
        plano = re.sub(r"[^a-z]", "", str(identidade.get("plano", "")).lower())
        prioridade = {"pro": 0, "plus": 1, "free": 2}.get(plano, 3)
        elegiveis.append((prioridade, conta))
        pastas.add(conta.onde.resolve())
    return [c for _, c in sorted(elegiveis, key=lambda item: item[0])]


def primeira_linha(arquivo: Path) -> dict[str, Any]:
    with arquivo.open("rb") as entrada:
        d = json.loads(entrada.readline(65536))
    return d if isinstance(d, dict) else {}


class Fallback:
    def __init__(self, sessoes: "Sessoes") -> None:
        self.sessoes = sessoes
        self.pendentes: dict[str, object] = {}
        self.inicios: dict[str, float] = {}

    def cancelar(self, id_: str) -> None:
        self.pendentes.pop(id_, None)

    def agendar(self, id_: str, comprovado: bool = False) -> None:
        if id_ in self.pendentes:
            return
        marca = object()
        self.pendentes[id_] = marca
        threading.Thread(
            target=self._executar,
            args=(id_, marca, comprovado),
            daemon=True,
            name=f"fallback-{id_}",
        ).start()

    def _registro(self, s: "Sessao", conta: contas.Conta) -> Interrupcao:
        from zervis.oficina.sessoes import _arquivo_da_conversa

        arquivo = _arquivo_da_conversa(s.motor, s.sdk_sessao, conta.onde) if s.sdk_sessao else None
        if arquivo is None and s.motor == "codex":
            # Primeiro turno: notify só informa o fio ao terminar. Identificação precisa
            # por pasta e instante de abertura; ambiguidade nunca escolhe outra conversa.
            encontrados = []
            for candidato in (conta.onde / "sessions").glob("**/*.jsonl"):
                if candidato.stat().st_mtime < self.inicios.get(s.id, time.time()):
                    continue
                meta = primeira_linha(candidato).get("payload", {})
                if meta.get("cwd") == str(s.onde) and not isinstance(meta.get("source"), dict):
                    encontrados.append(candidato)
            if len(encontrados) == 1:
                arquivo = encontrados[0]
        if arquivo is None or arquivo.stat().st_mtime < self.inicios.get(s.id, 0):
            return Interrupcao()
        resultado = ler_registro(arquivo, s.motor)
        if resultado.limite_em < self.inicios.get(s.id, 0):
            resultado.limite = False
        if s.motor == "claude":
            # O valor salvo pode diferir do /effort escolhido só para esta conversa.
            # A variável fixa o nível; sem ela, não inferimos o esforço pela conta.
            fixado = os.environ.get("CLAUDE_CODE_EFFORT_LEVEL", "")
            resultado.esforco = (
                fixado if fixado in ("low", "medium", "high", "xhigh", "max") else ""
            )
        resultado.fio = resultado.fio or s.sdk_sessao
        if not resultado.fio and s.motor == "codex":
            resultado.fio = str(primeira_linha(arquivo).get("payload", {}).get("id") or "")
        return resultado

    def _executar(self, id_: str, marca: object, comprovado: bool) -> None:
        ss = self.sessoes
        try:
            # Sai do callback do PTY antes de encerrar o leitor. Dá tempo para o agente
            # publicar a transcrição e para a tarefa sem terminal finalizar seus callbacks.
            time.sleep(0.4)
            prazo = time.monotonic() + 5
            while comprovado and id_ in ss.trabalhando() and time.monotonic() < prazo:
                time.sleep(0.05)
            with ss._operacoes:
                if self.pendentes.get(id_) is not marca:
                    return
                s = ss.ler(id_)
                if comprovado and not s.limite:
                    return
                ss.exigir_editavel(id_)
                ss._exigir_disponivel()
                cs = contas.Contas()
                atual = cs.achar(s.conta) if s.conta else cs.em_uso(s.motor)
                contexto = (
                    Interrupcao(s.ultimo_pedido, s.modelo, s.esforco, True, s.sdk_sessao)
                    if comprovado
                    else self._registro(s, atual)
                )
                if not contexto.limite or not contexto.pedido:
                    # Uma frase na tela sem evidência recente não altera estado, saldo,
                    # pedidos nem notificações. Pode ser só a conversa sendo redesenhada.
                    return
                ss._limite_visto.add(id_)
                pedido = continuidade.pedido_sem_contexto(contexto.pedido)
                while pedido.startswith(RETOMADA):
                    pedido = pedido[len(RETOMADA) :]
                if not pedido:
                    self._parada(s, "Não há pedido confirmado para retomar automaticamente.")
                    return
                # Não deixa padrões diferentes das contas mudarem o esforço silenciosamente.
                modelo = contexto.modelo or s.modelo
                esforco = contexto.esforco
                # Mesmo sem alternativa, Continuar precisa apontar ao pedido que realmente
                # falhou no terminal, não à última tarefa concluída registrada pelo notify.
                s = ss._mudar(
                    id_,
                    ultimo_pedido=pedido,
                    sdk_sessao=contexto.fio,
                    modelo=modelo,
                    esforco=esforco,
                    estado="erro",
                    limite=True,
                )
                if not modelo or not esforco:
                    self._parada(s, "Escolha um modelo e esforço explícitos antes de continuar.")
                    return
                bloqueios = ss._dados.listar("fallback-contas")
                excluidas = {
                    str(b["conta"])
                    for b in bloqueios
                    if b.get("verificado") and b.get("ate", 0) > time.time()
                }
                tentativas = ss._dados.ler("fallback-tentativas", id_) or {}
                excluidas.update(tentativas.get("contas", []))
                excluidas.add(atual.id)
                ss._dados.guardar("fallback-tentativas", {"contas": sorted(excluidas)}, id_)
                # Evita girar entre contas e também repetir a mesma conta em outras sessões.
                ss._dados.guardar(
                    "fallback-contas",
                    {"conta": atual.id, "ate": time.time() + 3600, "verificado": True},
                    atual.id,
                )
                opcoes = candidatas(cs, s.motor, modelo, esforco, excluidas)
                opcoes = [c for c in opcoes if c.onde.resolve() != atual.onde.resolve()]
                if not opcoes:
                    self._parada(
                        s,
                        "Nenhuma conta alternativa compatível disponível. "
                        "Modelo e esforço preservados.",
                    )
                    return
                nova = opcoes[0]
                ss._encerrar_agente(id_)
                # Todos os hooks do processo antigo são consumidos antes de reabrir.
                ss._consumir_eventos(id_)
                s = ss._mudar(
                    id_,
                    estado="erro",
                    limite=True,
                    sdk_sessao=contexto.fio,
                    ultimo_pedido=pedido,
                    modelo=modelo,
                    esforco=esforco,
                )
                # A transcrição de origem é a mais recente: uma cópia antiga na conta
                # de destino não pode esconder os passos executados desde a última troca.
                from zervis.oficina.sessoes import _arquivo_da_conversa

                origem = (
                    _arquivo_da_conversa(s.motor, s.sdk_sessao, atual.onde)
                    if s.sdk_sessao
                    else None
                )
                if origem is not None:
                    destino = _arquivo_da_conversa(s.motor, s.sdk_sessao, nova.onde)
                    destino = destino or nova.onde / origem.relative_to(atual.onde)
                    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as saida:
                        temporario = Path(saida.name)
                        try:
                            with origem.open("rb") as entrada:
                                shutil.copyfileobj(entrada, saida)
                            saida.flush()
                            temporario.replace(destino)
                        finally:
                            temporario.unlink(missing_ok=True)
                ss._trocar(id_, s.motor, nova.id)
                ss._mudar(id_, modelo=modelo, esforco=esforco)
                aviso = (
                    f"Conta alterada para {nova.nome}. Continuando com o mesmo modelo e esforço."
                )
                ss.anotar(id_, "sistema", aviso)
                atividade.PADRAO.registrar(
                    "execucao",
                    "Troca automática de conta",
                    sessao=id_,
                    conta=nova.id,
                    modelo=modelo,
                    esforco=esforco,
                )
                # Libera antes do lançamento: a nova conta pode atingir limite imediatamente.
                self.cancelar(id_)
                final = ss._enviar(id_, RETOMADA + pedido, "continuacao", None)
                if ss.ao_terminar:
                    ss.ao_terminar(final, aviso)
        except Exception:
            log.exception("fallback da sessão %s não concluído", id_)
            with ss._operacoes:
                if self.pendentes.get(id_) in (marca, None):
                    sessao_atual = ss.ler(id_)
                    if sessao_atual.limite:
                        self._parada(
                            sessao_atual,
                            "Troca automática não concluída. O trabalho foi preservado.",
                        )
        finally:
            if self.pendentes.get(id_) is marca:
                self.cancelar(id_)

    def _parada(self, s: "Sessao", motivo: str) -> None:
        self.sessoes.anotar(s.id, "sistema", motivo)
        final = self.sessoes._mudar(s.id, estado="erro", resumo=motivo)
        if self.sessoes.ao_terminar:
            self.sessoes.ao_terminar(final, motivo)
