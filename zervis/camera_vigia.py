"""Vigia de movimento da câmera (plano-camera): só guarda fotos, sem avisos."""

import contextlib
import logging
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import camera, fuso

log = logging.getLogger(__name__)
FOTOS = camera.FOTOS
# Os nomes variam com o firmware ("VideoMotion", "MotionDetect", "appEventHumanDetectAlarm",
# "PIRAlarm"…): vale o evento que fala de movimento, pessoa ou sensor PIR.
MOVIMENTO = ("motion", "human", "person", "pir")
ESPERA_RECONEXAO = 5
ESPERA_RECONEXAO_MAX = 60


class Vigia:
    def __init__(self, dispositivo: camera.Camera, pasta: Path) -> None:
        self.dispositivo = dispositivo
        self.pasta = pasta
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cliente: camera.Cliente | None = None
        self._pedidos_foto: queue.Queue[tuple[threading.Event, dict[str, Any]]] = queue.Queue()
        self._ultima_foto: dict[int, float] = {}  # por lente
        self.lentes = 1
        self._estado = "Sem conexão"
        dispositivo.ao_mudar = self.iniciar

    def iniciar(self) -> None:
        self.parar()
        conexao = self.dispositivo.conexao()
        if conexao is None:
            with self._trava:
                self._estado = "Não configurada"
            return
        if not conexao.ligado:
            with self._trava:
                self._estado = "Desligada"
            return
        self._parar.clear()
        with self._trava:
            self._estado = "Conectando"
        self._thread = threading.Thread(target=self._conectar, name="vigia-camera", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        with self._trava:
            thread = self._thread
            cliente = self._cliente
            self._cliente = None
        if cliente is not None:
            cliente.fechar()
        self._cancelar_fotos()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None

    def _cancelar_fotos(self) -> None:
        while True:
            try:
                pronto, resultado = self._pedidos_foto.get_nowait()
            except queue.Empty:
                return
            resultado["erro"] = "A conexão com a câmera foi fechada."
            pronto.set()

    def estado(self) -> str:
        with self._trava:
            return self._estado

    def _conectar(self) -> None:
        atraso = ESPERA_RECONEXAO
        while not self._parar.is_set():
            conexao = self.dispositivo.conexao()
            if conexao is None:
                with self._trava:
                    self._estado = "Não configurada"
                return
            try:
                cliente = self.dispositivo._criar_cliente(conexao)
                with self._trava:
                    self._cliente = cliente
                try:
                    with cliente:
                        self.lentes = cliente.canais
                        try:
                            if cliente.ligar_alarmes_na_rede():
                                log.info("vigia da câmera: aviso de movimento ligado na câmera")
                        except camera.CameraErro as erro:
                            log.warning("vigia da câmera: %s", erro)
                        cliente.assinar_alarmes()
                        with self._trava:
                            self._estado = "Conectada"
                        atraso = ESPERA_RECONEXAO
                        cliente.esperar_alarmes(self._parar, self._ao_alarme, self._processar_fotos)
                finally:
                    with self._trava:
                        if self._cliente is cliente:
                            self._cliente = None
            except camera.CredenciaisInvalidas:
                with self._trava:
                    self._estado = "Usuário ou senha inválidos."
                log.warning("vigia da câmera: acesso recusado; aguardando novo cadastro")
                return  # Só tenta novamente depois que o cadastro mudar.
            except (OSError, camera.CameraErro):
                if self._parar.is_set():
                    return
                with self._trava:
                    self._estado = "Sem conexão"
                if self._parar.wait(atraso):
                    return
                atraso = min(atraso * 2, ESPERA_RECONEXAO_MAX)
            except Exception:
                if self._parar.is_set():
                    return
                with self._trava:
                    self._estado = "Sem conexão"
                log.exception("vigia da câmera: falha inesperada")
                if self._parar.wait(atraso):
                    return
                atraso = min(atraso * 2, ESPERA_RECONEXAO_MAX)

    def _ao_alarme(self, dados: dict[str, Any]) -> None:
        evento = str(dados.get("Event", "")).lower()
        status = str(dados.get("Status", "")).lower()
        if not any(m in evento for m in MOVIMENTO) or status != "start":
            return
        conexao = self.dispositivo.conexao()
        if conexao is None:
            return
        canal = _canal(dados.get("Channel"), self.lentes)
        agora = time.monotonic()
        with self._trava:
            ultima = self._ultima_foto.get(canal)
            if ultima is not None and agora - ultima < conexao.intervalo_s:
                return
            self._ultima_foto[canal] = agora
        threading.Thread(
            target=self._fotografar, args=(canal,), name="foto-camera", daemon=True
        ).start()

    def _fotografar(self, canal: int) -> None:
        try:
            imagem = self.foto(canal)
            self.guardar_foto(imagem, canal if self.lentes > 1 else None)
        except (OSError, camera.CameraErro):
            log.info("vigia da câmera: não conseguiu guardar a foto do movimento")

    def foto(self, canal: int = 0, espera_s: float = 20.0) -> bytes:
        """Pede a foto na sessão já aberta para evitar um segundo login no aparelho."""
        with self._trava:
            conectado = self._cliente is not None and self._estado == "Conectada"
        if not conectado:
            return self.dispositivo.foto(canal)
        pronto = threading.Event()
        resultado: dict[str, Any] = {"canal": canal}
        self._pedidos_foto.put((pronto, resultado))
        if not pronto.wait(espera_s):
            resultado["cancelado"] = True
            raise camera.CameraErro("A câmera não respondeu ao pedido de foto.")
        if erro := resultado.get("erro"):
            raise camera.CameraErro(str(erro)) from None
        imagem = resultado.get("imagem")
        if not isinstance(imagem, bytes):
            raise camera.CameraErro("A câmera não respondeu ao pedido de foto.")
        return imagem

    def _processar_fotos(self) -> None:
        while True:
            try:
                pronto, resultado = self._pedidos_foto.get_nowait()
            except queue.Empty:
                return
            if resultado.get("cancelado"):
                continue
            try:
                with self._trava:
                    cliente = self._cliente
                if cliente is None:
                    raise camera.CameraErro("A conexão com a câmera caiu.")
                try:
                    resultado["imagem"] = cliente.foto(resultado["canal"])
                except (OSError, camera.CameraErro):
                    if self._parar.is_set():
                        raise camera.CameraErro("A conexão com a câmera foi fechada.") from None
                    resultado["imagem"] = self.dispositivo.foto_rtsp(resultado["canal"])
            except (OSError, camera.CameraErro) as erro:
                resultado["erro"] = str(erro)
            finally:
                pronto.set()

    def fotos_agora(self) -> list[Path]:
        """Uma foto de cada lente, agora (o pedido por voz ou pelo painel)."""
        lentes = [None] if self.lentes == 1 else list(range(self.lentes))
        return [self.guardar_foto(self.foto(lente or 0), lente) for lente in lentes]

    def guardar_foto(self, jpeg: bytes, lente: int | None = None) -> Path:
        if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            raise camera.CameraErro("A câmera respondeu sem uma foto JPEG válida.")
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.pasta, 0o700)
        nome = datetime.now(fuso.local()).strftime("%Y%m%d-%H%M%S")
        if lente is not None:
            nome += f"-lente{lente + 1}"
        destino = self.pasta / f"{nome}.jpg"
        sufixo = 1
        while destino.exists():
            destino = self.pasta / f"{nome}-{sufixo:03d}.jpg"
            sufixo += 1
        temporario = destino.with_suffix(".tmp")
        temporario.write_bytes(jpeg)
        os.chmod(temporario, 0o600)
        temporario.replace(destino)
        antigas = sorted(self.pasta.glob("*.jpg"))
        for velha in antigas[:-FOTOS]:
            with contextlib.suppress(OSError):
                velha.unlink()
        return destino

    def fotos(self) -> list[dict[str, Any]]:
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        imagens = sorted(self.pasta.glob("*.jpg"), reverse=True)[0:FOTOS]
        return [
            {
                "nome": imagem.name,
                "caminho": str(imagem),
                "quando": imagem.stat().st_mtime,
                "lente": _lente_do_nome(imagem.stem),
            }
            for imagem in imagens
            if imagem.is_file()
        ]

    def ler_foto(self, nome: str) -> Path:
        if Path(nome).name != nome or not nome.endswith(".jpg"):
            raise camera.CameraErro("Foto inválida.")
        caminho = self.pasta / nome
        try:
            caminho.resolve().relative_to(self.pasta.resolve())
            if not caminho.is_file():
                raise FileNotFoundError
        except (OSError, ValueError):
            raise camera.CameraErro("Foto não encontrada.") from None
        return caminho


def _canal(valor: Any, lentes: int) -> int:
    try:
        canal = int(valor)
    except (TypeError, ValueError):
        return 0
    return canal if 0 <= canal < lentes else 0


def _lente_do_nome(nome: str) -> int | None:
    """`20261112-180152-lente2` → 2; foto de câmera com uma lente só → None."""
    _, _, resto = nome.partition("-lente")
    numero = resto.split("-")[0]
    return int(numero) if numero.isdigit() else None
