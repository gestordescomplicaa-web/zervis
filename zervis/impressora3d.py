"""A impressora 3D na rede local (ADR 0083): uma Bambu Lab no modo só LAN com o modo
desenvolvedor ligado. O status e os comandos vão pelo MQTT dela (porta 8883, TLS, usuário `bblp`
e o código de acesso como senha); o arquivo fatiado sobe pelo FTPS implícito (porta 990) para o
cartão dela.

A conexão (o IP, o número de série e o código de acesso) é de quem usa: fica em
`<config>/impressora3d.json`, com permissão só do dono, e o código nunca volta para a tela.

Imprimir é uma ação física: quem chama pede o sim antes, e aqui a impressora só recebe um
trabalho quando está parada.
"""

import contextlib
import ftplib
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PORTA_MQTT = 8883
PORTA_FTP = 990
USUARIO = "bblp"
ESPERA_S = 12.0
# O começo do número de série diz o modelo (o perfil do Bambu Studio sai dele).
MODELOS = {"039": "A1", "030": "A1 mini", "01S": "P1P", "01P": "P1S", "00M": "X1 Carbon"}
ESTADOS = {
    "IDLE": "ociosa", "PREPARE": "preparando", "RUNNING": "imprimindo", "PAUSE": "pausada",
    "FINISH": "concluída", "FAILED": "falhou", "SLICING": "preparando",
}  # fmt: skip
LIVRE_PARA_IMPRIMIR = {"ociosa", "concluída", "falhou"}
COMANDOS = {"pausar": "pause", "retomar": "resume", "parar": "stop"}
ACOMPANHAR_S = 60.0


class ImpressoraErro(RuntimeError):
    """O que impede de falar com a impressora (o texto vai para a tela e para a voz)."""


@dataclass(frozen=True)
class Conexao:
    ip: str
    serie: str
    codigo: str

    @property
    def modelo(self) -> str:
        return MODELOS.get(self.serie[:3], "")


def _contexto_tls() -> ssl.SSLContext:
    # O certificado da impressora é da própria Bambu (BBL CA), sem nome que bata com o IP.
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto


# ---- achar a impressora na rede ----------------------------------------------------------


def nomes_do_certificado(der: bytes) -> list[str]:
    """Os CN de um certificado em DER (o da impressora traz o número de série)."""
    nomes = []
    for m in re.finditer(rb"\x55\x04\x03[\x0c\x13]([\x01-\x7f])", der):
        tamanho = m.group(1)[0]
        with contextlib.suppress(UnicodeDecodeError):
            nomes.append(der[m.end() : m.end() + tamanho].decode())
    return nomes


def porta_aberta(ip: str, espera_s: float = 0.4) -> bool:
    try:
        with socket.create_connection((ip, PORTA_MQTT), espera_s):
            return True
    except OSError:
        return False


def serie_em(ip: str, espera_s: float = 5.0) -> str | None:
    """O número de série da Bambu que responde nesse IP (None se não for uma). O TLS dela leva
    quase um segundo."""
    try:
        with (
            socket.create_connection((ip, PORTA_MQTT), espera_s) as bruto,
            _contexto_tls().wrap_socket(bruto) as seguro,
        ):
            der = seguro.getpeercert(binary_form=True) or b""
    except OSError:
        return None
    nomes = nomes_do_certificado(der)
    if not any("BBL" in n for n in nomes):
        return None
    return next((n for n in nomes if re.fullmatch(r"[0-9A-Z]{10,20}", n)), None)


