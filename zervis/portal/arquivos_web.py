"""Os arquivos da página do painel, achados na pasta a cada pedido.

Antes era uma lista fixa lida ao subir: um arquivo novo em `portal/web` (uma página, um módulo)
dava 404 até reiniciar o Zé. Agora vale o que está na pasta, com estas travas: só extensões
conhecidas, nada oculto, nada fora da pasta (nem por `..`, nem por link simbólico).
"""

from pathlib import Path

TIPOS = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".webmanifest": "application/manifest+json",
}


def achar(web: Path, caminho: str) -> Path | None:
    """O arquivo de `web` para a rota `caminho` (`/` é a página inicial), ou None."""
    if caminho == "/":
        caminho = "/index.html"
    if not caminho.startswith("/") or "\\" in caminho or "\x00" in caminho:
        return None
    partes = caminho[1:].split("/")
    if any(not parte or parte.startswith(".") for parte in partes):
        return None  # vazio (`//`, barra no fim), `..` e arquivos ocultos
    arquivo = web.joinpath(*partes)
    if arquivo.suffix not in TIPOS:
        return None
    try:
        real = arquivo.resolve(strict=True)
        if not real.is_relative_to(web.resolve()) or not real.is_file():
            return None
    except OSError:
        return None
    return real
