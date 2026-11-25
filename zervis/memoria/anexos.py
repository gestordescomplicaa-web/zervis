"""Os anexos do chat do Início (ADR 0137): imagens, PDF e texto que quem usa manda ao Zé.

Cada anexo fica em `DADOS/anexos`, com um nome único (`AAAAMMDD-HHMMSS-xxxxxx-nome.ext`), 0600. O
pedido escrito leva os nomes no fim (`[anexos: a.jpg, b.pdf]`): é o que vai ao cérebro, à memória e
ao histórico, sem mudar a máquina de voz. O cérebro lê só esta pasta, pela ferramenta `anexo_ler`
(`cerebro/ferramentas/anexos.py`); o painel mostra a miniatura e o nome pela `info`.

Falhar fechado: tipo fora da lista, conteúdo que não bate com a extensão (um "PDF" que não começa
por %PDF), nome com caminho ou arquivo grande demais são recusados. O conteúdo de um anexo é dado,
nunca instrução (pode ser o contrato de outra pessoa): a leitura deixa o turno "de fora".
"""

import base64
import io
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zervis import lugares

MAX_BYTES = 20 * 1024 * 1024
MAX_POR_PEDIDO = 5
DIAS_GUARDADOS = 30  # depois disso o arquivo sai; o pedido no histórico fica, só com o nome
LADO_PARA_O_MODELO = 1568  # o maior lado que o modelo aproveita; mais é só peso
LADO_MINIATURA = 320
MAX_TEXTO = 60_000  # caracteres que a ferramenta devolve de um PDF ou texto

IMAGENS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
TEXTOS = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
}
TIPOS = {**IMAGENS, ".pdf": "application/pdf", **TEXTOS}
# O começo de cada tipo binário: a extensão não basta.
ASSINATURAS = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF-",),
}
GUARDADO = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}-[A-Za-z0-9._-]{1,80}$")
MARCA = re.compile(r"\s*\[anexos: ([^\]]+)\]$")


class AnexoErro(Exception):
    """Mensagem curta para o painel ("Tipo não aceito.")."""


def separar(pedido: str) -> tuple[str, list[str]]:
    """O texto do pedido e os nomes dos anexos marcados no fim."""
    if not (m := MARCA.search(pedido)):
        return pedido, []
    nomes = [n.strip() for n in m.group(1).split(",") if GUARDADO.match(n.strip())]
    return pedido[: m.start()], nomes


def marcar(texto: str, nomes: list[str]) -> str:
    """O pedido com os anexos no fim, como o cérebro e o histórico recebem."""
    return f"{texto} [anexos: {', '.join(nomes)}]" if nomes else texto


def _limpo(nome: str) -> str:
    base = Path(nome.replace("\\", "/")).name
    raiz, ext = Path(base).stem, Path(base).suffix.lower()
    raiz = re.sub(r"[^A-Za-z0-9._-]+", "-", raiz).strip("-.")[:60] or "anexo"
    return f"{raiz}{ext}"


class Anexos:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def guardar(self, nome: str, dados: bytes) -> str:
        """Guarda um anexo e volta o nome guardado."""
        limpo = _limpo(nome)
        ext = Path(limpo).suffix
        if ext not in TIPOS:
            raise AnexoErro("Tipo não aceito. Envie imagem, PDF ou texto.")
        if not dados:
            raise AnexoErro("Arquivo vazio.")
        if len(dados) > MAX_BYTES:
            raise AnexoErro("Arquivo maior que 20 MB.")
        if ext == ".webp" and not (dados[:4] == b"RIFF" and dados[8:12] == b"WEBP"):
            raise AnexoErro("O conteúdo não é do tipo do arquivo.")
        if ext in ASSINATURAS and not dados.startswith(ASSINATURAS[ext]):
            raise AnexoErro("O conteúdo não é do tipo do arquivo.")
        if ext in TEXTOS:
            try:
                dados.decode("utf-8")
            except UnicodeDecodeError:
                raise AnexoErro("O texto não está em UTF-8.") from None
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._limpar_antigos()
        guardado = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}-{limpo}"
        destino = self.pasta / guardado
        temporario = destino.with_name(f".{guardado}.parcial")
        temporario.write_bytes(dados)
        temporario.chmod(0o600)
        temporario.rename(destino)
        return guardado

    def caminho(self, guardado: str) -> Path | None:
        """O arquivo de um nome guardado, ou None (nome fora do formato ou que não existe)."""
        if not GUARDADO.match(guardado):
            return None
        alvo = self.pasta / guardado
        return alvo if alvo.is_file() else None

    def info(self, guardado: str) -> dict[str, Any]:
        """Para o chat: o nome original, o tipo, o tamanho e, numa imagem, a miniatura."""
        original = guardado.split("-", 3)[-1] if GUARDADO.match(guardado) else guardado
        ext = Path(original).suffix.lower()
        dado: dict[str, Any] = {"nome": original, "tipo": TIPOS.get(ext, ""), "tamanho": 0}
        if (alvo := self.caminho(guardado)) is None:
            return dado
        dado["tamanho"] = alvo.stat().st_size
        if ext in IMAGENS and (mini := _jpeg(alvo.read_bytes(), LADO_MINIATURA, 80)):
            dado["miniatura"] = "data:image/jpeg;base64," + base64.b64encode(mini).decode()
        return dado

    def ler(self, guardado: str) -> tuple[str, bytes | str]:
        """Para o cérebro: ("imagem", o JPEG ou o original) ou ("texto", o texto do arquivo)."""
        if (alvo := self.caminho(guardado)) is None:
            raise AnexoErro("Anexo não encontrado.")
        ext = alvo.suffix.lower()
        dados = alvo.read_bytes()
        if ext in IMAGENS:
            return "imagem", _jpeg(dados, LADO_PARA_O_MODELO, 85) or dados
        if ext == ".pdf":
            return "texto", _texto_do_pdf(dados)
        return "texto", _cortado(dados.decode("utf-8", errors="replace"))

    def _limpar_antigos(self) -> None:
        limite = time.time() - DIAS_GUARDADOS * 86400
        for arquivo in self.pasta.iterdir():
            if arquivo.is_file() and arquivo.stat().st_mtime < limite:
                arquivo.unlink(missing_ok=True)


def _jpeg(dados: bytes, lado: int, qualidade: int) -> bytes | None:
    """A imagem em JPEG com o maior lado até `lado`; None se não abrir."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(dados)) as imagem:
            imagem.seek(0)  # um GIF animado: o primeiro quadro
            copia = imagem.convert("RGB")
            copia.thumbnail((lado, lado))
            saida = io.BytesIO()
            copia.save(saida, "JPEG", quality=qualidade)
            return saida.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _texto_do_pdf(dados: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        leitor = PdfReader(io.BytesIO(dados))
        if leitor.is_encrypted:
            raise AnexoErro("O PDF tem senha.")
        paginas = [p.extract_text() or "" for p in leitor.pages[:200]]
    except (PdfReadError, ValueError, OSError):
        raise AnexoErro("Não foi possível ler o PDF.") from None
    texto = "\n\n".join(f"[página {i}]\n{t.strip()}" for i, t in enumerate(paginas, 1) if t.strip())
    if not texto:
        return "O PDF não tem texto selecionável (é uma imagem escaneada)."
    return _cortado(texto)


def _cortado(texto: str) -> str:
    if len(texto) <= MAX_TEXTO:
        return texto
    return texto[:MAX_TEXTO] + f"\n\n[cortado: o arquivo tem {len(texto)} caracteres]"


PADRAO = Anexos(lugares.DADOS / "anexos")
