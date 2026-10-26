"""A entrada no painel de outro aparelho: senha, código do autenticador e aparelhos lembrados
(roteiro, passo 4.1).

O próprio PC entra sem senha. Qualquer outro aparelho (celular ou computador, pelo Wi-Fi, por um
túnel ou, adiante, pelo domínio da VPS) passa pela tela "Entrar": a senha e, com a verificação em
duas etapas ligada, o código de 6 dígitos do aplicativo autenticador (TOTP, RFC 6238: Google
Authenticator, Aegis, 1Password...). Com "lembrar este aparelho", 30 dias sem pedir de novo.

- A senha nunca é guardada: só o resultado do scrypt, com sal próprio. A semente do código fica no
  mesmo arquivo, `<config>/painel.json` (0600). Trocar a senha encerra todos os acessos.
- Cada aparelho recebe um código aleatório num cookie (HttpOnly, Secure, SameSite=Strict); o Zé
  guarda só o SHA-256 dele, com o aparelho e a origem, em `<estado>/painel-acessos.json` (0600).
- Cinco erros de um mesmo endereço em 15 minutos bloqueiam esse endereço por 15 minutos (quem
  ataca não tranca quem usa); 30 erros de qualquer lugar bloqueiam todos, contra tentativas
  espalhadas. Um código já usado não vale de novo.
- Primeiro acesso num servidor (sem o "próprio PC" para definir a senha): o instalador gera um
  convite de uso único, que vale uma hora e só enquanto não há senha. Quem tem o convite cria a
  senha pela tela Entrar; o convite some na hora. Guardamos só o resumo dele.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from zervis import lugares

ARQUIVO = lugares.CONFIG / "painel.json"
ACESSOS = lugares.ESTADO / "painel-acessos.json"
MINIMO = 8
LEMBRAR_S = 30 * 86400
SESSAO_S = 12 * 3600
TENTATIVAS = 5  # por endereço de origem
TENTATIVAS_TODOS = 30
JANELA_S = 15 * 60
SCRYPT = {"n": 2**14, "r": 8, "p": 1}
PASSO_S = 30  # o código muda a cada 30 s
DIGITOS = 6
CONVITE_S = 3600  # o convite do primeiro acesso vale uma hora
# Sem letras que se confundem (0/O, 1/I/L): o convite é lido no terminal e digitado no celular.
LETRAS_CONVITE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


# Ajustes de acesso que só valem pelo próprio PC (servidor do painel recusa de outro aparelho).
SO_NO_PC = {
    "acesso/senha",
    "acesso/encerrar",
    "acesso/desconectar",
    "acesso/codigo/preparar",
    "acesso/codigo/confirmar",
    "acesso/codigo/desligar",
    "tunel/ativar",
    "tunel/desativar",
    "tunel/fixar",
    "tunel/rapido",
    "remoto/ativar",
    "remoto/desativar",
    "ze/aplicar",
    "ze/sessao",
    "ze/central",
    "ze/unificar",
    "ze/diagnosticar",
    "ze/manutencao",
    "omniroute/salvar",
    "ze/descartar",
    "atualizacoes/canal",
    "atualizacoes/aplicar",
}


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


def codigo_totp(semente: str, passo: int) -> str:
    """O código de 6 dígitos de um passo de 30 s (RFC 6238, HMAC-SHA1)."""
    chave = base64.b32decode(semente + "=" * (-len(semente) % 8), casefold=True)
    resumo = hmac.new(chave, struct.pack(">Q", passo), hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    numero = struct.unpack(">I", resumo[deslocamento : deslocamento + 4])[0] & 0x7FFFFFFF
    return str(numero % 10**DIGITOS).zfill(DIGITOS)


def nome_do_aparelho(agente: str) -> str:
    """ "Android · Chrome" a partir do User-Agent, para a lista de aparelhos (um nome já curto
    fica como está)."""
    if " · " in agente:
        return agente
    sistema = next(
        (
            nome
            for padrao, nome in (
                (r"Android", "Android"),
                (r"iPhone|iPad", "iPhone"),
                (r"Windows", "Windows"),
                (r"Mac OS X|Macintosh", "Mac"),
                (r"Linux", "Linux"),
            )
            if re.search(padrao, agente)
        ),
        "Aparelho",
    )
    navegador = next(
        (
            nome
            for padrao, nome in (
                (r"Edg/", "Edge"),
                (r"Firefox/", "Firefox"),
                (r"Chrome/", "Chrome"),
                (r"Safari/", "Safari"),
            )
            if re.search(padrao, agente)
        ),
        "",
    )
    return f"{sistema} · {navegador}" if navegador else sistema


class Acesso:
    def __init__(
        self,
        arquivo: Path = ARQUIVO,
        acessos: Path = ACESSOS,
        agora: Callable[[], float] = time.time,
        ao_entrar: Callable[[str], None] | None = None,
    ) -> None:
        self.arquivo = arquivo
        self.acessos = acessos
        self.agora = agora
        self.ao_entrar = ao_entrar  # um aparelho entrou: o Zé avisa
        self.erros: dict[str, list[float]] = {}
        self.semente_pendente = ""  # a do código que a pessoa ainda está confirmando
        self._trava = threading.Lock()

    # --- senha -------------------------------------------------------------------------------

    @property
    def tem_senha(self) -> bool:
        return bool(_ler(self.arquivo).get("hash"))

    def definir(self, senha: str) -> None:
        if len(senha) < MINIMO:
            raise SenhaErro(f"A senha precisa de pelo menos {MINIMO} caracteres.")
        sal = secrets.token_bytes(16)
        resumo = hashlib.scrypt(senha.encode(), salt=sal, **SCRYPT)
        dados = {**_ler(self.arquivo), "sal": sal.hex(), "hash": resumo.hex(), **SCRYPT}
        _gravar(self.arquivo, dados)
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

    # --- convite do primeiro acesso (servidor) ------------------------------------------------

    def criar_convite(self, validade_s: float = CONVITE_S) -> str:
        """Um convite novo para criar a senha de fora; só enquanto não há senha."""
        with self._trava:
            if self.tem_senha:
                raise SenhaErro("O acesso já foi criado.")
            letras = "".join(secrets.choice(LETRAS_CONVITE) for _ in range(8))
            convite = f"{letras[:4]}-{letras[4:]}"
            dados = {
                **_ler(self.arquivo),
                "convite": _resumo(convite),
                "convite_expira": self.agora() + validade_s,
            }
            _gravar(self.arquivo, dados)
            return convite

    @property
    def convite_valido(self) -> bool:
        dados = _ler(self.arquivo)
        return (
            not dados.get("hash")
            and bool(dados.get("convite"))
            and float(dados.get("convite_expira", 0)) > self.agora()
        )

    def criar_acesso(
        self, convite: str, senha: str, aparelho: str = "", origem: str = ""
    ) -> tuple[str, int]:
        """Cria a senha com o convite e já entra; `SenhaErro` se o convite não valer."""
        with self._trava:
            agora = self.agora()
            if self._bloqueado(origem, agora):
                raise SenhaErro("Muitas tentativas. Tente de novo em alguns minutos.")
            dados = _ler(self.arquivo)
            limpo = re.sub(r"[^A-Z0-9]", "", convite.upper())
            digitado = f"{limpo[:4]}-{limpo[4:]}"
            if not self.convite_valido or not hmac.compare_digest(
                _resumo(digitado), str(dados.get("convite", ""))
            ):
                self.erros.setdefault(origem, []).append(agora)
                raise SenhaErro("Código de primeiro acesso inválido ou vencido.")
            if len(senha) < MINIMO:
                raise SenhaErro(f"A senha precisa de pelo menos {MINIMO} caracteres.")
            self.erros.pop(origem, None)
            sal = secrets.token_bytes(16)
            resumo = hashlib.scrypt(senha.encode(), salt=sal, **SCRYPT)
            dados = {k: v for k, v in dados.items() if not k.startswith("convite")}
            _gravar(self.arquivo, {**dados, "sal": sal.hex(), "hash": resumo.hex(), **SCRYPT})
            _gravar(self.acessos, {})
            codigo_aparelho, validade, nome = self._novo_aparelho(
                agora, False, aparelho, origem, duas_etapas=False
            )
        if self.ao_entrar is not None:
            self.ao_entrar(nome)
        return codigo_aparelho, validade

    # --- código do autenticador (verificação em duas etapas) ---------------------------------

    @property
    def tem_codigo(self) -> bool:
        return bool(_ler(self.arquivo).get("totp"))

    def preparar_codigo(self, conta: str = "") -> str:
        """Uma semente nova, ainda não valendo, e o endereço `otpauth://` para o QR."""
        self.semente_pendente = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        rotulo = quote(f"Zérvis:{conta}" if conta else "Zérvis")
        return f"otpauth://totp/{rotulo}?secret={self.semente_pendente}&issuer=Z%C3%A9rvis"

    def confirmar_codigo(self, codigo: str) -> None:
        """Liga a verificação em duas etapas se o código bater com a semente preparada."""
        if not self.semente_pendente:
            raise SenhaErro("Gere o código de novo.")
        if self._passo_valido(self.semente_pendente, codigo) is None:
            raise SenhaErro("Código incorreto. Confira a hora do celular.")
        _gravar(self.arquivo, {**_ler(self.arquivo), "totp": self.semente_pendente, "usado": 0})
        self.semente_pendente = ""
        self.sair_todos()

    def desligar_codigo(self) -> None:
        dados = _ler(self.arquivo)
        dados.pop("totp", None)
        dados.pop("usado", None)
        _gravar(self.arquivo, dados)

    def _passo_valido(self, semente: str, codigo: str) -> int | None:
        """O passo de 30 s em que o código vale (um passo de tolerância para cada lado)."""
        codigo = re.sub(r"\D", "", codigo)
        agora = int(self.agora() // PASSO_S)
        for passo in (agora - 1, agora, agora + 1):
            if len(codigo) == DIGITOS and hmac.compare_digest(codigo_totp(semente, passo), codigo):
                return passo
        return None

    # --- entrada -----------------------------------------------------------------------------

    def _bloqueado(self, origem: str, agora: float) -> bool:
        self.erros = {
            o: recentes
            for o, lista in self.erros.items()
            if (recentes := [t for t in lista if agora - t < JANELA_S])
        }
        todos = sum(len(lista) for lista in self.erros.values())
        return len(self.erros.get(origem, [])) >= TENTATIVAS or todos >= TENTATIVAS_TODOS

    def entrar(
        self,
        senha: str,
        codigo: str = "",
        lembrar: bool = False,
        aparelho: str = "",
        origem: str = "",
    ) -> tuple[str, int]:
        """O código do aparelho e por quantos segundos ele vale; `SenhaErro` se não entrar."""
        with self._trava:
            agora = self.agora()
            if self._bloqueado(origem, agora):
                raise SenhaErro("Muitas tentativas. Tente de novo em alguns minutos.")
            if not self.tem_senha:
                raise SenhaErro("Defina a senha de acesso no computador do Zé.")
            dados = _ler(self.arquivo)
            passo = None
            if dados.get("totp"):
                passo = self._passo_valido(str(dados["totp"]), codigo)
                if passo is not None and passo <= int(dados.get("usado", 0)):
                    passo = None  # código já usado: quem viu não reaproveita
            if not self._confere(senha) or (dados.get("totp") and passo is None):
                self.erros.setdefault(origem, []).append(agora)
                errou = "Senha ou código incorreto." if dados.get("totp") else "Senha incorreta."
                raise SenhaErro(errou)
            self.erros.pop(origem, None)
            if passo is not None:
                _gravar(self.arquivo, {**dados, "usado": passo})
            codigo_aparelho, validade, nome = self._novo_aparelho(
                agora, lembrar, aparelho, origem, duas_etapas=passo is not None
            )
        if self.ao_entrar is not None:
            self.ao_entrar(nome)
        return codigo_aparelho, validade

    def _novo_aparelho(
        self, agora: float, lembrar: bool, aparelho: str, origem: str, duas_etapas: bool
    ) -> tuple[str, int, str]:
        validade = LEMBRAR_S if lembrar else SESSAO_S
        codigo_aparelho = secrets.token_urlsafe(32)
        acessos = self._validos(agora)
        nome = nome_do_aparelho(aparelho)
        acessos[_resumo(codigo_aparelho)] = {
            "expira": agora + validade,
            "aparelho": nome,
            "origem": origem[:64],
            "desde": agora,
            "duas_etapas": duas_etapas,
        }
        _gravar(self.acessos, acessos)
        return codigo_aparelho, validade, nome

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

    def confiavel(self, codigo: str) -> bool:
        """Entrou com a senha e o código do autenticador: pode fazer ajustes de fora, num
        servidor (onde não há o próprio PC)."""
        if not self.valido(codigo):
            return False
        return bool(self._validos(self.agora())[_resumo(codigo)].get("duas_etapas"))

    def sair(self, codigo: str) -> None:
        self.desconectar(_resumo(codigo))

    def desconectar(self, resumo: str) -> None:
        with self._trava:
            acessos = self._validos(self.agora())
            acessos.pop(resumo, None)
            _gravar(self.acessos, acessos)

    def sair_todos(self) -> None:
        with self._trava:
            _gravar(self.acessos, {})

    def aparelhos(self) -> int:
        return len(self._validos(self.agora()))

    def lista(self) -> list[dict[str, Any]]:
        """Os aparelhos com acesso, do mais recente ao mais antigo, sem o código deles."""
        acessos = self._validos(self.agora())
        return sorted(
            (
                {
                    "id": k[:16],
                    "aparelho": nome_do_aparelho(str(v.get("aparelho", ""))),
                    "origem": v.get("origem", ""),
                    "desde": v.get("desde", 0),
                }
                for k, v in acessos.items()
            ),
            key=lambda a: -float(a["desde"]),
        )

    def desconectar_por_id(self, id_: str) -> None:
        alvo = next((k for k in self._validos(self.agora()) if k.startswith(id_)), None)
        if alvo is None or len(id_) < 16:
            raise SenhaErro("Aparelho não encontrado.")
        self.desconectar(alvo)
