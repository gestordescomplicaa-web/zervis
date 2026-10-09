"""O Foco do Zé (08/10/2026): as frentes do usuário, para ele não se perder no que começou.

Pedido do usuário, que tem TDAH: o Zé é o funcionário que nunca cansa e o traz de volta para o
que ele começou, aprovou ou deixou pendente. Cada **frente** tem um próximo passo concreto, o
bloqueio (se houver), o projeto do Orca e o estado:

- `ativa`: em andamento (no máximo LIMITE ao mesmo tempo; passou disso, pausar uma antes);
- `pausada`: parada de propósito, volta quando ele quiser;
- `bloqueada`: travada por algo (o bloqueio diz o quê);
- `concluida`: feita (com a data; nada é apagado);
- `ideia`: o estacionamento de ideias: guardada sem virar frente nem roubar o foco;
- `descartada`: anotada por engano, repetida ou juntada a outra (some da tela e das falas, mas
  fica no arquivo: nada é apagado).

Uma frente ativa é **a atual** ("no que eu estava?"). As respostas faladas trazem uma coisa
só, ou no máximo três: nunca a lista inteira. Fica em `~/.local/share/zervis/foco/frentes.json`
(escrita atômica); cada mudança importante vai também para a linha do tempo.
"""

import difflib
import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis import fuso

FUSO = fuso.local()
LIMITE = 3
ESTADOS = ("ativa", "pausada", "bloqueada", "concluida", "ideia", "descartada")
ABERTAS = ("ativa", "bloqueada", "pausada")


class FocoErro(ValueError):
    pass


def agora() -> datetime:
    return datetime.now(FUSO)


