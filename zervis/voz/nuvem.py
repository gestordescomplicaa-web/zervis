"""Vozes pela nuvem (ElevenLabs e Fish Audio), opcionais, no lugar do Cadu (ADR 0041).

O Cadu (Piper, local) continua o padrão e a reserva. Sem chave, sem voz escolhida ou com o
provedor fora do ar (sem crédito, sem rede), a fala sai pelo Cadu e a Atividade diz por quê. O
texto de cada resposta falada vai ao provedor escolhido; o áudio do microfone, não.

Os provedores sintetizam em streaming (PCM de 16 bits) e o motor devolve no formato do Piper
(float32, frase a frase). Por isso a fila, a interrupção e o anel da `zervis/voz/saida.py` não
mudam. Uma conexão fica aberta entre as frases e é aquecida quando um pedido vai ao cérebro: o
aperto de mão TLS até o provedor custa centenas de milissegundos, que de outro jeito sairiam na
primeira frase de toda resposta.

Cada provedor é um módulo (`zervis/voz/elevenlabs.py`, `zervis/voz/fish.py`) com o mesmo
contrato: `NOME`, `TITULO`, `DESCRICAO`, `ENDERECO`, `CADASTRO`, `TAXA`, `motivo`, `conta`, `vozes`,
`voz_colada` e `pedido`. As chaves ficam em `<config>/<provedor>.key` (0600), gravadas pelo
painel; a escolha (motor e voz de cada provedor), em `<config>/voz.json`.
"""

import http.client
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

import numpy as np

from zervis import atividade, lugares
from zervis.voz import piper
from zervis.voz.deepgram import gravar_chave, ler_chave

log = logging.getLogger(__name__)

PRAZO_S = 5.0  # sem resposta nesse tempo, o Cadu fala a frase
PAUSA_DEPOIS_DE_FALHA_S = 60.0  # sem rede ou sem crédito, não atrasa cada frase tentando de novo
LOCAL = "piper"


class ErroVoz(RuntimeError):
    pass


@dataclass(frozen=True)
class Escolha:
    """O motor que fala e, de cada provedor, a última voz escolhida ({"id", "nome", "modelo"})."""

    motor: str = LOCAL
    vozes: dict[str, dict[str, str]] = field(default_factory=dict)

    def voz(self, provedor: str) -> dict[str, str]:
        return self.vozes.get(provedor) or {}

    def com_voz(self, provedor: str, voz: dict[str, str]) -> "Escolha":
        guardada = {k: str(voz.get(k, "")) for k in ("id", "nome", "modelo")}
        return Escolha(provedor, {**self.vozes, provedor: guardada})


def ler_escolha(arquivo: Path, motores: tuple[str, ...]) -> Escolha:
    try:
        dados = json.loads(arquivo.read_text())
        vozes = {
            str(p): {k: str(v.get(k, "")) for k in ("id", "nome", "modelo")}
            for p, v in dict(dados.get("vozes") or {}).items()
            if p in motores and isinstance(v, dict)
        }
        escolha = Escolha(str(dados["motor"]), vozes)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return Escolha()
    return escolha if escolha.motor in (LOCAL, *motores) else replace(escolha, motor=LOCAL)


def gravar_escolha(escolha: Escolha, arquivo: Path) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(
        json.dumps({"motor": escolha.motor, "vozes": escolha.vozes}, ensure_ascii=False)
    )
    temporario.replace(arquivo)


def amostra(titulo: str, nome: str) -> str:
    """A frase dita ao trocar de voz; o nome no texto evita que a regra de não repetir a cale."""
    return f"Oi! Agora eu falo com a voz {nome or titulo}."


# --- HTTP ---------------------------------------------------------------------------------------


def conexao(endereco: str, prazo: float = PRAZO_S) -> http.client.HTTPConnection:
    partes = urlsplit(endereco)
    tipo = http.client.HTTPSConnection if partes.scheme == "https" else http.client.HTTPConnection
    return tipo(partes.netloc, timeout=prazo)


def pedir(
    c: http.client.HTTPConnection,
    metodo: str,
    caminho: str,
    cabecalhos: dict[str, str],
    motivo: Callable[[int, bytes], str],
    corpo: dict[str, Any] | None = None,
) -> http.client.HTTPResponse:
    """Um pedido; recusa (4xx/5xx) vira `ErroVoz` com o motivo dito pelo provedor."""
    dados = None
    cabecalhos = {"Accept": "*/*", **cabecalhos}
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos["Content-Type"] = "application/json"
    c.request(metodo, caminho, body=dados, headers=cabecalhos)
    resposta = c.getresponse()
    if resposta.status >= 400:
        raise ErroVoz(motivo(resposta.status, resposta.read()))
    return resposta


def obter(
    endereco: str,
    caminho: str,
    cabecalhos: dict[str, str],
    motivo: Callable[[int, bytes], str],
    titulo: str,
) -> Any:
    """GET de JSON numa conexão própria (conferir chave, listar vozes)."""
    c = conexao(endereco, 10)
    try:
        return json.loads(pedir(c, "GET", caminho, cabecalhos, motivo).read())
    except (OSError, http.client.HTTPException, ValueError) as erro:
        raise ErroVoz(f"Sem conexão com o {titulo}.") from erro
    finally:
        c.close()


