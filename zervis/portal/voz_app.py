"""O app de voz do Android (`android/`): pareado uma vez, abre só a voz (26/10/2026).

O app não tem tela: fala com o Zé com o celular bloqueado, pelo mesmo canal de voz do navegador
(ADR 0024), em `/voz-app/ws`. Ele não entra no painel: não tem a senha, o cookie nem o código
do painel. No lugar, uma chave só de voz, dada no pareamento:

1. No painel (Voz → App de voz), "Parear celular" mostra um código de uso único (10 minutos) e o
   QR com o endereço e o código.
2. O app manda o código a `/voz-app/parear`; o Zé devolve a chave e guarda só o resumo dela.
3. Cada conexão de voz leva a chave no cabeçalho `Authorization`. Remover o aparelho no painel
   corta a chave na hora.

Cinco códigos errados seguidos invalidam o código da vez: adivinhar exige pedir outro no painel.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis import lugares

ARQUIVO = lugares.CONFIG / "voz-app.json"  # os aparelhos pareados (só o resumo da chave), 0600
VALIDADE_S = 600.0
TENTATIVAS = 5
LETRAS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I/L, para ler e digitar
TAMANHO = 8
MAXIMO_APARELHOS = 10


class PareamentoErro(ValueError):
    """Código errado, vencido ou já usado (a mensagem vai para o app)."""


def _resumo(segredo: str) -> str:
    return hashlib.sha256(segredo.encode()).hexdigest()


def _ler(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(arquivo: Path, dados: dict[str, Any]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(json.dumps(dados))
    temporario.replace(arquivo)


def normalizar(codigo: str) -> str:
    """O que a pessoa digitou ("ab12-cd34", com espaço) no formato do código."""
    return "".join(c for c in codigo.upper() if c.isalnum())


class AparelhosDeVoz:
    def __init__(self, arquivo: Path = ARQUIVO, agora: Callable[[], float] = time.time) -> None:
        self.arquivo = arquivo
        self.agora = agora
        self._codigo: tuple[str, float] | None = None  # (resumo, vence em)
        self._erros = 0
        self._trava = threading.Lock()

    # --- pareamento --------------------------------------------------------------------------

    def novo_codigo(self) -> str:
        """Um código de uso único; o anterior deixa de valer."""
        codigo = "".join(secrets.choice(LETRAS) for _ in range(TAMANHO))
        with self._trava:
            self._codigo = (_resumo(codigo), self.agora() + VALIDADE_S)
            self._erros = 0
        return codigo

    def parear(self, codigo: str, nome: str) -> str:
        """Troca o código por uma chave só de voz (devolvida uma vez, nunca guardada)."""
        with self._trava:
            pendente = self._codigo
            if pendente is None or self.agora() > pendente[1]:
                self._codigo = None
                raise PareamentoErro("Código vencido. Peça outro no painel do Zé.")
            if not hmac.compare_digest(_resumo(normalizar(codigo)), pendente[0]):
                self._erros += 1
                if self._erros >= TENTATIVAS:
                    self._codigo = None
                raise PareamentoErro("Código errado.")
            self._codigo = None
            chave = secrets.token_urlsafe(32)
            dados = _ler(self.arquivo)
            aparelhos = dados.get("aparelhos", [])[-(MAXIMO_APARELHOS - 1) :]
            aparelhos.append(
                {
                    "id": secrets.token_hex(4),
                    "nome": (nome.strip() or "Android")[:60],
                    "resumo": _resumo(chave),
                    "desde": self.agora(),
                    "uso": 0.0,
                }
            )
            _gravar(self.arquivo, {**dados, "aparelhos": aparelhos})
            return chave

    # --- uso ---------------------------------------------------------------------------------

    def aparelho(self, chave: str) -> dict[str, Any] | None:
        """O aparelho dono desta chave (e anota o uso), ou None."""
        if not chave:
            return None
        resumo = _resumo(chave)
        with self._trava:
            dados = _ler(self.arquivo)
            for a in dados.get("aparelhos", []):
                if hmac.compare_digest(str(a.get("resumo", "")), resumo):
                    a["uso"] = self.agora()
                    _gravar(self.arquivo, dados)
                    return {k: v for k, v in a.items() if k != "resumo"}
        return None

    def lista(self) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in a.items() if k != "resumo"}
            for a in _ler(self.arquivo).get("aparelhos", [])
        ]

    def remover(self, id_: str) -> bool:
        with self._trava:
            dados = _ler(self.arquivo)
            antes = dados.get("aparelhos", [])
            depois = [a for a in antes if a.get("id") != id_]
            _gravar(self.arquivo, {**dados, "aparelhos": depois})
            return len(depois) != len(antes)
