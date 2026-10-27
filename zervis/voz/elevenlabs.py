"""Voz pelo ElevenLabs, opcional, no lugar do Cadu (ADR 0041).

O Cadu (Piper, local) continua o padrão e a reserva: sem chave, sem voz escolhida ou com o
ElevenLabs fora do ar (sem crédito, sem rede), a fala sai pelo Cadu, e a Atividade diz por quê.
O texto de cada resposta falada vai ao ElevenLabs; o áudio do microfone, não.

A síntese é em streaming (`/v1/text-to-speech/{voz}/stream`, PCM 16 bits a 24 kHz) e volta no
mesmo formato do Piper (float32 frase a frase), então a fila, a interrupção e o anel da
`zervis/voz/saida.py` não mudam. Uma conexão fica aberta entre as frases e é aquecida quando um
pedido vai ao cérebro: o aperto de mão TLS até os servidores do ElevenLabs custa centenas de
milissegundos, que de outro jeito sairiam na primeira frase de toda resposta.

A chave fica em `<config>/elevenlabs.key` (0600), gravada pelo painel; a escolha (motor e voz),
em `<config>/voz.json`. Conta e chave: https://elevenlabs.io/app/settings/api-keys
"""

import http.client
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import numpy as np

from zervis import atividade, lugares
from zervis.voz import piper
from zervis.voz.deepgram import gravar_chave, ler_chave

log = logging.getLogger(__name__)

ENDERECO = "https://api.elevenlabs.io"
CADASTRO = "https://elevenlabs.io/app/settings/api-keys"
# v4 Turbo: o recomendado para conversa em tempo real (~100 ms), com o mesmo preço por
# caractere do Flash v2.5 (US$ 0,04 por mil na tabela de 27/10/2026).
MODELO = "eleven_v4_turbo"
TAXA = 24000
IDIOMA = "pt"
PRAZO_S = 5.0  # sem resposta nesse tempo, o Cadu fala a frase
PAUSA_DEPOIS_DE_FALHA_S = 60.0  # sem rede ou sem crédito, não atrasa cada frase tentando de novo
ARQUIVO_CHAVE = lugares.CONFIG / "elevenlabs.key"
ARQUIVO_ESCOLHA = lugares.CONFIG / "voz.json"
MOTORES = ("piper", "elevenlabs")
NOMES = {"piper": "Cadu", "elevenlabs": "ElevenLabs"}


class ErroVoz(RuntimeError):
    pass


@dataclass(frozen=True)
class Escolha:
    motor: str = "piper"
    voz: str = ""  # voice_id do ElevenLabs
    nome: str = ""  # nome da voz, para a tela


def amostra(escolha: Escolha) -> str:
    """A frase dita ao trocar de voz."""
    nome = "do Cadu" if escolha.motor == "piper" else escolha.nome or "nova"
    return f"Oi! Agora eu falo com a voz {nome}."


def ler_escolha(arquivo: Path = ARQUIVO_ESCOLHA) -> Escolha:
    try:
        dados = json.loads(arquivo.read_text())
        escolha = Escolha(
            str(dados["motor"]), str(dados.get("voz", "")), str(dados.get("nome", ""))
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return Escolha()
    return escolha if escolha.motor in MOTORES else Escolha()


def gravar_escolha(escolha: Escolha, arquivo: Path = ARQUIVO_ESCOLHA) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps(asdict(escolha), ensure_ascii=False))
    temporario.replace(arquivo)


# --- HTTP ---------------------------------------------------------------------------------------


def _conexao(endereco: str, prazo: float) -> http.client.HTTPConnection:
    partes = urlsplit(endereco)
    tipo = http.client.HTTPSConnection if partes.scheme == "https" else http.client.HTTPConnection
    return tipo(partes.netloc, timeout=prazo)


def motivo(codigo: int, corpo: bytes) -> str:
    """O que o ElevenLabs explica na recusa (`detail.status` e `detail.message`), em uma linha."""
    try:
        detalhe = json.loads(corpo or b"{}").get("detail") or {}
    except (ValueError, AttributeError):
        detalhe = {}
    situacao = str(detalhe.get("status", "")) if isinstance(detalhe, dict) else ""
    conhecidos = {
        "invalid_api_key": "Chave inválida.",
        "quota_exceeded": "Sem créditos no ElevenLabs.",
        "missing_permissions": "A chave não tem permissão para isso.",
        "voice_not_found": "Essa voz não existe mais na conta.",
        "paid_plan_required": "Essa voz exige um plano pago no ElevenLabs.",
    }
    if situacao in conhecidos:
        return conhecidos[situacao]
    if codigo == 401:
        return "Chave inválida."
    if codigo == 429:
        return "Limite de pedidos do ElevenLabs."
    mensagem = detalhe.get("message", "") if isinstance(detalhe, dict) else str(detalhe)
    explicacao = " ".join(str(mensagem).split())[:120]
    return f"Erro do ElevenLabs ({codigo})" + (f": {explicacao}." if explicacao else ".")