def detalhe_do_erro(corpo: bytes) -> tuple[str, str]:
    """(status, mensagem) de um corpo de erro em JSON, nos formatos que os provedores usam."""
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        return "", ""
    if not isinstance(dados, dict):
        return "", ""
    detalhe = dados.get("detail", dados)
    if not isinstance(detalhe, dict):
        return "", " ".join(str(detalhe).split())[:120]
    mensagem = detalhe.get("message", "")
    return str(detalhe.get("status", "")), " ".join(str(mensagem).split())[:120]


def recusa_generica(titulo: str, codigo: int, mensagem: str) -> str:
    if codigo == 401:
        return "Chave inválida."
    if codigo == 429:
        return f"Limite de pedidos do {titulo}."
    return f"Erro do {titulo} ({codigo})" + (f": {mensagem}." if mensagem else ".")


# --- a fala -------------------------------------------------------------------------------------


class FluxoPcm:
    """PCM 16 bits da resposta, devolvido em float32 como o Piper entrega (`saida.Fluxo`)."""

    def __init__(self, resposta: http.client.HTTPResponse, ao_fechar: Callable[[bool], None]):
        self.resposta: http.client.HTTPResponse | None = resposta
        self.ao_fechar = ao_fechar
        self.resto = b""
        self.inteiro = False  # leu até o fim: a conexão pode servir à próxima frase

    def read1(self, n: int = -1, /) -> bytes:
        while self.resposta is not None:
            dados = self.resposta.read1(16384)
            if not dados:
                self.inteiro = True
                self.close()
                return b""
            dados = self.resto + dados
            util = len(dados) // 2 * 2
            self.resto = dados[util:]
            if util:
                amostras = np.frombuffer(dados[:util], "<i2").astype("<f4") / 32768.0
                return amostras.astype("<f4").tobytes()
        return b""

    def close(self) -> None:
        resposta, self.resposta = self.resposta, None
        if resposta is not None:
            if not self.inteiro:
                resposta.close()
            self.ao_fechar(self.inteiro)


def provedores_padrao() -> dict[str, ModuleType]:
    from zervis.voz import elevenlabs, fish

    return {elevenlabs.NOME: elevenlabs, fish.NOME: fish}


