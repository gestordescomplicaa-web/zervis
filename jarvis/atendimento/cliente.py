"""O lado do Zé da Central de Atendimento: sobe o serviço, fala com a API e traz os eventos.

A Central (`central.py`) roda fora do Zé, no serviço do usuário `zervis-atendimento` (ou como
processo filho onde não há systemd). O Zé:

- sobe a Central quando o WhatsApp está escolhido ou quando a pessoa pede para conectar, e a
  reinicia se a versão do código dela não for a mesma do Zé (depois de uma atualização);
- mostra o estado pela API e manda "conectar", "desconectar" e "devolver";
- busca os eventos com espera longa: "passou" vira o aviso falado; "mensagem" vai para os avisos
  de lead quente. Ao subir, só repassa o que passou para você na última hora.
"""

import contextlib
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jarvis import lugares
from jarvis.atendimento import central, whatsapp
from jarvis.portal import tunel

log = logging.getLogger(__name__)

UNIDADE = "zervis-atendimento"
REGISTRO = lugares.ESTADO / "atendimento.log"
REPASSAR_S = 3600  # ao subir, o que passou para você há menos que isto ainda vira aviso
SUBIDA_S = 20.0
_AMBIENTE = ("PATH", "JARVIS_PERFIL", "JARVIS_RAIZ", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
             "XDG_STATE_HOME", "XDG_RUNTIME_DIR")  # fmt: skip


class CentralErro(RuntimeError):
    """Mensagem curta, pronta para a tela."""


def ambiente() -> dict[str, str]:
    """O que o serviço precisa herdar do Zé (o systemd não passa o ambiente de quem chama)."""
    return {k: os.environ[k] for k in _AMBIENTE if os.environ.get(k)}


def lancador() -> "tunel.Direto | tunel.Systemd":
    return tunel.Systemd(UNIDADE, ambiente()) if tunel.tem_systemd() else tunel.Direto()