def _pedir(
    conexao: http.client.HTTPConnection,
    metodo: str,
    caminho: str,
    chave: str,
    corpo: dict[str, Any] | None = None,
) -> http.client.HTTPResponse:
    cabecalhos = {"xi-api-key": chave, "Accept": "*/*"}
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos["Content-Type"] = "application/json"
    conexao.request(metodo, caminho, body=dados, headers=cabecalhos)
    resposta = conexao.getresponse()
    if resposta.status >= 400:
        texto = resposta.read()
        raise ErroVoz(motivo(resposta.status, texto))
    return resposta


def _detalhe_da_voz(v: dict[str, Any]) -> str:
    rotulos = v.get("labels") or {}
    traducao = {"male": "masculina", "female": "feminina", "neutral": "neutra"}
    partes = [traducao.get(str(rotulos.get("gender", "")), "")]
    partes += [str(rotulos.get(k, "")) for k in ("accent", "age", "descriptive", "use_case")]
    return ", ".join(p.replace("_", " ") for p in partes if p)


def _fala_portugues(v: dict[str, Any]) -> bool:
    return any(
        str(idioma.get("language", "")).lower().startswith("pt")
        for idioma in v.get("verified_languages") or []
        if isinstance(idioma, dict)
    )


def vozes(chave: str, endereco: str = ENDERECO) -> list[dict[str, str]]:
    """As vozes da conta (as prontas do ElevenLabs e as da pessoa), as de português primeiro."""
    conexao = _conexao(endereco, 10)
    try:
        resposta = _pedir(conexao, "GET", "/v2/voices?page_size=100", chave)
        dados = json.loads(resposta.read())
    except (OSError, http.client.HTTPException) as erro:
        raise ErroVoz("Sem conexão com o ElevenLabs.") from erro
    finally:
        conexao.close()
    lista = [v for v in dados.get("voices") or [] if isinstance(v, dict) and v.get("voice_id")]
    lista.sort(
        key=lambda v: (
            not _fala_portugues(v),
            (v.get("labels") or {}).get("gender") != "male",  # "Zé": voz masculina primeiro
            str(v.get("name", "")).lower(),
        )
    )
    return [
        {"id": str(v["voice_id"]), "nome": str(v.get("name", "")), "detalhe": _detalhe_da_voz(v)}
        for v in lista
    ]


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


