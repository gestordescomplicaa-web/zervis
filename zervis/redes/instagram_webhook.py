"""Os avisos da Meta na hora (ADR 0122): um comentário ou uma mensagem no direct chega ao Zé no
instante em que é feito, sem esperar a conferência periódica.

A Meta chama `https://<endereço fixo do Zé>/instagram/webhook` (o túnel, ADR 0093):

- `GET` com `hub.mode=subscribe`, `hub.verify_token` e `hub.challenge`: a Meta confere o endereço
  quando quem usa o cadastra no painel de apps; o Zé devolve o desafio se o token for o dele.
- `POST` com o aviso, assinado com a chave secreta do app (`X-Hub-Signature-256`, HMAC-SHA256 do
  corpo). Sem a chave salva, ou com a assinatura errada, o aviso é recusado: a rota é pública,
  então só a assinatura prova que veio da Meta.

O aviso não é usado como dado: só acorda os ciclos que já existem (os comentários, ADR 0118, e a
conversa no direct, ADR 0119), que leem tudo pela API, com as mesmas travas (cada comentário uma
vez, nunca os da própria conta). Avisos que chegam durante uma volta viram uma volta a mais, não
várias. Depois do primeiro aviso assinado, a conferência periódica passa de 2 em 2 minutos para
de 30 em 30, só como rede de segurança (um aviso perdido).

Estado em `<config>/instagram-webhook.json` (0600): a chave secreta do app, o token de
verificação (gerado aqui), quando chegou o último aviso e quantos foram recusados.
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.redes.instagram import InstagramErro, _gravar_privado

log = logging.getLogger(__name__)

ARQUIVO = lugares.CONFIG / "instagram-webhook.json"
CAMINHO = "/instagram/webhook"
CAMPOS = "comments,messages"
FOLGA_S = 30 * 60  # com os avisos chegando, a conferência periódica é só a rede de segurança
_SEGREDO = re.compile(r"[A-Za-z0-9]{16,128}")


class Despertador:
    """Roda `fazer` numa thread assim que acordado. Acordar durante uma volta pede uma volta a
    mais (uma só, por mais avisos que cheguem); a thread nasce no primeiro aviso."""

    def __init__(self, fazer: Callable[[], None], nome: str = "instagram-avisos") -> None:
        self.fazer = fazer
        self.nome = nome
        self._pedido = threading.Event()
        self._trava = threading.Lock()
        self._thread: threading.Thread | None = None

    def acordar(self) -> None:
        self._pedido.set()
        with self._trava:
            if self._thread is None:
                self._thread = threading.Thread(target=self._laco, name=self.nome, daemon=True)
                self._thread.start()

    def _laco(self) -> None:
        while True:
            self._pedido.wait()
            self._pedido.clear()
            try:
                self.fazer()
            except Exception:  # um aviso que falha não derruba os próximos
                log.exception("instagram: falha ao atender um aviso da Meta")


class Webhook:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        agora: Callable[[], float] = time.time,
        assinar: Callable[[], None] | None = None,
    ) -> None:
        self.arquivo = arquivo
        self.agora = agora
        self._assinar = assinar or _assinar_na_meta
        self._trava = threading.Lock()
        self.acordar: Callable[[], None] | None = None  # quem atende (o agendador liga)

    # --- o estado -----------------------------------------------------------------------------

    def _ler(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            dados = {}
        return dados if isinstance(dados, dict) else {}

    def estado(self) -> dict[str, Any]:
        """O que o painel mostra (sem a chave secreta)."""
        d = self._ler()
        return {
            "configurado": bool(d.get("segredo")),
            "verificacao": self.verificacao(),
            "ultimo": float(d.get("ultimo") or 0),
            "recusados": int(d.get("recusados") or 0),
        }

    def verificacao(self) -> str:
        """O token que quem usa cola no painel de apps da Meta; gerado na primeira vez."""
        with self._trava:
            d = self._ler()
            if not d.get("verificacao"):
                d["verificacao"] = secrets.token_urlsafe(24)
                _gravar_privado(self.arquivo, d)
            return str(d["verificacao"])

    def confirmado(self) -> bool:
        """Já chegou um aviso assinado com a chave atual: a Meta está mandando."""
        d = self._ler()
        return bool(d.get("segredo") and d.get("ultimo"))

    def guardar(self, segredo: str) -> None:
        """Salva a chave secreta do app e assina a conta nos avisos de comentários e mensagens."""
        segredo = segredo.strip()
        if not _SEGREDO.fullmatch(segredo):
            raise InstagramErro("Chave secreta inválida.")
        self._assinar()
        with self._trava:
            d = self._ler()
            if d.get("segredo") != segredo:
                d.pop("ultimo", None)  # chave nova: espera o primeiro aviso assinado com ela
            d.update(segredo=segredo, recusados=0)
            _gravar_privado(self.arquivo, d)

    def esquecer(self) -> None:
        with self._trava:
            d = self._ler()
            for k in ("segredo", "ultimo", "recusados"):
                d.pop(k, None)
            _gravar_privado(self.arquivo, d)

    # --- a Meta chama -------------------------------------------------------------------------

    def desafio(self, consulta: str) -> str | None:
        """A conferência do endereço: o desafio, se o token for o nosso; None se não for."""
        q = dict(urllib.parse.parse_qsl(consulta))
        token = q.get("hub.verify_token", "")
        if q.get("hub.mode") != "subscribe" or not token:
            return None
        if not hmac.compare_digest(token.encode(), self.verificacao().encode()):
            return None
        return q.get("hub.challenge", "")[:200]

    def receber(self, corpo: bytes, assinatura: str) -> bool:
        """Confere a assinatura e acorda quem atende; False (recusado) se ela não confere."""
        d = self._ler()
        segredo = str(d.get("segredo") or "")
        esperada = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
        if not segredo or not hmac.compare_digest(assinatura.strip().encode(), esperada.encode()):
            with self._trava:
                d = self._ler()
                d["recusados"] = int(d.get("recusados") or 0) + 1
                _gravar_privado(self.arquivo, d)
            log.warning("instagram: aviso da Meta recusado (assinatura não confere)")
            return False
        with self._trava:
            d = self._ler()
            d["ultimo"] = self.agora()
            _gravar_privado(self.arquivo, d)
        if _interessa(corpo) and self.acordar is not None:
            self.acordar()
        return True


def _interessa(corpo: bytes) -> bool:
    """O aviso traz um comentário ou uma mensagem de outra pessoa? Os da própria conta (a resposta
    pública que o Zé deu, o eco da mensagem que ele mandou) não acordam ninguém."""
    try:
        aviso = json.loads(corpo or b"{}")
    except ValueError:
        return False
    if not isinstance(aviso, dict):
        return False
    for entrada in aviso.get("entry") or []:
        if not isinstance(entrada, dict):
            continue
        conta = str(entrada.get("id", ""))
        for mudanca in entrada.get("changes") or []:
            valor = (mudanca or {}).get("value") or {}
            de = str((valor.get("from") or {}).get("id", ""))
            if (mudanca or {}).get("field") == "comments" and de != conta:
                return True
        for m in entrada.get("messaging") or []:
            if not ((m or {}).get("message") or {}).get("is_echo"):
                return True
    return False


def _assinar_na_meta() -> None:
    """Assina a conta do Instagram (Login do Instagram) nos avisos de comentários e mensagens."""
    from zervis.redes import instagram_comentarios

    c = instagram_comentarios.PADRAO
    base, _conta, _token = c.instagram._token()
    if base != "ig":
        raise InstagramErro("Os avisos na hora pedem a conta conectada pelo Login do Instagram.")
    if not c._enviar("me/subscribed_apps", {"subscribed_fields": CAMPOS}).get("success"):
        raise InstagramErro("O Instagram recusou a assinatura dos avisos.")


PADRAO = Webhook()