class Cliente:
    def __init__(
        self,
        ao_evento: Callable[[dict[str, Any]], None],
        lancar: "tunel.Direto | tunel.Systemd | None" = None,
        estado: Path = central.ESTADO,
        token: Path = central.TOKEN,
        abrir: Callable[..., Any] = urllib.request.urlopen,
        comando: list[str] | None = None,
    ) -> None:
        self.ao_evento = ao_evento
        self.lancar = lancar or lancador()
        self.estado = estado
        self.arquivo_token = token
        self.abrir = abrir
        self.comando = comando or [sys.executable, "-m", "jarvis.atendimento"]
        self.whatsapp_ativo = False  # o WhatsApp está de pé na Central (lido a cada volta)
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None
        self._trava = threading.Lock()

    # --- a API ----------------------------------------------------------------------------

    def _porta(self) -> int:
        try:
            return int(json.loads(self.estado.read_text())["porta"])
        except (OSError, ValueError, KeyError, TypeError) as erro:
            raise CentralErro("Central de atendimento desligada.") from erro

    def _api(self, metodo: str, caminho: str, corpo: Any = None, espera: float = 10.0) -> Any:
        dados = None if corpo is None else json.dumps(corpo).encode()
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{self._porta()}{caminho}",
            data=dados,
            method=metodo,
            headers={
                "X-Atendimento-Token": central.garantir_token(self.arquivo_token),
                "Content-Type": "application/json",
            },
        )
        try:
            with self.abrir(pedido, timeout=espera) as resposta:
                return json.loads(resposta.read() or b"{}")
        except urllib.error.HTTPError as erro:
            with contextlib.suppress(ValueError, OSError):
                if mensagem := json.loads(erro.read() or b"{}").get("erro"):
                    raise CentralErro(str(mensagem)) from erro
            raise CentralErro("Sem conexão com a Central de atendimento.") from erro
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise CentralErro("Sem conexão com a Central de atendimento.") from erro

    def _saude(self) -> dict[str, Any] | None:
        try:
            resposta: dict[str, Any] = self._api("GET", "/saude", espera=3.0)
            return resposta
        except CentralErro:
            return None

    # --- o serviço --------------------------------------------------------------------------

    def garantir(self) -> None:
        """A Central de pé e na versão do Zé; sobe ou reinicia se preciso."""
        with self._trava:
            central.garantir_token(self.arquivo_token)
            esperada = central.versao()
            saude = self._saude()
            if saude is not None and saude.get("versao") == esperada:
                return
            if saude is not None or self.lancar.ativo():
                log.info("atendimento: reiniciando a Central (versão nova do código)")
                self.lancar.parar()
            with contextlib.suppress(OSError):
                self.estado.unlink()
            REGISTRO.parent.mkdir(parents=True, exist_ok=True)
            self.lancar.iniciar(self.comando, REGISTRO)
            fim = time.monotonic() + SUBIDA_S
            while time.monotonic() < fim:
                saude = self._saude()
                if saude is not None and saude.get("versao") == esperada:
                    log.info("atendimento: Central de pé")
                    return
                time.sleep(0.2)
            raise CentralErro("A Central de atendimento não subiu.")

    def parar_servico(self) -> None:
        self.lancar.parar()
        self.whatsapp_ativo = False

    # --- o que o painel usa -------------------------------------------------------------------

    def para_tela(self) -> dict[str, Any]:
        try:
            tela: dict[str, Any] = self._api("GET", "/whatsapp")
        except CentralErro:
            if whatsapp.escolhido():
                tela = {"estado": "iniciando"}
            else:
                pronto = whatsapp.go() is not None or whatsapp.binario() is not None
                tela = {"estado": "desligado" if pronto else "indisponivel", "falha": ""}
        self.whatsapp_ativo = tela.get("estado") not in ("desligado", "indisponivel", "iniciando")
        return tela

    def conectar(self) -> None:
        self.garantir()
        self._api("POST", "/whatsapp/conectar", {})
        self.iniciar_eventos()

    def desconectar(self) -> None:
        self.garantir()
        self._api("POST", "/whatsapp/desconectar", {}, espera=30.0)
        self.parar_servico()

    def pausados(self) -> list[dict[str, Any]]:
        try:
            lista = self._api("GET", "/pausados").get("pausados", [])
        except CentralErro:
            return []
        return [p for p in lista if isinstance(p, dict)]

    def devolver(self, telefone: str) -> None:
        self._api("POST", "/devolver", {"telefone": telefone})

    # --- os eventos ---------------------------------------------------------------------------

    def iniciar_eventos(self) -> None:
        if self._fio is not None and self._fio.is_alive():
            return
        self._parar.clear()
        self._fio = threading.Thread(target=self._ouvir, name="atendimento-eventos", daemon=True)
        self._fio.start()

    def _ouvir(self) -> None:
        visto: int | None = None
        while not self._parar.is_set():
            try:
                if visto is None:  # primeira leitura: só o que passou para você há pouco
                    r = self._api("GET", "/eventos?depois=0")
                    agora = time.time()
                    for e in r.get("eventos", []):
                        if e.get("tipo") == "passou" and agora - e.get("quando", 0) < REPASSAR_S:
                            self._entregar(e)
                    visto = int(r.get("ultimo", 0))
                    self.para_tela()
                    continue
                espera = central.ESPERA_EVENTOS_S
                r = self._api("GET", f"/eventos?depois={visto}&espera={espera}", espera=espera + 10)
                for e in r.get("eventos", []):
                    self._entregar(e)
                ultimo = int(r.get("ultimo", 0))
                if ultimo < visto:  # a Central reiniciou
                    visto = None
                    continue
                visto = ultimo
                self.para_tela()
            except CentralErro:
                visto = None
                self.whatsapp_ativo = False
                self._parar.wait(5.0)

    def _entregar(self, e: dict[str, Any]) -> None:
        try:
            self.ao_evento(e)
        except Exception:
            log.exception("atendimento: evento não tratado")

    def parar(self) -> None:
        """Para de ouvir; a Central continua (o atendimento não cai com o Zé)."""
        self._parar.set()
