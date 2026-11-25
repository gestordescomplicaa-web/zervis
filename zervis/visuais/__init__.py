"""Os visuais do chat (ADR 0138): apresentações, diagramas, gráficos e painéis em HTML que o Zé
monta e o chat mostra, animados e com controles, para ver em tela cheia e baixar (HTML, PNG, PDF).

O cérebro escreve só o conteúdo (o `<body>`), com as peças do kit (`kit.css`, `kit.js`: slides,
cartões, números que contam, barras, fluxos, controles que mexem em parâmetros). Cada um fica em
`DADOS/visuais/<id>.html`, com o título ao lado (`<id>.json`); a página inteira se monta ao servir,
então o kit novo vale também para os antigos.

Isolamento (falhar fechado): a página vai com uma regra de segurança própria (`CSP`): sem rede,
sem formulário, numa origem à parte (`sandbox`), e só abre dentro do próprio painel. O HTML é do
modelo, que pode ter lido uma página de fora: ele não alcança o painel, o token nem a internet.
"""

import json
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from base64 import b64encode
from collections.abc import Iterator
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any, NamedTuple

from zervis import lugares

MAX_HTML = 400_000  # caracteres do conteúdo: uma apresentação rica cabe; um despejo, não
DIAS_GUARDADOS = 90
ESPECIES = ("apresentacao", "diagrama", "grafico", "painel", "pagina")
NAVEGADORES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
LARGURA, ALTURA = 1280, 720  # o PNG e a página do PDF: 16:9
ID = re.compile(r"^[0-9a-f]{16}$")
# A regra da página: scripts e estilos dela mesma (as contas dos controles usam `Function`),
# imagens e fontes embutidas; nada de rede. Vai na própria página (vale no arquivo baixado) e, no
# painel, também no cabeçalho, com a origem à parte e só dentro do painel.
CSP_PAGINA = (
    "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; "
    "img-src data: blob:; font-src data:; media-src data: blob:; base-uri 'none'; "
    "form-action 'none'"
)
CSP = f"{CSP_PAGINA}; frame-ancestors 'self'; sandbox allow-scripts"
# Uma imagem que quem usa anexou no chat, num cartão: src="zk:anexo/<nome guardado>".
IMAGEM_ANEXADA = re.compile(r'src="zk:anexo/([A-Za-z0-9._-]{1,120})"')
PASTA_KIT = Path(__file__).parent
FONTE = Path(__file__).resolve().parents[1] / "portal/web/fontes/geist.woff2"


class VisualErro(Exception):
    """Mensagem curta para o cérebro ("O conteúdo está vazio.")."""


class Visual(NamedTuple):
    id: str
    titulo: str
    especie: str
    criado: datetime

    def para_tela(self) -> dict[str, Any]:
        return {"id": self.id, "titulo": self.titulo, "especie": self.especie}


def _kit() -> str:
    """O estilo e o script do kit, com a fonte do painel embutida (a página não tem rede)."""
    fonte = b64encode(FONTE.read_bytes()).decode() if FONTE.is_file() else ""
    css = (PASTA_KIT / "kit.css").read_text()
    if fonte:
        css = (
            '@font-face { font-family: "Geist"; font-weight: 100 900; font-display: block;'
            f' src: url(data:font/woff2;base64,{fonte}) format("woff2"); }}\n{css}'
        )
    return f"<style>{css}</style>\n<script>{(PASTA_KIT / 'kit.js').read_text()}</script>"