class Motor:
    """Quem fala cada frase: o ElevenLabs, quando escolhido e com chave; senão (ou se falhar),
    o Cadu. Entrega `abrir_fluxo(texto) -> (taxa, fluxo)`, o contrato da `saida.Voz`."""

    def __init__(
        self,
        local: Any = piper.PADRAO,
        arquivo_chave: Path = ARQUIVO_CHAVE,
        arquivo_escolha: Path = ARQUIVO_ESCOLHA,
        endereco: str = ENDERECO,
    ) -> None:
        self.local = local
        self.arquivo_chave = arquivo_chave
        self.arquivo_escolha = arquivo_escolha
        self.endereco = endereco
        self._trava = threading.Lock()
        self._livre: http.client.HTTPConnection | None = None  # aberta, pronta para a próxima
        self._pausa_ate = 0.0
        self.ultimo_erro: str | None = None
        self.ultimo = "piper"  # quem falou a última frase (latências)
        self.caracteres_hoje = (time.strftime("%Y-%m-%d"), 0)
        self.vozes: list[dict[str, str]] = []
        self.recarregar()

    def recarregar(self) -> None:
        """O painel mudou a chave ou a escolha: vale na próxima frase."""
        self.chave = ler_chave(self.arquivo_chave)
        self.escolha = ler_escolha(self.arquivo_escolha)
        self._pausa_ate = 0.0
        self.ultimo_erro = None

    @property
    def nuvem(self) -> bool:
        return self.escolha.motor == "elevenlabs" and bool(self.chave) and bool(self.escolha.voz)

    def situacao(self) -> dict[str, Any]:
        dia, total = self.caracteres_hoje
        return {
            "motor": self.escolha.motor if self.nuvem else "piper",
            "chave": {"tem": self.chave is not None, "fim": (self.chave or "")[-4:]},
            "voz": self.escolha.voz,
            "nome": self.escolha.nome,
            "caracteres_hoje": total if dia == time.strftime("%Y-%m-%d") else 0,
            "erro": self.ultimo_erro or "",
        }

    # --- conexão -------------------------------------------------------------------------------

    def _pegar(self) -> tuple[http.client.HTTPConnection, bool]:
        """A conexão aberta, se houver uma livre (reaproveitada = True); senão, uma nova."""
        with self._trava:
            conexao, self._livre = self._livre, None
        if conexao is not None:
            return conexao, True
        return _conexao(self.endereco, PRAZO_S), False

    def _devolver(self, conexao: http.client.HTTPConnection) -> None:
        with self._trava:
            if self._livre is None:
                self._livre = conexao
                return
        conexao.close()

    def aquecer(self) -> None:
        """Abre a conexão antes da primeira frase (o cérebro ainda está pensando)."""
        if not self.nuvem or time.monotonic() < self._pausa_ate:
            return
        with self._trava:
            if self._livre is not None:
                return

        def abrir() -> None:
            conexao = _conexao(self.endereco, PRAZO_S)
            try:
                conexao.connect()
            except OSError:
                conexao.close()
                return
            self._devolver(conexao)

        threading.Thread(target=abrir, name="elevenlabs-aquecer", daemon=True).start()

    # --- síntese -------------------------------------------------------------------------------

    def _sintetizar(self, texto: str, voz: str) -> FluxoPcm:
        assert self.chave is not None  # noqa: S101 (só com nuvem)
        caminho = f"/v1/text-to-speech/{quote(voz, safe='')}/stream?output_format=pcm_{TAXA}"
        corpo = {"text": texto, "model_id": MODELO, "language_code": IDIOMA}
        for tentativa in range(2):
            conexao, reaproveitada = self._pegar()
            try:
                resposta = _pedir(conexao, "POST", caminho, self.chave, corpo)
            except ErroVoz:
                conexao.close()
                raise
            except (OSError, http.client.HTTPException) as erro:
                conexao.close()
                # Conexão parada há muito tempo: o servidor a fechou; uma nova resolve.
                if reaproveitada and tentativa == 0:
                    continue
                raise ErroVoz("Sem conexão com o ElevenLabs.") from erro

            def ao_fechar(inteiro: bool, conexao: http.client.HTTPConnection = conexao) -> None:
                if inteiro:
                    self._devolver(conexao)
                else:
                    conexao.close()  # interrompida no meio: o resto da resposta não serve

            return FluxoPcm(resposta, ao_fechar)
        raise ErroVoz("Sem conexão com o ElevenLabs.")  # pragma: no cover (o laço sempre sai)

    def _contar(self, texto: str) -> None:
        dia, total = self.caracteres_hoje
        hoje = time.strftime("%Y-%m-%d")
        self.caracteres_hoje = (hoje, (total if dia == hoje else 0) + len(texto))

    def abrir_fluxo(self, texto: str) -> tuple[int, Any]:
        if self.nuvem and time.monotonic() >= self._pausa_ate:
            try:
                fluxo = self._sintetizar(texto, self.escolha.voz)
            except ErroVoz as erro:
                self._falhou(str(erro))
            else:
                self._contar(texto)
                self.ultimo_erro = None
                self.ultimo = "elevenlabs"
                return TAXA, fluxo
        self.ultimo = "piper"
        taxa, fluxo = self.local.abrir_fluxo(texto)
        return int(taxa), fluxo

    def _falhou(self, mensagem: str) -> None:
        self._pausa_ate = time.monotonic() + PAUSA_DEPOIS_DE_FALHA_S
        log.warning("ElevenLabs falhou (%s): o Cadu fala por um minuto", mensagem)
        if mensagem != self.ultimo_erro:
            atividade.PADRAO.registrar(
                "falha", "A voz do ElevenLabs falhou; o Cadu falou no lugar", erro=mensagem
            )
        self.ultimo_erro = mensagem


def guardar_chave(motor: Motor, chave: str) -> list[dict[str, str]]:
    """Confere a chave listando as vozes; só grava se ela vale. Devolve as vozes."""
    chave = chave.strip()
    if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
        raise ErroVoz("Chave vazia ou com espaços.")
    lista = vozes(chave, motor.endereco)
    if not lista:
        raise ErroVoz("A conta não tem nenhuma voz.")
    gravar_chave(motor.arquivo_chave, chave)
    return lista