def _simples(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join(
        "".join(c for c in t if not unicodedata.combining(c) and (c.isalnum() or c == " ")).split()
    )


def _id(titulo: str, usados: set[str]) -> str:
    base = "-".join(_simples(titulo).split()[:4])[:32] or "frente"
    candidato, n = base, 2
    while candidato in usados:
        candidato, n = f"{base}-{n}", n + 1
    return candidato


@dataclass
class Frente:
    id: str
    titulo: str
    estado: str
    criada: str
    atualizada: str
    proximo_passo: str = ""
    bloqueio: str = ""
    projeto: str = ""
    origem: str = "voz"
    atual: bool = False
    concluida_em: str = ""
    notas: list[str] = field(default_factory=list)  # "08/10 14:03 o agente terminou: …"

    def resumo(self) -> str:
        partes = [self.titulo]
        if self.projeto and _simples(self.projeto) not in _simples(self.titulo):
            partes.append(f"(projeto {self.projeto})")
        if self.estado == "bloqueada" and self.bloqueio:
            partes.append(f"— travada: {self.bloqueio}")
        elif self.proximo_passo:
            partes.append(f"— próximo passo: {self.proximo_passo}")
        return " ".join(partes)


class Foco:
    def __init__(
        self, arquivo: Path, ao_mudar: Callable[[str, Frente], None] | None = None
    ) -> None:
        self.arquivo = arquivo
        self.ao_mudar = ao_mudar  # (o que houve, frente): linha do tempo, comemoração
        self.frentes: list[Frente] = []
        self._carregar()

    # --- disco ---------------------------------------------------------------------------

    def _carregar(self) -> None:
        try:
            dados = json.loads(self.arquivo.read_text())
            self.frentes = [Frente(**d) for d in dados.get("frentes", [])]
        except (OSError, ValueError, TypeError):
            self.frentes = []

    def _gravar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(
            json.dumps({"frentes": [asdict(f) for f in self.frentes]}, ensure_ascii=False, indent=1)
        )
        temporario.replace(self.arquivo)

    def _avisar(self, o_que: str, frente: Frente) -> None:
        if self.ao_mudar is not None:
            self.ao_mudar(o_que, frente)

    # --- consultas -----------------------------------------------------------------------

    def com_estado(self, *estados: str) -> list[Frente]:
        return sorted(
            (f for f in self.frentes if f.estado in estados),
            key=lambda f: f.atualizada,
            reverse=True,
        )

    def atual(self) -> Frente | None:
        ativas = self.com_estado("ativa")
        return next((f for f in ativas if f.atual), ativas[0] if ativas else None)

    def pendentes(self, n: int = LIMITE) -> tuple[list[Frente], int]:
        """As n mais importantes (a atual, as outras ativas, as travadas, as pausadas) e o resto."""
        atual = self.atual()
        ordem = [atual] if atual else []
        ordem += [f for f in self.com_estado("ativa") if f is not atual]
        ordem += self.com_estado("bloqueada") + self.com_estado("pausada")
        return ordem[:n], max(0, len(ordem) - n)

    def achar(self, nome: str, estados: tuple[str, ...] = ABERTAS) -> Frente:
        """Pelo id, pelo título ou pelo projeto, tolerando a transcrição ("Ligatia" ~ "ligacia")."""
        alvo = _simples(nome)
        candidatas = [f for f in self.frentes if f.estado in estados]
        exata = next((f for f in candidatas if f.id == nome), None)
        if exata is not None:
            return exata
        for f in candidatas:
            if alvo in (f.id, _simples(f.titulo), _simples(f.projeto)):
                return f
        contem = [
            f
            for f in candidatas
            if alvo and (alvo in _simples(f.titulo) or alvo in _simples(f.projeto))
        ]
        if len(contem) == 1:
            return contem[0]
        nomes = {_simples(f.titulo): f for f in candidatas} | {
            _simples(f.projeto): f for f in candidatas if f.projeto
        }
        perto = difflib.get_close_matches(alvo, list(nomes), n=1, cutoff=0.6)
        if perto:
            return nomes[perto[0]]
        if len(contem) > 1:
            raise FocoErro(
                f"mais de uma frente com {nome!r}: " + "; ".join(f.titulo for f in contem)
            )
        raise FocoErro(f"nenhuma frente aberta com {nome!r}")

    # --- mudanças ------------------------------------------------------------------------

    def _tocar(self, f: Frente, nota: str = "") -> None:
        f.atualizada = agora().isoformat(timespec="seconds")
        if nota:
            f.notas = [*f.notas, f"{agora():%d/%m %H:%M} {nota}"][-12:]

    def _marcar_atual(self, alvo: Frente) -> None:
        for f in self.frentes:
            f.atual = f is alvo

    def criar(
        self,
        titulo: str,
        proximo_passo: str = "",
        projeto: str = "",
        origem: str = "voz",
        ideia: bool = False,
    ) -> Frente:
        titulo = " ".join(titulo.split())[:120]
        if not titulo:
            raise FocoErro("a frente precisa de um nome")
        try:  # a mesma frente aberta: atualiza em vez de duplicar
            existente = self.achar(titulo)
        except FocoErro:
            existente = None
        if existente is not None and not ideia:
            if proximo_passo:
                existente.proximo_passo = proximo_passo
            self._tocar(existente)
            self._gravar()
            return existente
        cheia = not ideia and len(self.com_estado("ativa")) >= LIMITE
        estado = "ideia" if ideia else ("pausada" if cheia else "ativa")
        momento = agora().isoformat(timespec="seconds")
        f = Frente(
            id=_id(titulo, {x.id for x in self.frentes}),
            titulo=titulo,
            estado=estado,
            criada=momento,
            atualizada=momento,
            proximo_passo=proximo_passo,
            projeto=projeto,
            origem=origem,
        )
        self.frentes.append(f)
        if estado == "ativa" and len(self.com_estado("ativa")) == 1:
            self._marcar_atual(f)
        self._gravar()
        self._avisar("ideia" if ideia else ("fila" if cheia else "criada"), f)
        return f

    def atualizar(
        self,
        nome: str,
        proximo_passo: str | None = None,
        bloqueio: str | None = None,
        estado: str | None = None,
        nota: str = "",
        titulo: str | None = None,
    ) -> Frente:
        f = self.achar(nome, (*ABERTAS, "ideia"))
        if titulo is not None and (novo := " ".join(titulo.split())[:120]):
            if novo != f.titulo:
                nota = nota or f"antes: {f.titulo}"
            f.titulo = novo
        if proximo_passo is not None:
            f.proximo_passo = " ".join(proximo_passo.split())[:200]
        if bloqueio is not None:
            f.bloqueio = " ".join(bloqueio.split())[:200]
            if f.bloqueio and estado is None:
                estado = "bloqueada"
        if estado is not None:
            self._mudar_estado(f, estado)
        self._tocar(f, nota)
        self._gravar()
        return f

    def _mudar_estado(self, f: Frente, estado: str) -> None:
        if estado not in ESTADOS:
            raise FocoErro(f"estado desconhecido: {estado}")
        if estado == "concluida":
            raise FocoErro("para concluir, use concluir")
        if estado == "ativa" and f.estado != "ativa" and len(self.com_estado("ativa")) >= LIMITE:
            ativas = ", ".join(x.titulo for x in self.com_estado("ativa"))
            raise FocoErro(f"já há {LIMITE} frentes ativas ({ativas}); pause uma antes")
        if estado != "bloqueada":
            f.bloqueio = "" if estado == "ativa" else f.bloqueio
        anterior, f.estado = f.estado, estado
        if estado != "ativa":
            f.atual = False
        if anterior != estado:
            self._avisar({"ativa": "retomada", "pausada": "pausada"}.get(estado, estado), f)

    def juntar(self, manter: str, outras: list[str], titulo: str = "") -> Frente:
        """Várias anotações do mesmo assunto viram uma (as outras ficam descartadas)."""
        f = self.achar(manter, (*ABERTAS, "ideia"))
        juntadas = [self.achar(n, (*ABERTAS, "ideia")) for n in outras]
        juntadas = [x for x in juntadas if x is not f]
        if not juntadas:
            raise FocoErro("nada para juntar")
        for x in juntadas:
            x.estado, x.atual = "descartada", False
            self._tocar(x, f"juntada em {f.titulo}")
            if x.proximo_passo and not f.proximo_passo:
                f.proximo_passo = x.proximo_passo
        if titulo and (novo := " ".join(titulo.split())[:120]):
            f.titulo = novo
        self._tocar(f, "juntou: " + "; ".join(x.titulo for x in juntadas))
        self._gravar()
        return f

    def focar(self, nome: str) -> Frente:
        """Esta passa a ser a atual (ativando, se couber)."""
        f = self.achar(nome, (*ABERTAS, "ideia"))
        if f.estado != "ativa":
            self._mudar_estado(f, "ativa")
        self._marcar_atual(f)
        self._tocar(f)
        self._gravar()
        return f

    def concluir(self, nome: str) -> Frente:
        f = self.achar(nome)
        era_atual = f.atual
        f.estado, f.atual, f.bloqueio = "concluida", False, ""
        f.concluida_em = agora().isoformat(timespec="seconds")
        self._tocar(f, "concluída")
        if era_atual and (proxima := self.atual()) is not None:
            self._marcar_atual(proxima)
        self._gravar()
        self._avisar("concluida", f)
        return f

    def anotar_projeto(self, projeto: str, nota: str, proximo_passo: str = "") -> Frente | None:
        """O que acontece num projeto (um agente terminou) entra na frente aberta dele."""
        alvo = _simples(projeto)
        f = next((x for x in self.com_estado(*ABERTAS) if _simples(x.projeto) == alvo), None)
        if f is None:
            return None
        if proximo_passo:
            f.proximo_passo = proximo_passo
        self._tocar(f, nota)
        self._gravar()
        return f

    def por_id(self, id_: str) -> Frente:
        f = next((x for x in self.frentes if x.id == id_), None)
        if f is None:
            raise FocoErro(f"frente {id_!r} não existe mais")
        return f

    def passo_feito(self, nome: str) -> tuple[Frente, str]:
        """O próximo passo foi feito: fica nas notas e o passo seguinte fica em aberto."""
        f = self.achar(nome)
        feito, f.proximo_passo = f.proximo_passo, ""
        self._tocar(f, f"passo feito: {feito}" if feito else "passo feito")
        self._gravar()
        self._avisar("passo feito", f)
        return f, feito

    def quadro(self) -> dict[str, Any]:
        """O que a vista Foco da tela mostra: a atual grande, as outras ativas, o resto contado."""

        def cartao(f: Frente) -> dict[str, Any]:
            mexida = datetime.fromisoformat(f.atualizada).strftime("%d/%m %H:%M")
            return {
                "id": f.id,
                "titulo": f.titulo,
                "proximo_passo": f.proximo_passo,
                "bloqueio": f.bloqueio,
                "projeto": f.projeto,
                "mexida": mexida,
            }

        atual = self.atual()
        return {
            "atual": cartao(atual) if atual else None,
            "ativas": [cartao(f) for f in self.com_estado("ativa") if f is not atual],
            "travadas": [cartao(f) for f in self.com_estado("bloqueada")],
            "pausadas": [cartao(f) for f in self.com_estado("pausada")],
            "ideias": [cartao(f) for f in self.com_estado("ideia")],
            "concluidas_hoje": sum(
                1
                for f in self.com_estado("concluida")
                if f.concluida_em[:10] == agora().date().isoformat()
            ),
            "limite": LIMITE,
        }

    # --- falas ---------------------------------------------------------------------------

    def onde_estava(self) -> str:
        f = self.atual()
        if f is None:
            pausadas = self.com_estado("pausada", "bloqueada")
            if pausadas:
                return f"Nenhuma frente ativa agora. A última parada foi: {pausadas[0].resumo()}."
            return "Nenhuma frente aberta. Quando começar algo, me diga que eu anoto."
        return f"Você estava em {f.resumo()}."

    def fala_do_quadro(self) -> str:
        """O que o Zé diz ao abrir o quadro: o que está nele, numa frase."""
        f = self.atual()
        if f is not None:
            passo = (
                f", próximo passo: {f.proximo_passo}. Marque o V quando fizer"
                if f.proximo_passo
                else ". Falta o próximo passo: me diga qual é"
            )
            return f"Seu foco na tela: {f.titulo}{passo}."
        paradas = len(self.com_estado("pausada", "bloqueada"))
        ideias = len(self.com_estado("ideia"))
        if ideias or paradas:
            partes = [
                f"{n} {um if n == 1 else varios}"
                for n, um, varios in (
                    (ideias, "ideia", "ideias"),
                    (paradas, "frente parada", "frentes paradas"),
                )
                if n
            ]
            return (
                "Nenhuma frente em andamento. Na tela: "
                + " e ".join(partes)
                + "; toque em Virar frente na que quiser começar."
            )
        return "Seu quadro está vazio. Me diga o que você começou que eu anoto."

    def falar_pendentes(self) -> str:
        top, resto = self.pendentes()
        if not top:
            return "Nada pendente nas suas frentes."
        texto = " ".join(f"{i}. {f.resumo()}." for i, f in enumerate(top, 1))
        if resto:
            texto += f" E mais {resto} parada{'s' if resto > 1 else ''}; peça se quiser ver."
        return texto


def nome_falado(texto: str) -> str:
    """Tira artigos do começo: "o Ligatia" -> "Ligatia"."""
    return re.sub(r"^(o|a|os|as|do|da|no|na)\s+", "", texto.strip(), flags=re.I)