class Visuais:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def criar(self, titulo: str, html: str, especie: str = "apresentacao") -> Visual:
        titulo = " ".join(titulo.split())[:120]
        if not titulo:
            raise VisualErro("Falta o título.")
        if not html.strip():
            raise VisualErro("O conteúdo está vazio.")
        if len(html) > MAX_HTML:
            raise VisualErro("O conteúdo passou do limite; divida em visuais menores.")
        especie = especie if especie in ESPECIES else "apresentacao"
        self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._limpar_antigos()
        from zervis.memoria.linha import agora  # o fuso de quem usa, o mesmo do chat

        visual = Visual(secrets.token_hex(8), titulo, especie, agora())
        dados = {"titulo": titulo, "especie": especie, "criado": visual.criado.isoformat()}
        self._gravar(self.pasta / f"{visual.id}.html", html)
        self._gravar(self.pasta / f"{visual.id}.json", json.dumps(dados, ensure_ascii=False))
        return visual

    def ler(self, id_: str) -> Visual | None:
        if not ID.match(id_) or not (meta := self.pasta / f"{id_}.json").is_file():
            return None
        dados = json.loads(meta.read_text())
        criado = datetime.fromisoformat(dados["criado"])
        return Visual(id_, str(dados["titulo"]), str(dados["especie"]), criado)

    def do_dia(self, dia: date) -> list[Visual]:
        """Os visuais criados no dia, do mais antigo ao mais novo (o fio do chat)."""
        if not self.pasta.is_dir():
            return []
        visuais = (self.ler(m.stem) for m in self.pasta.glob("*.json"))
        return sorted((v for v in visuais if v and v.criado.date() == dia), key=lambda v: v.criado)

    def pagina(self, id_: str) -> str | None:
        """A página inteira: o kit, a regra de segurança e o conteúdo do cérebro."""
        if (visual := self.ler(id_)) is None:
            return None
        corpo = IMAGEM_ANEXADA.sub(_imagem_anexada, (self.pasta / f"{id_}.html").read_text())
        return (
            '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP_PAGINA}">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{escape(visual.titulo)}</title>\n{_kit()}\n</head>\n"
            f'<body class="zk">\n{corpo}\n</body></html>\n'
        )

    def servir(self, nome: str) -> tuple[str, bytes] | None:
        """Para o painel: `<id>` (a página), `<id>.png` ou `<id>.pdf`; None se não existe."""
        id_, _, formato = nome.partition(".")
        if formato not in ("", "png", "pdf") or (pagina := self.pagina(id_)) is None:
            return None
        if not formato:
            return "text/html", pagina.encode()
        return ("image/png" if formato == "png" else "application/pdf"), renderizar(pagina, formato)

    def fluxo(self, consulta: dict[str, str]) -> tuple[str, Iterator[bytes], str]:
        """Para o painel, em /fluxo/visual?id=…[&formato=png|pdf], com a regra da página."""
        formato = consulta.get("formato", "")
        achado = self.servir(consulta.get("id", "") + (f".{formato}" if formato else ""))
        if achado is None:
            raise ValueError("Visual não encontrado.")
        tipo, corpo = achado
        regra = CSP if tipo == "text/html" else "frame-ancestors 'self'"
        return (f"{tipo}; charset=utf-8" if tipo == "text/html" else tipo), iter([corpo]), regra

    def _gravar(self, alvo: Path, texto: str) -> None:
        temporario = alvo.with_name(f".{alvo.name}.parcial")
        temporario.write_text(texto)
        temporario.chmod(0o600)
        temporario.rename(alvo)

    def _limpar_antigos(self) -> None:
        limite = time.time() - DIAS_GUARDADOS * 86400
        for arquivo in self.pasta.iterdir():
            if arquivo.is_file() and arquivo.stat().st_mtime < limite:
                arquivo.unlink(missing_ok=True)


def _imagem_anexada(m: re.Match[str]) -> str:
    """A imagem anexada, embutida (a página não tem rede); some se o anexo não existe mais."""
    from zervis.memoria import anexos

    try:
        tipo, dados = anexos.PADRAO.ler(m.group(1))
    except anexos.AnexoErro:
        return 'src="" data-sem-imagem'
    if tipo != "imagem" or not isinstance(dados, bytes):
        return 'src="" data-sem-imagem'
    return f'src="data:image/jpeg;base64,{b64encode(dados).decode()}"'


def renderizar(pagina: str, formato: str, executar: Any = None) -> bytes:
    """A página em PNG (o primeiro quadro, 1280x720) ou PDF (um slide por página), pelo Chromium
    sem tela. O kit, ao imprimir, mostra todos os slides, sem animação."""
    binario = next((b for b in map(shutil.which, NAVEGADORES) if b), None)
    if binario is None:
        raise VisualErro("Chromium não encontrado nesta máquina.")
    with tempfile.TemporaryDirectory(prefix="ze-visual-") as tmp:
        origem, saida = Path(tmp) / "visual.html", Path(tmp) / f"visual.{formato}"
        origem.write_text(pagina.replace('<body class="zk">', '<body class="zk zk-captura">', 1))
        alvo = f"--screenshot={saida}" if formato == "png" else f"--print-to-pdf={saida}"
        (executar or subprocess.run)(  # o Chromium, com a página do próprio Zé
            [
                binario, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                "--no-first-run", "--disable-extensions", f"--user-data-dir={tmp}/perfil",
                f"--window-size={LARGURA},{ALTURA}", "--virtual-time-budget=4000",
                "--no-pdf-header-footer", alvo, origem.as_uri(),
            ],
            capture_output=True, timeout=60, check=False,
        )  # fmt: skip
        if not saida.is_file():
            raise VisualErro("Não consegui desenhar o visual.")
        return saida.read_bytes()


PADRAO = Visuais(lugares.DADOS / "visuais")