def ip_local() -> str:
    """O IP desta máquina na rede local (o UDP não envia nada: só escolhe a rota)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))
        return str(s.getsockname()[0])


def descobrir() -> list[dict[str, str]]:
    """As impressoras Bambu na mesma rede /24 desta máquina: IP, número de série e modelo.
    Primeiro quem tem a porta aberta (rápido); depois, só nesses, o certificado."""
    rede = ipaddress.ip_network(f"{ip_local()}/24", strict=False)
    if not rede.is_private:
        return []
    with ThreadPoolExecutor(64) as fila:
        hosts = list(rede.hosts())
        respostas = fila.map(lambda ip: porta_aberta(str(ip)), hosts)
        abertos = [ip for ip, sim in zip(hosts, respostas, strict=True) if sim]
        series = list(fila.map(lambda ip: serie_em(str(ip)), abertos))
    return [
        {"ip": str(ip), "serie": serie, "modelo": MODELOS.get(serie[:3], "")}
        for ip, serie in zip(abertos, series, strict=True)
        if serie
    ]


# ---- o FTPS implícito (o cartão da impressora) ------------------------------------------


class _FTPImplicito(ftplib.FTP_TLS):
    """FTPS implícito, reaproveitando a sessão TLS no canal de dados (a Bambu exige)."""

    def __init__(self, contexto: ssl.SSLContext) -> None:
        super().__init__(context=contexto)
        self._contexto = contexto

    def connect(
        self, host: str = "", port: int = 0, timeout: float = -999, source_address: Any = None
    ) -> str:
        self.host, self.port = host, port
        if timeout != -999:
            self.timeout = timeout
        bruto = socket.create_connection((host, port), self.timeout)
        self.af = bruto.family
        self.sock = self._contexto.wrap_socket(bruto, server_hostname=host)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd: str, rest: Any = None) -> tuple[socket.socket, int | None]:
        conexao, tamanho = ftplib.FTP.ntransfercmd(self, cmd, rest)  # noqa: S321 (o TLS vem abaixo)
        if self._prot_p:  # type: ignore[attr-defined]
            conexao = self._contexto.wrap_socket(
                conexao,
                server_hostname=self.host,
                session=self.sock.session,  # type: ignore[union-attr]
            )
        return conexao, tamanho


def enviar_arquivo(conexao: Conexao, origem: Path, nome: str) -> None:
    ftp = _FTPImplicito(_contexto_tls())
    try:
        ftp.connect(conexao.ip, PORTA_FTP, timeout=30)
        ftp.login(USUARIO, conexao.codigo)
        ftp.prot_p()
        with origem.open("rb") as f:
            ftp.storbinary(f"STOR /{nome}", f)
    except (OSError, ftplib.Error) as erro:
        raise ImpressoraErro(f"O arquivo não chegou à impressora ({erro}).") from None
    finally:
        with contextlib.suppress(OSError, ftplib.Error):
            ftp.quit()


# ---- o MQTT -------------------------------------------------------------------------------


class Impressora3D:
    def __init__(
        self,
        arquivo: Path,
        mqtt: Callable[[Conexao, list[dict[str, Any]], float], dict[str, Any]] | None = None,
        enviar: Callable[[Conexao, Path, str], None] = enviar_arquivo,
    ) -> None:
        self.arquivo = arquivo
        self._mqtt = mqtt or conversar
        self._enviar = enviar
        self.ao_avisar: Callable[[str], None] | None = None  # o fim de uma impressão, falado
        self._acompanhando: threading.Thread | None = None

    # ---- a conexão de quem usa ----

    def conexao(self) -> Conexao | None:
        try:
            d = json.loads(self.arquivo.read_text())
            return Conexao(str(d["ip"]), str(d["serie"]), str(d["codigo"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def guardar(self, ip: str, serie: str, codigo: str) -> None:
        """Codigo vazio mantém o que estava (a tela nunca recebe o código de volta)."""
        try:
            endereco = ipaddress.ip_address(ip.strip())
        except ValueError:
            raise ImpressoraErro("Endereço IP inválido.") from None
        if not endereco.is_private:
            raise ImpressoraErro("A impressora precisa estar na rede local.")
        serie = serie.strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{10,20}", serie):
            raise ImpressoraErro("Número de série inválido.")
        codigo = codigo.strip() or (atual.codigo if (atual := self.conexao()) else "")
        if not re.fullmatch(r"[0-9A-Za-z]{6,16}", codigo):
            raise ImpressoraErro("Código de acesso inválido.")
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps({"ip": str(endereco), "serie": serie, "codigo": codigo}))
        os.chmod(temporario, 0o600)
        temporario.replace(self.arquivo)

    def para_tela(self) -> dict[str, Any]:
        c = self.conexao()
        if c is None:
            return {"configurada": False, "ip": "", "serie": "", "modelo": ""}
        return {"configurada": True, "ip": c.ip, "serie": c.serie, "modelo": c.modelo}

    def _exigir(self) -> Conexao:
        if (c := self.conexao()) is None:
            raise ImpressoraErro("Impressora não configurada.")
        return c

    # ---- status e comandos ----

    def status(self) -> dict[str, Any]:
        """O que a impressora diz agora, em português e só com o que importa."""
        bruto = self._mqtt(self._exigir(), [], ESPERA_S)
        return resumir(bruto)

    def comando(self, qual: str) -> None:
        if qual not in COMANDOS:
            raise ImpressoraErro("Comando desconhecido.")
        pedido = {"print": {"sequence_id": "0", "command": COMANDOS[qual]}}
        self._mqtt(self._exigir(), [pedido], 3.0)

    def imprimir(self, fatiado: Path, nome: str, bandeja: int | None) -> dict[str, Any]:
        """Manda o 3MF fatiado e começa: só com a impressora parada. `bandeja`: a do AMS (0 a 3,
        ou 4n+i no segundo AMS); None, o carretel de fora."""
        conexao = self._exigir()
        agora = self.status()
        if agora["estado"] not in LIVRE_PARA_IMPRIMIR:
            raise ImpressoraErro(f"A impressora está {agora['estado']}.")
        arquivo = re.sub(r"[^\w.-]+", "-", nome).strip("-.")[:60] + ".3mf"
        self._enviar(conexao, fatiado, arquivo)
        pedido = {
            "print": {
                "sequence_id": "0",
                "command": "project_file",
                "param": "Metadata/plate_1.gcode",
                "subtask_name": arquivo,
                "file": arquivo,
                "url": f"file:///sdcard/{arquivo}",
                "md5": "",
                "bed_type": "auto",
                "bed_levelling": True,
                "flow_cali": False,
                "vibration_cali": False,
                "layer_inspect": False,
                "timelapse": False,
                "use_ams": bandeja is not None,
                "ams_mapping": [bandeja] if bandeja is not None else [],
            }
        }
        self._mqtt(conexao, [pedido], 3.0)
        self.acompanhar(nome)
        return {"enviado": arquivo}

    def acompanhar(self, nome: str, intervalo_s: float = ACOMPANHAR_S) -> None:
        """Olha a impressora de tempos em tempos e avisa quando a impressão termina ou falha."""
        if self._acompanhando is not None and self._acompanhando.is_alive():
            return

        def olhar() -> None:
            comecou = False
            for _ in range(int(48 * 3600 / max(intervalo_s, 0.01))):
                time.sleep(intervalo_s)
                try:
                    estado = self.status()["estado"]
                except ImpressoraErro:
                    continue
                if estado in ("imprimindo", "preparando", "pausada"):
                    comecou = True
                elif comecou and estado in ("concluída", "falhou", "ociosa"):
                    if self.ao_avisar is not None:
                        self.ao_avisar(
                            f"A impressão de {nome} terminou."
                            if estado == "concluída"
                            else f"A impressão de {nome} parou antes do fim."
                        )
                    return

        self._acompanhando = threading.Thread(target=olhar, name="impressora3d", daemon=True)
        self._acompanhando.start()


def resumir(bruto: dict[str, Any]) -> dict[str, Any]:
    p = bruto.get("print") or {}
    bandejas = []
    for ams in (p.get("ams") or {}).get("ams") or []:
        for t in ams.get("tray") or []:
            if t.get("tray_type"):
                bandejas.append(
                    {
                        "indice": int(ams.get("id", 0)) * 4 + int(t.get("id", 0)),
                        "tipo": str(t["tray_type"]),
                        "marca": str(t.get("tray_sub_brands") or ""),
                        "cor": "#" + str(t.get("tray_color") or "")[:6],
                    }
                )
    externo = p.get("vt_tray") or {}
    return {
        "estado": ESTADOS.get(str(p.get("gcode_state") or ""), "desconhecido"),
        "percentual": int(p.get("mc_percent") or 0),
        "restante_min": int(p.get("mc_remaining_time") or 0),
        "camada": int(p.get("layer_num") or 0),
        "camadas": int(p.get("total_layer_num") or 0),
        "tarefa": str(p.get("subtask_name") or ""),
        "bico_c": round(float(p.get("nozzle_temper") or 0)),
        "mesa_c": round(float(p.get("bed_temper") or 0)),
        "bandejas": bandejas,
        "externo": str(externo.get("tray_type") or ""),
    }


def conversar(conexao: Conexao, pedidos: list[dict[str, Any]], espera_s: float) -> dict[str, Any]:
    """Conecta pelo MQTT, manda os pedidos e devolve o retrato completo da impressora (o
    `pushall`): cada pedido sai depois da conexão confirmada."""
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion

    retrato: dict[str, Any] = {}
    pronto, conectou = threading.Event(), threading.Event()
    erro: list[str] = []

    def ao_conectar(c: Any, _u: Any, _f: Any, codigo: Any, _p: Any = None) -> None:
        if getattr(codigo, "is_failure", False):
            erro.append(str(codigo))
            pronto.set()
            return
        conectou.set()
        c.subscribe(f"device/{conexao.serie}/report")
        for pedido in [*pedidos, {"pushing": {"sequence_id": "0", "command": "pushall"}}]:
            c.publish(f"device/{conexao.serie}/request", json.dumps(pedido))

    def ao_receber(_c: Any, _u: Any, mensagem: Any) -> None:
        with contextlib.suppress(ValueError):
            dados = json.loads(mensagem.payload)
            if isinstance(dados.get("print"), dict):
                retrato.setdefault("print", {}).update(dados["print"])
                if "gcode_state" in retrato["print"]:
                    pronto.set()

    cliente = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"ze-{os.getpid()}")
    cliente.username_pw_set(USUARIO, conexao.codigo)
    cliente.tls_set_context(_contexto_tls())
    cliente.on_connect, cliente.on_message = ao_conectar, ao_receber
    try:
        cliente.connect(conexao.ip, PORTA_MQTT, 30)
    except OSError:
        raise ImpressoraErro("Sem conexão com a impressora.") from None
    cliente.loop_start()
    try:
        pronto.wait(espera_s)
    finally:
        cliente.loop_stop()
        cliente.disconnect()
    if erro:
        raise ImpressoraErro("Código de acesso recusado.")
    if not conectou.is_set():
        raise ImpressoraErro("Sem conexão com a impressora.")
    if not pronto.is_set() and not pedidos:  # um comando já saiu com a conexão confirmada
        raise ImpressoraErro("A impressora não respondeu.")
    return retrato
