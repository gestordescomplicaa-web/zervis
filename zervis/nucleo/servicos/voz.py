"""Serviço de voz; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import collections
import concurrent.futures
import contextlib
import logging
import queue
import subprocess
import threading
import time
import wave
from functools import partial
from pathlib import Path
from typing import Any, Protocol

from zervis import atividade
from zervis.config import Config
from zervis.habilidades import evidencias
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import CHAMADOS_GUARDADOS, ESTADO, PRIMEIRA_FALA_S, Status
from zervis.presenca import modo as modo_escuta
from zervis.presenca.rostos import Rostos
from zervis.sistema.midia import Midia
from zervis.transporte.entrada import Entrada
from zervis.transporte.local import SERVIDOR
from zervis.voz import chamado, espera, piper
from zervis.voz.ativacao import VAD, Detector, SemAtivacao
from zervis.voz.deepgram import Deepgram, EscutaDeepgram, EscutaErro
from zervis.voz.escuta import DURACAO_QUADRO_S, Segmentador
from zervis.voz.latencia import Latencias

log = logging.getLogger(__name__)


class ContextoVoz(Protocol):
    _antes_do_chamado: collections.deque[bytes]
    _digitado_em: float | None
    _fim_fala_em: float | None
    _fonte: Any
    _ouvido: Any
    _ouvindo_desde: Any
    _ouviu_voz: Any
    _transcricao_inicio: Any
    _turno_atual: str | None
    _ultima_fala: Any
    bip: Any
    captura: Entrada
    cfg: Config
    chamado: Any
    deepgram: Deepgram
    detector: Detector
    escuta: EscutaDeepgram | None
    espera: Any
    eventos: queue.Queue[e.Evento]
    evidencias: evidencias.Evidencias
    latencias: Latencias
    maquina: e.Maquina
    meio_transcricao: Any
    modelo_ativacao: Any
    modo_escuta: Any
    rostos: Rostos
    segmentador: Segmentador
    status: Status
    tem_janela: Any
    transcrevendo: concurrent.futures.Future[str] | None
    transcricoes: concurrent.futures.ThreadPoolExecutor
    vad: VAD

    def _aplicar_espera(self) -> None: ...
    def _descartar_escuta(self) -> None: ...
    def _erro(self, mensagem: str) -> None: ...
    def _fechar_escuta(self) -> None: ...
    def _fechar_latencia(self, resultado: str = "concluido") -> None: ...
    def _ligar_ativacao(self) -> None: ...
    def _pedido_fechado(self, trecho: bytes, por: str = "") -> None: ...
    def _tocar_som(self, som: Path) -> None: ...
    def _transcrever(self, trecho: bytes, escuta: EscutaDeepgram | None) -> str: ...
    def _transcrito(
        self, futuro: concurrent.futures.Future[str], turno: str | None = None
    ) -> None: ...
    @property
    def microfone_travado(self) -> bool: ...
    def tratar(self, evento: e.Evento) -> None: ...


class ServicoVoz:
    def __init__(self, contexto: ContextoVoz) -> None:
        self.n = contexto

    def _voz_ociosa(self, numero: int) -> None:
        # Só a última fala pedida conta: o aviso atrasado de uma frase anterior não pode abrir
        # o microfone no meio da pergunta de confirmação (eco aprovando o próprio "sim").
        if numero >= self.n._ultima_fala:
            self.n.eventos.put(e.FalaOcioso())

    def _transcrito(self, futuro: concurrent.futures.Future[str], turno: str | None = None) -> None:
        try:
            texto = futuro.result()
        except Exception as erro:
            self.n._erro(f"transcrição: {type(erro).__name__}: {erro}")
            texto = ""
        self.n.latencias.marcar(turno, "transcrito")
        self.n.latencias.contexto(turno, transcricao_por=self.n.meio_transcricao)
        log.info(
            "transcrito em %.2f s (%s)",
            time.monotonic() - self.n._transcricao_inicio,
            self.n.meio_transcricao,
        )
        if self.n.cfg["escuta"]["registrar_texto"]:
            log.info("transcrição (diagnóstico): %r", texto)
        self.n.status.tempos["transcricao_s"] = round(
            time.monotonic() - self.n._transcricao_inicio, 2
        )
        self.n.status.meio_transcricao = self.n.meio_transcricao
        if not texto.strip():
            self.n.evidencias.registrar("transcricao_vazia")
        self.n._ouvido = texto  # para o "não entendi" dizer o que foi ouvido
        self.n.eventos.put(e.FimDeFala(texto))

    def _abrir_latencia(self, rota: str) -> None:
        if self.n._digitado_em is not None:
            self.n._fechar_latencia("interrompido")
            self.n._turno_atual = self.n.latencias.iniciar("teclado", self.n._digitado_em)
            self.n.latencias.marcar(self.n._turno_atual, "pedido_fechado", self.n._digitado_em)
        self.n.latencias.contexto(self.n._turno_atual, rota=rota)

    def _fechar_latencia(self, resultado: str = "concluido") -> None:
        turno, self.n._turno_atual = self.n._turno_atual, None
        self.n.latencias.finalizar(turno, resultado)

    def mudar_escuta(self, modo: str) -> str:
        """Troca quando o Zé escuta o chamado: sempre, ou só com a janela aberta (ADR 0021)."""
        if modo == "janela" and not self.n.tem_janela:
            raise ValueError("Requer Hyprland.")
        self.n.modo_escuta = modo_escuta.gravar(modo)
        self.n.rostos.marcar("sempre", modo == "sempre")
        log.info("escuta: %s", modo)
        return f"Escuta: {modo_escuta.NOMES[modo].lower()}."

    def _carregar_voz(self) -> None:
        try:
            piper.PADRAO.carregar()
        except Exception as erro:
            log.warning("voz indisponível: %s", erro)

    def _tocar_bip(self) -> None:
        self.n._tocar_som(self.n.bip)
        self.n._descartar_escuta()

    def _tocar_som(self, som: Path) -> None:
        remota = self.n._fonte
        if remota is not None and remota.conectada:
            try:
                remota.tocar_wav(som)
            except Exception as erro:
                self.n._erro(f"bip remoto: {erro}")
            # O navegador cancela o eco do bip: o que chegou enquanto ele tocava é a pessoa já
            # falando, e fica para o pedido.
            self.n.segmentador.limpar()
            self.n.vad.reiniciar()
            return
        try:
            subprocess.run(  # noqa: S603 (comando fixo, arquivo nosso)
                [
                    "/usr/bin/paplay",
                    "--server",
                    SERVIDOR,
                    "--device",
                    "@DEFAULT_SINK@",
                    str(som),
                ],
                timeout=3,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError) as erro:
            self.n._erro(f"{som.stem}: {erro}")

    def _descartar_escuta(self) -> None:
        """O bip e a cauda da própria voz não podem virar começo do próximo pedido."""
        with contextlib.suppress(queue.Empty):
            while True:
                self.n.captura.quadros.get_nowait()
        self.n.segmentador.limpar()
        self.n.vad.reiniciar()

    def _guardar_chamado(self, ignorado: bool = False) -> None:
        """Os segundos de som que dispararam o chamado, para entender ativações sozinhas
        (achado 8 da auditoria de voz). Só neste computador, 0600, e só as últimas."""
        pasta = ESTADO / "chamados"
        try:
            pasta.mkdir(mode=0o700, exist_ok=True)
            nota = f"{self.n.detector.nota_disparo:.3f}{'-ignorado' if ignorado else ''}"
            arquivo = pasta / f"{time.strftime('%Y%m%d-%H%M%S')}-{nota}.wav"
            with wave.open(str(arquivo), "wb") as w:
                w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                w.writeframes(b"".join(self.n._antes_do_chamado))
            arquivo.chmod(0o600)
            for velho in sorted(pasta.glob("*.wav"))[:-CHAMADOS_GUARDADOS]:
                velho.unlink(missing_ok=True)
        except OSError as erro:
            log.warning("chamado: %s", erro)

    def _pausar_midia(self) -> bool:
        cfg: Config | None = getattr(self.n, "cfg", None)
        return cfg is None or bool(cfg["escuta"].get("pausar_midia", True))

    def _dar_a_vez(self, antes: e.Estado, depois: e.Estado) -> None:
        """Saiu de ATIVO (ouvir, pensar, falar): a mídia pausa; voltou a ATIVO: retoma. Só com o
        microfone do PC: a voz do celular não precisa calar o computador."""
        midia: Midia | None = getattr(self.n, "midia", None)
        if midia is None:
            return
        local = getattr(self.n, "_fonte", None) is None
        if antes is e.Estado.ATIVO and depois is not e.Estado.INATIVO and local:
            threading.Thread(target=midia.pausar, daemon=True).start()
        elif depois in (e.Estado.ATIVO, e.Estado.INATIVO) and midia.pausados:
            threading.Thread(target=midia.retomar, daemon=True).start()

    def _ninguem_falou(self) -> bool:
        """Chamado sem ninguém falar depois (um vídeo, um ruído): fecha em poucos segundos, em
        vez de deixar o microfone aberto e mandando áudio ao reconhecimento pelo prazo inteiro."""
        return (
            not self.n._ouviu_voz
            and not self.n.maquina.segurando
            and not self.n.maquina.ao_vivo
            and time.monotonic() - self.n._ouvindo_desde > PRIMEIRA_FALA_S
        )

    def _pedido_fechado(self, trecho: bytes, por: str = "") -> None:
        """O áudio do pedido está completo (pausa, fim de turno ou botão solto): transcreve."""
        por = por or ("modelo" if self.n.segmentador.fechou_pelo_modelo else "silencio")
        self.n.status.tempos["fim_pelo_modelo"] = self.n.segmentador.fechou_pelo_modelo
        notas = " ".join(f"{n:.2f}" for n in self.n.segmentador.notas_do_ultimo)
        nomes = {"modelo": "pelo modelo", "silencio": "pelo silêncio", "botao": "pelo botão"}
        log.info("pedido fechado %s (fim de turno: %s)", nomes[por], notas or "sem consulta")
        self.n._transcricao_inicio = time.monotonic()
        turno = None
        if self.n.maquina.estado is e.Estado.OUVINDO:
            fim = self.n._fim_fala_em or self.n._transcricao_inicio
            self.n._turno_atual = turno = self.n.latencias.iniciar("voz", fim)
            self.n.latencias.marcar(turno, "fim_fala", fim)
            self.n.latencias.marcar(turno, "pedido_fechado", self.n._transcricao_inicio)
            self.n.latencias.contexto(turno, fim_por=por)
        self.n._fim_fala_em = None
        escuta, self.n.escuta = self.n.escuta, None
        self.n.transcrevendo = self.n.transcricoes.submit(self.n._transcrever, trecho, escuta)
        self.n.transcrevendo.add_done_callback(partial(self.n._transcrito, turno=turno))

    def _fechar_pelo_botao(self) -> None:
        """O botão foi solto: o pedido fecha com o que já foi ouvido; sem fala, nada acontece
        (e numa confirmação, soltar sem dizer nada não nega)."""
        self.n.segmentador.segurando = False
        if self.n.transcrevendo is not None:
            return
        trecho = self.n.segmentador.fechar()
        if trecho is not None:
            self.n._pedido_fechado(trecho, "botao")
        elif self.n.maquina.estado is e.Estado.OUVINDO:
            self.n._fechar_escuta()
            self.n.tratar(e.Silencio())

    @property
    def microfone_travado(self) -> bool:
        """No Silencioso o Zé não ouve: o microfone fica fechado e o botão não abre."""
        return getattr(self.n, "modo_fala", "") == "silencioso"

    def apertar(self) -> None:
        if self.n.microfone_travado:
            raise ValueError("Microfone desligado no modo Silencioso.")
        self.n.eventos.put(e.Apertou())

    def soltar(self) -> None:
        self.n.eventos.put(e.Soltou())

    def _aplicar_espera(self) -> None:
        pausa, silencio = espera.TEMPOS[self.n.espera]
        self.n.segmentador.pausa_consulta = max(1, round(pausa / DURACAO_QUADRO_S))
        self.n.segmentador.fim_silencio_s = silencio

    def mudar_espera(self, modo: str) -> str:
        """Troca quanto o Zé espera antes de responder: Rápida, Normal ou Longa."""
        self.n.espera = espera.gravar(modo)
        self.n._aplicar_espera()
        log.info("espera: %s", modo)
        return f"Espera: {espera.NOMES[modo]}."

    def mudar_chamado(self, modo: str) -> str:
        """Troca como a pessoa chama o Zé: "Ei Zé" ou só o botão (ADR 0022)."""
        self.n.chamado = chamado.gravar(modo)
        self.n._ligar_ativacao()
        log.info("ativação: %s", modo)
        return f"Ativação: {chamado.NOMES[modo]}."

    def _fechar_escuta(self) -> None:
        """Parou de ouvir sem pedido (silêncio, janela fechada): a conexão fecha na hora."""
        if self.n.escuta is not None:
            self.n.escuta.cancelar()
            self.n.escuta = None

    def _transcrever(self, trecho: bytes, escuta: EscutaDeepgram | None) -> str:
        """O texto do pedido pelo Deepgram; sem ele (ou se falhar), vazio: o Zé diz que não
        entendeu e o usuário repete, ou usa o teclado."""
        if escuta is None:
            return ""
        try:
            texto = escuta.terminar()
            self.n.deepgram.contar(escuta)
            return texto
        except EscutaErro as erro:
            log.warning("Deepgram falhou (%s)", erro)
            atividade.PADRAO.registrar("falha", "A transcrição falhou (Deepgram)", erro=str(erro))
            return ""

    def _ligar_ativacao(self) -> None:
        """Sem a chave do Deepgram o chamado não dispara (não haveria quem transcrevesse); com a
        ativação "Só o botão", também não (ADR 0022)."""
        ouvir = self.n.deepgram.disponivel and self.n.chamado == "voz"
        modelo = self.n.modelo_ativacao if ouvir else SemAtivacao()
        self.n.detector.modelo = modelo
        self.n.detector.limiar = modelo.limiar

    def aplicar_escuta(self) -> None:
        """O painel guardou ou apagou a chave do Deepgram: vale na hora."""
        self.n.deepgram.recarregar()
        self.n._ligar_ativacao()
