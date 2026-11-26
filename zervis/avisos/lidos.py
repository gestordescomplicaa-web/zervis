"""O que quem usa já viu e já leu no sino do painel (ADR 0139), como nas notificações de um app.

Dois passos, cada um por chave: **visto** quando o sino abre com o item na lista (o número do sino
conta só o que ainda não foi visto) e **lido** quando a pessoa clica nele (o ponto some). A chave
muda quando o item muda: um lead que manda outra mensagem ou mais uma sugestão de memória voltam
a ser novidade.

Fica em SQLite, no Zé: o computador e o celular veem o mesmo. Uma marca vale por 30 dias; os
avisos que já existiam na primeira vez contam como lidos, para o sino não começar cheio.
"""

import hashlib
import re
import time
from collections.abc import Iterable
from pathlib import Path

from zervis import lugares
from zervis.dados.documentos import Documentos

COMO = ("visto", "lido")
GUARDA_S = 30 * 24 * 3600
CHAVE = re.compile(r"^[0-9a-f]{16}$")


def chave(*partes: str) -> str:
    """A marca de um item: muda quando o que ele diz muda."""
    return hashlib.sha256("|".join(partes).encode()).hexdigest()[:16]


class Lidos:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self._dados: Documentos | None = None

    @property
    def dados(self) -> Documentos:
        if self._dados is None:  # o banco só nasce quando o sino é lido
            self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._dados = Documentos(self.arquivo)
        return self._dados

    def inicio(self) -> float:
        """Quando o sino passou a guardar as marcas (epoch): o que é de antes conta como lido."""
        if (marca := self.dados.ler("inicio", "inicio")) is None:
            marca = {"em": time.time()}
            self.dados.guardar("inicio", marca, "inicio")
        return float(marca["em"])

    def estado(self, chaves: Iterable[str]) -> dict[str, set[str]]:
        """Para cada chave marcada, o que já se fez com ela ({"visto"} ou {"visto", "lido"})."""
        lista = list(dict.fromkeys(chaves))
        marcas = self.dados.filtrar("marcas", "chave", lista, len(lista) or 1)
        return {str(m["chave"]): set(m.get("como") or ()) for m in marcas}

    def marcar(self, chaves: Iterable[str], como: str) -> None:
        if como not in COMO:
            raise ValueError(como)
        agora = time.time()
        feitos = {"visto", "lido"} if como == "lido" else {"visto"}
        validas = [c for c in dict.fromkeys(chaves) if CHAVE.match(c)]
        antes = self.estado(validas)
        with self.dados.banco.transacao():
            for c in validas:
                ja = antes.get(c, set())
                if not feitos <= ja:
                    self.dados.guardar(
                        "marcas", {"chave": c, "como": sorted(ja | feitos), "em": agora}, c
                    )
        self._esquecer(agora - GUARDA_S)

    def _esquecer(self, ate: float) -> None:
        with self.dados.banco.conexao() as db:
            db.execute(
                "DELETE FROM registros WHERE colecao='marcas' AND json_extract(dados,'$.em') < ?",
                (ate,),
            )


PADRAO = Lidos(lugares.DADOS / "avisos-lidos.db")
