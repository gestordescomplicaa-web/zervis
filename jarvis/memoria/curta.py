"""Memória curta (docs/02-investigacao-hermes.md, seção 1; requisitos R4.1, R4.3 e R4.4).

Dois arquivos curtos e curados em `~/.local/share/zervis/memoria/`:
- `USUARIO.md`: quem o usuário é, preferências, jeito de trabalhar;
- `JARVIS.md`: fatos do ambiente, convenções e lições do próprio Zé.
Entradas separadas por `§`, com limite rígido: memória cheia não compacta sozinha, o erro devolve
as entradas para o cérebro consolidar (curadoria em vez de acúmulo).

Entra no prompt como **foto congelada** no começo de cada sessão do cérebro: o que muda durante a
conversa vale na próxima. Toda escrita passa pela aprovação falada do usuário e, antes dela, pela
varredura de segurança (o conteúdo vai parar no prompt de sistema) e pela checagem de duplicata
(o `USER.md` do Hermes acumulou entradas quase iguais sem revisão).
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

SEPARADOR = "\n§\n"
ARQUIVOS = {"usuario": "USUARIO.md", "jarvis": "JARVIS.md"}
TITULOS = {"usuario": "Sobre o usuário", "jarvis": "Notas do Zé (ambiente e lições)"}
PARECIDO = 0.85

# Padrões que não podem virar prompt de sistema. Reimplementado com testes próprios a partir da
# ideia do `_scan_memory_content` do Hermes (MIT), sem copiar código.
SUSPEITOS = [
    (
        r"ignor\w*\s+(as\s+|todas\s+as\s+|all\s+|previous\s+|prior\s+)*(instru|instruction|regra)",
        "injeção",
    ),
    (
        r"(desconsider|esqueç|esquec|forget|disregard)\w*\s+.{0,30}(instru|instruction|regra|rules)",
        "injeção",
    ),
    (r"(system\s*prompt|prompt\s+de\s+sistema|<\|im_start\|>|<\|system\|>|\[/?inst\])", "injeção"),
    (r"(você|voce|you)\s+(agora\s+é|agora\s+e|are\s+now)\b", "injeção"),
    (r"(new|novas?)\s+(instructions|instruções|instrucoes)", "injeção"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "chave privada"),
    (r"\bssh-(rsa|ed25519|dss)\s+AAAA", "chave SSH"),
    (r"authorized_keys", "chave SSH"),
    (
        r"\b(sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9\-]{10,})",
        "credencial",
    ),
    (
        r"(senha|password|passwd|token|api[_\s-]?key)\b[^\n]{0,30}?(?:[:=]|\b(?:é|e|is)\b)\s*(?:(?=\S*\d)\S{6,}|\S{12,})",
        "credencial",
    ),
    (r"(curl|wget)\s+[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "comando remoto"),
]
INVISIVEIS = re.compile("[​-‏‪-‮⁠-⁤﻿]")


class MemoriaErro(ValueError):
    """Mensagem para o cérebro (não é falada como está)."""


def varrer(texto: str) -> str | None:
    """O motivo do bloqueio, ou None se o texto pode ir para a memória."""
    if INVISIVEIS.search(texto):
        return "caracteres invisíveis"
    if "§" in texto:
        return "o separador § não pode aparecer numa entrada"
    for padrao, motivo in SUSPEITOS:
        if re.search(padrao, texto, re.IGNORECASE):
            return motivo
    return None


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in sem_acento if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class Mudanca:
    acao: str  # adicionar, trocar, remover
    alvo: str  # usuario, jarvis
    texto: str = ""
    antigo: str = ""


class Memoria:
    def __init__(self, pasta: Path, limites: dict[str, int]) -> None:
        self.pasta = pasta
        self.limites = limites

    def _arquivo(self, alvo: str) -> Path:
        if alvo not in ARQUIVOS:
            raise MemoriaErro(f"alvo desconhecido: {alvo}; use usuario ou jarvis")
        return self.pasta / ARQUIVOS[alvo]

    def entradas(self, alvo: str) -> list[str]:
        try:
            bruto = self._arquivo(alvo).read_text()
        except FileNotFoundError:
            return []
        return [e.strip() for e in bruto.split("§") if e.strip()]

    def _achar(self, entradas: list[str], antigo: str) -> int:
        alvo = _normal(antigo)
        achadas = [i for i, e in enumerate(entradas) if alvo and alvo in _normal(e)]
        if len(achadas) != 1:
            quantas = "nenhuma entrada" if not achadas else "mais de uma entrada"
            raise MemoriaErro(f"{quantas} tem o trecho '{antigo}'; use um trecho único")
        return achadas[0]

    def resultado(self, m: Mudanca) -> list[str]:
        """As entradas como ficariam, depois de todas as checagens; não grava nada."""
        entradas = self.entradas(m.alvo)
        texto = " ".join(m.texto.split())
        if m.acao in ("adicionar", "trocar"):
            if not texto:
                raise MemoriaErro("texto vazio")
            if motivo := varrer(texto):
                raise MemoriaErro(f"bloqueado pela varredura de segurança ({motivo})")
        if m.acao == "adicionar":
            for e in entradas:
                if difflib.SequenceMatcher(None, _normal(e), _normal(texto)).ratio() >= PARECIDO:
                    raise MemoriaErro(
                        f"já existe uma entrada parecida: '{e}'; troque-a se precisar"
                    )
            novas = [*entradas, texto]
        elif m.acao == "trocar":
            novas = list(entradas)
            novas[self._achar(entradas, m.antigo)] = texto
        elif m.acao == "remover":
            novas = list(entradas)
            del novas[self._achar(entradas, m.antigo)]
        else:
            raise MemoriaErro(f"ação desconhecida: {m.acao}")
        tamanho = len(SEPARADOR.join(novas))
        limite = self.limites[m.alvo]
        if tamanho > limite:
            atuais = " | ".join(entradas)
            raise MemoriaErro(
                f"memória cheia ({tamanho} de {limite} caracteres). Consolide antes: junte ou "
                f"remova entradas. Atuais: {atuais}"
            )
        return novas

    def aplicar(self, m: Mudanca) -> list[str]:
        novas = self.resultado(m)
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        arquivo = self._arquivo(m.alvo)
        temporario = arquivo.with_suffix(".next")
        temporario.write_text(SEPARADOR.join(novas) + ("\n" if novas else ""))
        temporario.chmod(0o600)
        temporario.replace(arquivo)
        return novas

    def foto(self) -> str:
        """O bloco que vai no prompt de sistema no começo da sessão."""
        partes = [
            "## Memória (foto do começo desta conversa)",
            "O que está abaixo foi aprovado pelo usuário. Mudanças aprovadas agora valem na "
            "próxima conversa.",
        ]
        for alvo, titulo in TITULOS.items():
            entradas = self.entradas(alvo)
            uso = len(SEPARADOR.join(entradas))
            partes.append(f"### {titulo} [{uso} de {self.limites[alvo]} caracteres]")
            if entradas:
                partes.extend(f"- {e}" for e in entradas)
            else:
                partes.append("(vazio)")
        return "\n".join(partes)
