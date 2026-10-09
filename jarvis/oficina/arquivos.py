"""O explorador de arquivos de uma sessão (como o do Orca e dos editores; 09/10/2026).

Tudo relativo à pasta da sessão e preso a ela: um caminho que, resolvido, sai da pasta (por
`..` ou por link simbólico) é recusado. Lê pastas uma de cada vez (a árvore abre sob demanda),
marca o que o git ignora, busca por nome ou por conteúdo e mostra um arquivo (texto até 200 KB;
imagem como data URL até 5 MB). Nunca entra em `.git`.
"""

import base64
import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Any

LIMITE_TEXTO = 200 * 1024
LIMITE_IMAGEM = 5 * 1024 * 1024
LIMITE_ITENS = 500
LIMITE_ACHADOS = 100
NUNCA = {".git"}
PESADAS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    "target",
    ".cache",
}
IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


class ArquivoErro(ValueError):
    """Mensagem curta para a tela."""


def dentro(base: Path, relativo: str) -> Path:
    """O caminho dentro da pasta da sessão, ou erro; resolve links antes de conferir."""
    base = base.resolve()
    partes = Path(relativo.strip().lstrip("/")).parts
    if any(p in NUNCA for p in partes):
        raise ArquivoErro("essa pasta não é mostrada")
    alvo = (base / Path(*partes)).resolve() if partes else base
    if alvo != base and base not in alvo.parents:
        raise ArquivoErro("fora da pasta da sessão")
    return alvo


def _ignorados(base: Path, nomes: list[str]) -> set[str]:
    if not nomes or not _no_git(base):
        return set()
    try:
        feito = subprocess.run(  # noqa: S603 (git fixo, entrada pelo stdin)
            ["git", "-C", str(base), "check-ignore", "--stdin"],  # noqa: S607
            input="\n".join(nomes),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {linha.strip().rstrip("/") for linha in feito.stdout.splitlines() if linha.strip()}


def _no_git(pasta: Path) -> bool:
    return any((p / ".git").exists() for p in (pasta, *pasta.parents))


def listar(base: Path, relativo: str = "") -> list[dict[str, Any]]:
    """O conteúdo de uma pasta: pastas primeiro, depois arquivos, em ordem alfabética."""
    pasta = dentro(base, relativo)
    if not pasta.is_dir():
        raise ArquivoErro("não é uma pasta")
    itens: list[dict[str, Any]] = []
    with os.scandir(pasta) as entradas:
        for e in entradas:
            if e.name in NUNCA:
                continue
            try:
                eh_pasta = e.is_dir()
                tamanho = 0 if eh_pasta else e.stat().st_size
            except OSError:
                continue
            caminho = str(Path(relativo.strip("/")) / e.name) if relativo.strip("/") else e.name
            itens.append(
                {"nome": e.name, "caminho": caminho, "pasta": eh_pasta, "tamanho": tamanho}
            )
    itens.sort(key=lambda i: (not i["pasta"], i["nome"].casefold()))
    itens = itens[:LIMITE_ITENS]
    ignorados = _ignorados(base.resolve(), [i["caminho"] for i in itens])
    for i in itens:
        i["ignorado"] = i["caminho"] in ignorados or i["nome"] in PESADAS
    return itens


def ler(base: Path, relativo: str) -> dict[str, Any]:
    arquivo = dentro(base, relativo)
    if not arquivo.is_file():
        raise ArquivoErro("arquivo não encontrado")
    tamanho = arquivo.stat().st_size
    sufixo = arquivo.suffix.lower()
    if sufixo in IMAGENS:
        if tamanho > LIMITE_IMAGEM:
            return {"caminho": relativo, "tipo": "grande", "tamanho": tamanho}
        tipo = mimetypes.guess_type(arquivo.name)[0] or "image/png"
        dados = base64.b64encode(arquivo.read_bytes()).decode()
        return {
            "caminho": relativo,
            "tipo": "imagem",
            "tamanho": tamanho,
            "url": f"data:{tipo};base64,{dados}",
        }
    bruto = arquivo.read_bytes()[:LIMITE_TEXTO]
    if b"\0" in bruto[:4096]:
        return {"caminho": relativo, "tipo": "binario", "tamanho": tamanho}
    return {
        "caminho": relativo,
        "tipo": "texto",
        "tamanho": tamanho,
        "cortado": tamanho > LIMITE_TEXTO,
        "texto": bruto.decode("utf-8", "replace"),
    }


def _andar(base: Path) -> list[Path]:
    achados: list[Path] = []
    for raiz, pastas, arquivos in os.walk(base):
        pastas[:] = sorted(p for p in pastas if p not in PESADAS)
        achados += [Path(raiz) / a for a in sorted(arquivos)]
        if len(achados) > 20000:
            break
    return achados


def buscar(base: Path, termo: str, modo: str = "nomes") -> list[dict[str, Any]]:
    """Por nome (parte do caminho) ou por conteúdo (linha a linha); no máximo cem achados."""
    termo = termo.strip()
    if len(termo) < 2:
        return []
    base = base.resolve()
    alvo = termo.casefold()
    saida: list[dict[str, Any]] = []
    if modo == "nomes":
        for arquivo in _andar(base):
            relativo = str(arquivo.relative_to(base))
            if alvo in relativo.casefold():
                saida.append({"caminho": relativo})
                if len(saida) >= LIMITE_ACHADOS:
                    break
        return saida
    for arquivo in _andar(base):
        try:
            if arquivo.stat().st_size > LIMITE_TEXTO:
                continue
            bruto = arquivo.read_bytes()
        except OSError:
            continue
        if b"\0" in bruto[:4096]:
            continue
        for numero, linha in enumerate(bruto.decode("utf-8", "replace").splitlines(), 1):
            if alvo in linha.casefold():
                saida.append(
                    {
                        "caminho": str(arquivo.relative_to(base)),
                        "linha": numero,
                        "trecho": linha.strip()[:160],
                    }
                )
                if len(saida) >= LIMITE_ACHADOS:
                    return saida
    return saida
