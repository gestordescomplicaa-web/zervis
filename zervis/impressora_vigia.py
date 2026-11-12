"""O vigia da impressora 3D (ADR 0085): uma conexão MQTT que fica aberta enquanto o Zé roda, com
o estado chegando na hora, e os avisos que importam, falados.

- **O que vira aviso:** a impressão pausou por um erro (com o motivo), falhou, terminou, voltou de
  uma pausa, ou a primeira camada ficou pronta (onde a maioria das falhas começa). Vale também para
  uma impressão que não foi o Zé que mandou, e depois de um reinício (o retrato chega na conexão).
- **O motivo:** o código de erro da impressora, procurado na tabela oficial da Bambu que o Bambu
  Studio guarda na máquina (`hms_<idioma>_<modelo>.json`). Em português quando existe; senão, o
  Zé diz a categoria em português, tirada do próprio texto da Bambu ("acabou o filamento"), e o
  texto inteiro fica no painel. Sem a tabela, o código.
- **A foto:** nos avisos de erro, de fim e da primeira camada, uma foto da câmera da impressora
  (porta 6000, o protocolo da Bambu: 80 bytes de login e quadros JPEG) fica na pasta do Zé.

A impressora manda só o que mudou (o `pushall`, ao conectar, traz o retrato inteiro): o vigia
junta as partes num retrato só.
"""

import contextlib
import json
import logging
import socket
import struct
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis.impressora3d import Conexao, Impressora3D, _contexto_tls, resumir

log = logging.getLogger(__name__)
PORTA_CAMERA = 6000
FOTOS = 20  # as mais novas ficam
AVISOS = 30
# A categoria em português, achada no texto da própria Bambu (inglês).
CATEGORIAS = (
    (("run out", "ran out"), "acabou o filamento"),
    (("clog",), "o bico pode estar entupido"),
    (("foreign object",), "há algo sobre a mesa"),
    (("entangled", "tangled", "stuck spool"), "o filamento enroscou"),
    (("broken inside", "filament is broken"), "o filamento quebrou dentro do extrusor"),
    (("door", "front cover"), "a porta ou a tampa está aberta"),
    (("step loss", "is blocked", "blocked by"), "o cabeçote travou"),
    (("temperature",), "um problema de temperatura"),
    (("paused by the user",), "foi pausada na impressora"),
    (("cancel",), "foi cancelada"),
)


# ---- a tabela de erros da Bambu ----------------------------------------------------------


def pastas_da_tabela() -> list[Path]:
    """Onde o Bambu Studio guarda a tabela: a baixada (mais nova) e a que vem com ele."""
    casa = Path.home()
    pastas = [
        casa / ".var/app/com.bambulab.BambuStudio/config/BambuStudio/hms",
        casa / ".config/BambuStudio/hms",
    ]
    with contextlib.suppress(Exception):
        from zervis import fatiador

        if (estudio := fatiador.encontrar()) is not None:
            pastas.append(estudio.perfis.parent.parent / "hms")
    return [p for p in pastas if p.is_dir()]


def tabela(modelo: str, pastas: list[Path] | None = None) -> tuple[dict[str, str], str]:
    """{código: texto} do modelo (`039` na A1) e o idioma achado ("pt" ou "en")."""
    for idioma, arquivos in (("pt", ("pt-BR", "pt-PT")), ("en", ("en",))):
        for pasta in pastas if pastas is not None else pastas_da_tabela():
            for nome in arquivos:
                try:
                    dados = json.loads((pasta / f"hms_{nome}_{modelo}.json").read_text())["data"]
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                textos: dict[str, str] = {}
                for grupo in ("device_error", "device_hms"):
                    for lista in (dados.get(grupo) or {}).values():
                        if isinstance(lista, list):
                            for e in lista:
                                if isinstance(e, dict) and e.get("intro"):
                                    textos[str(e["ecode"]).upper()] = str(e["intro"])
                if textos:
                    return textos, idioma
    return {}, ""


def motivo(codigo: str, textos: dict[str, str], idioma: str) -> tuple[str, str]:
    """(o que o Zé fala, o texto inteiro para o painel) de um código de erro."""
    texto = textos.get(codigo.upper(), "")
    legivel = "_".join(codigo[i : i + 4] for i in range(0, len(codigo), 4))
    if texto and idioma == "pt":
        return texto.rstrip(". "), texto
    for chaves, frase in CATEGORIAS:
        if any(c in texto.lower() for c in chaves):
            return frase, texto
    return f"um erro, código {legivel}", texto or f"Código {legivel}"