class Motor:
    """Quem fala cada frase: o provedor escolhido, com chave e voz; senão (ou se falhar), o Cadu.
    Entrega `abrir_fluxo(texto) -> (taxa, fluxo)`, o contrato da `saida.Voz`."""

    def __init__(
        self,
        local: Any = piper.PADRAO,
        pasta: Path = lugares.CONFIG,
        provedores: dict[str, ModuleType] | None = None,
        enderecos: dict[str, str] | None = None,
    ) -> None:
        self.local = local
        self.pasta = pasta
        self.provedores = provedores if provedores is not None else provedores_padrao()
        self.enderecos = {
            n: (enderecos or {}).get(n, p.ENDERECO) for n, p in self.provedores.items()
        }
        self.arquivo_escolha = pasta / "voz.json"
        self._trava = threading.Lock()
        self._livres: dict[str, http.client.HTTPConnection] = {}  # abertas, prontas
        self._pausa_ate = 0.0
        self.ultimo_erro: str | None = None
        self.ultimo = LOCAL  # quem falou a última frase (latências)
        self._caracteres: tuple[str, dict[str, int]] = (time.strftime("%Y-%m-%d"), {})
        self.vozes: dict[str, list[dict[str, str]]] = {}  # a lista da tela, por provedor
        self.contas: dict[str, str] = {}  # o que a tela diz da conta (saldo, modelo)
        self.recarregar()

    def arquivo_chave(self, provedor: str) -> Path:
        return self.pasta / f"{provedor}.key"

    def recarregar(self) -> None:
        """O painel mudou uma chave ou a escolha: vale na próxima frase."""
        self.chaves = {n: ler_chave(self.arquivo_chave(n)) for n in self.provedores}
        self.escolha = ler_escolha(self.arquivo_escolha, tuple(self.provedores))
        self._pausa_ate = 0.0
        self.ultimo_erro = None

    def gravar(self, escolha: Escolha) -> None:
        gravar_escolha(escolha, self.arquivo_escolha)
        self.recarregar()

    @property
    def ativo(self) -> str | None:
        """O provedor que fala agora (escolhido, com chave e voz), ou None: o Cadu."""
        nome = self.escolha.motor
        if nome in self.provedores and self.chaves.get(nome) and self.escolha.voz(nome).get("id"):
            return nome
        return None

    @property
    def nuvem(self) -> bool:
        return self.ativo is not None

    def titulo(self, provedor: str) -> str:
        return str(self.provedores[provedor].TITULO) if provedor in self.provedores else "Cadu"

    def caracteres_hoje(self, provedor: str) -> int:
        dia, contagem = self._caracteres
        return contagem.get(provedor, 0) if dia == time.strftime("%Y-%m-%d") else 0

    def situacao(self) -> dict[str, Any]:
        return {
            "motor": self.ativo or LOCAL,
            "erro": self.ultimo_erro or "",
            "provedores": {
                n: {
                    "titulo": p.TITULO,
                    "descricao": p.DESCRICAO,
                    "cadastro": p.CADASTRO,
                    "chave": {
                        "tem": self.chaves.get(n) is not None,
                        "fim": (self.chaves.get(n) or "")[-4:],
                    },
                    "voz": self.escolha.voz(n).get("id", ""),
                    "nome": self.escolha.voz(n).get("nome", ""),
                    "caracteres_hoje": self.caracteres_hoje(n),
                }
                for n, p in self.provedores.items()
            },
        }

    # --- conexão -------------------------------------------------------------------------------

    def _pegar(self, provedor: str) -> tuple[http.client.HTTPConnection, bool]:
        """A conexão aberta, se houver uma livre (reaproveitada = True); senão, uma nova."""
        with self._trava:
            c = self._livres.pop(provedor, None)
        if c is not None:
            return c, True
        return conexao(self.enderecos[provedor]), False

    def _devolver(self, provedor: str, c: http.client.HTTPConnection) -> None:
        with self._trava:
            if provedor not in self._livres:
                self._livres[provedor] = c
                return
        c.close()

    def aquecer(self) -> None:
        """Abre a conexão antes da primeira frase (o cérebro ainda está pensando)."""
        provedor = self.ativo
        if provedor is None or time.monotonic() < self._pausa_ate:
            return
        with self._trava:
            if provedor in self._livres:
                return

        def abrir() -> None:
            c = conexao(self.enderecos[provedor])
            try:
                c.connect()
            except OSError:
                c.close()
                return
            self._devolver(provedor, c)

        threading.Thread(target=abrir, name="voz-aquecer", daemon=True).start()

    # --- síntese -------------------------------------------------------------------------------

    def _sintetizar(self, provedor: str, texto: str) -> FluxoPcm:
        p = self.provedores[provedor]
        voz = self.escolha.voz(provedor)
        chave = self.chaves[provedor] or ""
        caminho, corpo, cabecalhos = p.pedido(texto, voz["id"], voz.get("modelo", ""), chave)
        for tentativa in range(2):
            c, reaproveitada = self._pegar(provedor)
            try:
                resposta = pedir(c, "POST", caminho, cabecalhos, p.motivo, corpo)
            except ErroVoz:
                c.close()
                raise
            except (OSError, http.client.HTTPException) as erro:
                c.close()
                # Conexão parada há muito tempo: o servidor a fechou; uma nova resolve.
                if reaproveitada and tentativa == 0:
                    continue
                raise ErroVoz(f"Sem conexão com o {p.TITULO}.") from erro

            def ao_fechar(inteiro: bool, c: http.client.HTTPConnection = c) -> None:
                if inteiro:
                    self._devolver(provedor, c)
                else:
                    c.close()  # interrompida no meio: o resto da resposta não serve

            return FluxoPcm(resposta, ao_fechar)
        raise ErroVoz(f"Sem conexão com o {p.TITULO}.")  # pragma: no cover (o laço sempre sai)

    def _contar(self, provedor: str, texto: str) -> None:
        dia, contagem = self._caracteres
        hoje = time.strftime("%Y-%m-%d")
        contagem = dict(contagem) if dia == hoje else {}
        contagem[provedor] = contagem.get(provedor, 0) + len(texto)
        self._caracteres = (hoje, contagem)

    def abrir_fluxo(self, texto: str) -> tuple[int, Any]:
        provedor = self.ativo
        if provedor is not None and time.monotonic() >= self._pausa_ate:
            try:
                fluxo = self._sintetizar(provedor, texto)
            except ErroVoz as erro:
                self._falhou(provedor, str(erro))
            else:
                self._contar(provedor, texto)
                self.ultimo_erro = None
                self.ultimo = provedor
                return int(self.provedores[provedor].TAXA), fluxo
        self.ultimo = LOCAL
        taxa, fluxo = self.local.abrir_fluxo(texto)
        return int(taxa), fluxo

    def _falhou(self, provedor: str, mensagem: str) -> None:
        self._pausa_ate = time.monotonic() + PAUSA_DEPOIS_DE_FALHA_S
        titulo = self.titulo(provedor)
        log.warning("%s falhou (%s): o Cadu fala por um minuto", titulo, mensagem)
        if mensagem != self.ultimo_erro:
            atividade.PADRAO.registrar(
                "falha", f"A voz do {titulo} falhou; o Cadu falou no lugar", erro=mensagem
            )
        self.ultimo_erro = mensagem


def validar_chave(chave: str) -> str:
    chave = chave.strip()
    if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
        raise ErroVoz("Chave vazia ou com espaços.")
    return chave


def guardar_chave(motor: Motor, provedor: str, chave: str) -> None:
    gravar_chave(motor.arquivo_chave(provedor), chave)
