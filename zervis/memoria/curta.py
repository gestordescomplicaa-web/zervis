"""Memória curta (docs/02-investigacao-hermes.md, seção 1; requisitos R4.1, R4.3 e R4.4).

Dois arquivos curtos e curados em `~/.local/share/zervis/memoria/`:
- `USUARIO.md`: quem o usuário é, preferências, jeito de trabalhar;
- `JARVIS.md`: fatos do ambiente, convenções e lições do próprio Zé.
Entradas separadas por `§`, com limite rígido: memória cheia não compacta sozinha, o erro devolve
as entradas para o cérebro consolidar (curadoria em vez de acúmulo).

Entra no prompt como **foto congelada** no começo de cada sessão do cérebro: o que muda durante a
conversa vale na próxima. Toda escrita passa pela aprovação falada do usuário, menos o fato novo
que a revisão grava sozinha (ADR 0090); antes de qualquer uma, vêm a
varredura de segurança (o conteúdo vai parar no prompt de sistema) e pela checagem de duplicata
(o `USER.md` do Hermes acumulou entradas quase iguais sem revisão).

Validade (ADR 0098): uma entrada que só vale até um dia termina em ` · até DD/MM/AAAA`. No dia
seguinte ela sai da foto e, na próxima escrita, vai para o `ARQUIVO.md` (o arquivo é escrito
antes, então ela nunca some). Só sai assim o que venceu pela própria data; tirar uma entrada
que ainda vale continua pedindo a pessoa.
"""

import difflib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from zervis import fuso

SEPARADOR = "\n§\n"
ARQUIVOS = {"usuario": "USUARIO.md", "jarvis": "JARVIS.md"}
TITULOS = {"usuario": "Sobre o usuário", "jarvis": "Notas do Zé (ambiente e lições)"}
PARECIDO = 0.85
ARQUIVO = "ARQUIVO.md"  # as entradas que venceram, com o dia em que saíram
VALIDADE = re.compile(r"\s*·\s*até\s+(\d{1,2})/(\d{1,2})/(\d{4})\s*$", re.IGNORECASE)

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


def validade(texto: str) -> date | None:
    """O último dia em que a entrada vale, ou None se ela não tem validade (ou a data é
    impossível, o que a escrita recusa)."""
    achado = VALIDADE.search(texto)
    if not achado:
        return None
    dia, mes, ano = (int(g) for g in achado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def vencida(texto: str, hoje: date) -> bool:
    fim = validade(texto)
    return fim is not None and fim < hoje


def _hoje() -> date:
    return datetime.now(fuso.local()).date()


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


def normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in sem_acento if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class Mudanca:
    acao: str  # adicionar, trocar, remover
    alvo: str  # usuario, jarvis
    texto: str = ""
    antigo: str = ""


class Memoria:
    def __init__(
        self, pasta: Path, limites: dict[str, int], hoje: Callable[[], date] = _hoje
    ) -> None:
        self.pasta = pasta
        self.limites = limites
        self.hoje = hoje

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
        alvo = normal(antigo)
        achadas = [i for i, e in enumerate(entradas) if alvo and alvo in normal(e)]
        if len(achadas) != 1:
            quantas = "nenhuma entrada" if not achadas else "mais de uma entrada"
            raise MemoriaErro(f"{quantas} tem o trecho '{antigo}'; use um trecho único")
        return achadas[0]

    def vencidas(self, alvo: str) -> list[str]:
        """As entradas que já passaram da validade e ainda não foram para o arquivo."""
        hoje = self.hoje()
        return [e for e in self.entradas(alvo) if vencida(e, hoje)]

    def resultado(self, m: Mudanca) -> list[str]:
        """As entradas como ficariam, depois de todas as checagens; não grava nada. As vencidas
        não ficam: vão para o arquivo quando a mudança for gravada."""
        return self._plano(m)[0]

    def _plano(self, m: Mudanca) -> tuple[list[str], list[str]]:
        hoje = self.hoje()
        todas = self.entradas(m.alvo)
        entradas = [e for e in todas if not vencida(e, hoje)]
        saem = [e for e in todas if vencida(e, hoje)]
        texto = " ".join(m.texto.split())
        if m.acao in ("adicionar", "trocar"):
            if not texto:
                raise MemoriaErro("texto vazio")
            if motivo := varrer(texto):
                raise MemoriaErro(f"bloqueado pela varredura de segurança ({motivo})")
            if VALIDADE.search(texto):
                fim = validade(texto)
                if fim is None:
                    raise MemoriaErro("data de validade impossível; use ' · até DD/MM/AAAA'")
                if fim < hoje:
                    raise MemoriaErro("a validade já passou; o fato não vale mais")
        if m.acao == "adicionar":
            for e in entradas:
                if difflib.SequenceMatcher(None, normal(e), normal(texto)).ratio() >= PARECIDO:
                    raise MemoriaErro(
                        f"já existe uma entrada parecida: '{e}'; troque-a se precisar"
                    )
            novas = [*entradas, texto]
        elif m.acao == "trocar":
            novas = list(entradas)
            novas[self._achar(entradas, m.antigo)] = texto
        elif m.acao == "remover":
            novas = list(entradas)
            try:
                del novas[self._achar(entradas, m.antigo)]
            except MemoriaErro:
                # Tirar uma vencida: ela já sai, para o arquivo. Senão, vale o erro de antes.
                alvo = normal(m.antigo)
                if not alvo or sum(alvo in normal(e) for e in saem) != 1:
                    raise
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
        return novas, saem

    def aplicar(self, m: Mudanca) -> list[str]:
        novas, saem = self._plano(m)
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        if saem:  # o arquivo antes: uma entrada nunca fica fora dos dois
            self._arquivar(m.alvo, saem)
        arquivo = self._arquivo(m.alvo)
        temporario = arquivo.with_suffix(".next")
        temporario.write_text(SEPARADOR.join(novas) + ("\n" if novas else ""))
        temporario.chmod(0o600)
        temporario.replace(arquivo)
        return novas

    def arquivadas(self) -> list[str]:
        try:
            return [
                linha[2:]
                for linha in self._caminho_arquivo().read_text().splitlines()
                if linha.startswith("- ")
            ]
        except FileNotFoundError:
            return []

    def _caminho_arquivo(self) -> Path:
        return self.pasta / ARQUIVO

    def _arquivar(self, alvo: str, entradas: list[str]) -> None:
        caminho = self._caminho_arquivo()
        novo = not caminho.exists()
        dia = self.hoje().strftime("%d/%m/%Y")
        with caminho.open("a") as f:
            if novo:
                f.write("# Memória arquivada (entradas que passaram da validade)\n\n")
            f.writelines(f"- [{alvo}] {e} · arquivada em {dia}\n" for e in entradas)
        caminho.chmod(0o600)

    def foto(self) -> str:
        """O bloco que vai no prompt de sistema no começo da sessão."""
        partes = [
            "## Memória (foto do começo desta conversa)",
            "O que está abaixo foi aprovado pelo usuário. Mudanças aprovadas agora valem na "
            "próxima conversa.",
        ]
        hoje = self.hoje()
        for alvo, titulo in TITULOS.items():
            entradas = [e for e in self.entradas(alvo) if not vencida(e, hoje)]
            uso = len(SEPARADOR.join(entradas))
            partes.append(f"### {titulo} [{uso} de {self.limites[alvo]} caracteres]")
            if entradas:
                partes.extend(f"- {e}" for e in entradas)
            else:
                partes.append("(vazio)")
        return "\n".join(partes)
