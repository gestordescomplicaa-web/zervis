"""Ler, achar e listar as sessões, e gravar uma mudança nelas.
Funções da classe `Sessoes`, tiradas de `sessoes.py`; a classe repassa a chamada."""

import contextlib
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zervis.oficina import sessoes as ses

if TYPE_CHECKING:
    from zervis.oficina.sessoes import Sessoes


def ler(n: "Sessoes", id_: str) -> ses.Sessao:
    n._dir(id_)
    dados = n._dados.ler("sessoes", id_)
    if dados is None:
        raise ses.SessaoErro("sessão desconhecida")
    try:
        s = ses.Sessao(**dados)
        if s.limite and (not s.limite_conta or s.limite_conta != s.conta):
            # Versões anteriores inferiam limite pelo texto da tela, inclusive histórico.
            # Esse registro não comprova indisponibilidade da conta atual.
            s.limite = False
            s.limite_conta = ""
            if "bateu o limite" in s.resumo:
                s.resumo = ""
                s.estado = "parada"
        return s
    except (ValueError, TypeError):
        raise ses.SessaoErro("sessão desconhecida") from None


def achar(n: "Sessoes", ref: str) -> ses.Sessao:
    """A sessão pelo id ou pelo nome (sem acento nem maiúscula; basta um pedaço único);
    vazio é a sessão em foco."""
    ref = ref.strip()
    if not ref:
        id_, quando = n.em_foco
        if not id_ or time.time() - quando > ses.FOCO_S:
            raise ses.SessaoErro("diga de qual sessão se trata")
        return n.ler(id_)
    with contextlib.suppress(ses.SessaoErro):
        return n.ler(ref)
    alvo = ses._simples(ref)
    todas = n.listar()
    iguais = [x for x in todas if ses._simples(x.nome) == alvo]
    parecidas = iguais or [x for x in todas if alvo in ses._simples(x.nome)]
    if len(parecidas) == 1:
        return parecidas[0]
    if not parecidas:
        raise ses.SessaoErro(f"não há sessão {ref}")
    raise ses.SessaoErro("há mais de uma: " + ", ".join(x.nome for x in parecidas[:4]))


def listar(n: "Sessoes", incluir_arquivadas: bool = False) -> list[ses.Sessao]:
    return sorted(
        (
            ses.Sessao(**dados)
            for dados in n._dados.listar("sessoes")
            if incluir_arquivadas or not n.arquivada_em(str(dados["id"]))
        ),
        key=lambda s: s.atualizada,
        reverse=True,
    )


def _mudar(n: "Sessoes", id_: str, **campos: Any) -> ses.Sessao:
    with n.trava:
        s = n.ler(id_)
        if campos.get("conta", s.conta) != s.conta or campos.get("motor", s.motor) != s.motor:
            campos.setdefault("limite", False)
        if campos.get("limite") is True:
            campos["limite_conta"] = campos.get("conta", s.conta)
        for chave, valor in campos.items():
            setattr(s, chave, valor)
        if not s.limite:
            s.limite_conta = ""
        s.atualizada = ses.agora()
        n._gravar(s)
        return s


def _pasta_permitida(n: "Sessoes", pasta: str) -> Path:
    caminho = Path(pasta).expanduser().resolve()
    if not caminho.is_dir():
        raise ses.SessaoErro("essa pasta não existe")
    raiz = next((r for r in n.raizes if caminho == r or r in caminho.parents), None)
    if raiz is None:
        raise ses.SessaoErro("essa pasta está fora das pastas permitidas")
    if any(parte.startswith(".") for parte in caminho.relative_to(raiz).parts):
        raise ses.SessaoErro("pastas ocultas (configurações, chaves) não viram sessão")
    return caminho


LIMITE_NOME = 80


def nome_limpo(nome: str) -> str:
    """O nome de uma sessão: sem espaços sobrando e, se longo, cortado no fim de uma palavra."""
    limpo = " ".join(str(nome).split())
    if len(limpo) <= LIMITE_NOME:
        return limpo
    corte = limpo[: LIMITE_NOME - 1]
    return (corte.rsplit(" ", 1)[0] if " " in corte else corte).rstrip(" ·,;:-") + "…"


def renomear(n: "Sessoes", id_: str, nome: str) -> ses.Sessao:
    """Dá um nome novo à sessão: a voz e o painel passam a achá-la por ele."""
    limpo = nome_limpo(nome)
    if not limpo:
        raise ses.SessaoErro("diga o nome novo da sessão")
    antigo = n.ler(id_).nome
    s = _mudar(n, id_, nome=limpo)
    if limpo != antigo:
        n.anotar(id_, "sistema", f"Sessão renomeada de {antigo} para {limpo}.")
    return s
