"""A senha de acesso ao painel de outro aparelho (roteiro, passo 4.1).

O próprio PC entra sem senha. Qualquer outro aparelho (celular ou computador, pelo Wi-Fi, pelo
Tailscale ou, adiante, pelo domínio da VPS) passa pela tela "Entrar": a senha uma vez por aparelho
e, com "lembrar este aparelho", 30 dias sem pedir de novo.

- A senha nunca é guardada: só o resultado do scrypt (biblioteca padrão), com sal próprio, em
  `<config>/painel.json` (0600). Trocar a senha encerra todos os acessos.
- Cada aparelho recebe um código aleatório num cookie (HttpOnly, Secure, SameSite=Strict); o Zé
  guarda só o SHA-256 dele, em `<estado>/painel-acessos.json` (0600).
- Cinco senhas erradas em 15 minutos bloqueiam novas tentativas por 15 minutos.
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

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "painel.json"
ACESSOS = lugares.ESTADO / "painel-acessos.json"
MINIMO = 8
LEMBRAR_S = 30 * 86400
SESSAO_S = 12 * 3600
TENTATIVAS = 5
JANELA_S = 15 * 60
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class SenhaErro(ValueError):
    pass


def _gravar(arquivo: Path, dados: Any) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(json.dumps(dados))
    temporario.replace(arquivo)


def _ler(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _resumo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


class Acesso:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        acessos: Path = ACESSOS,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self.arquivo = arquivo
        self.acessos = acessos
        self.agora = agora
        self.erros: list[float] = []
        self._trava = threading.Lock()

    @property
    def tem_senha(self) -> bool:
        return bool(_ler(self.arquivo).get("hash"))

    def definir(self, senha: str) -> None:
        if len(senha) < MINIMO:
            raise SenhaErro(f"A senha precisa de pelo menos {MINIMO} caracteres.")
        sal = secrets.token_bytes(16)
        resumo = hashlib.scrypt(senha.encode(), salt=sal, **SCRYPT)
        _gravar(self.arquivo, {"sal": sal.hex(), "hash": resumo.hex(), **SCRYPT})
        self.sair_todos()

    def _confere(self, senha: str) -> bool:
        dados = _ler(self.arquivo)
        if not dados.get("hash"):
            return False
        try:
            resumo = hashlib.scrypt(
                senha.encode(),
                salt=bytes.fromhex(dados["sal"]),
                n=int(dados["n"]),
                r=int(dados["r"]),
                p=int(dados["p"]),
            )
        except (KeyError, ValueError):
            return False
        return hmac.compare_digest(resumo.hex(), str(dados["hash"]))

    def entrar(self, senha: str, lembrar: bool, aparelho: str = "") -> tuple[str, int]:
        """O código do aparelho e por quantos segundos ele vale; `SenhaErro` se não entrar."""
        with self._trava:
            agora = self.agora()
            self.erros = [t for t in self.erros if agora - t < JANELA_S]
            if len(self.erros) >= TENTATIVAS:
                raise SenhaErro("Muitas tentativas. Tente de novo em alguns minutos.")
            if not self.tem_senha:
                raise SenhaErro("Defina a senha de acesso no computador do Zé.")
            if not self._confere(senha):
                self.erros.append(agora)
                raise SenhaErro("Senha incorreta.")
            self.erros.clear()
            validade = LEMBRAR_S if lembrar else SESSAO_S
            codigo = secrets.token_urlsafe(32)
            acessos = self._validos(agora)
            acessos[_resumo(codigo)] = {
                "expira": agora + validade,
                "aparelho": aparelho[:120],
                "desde": agora,
            }
            _gravar(self.acessos, acessos)
            return codigo, validade

    def _validos(self, agora: float) -> dict[str, Any]:
        return {
            k: v
            for k, v in _ler(self.acessos).items()
            if isinstance(v, dict) and float(v.get("expira", 0)) > agora
        }

    def valido(self, codigo: str) -> bool:
        if not codigo or not self.tem_senha:
            return False
        return _resumo(codigo) in self._validos(self.agora())

    def sair(self, codigo: str) -> None:
        with self._trava:
            acessos = self._validos(self.agora())
            acessos.pop(_resumo(codigo), None)
            _gravar(self.acessos, acessos)

    def sair_todos(self) -> None:
        with self._trava:
            _gravar(self.acessos, {})

    def aparelhos(self) -> int:
        return len(self._validos(self.agora()))