# ---- a câmera ----------------------------------------------------------------------------


def foto(conexao: Conexao, espera_s: float = 10.0) -> bytes:
    """Um quadro JPEG da câmera da impressora."""
    login = struct.pack("<IIII", 0x40, 0x3000, 0, 0)
    login += b"bblp".ljust(32, b"\0") + conexao.codigo.encode().ljust(32, b"\0")
    with (
        socket.create_connection((conexao.ip, PORTA_CAMERA), espera_s) as bruto,
        _contexto_tls().wrap_socket(bruto) as s,
    ):
        s.settimeout(espera_s)
        s.sendall(login)

        def ler(n: int) -> bytes:
            dados = b""
            while len(dados) < n:
                if not (parte := s.recv(n - len(dados))):
                    raise OSError("a câmera fechou")
                dados += parte
            return dados

        tamanho = struct.unpack_from("<I", ler(16), 0)[0]
        if not 0 < tamanho < 8 * 1024 * 1024:
            raise OSError("quadro inválido")
        quadro = ler(tamanho)
    if not quadro.startswith(b"\xff\xd8"):
        raise OSError("a câmera não mandou uma imagem")
    return quadro


# ---- o que vira aviso --------------------------------------------------------------------


def nome_da_tarefa(tarefa: str) -> str:
    return tarefa.removesuffix(".3mf").removesuffix(".gcode").replace("-", " ").strip() or "peça"


def eventos(
    antes: dict[str, Any] | None, agora: dict[str, Any], textos: dict[str, str], idioma: str
) -> list[dict[str, Any]]:
    """Os avisos entre dois retratos resumidos: [{fala, texto, foto}]. O primeiro retrato (sem
    `antes`) só marca o ponto de partida."""
    if antes is None:
        return []
    n = nome_da_tarefa(agora["tarefa"])
    erro = agora.get("erro") or ""
    fala_erro, texto_erro = motivo(erro, textos, idioma) if erro else ("", "")
    estado, anterior = agora["estado"], antes["estado"]

    def evento(fala: str, foto_: bool, texto: str = "") -> dict[str, Any]:
        return {"fala": fala, "texto": texto or fala, "foto": foto_}

    if estado != anterior:
        if estado == "pausada" and erro:
            return [evento(f"A impressão de {n} pausou: {fala_erro}.", True, texto_erro)]
        if estado == "pausada":
            return [evento(f"A impressão de {n} está pausada.", False)]
        if estado == "cancelada":
            return [evento(f"A impressão de {n} foi cancelada.", False)]
        if estado == "falhou":
            fala = f"A impressão de {n} falhou" + (f": {fala_erro}." if erro else ".")
            return [evento(fala, True, texto_erro)]
        if estado == "concluída" and anterior in ("imprimindo", "pausada", "preparando"):
            return [evento(f"A impressão de {n} terminou.", True)]
        if estado == "imprimindo" and anterior == "pausada":
            return [evento(f"A impressão de {n} voltou.", False)]
        return []
    if estado == "imprimindo" and erro and erro != (antes.get("erro") or ""):
        return [evento(f"A impressora avisou: {fala_erro}.", True, texto_erro)]
    if estado == "imprimindo" and antes["camada"] <= 1 < agora["camada"] and agora["camadas"] > 2:
        return [evento(f"A primeira camada de {n} está pronta.", True)]
    return []


class Vigia:
    def __init__(
        self,
        impressora: Impressora3D,
        avisar: Callable[[str], None],
        pasta: Path,
        textos: Callable[[str], tuple[dict[str, str], str]] = tabela,
        fotografar: Callable[[Conexao], bytes] = foto,
    ) -> None:
        self.impressora = impressora
        self._avisar = avisar
        self.pasta = pasta
        self._textos = textos
        self._fotografar = fotografar
        self._trava = threading.Lock()
        self._retrato: dict[str, Any] = {}
        self._resumo: dict[str, Any] | None = None
        self._recebido = 0.0
        self._cliente: Any = None
        self._conexao: Conexao | None = None
        self._tabela: tuple[dict[str, str], str] = ({}, "")
        self.avisos: list[dict[str, Any]] = []
        impressora.retrato_vivo = self.retrato
        impressora.publicar = self.publicar
        impressora.fotografar = self.tirar_foto
        impressora.avisos = lambda: list(self.avisos)

    # ---- a conexão que fica aberta ----

    def iniciar(self) -> None:
        """Conecta (e reconecta sozinho) à impressora configurada; sem ela, nada."""
        self.parar()
        conexao = self.impressora.conexao()
        if conexao is None:
            return
        import paho.mqtt.client as mqtt
        from paho.mqtt.enums import CallbackAPIVersion

        self._conexao = conexao
        self._tabela = self._textos(conexao.serie[:3])
        cliente = mqtt.Client(
            CallbackAPIVersion.VERSION2, client_id=f"ze-vigia-{conexao.serie[-6:]}"
        )
        cliente.username_pw_set("bblp", conexao.codigo)
        cliente.tls_set_context(_contexto_tls())
        cliente.reconnect_delay_set(5, 60)

        def ao_conectar(c: Any, _u: Any, _f: Any, codigo: Any, _p: Any = None) -> None:
            if getattr(codigo, "is_failure", False):
                log.warning("vigia da impressora: conexão recusada (%s)", codigo)
                return
            c.subscribe(f"device/{conexao.serie}/report")
            self.publicar({"pushing": {"sequence_id": "0", "command": "pushall"}})

        cliente.on_connect = ao_conectar
        cliente.on_message = lambda _c, _u, m: self.receber(m.payload)
        cliente.connect_async(conexao.ip, 8883, 30)
        cliente.loop_start()
        self._cliente = cliente

    def parar(self) -> None:
        if self._cliente is not None:
            with contextlib.suppress(Exception):
                self._cliente.loop_stop()
                self._cliente.disconnect()
            self._cliente = None
        with self._trava:
            self._retrato, self._resumo, self._recebido = {}, None, 0.0

    def publicar(self, pedido: dict[str, Any]) -> bool:
        """Manda pela conexão aberta; False se ela não está de pé (quem chama abre outra)."""
        cliente, conexao = self._cliente, self._conexao
        if cliente is None or conexao is None or not cliente.is_connected():
            return False
        cliente.publish(f"device/{conexao.serie}/request", json.dumps(pedido))
        return True

    def retrato(self, idade_s: float = 15.0) -> dict[str, Any] | None:
        """O retrato completo, se chegou há pouco (senão, quem chama pergunta à impressora)."""
        with self._trava:
            if not self._retrato or time.monotonic() - self._recebido > idade_s:
                return None
            return {"print": dict(self._retrato)}

    # ---- o que chega ----

    def receber(self, carga: bytes) -> None:
        try:
            dados = json.loads(carga)
        except ValueError:
            return
        parte = dados.get("print") if isinstance(dados, dict) else None
        if not isinstance(parte, dict):
            return
        with self._trava:
            self._retrato.update(parte)
            self._recebido = time.monotonic()
            if "gcode_state" not in self._retrato:
                return  # ainda sem o retrato inteiro
            agora = resumir({"print": self._retrato})
            antes, self._resumo = self._resumo, agora
        textos, idioma = self._tabela
        for e in eventos(antes, agora, textos, idioma):
            threading.Thread(target=self._registrar, args=(e,), daemon=True).start()

    def _registrar(self, evento: dict[str, Any]) -> None:
        caminho = ""
        if evento["foto"] and self._conexao is not None:
            try:
                caminho = str(self.guardar_foto(self._fotografar(self._conexao)))
            except OSError as erro:
                log.info("vigia da impressora: sem foto (%s)", erro)
        aviso = {"quando": time.time(), "fala": evento["fala"], "texto": evento["texto"],
                 "foto": caminho}  # fmt: skip
        with self._trava:
            self.avisos = [aviso, *self.avisos][:AVISOS]
        self._avisar(evento["fala"])

    def guardar_foto(self, jpeg: bytes) -> Path:
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        destino = self.pasta / f"{time.strftime('%Y%m%d-%H%M%S')}.jpg"
        destino.write_bytes(jpeg)
        for velha in sorted(self.pasta.glob("*.jpg"))[:-FOTOS]:
            velha.unlink(missing_ok=True)
        return destino

    def tirar_foto(self) -> Path:
        conexao = self.impressora.conexao()
        if conexao is None:
            from zervis.impressora3d import ImpressoraErro

            raise ImpressoraErro("Impressora não configurada.")
        return self.guardar_foto(self._fotografar(conexao))
