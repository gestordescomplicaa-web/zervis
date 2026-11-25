"""Os visuais do chat (ADR 0138): guardar, montar com o kit, servir isolado e mostrar no chat."""

import asyncio
import http.client
import io
import os
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from zervis import visuais
from zervis.cerebro import ferramentas, rapido
from zervis.cerebro.ferramentas import visuais as g_visuais
from zervis.memoria import anexos
from zervis.memoria.linha import agora
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import Portal
from zervis.visuais import Visuais, VisualErro

SLIDES = '<div class="zk-slides"><section class="zk-slide"><h1>Olá</h1></section></div>'


def test_cria_e_le_o_visual_do_dia(tmp_path: Path) -> None:
    loja = Visuais(tmp_path / "visuais")
    v = loja.criar("  Auditoria   da câmera ", SLIDES, "diagrama")
    assert visuais.ID.match(v.id) and v.titulo == "Auditoria da câmera" and v.especie == "diagrama"
    assert oct((tmp_path / "visuais" / f"{v.id}.html").stat().st_mode & 0o777) == "0o600"
    assert loja.ler(v.id) == v
    assert loja.do_dia(v.criado.date()) == [v]
    assert loja.do_dia(date(2000, 1, 1)) == []
    assert loja.criar("Sem espécie", SLIDES, "qualquer").especie == "apresentacao"


@pytest.mark.parametrize(
    ("titulo", "html", "erro"),
    [("", SLIDES, "título"), ("Vazio", "   ", "vazio"), ("Grande", "x" * 400_001, "limite")],
)
def test_recusa_o_que_nao_e_um_visual(tmp_path: Path, titulo: str, html: str, erro: str) -> None:
    with pytest.raises(VisualErro, match=erro):
        Visuais(tmp_path).criar(titulo, html)


def test_so_le_ids_do_formato(tmp_path: Path) -> None:
    loja = Visuais(tmp_path)
    for nome in ("../x", "abc", "0123456789abcdeg", ""):
        assert loja.ler(nome) is None and loja.servir(nome) is None
    assert loja.servir(f"{loja.criar('A', SLIDES).id}.exe") is None


def test_a_pagina_leva_o_kit_a_fonte_e_a_regra_sem_rede(tmp_path: Path) -> None:
    loja = Visuais(tmp_path)
    v = loja.criar("<Título>", SLIDES)
    pagina = loja.pagina(v.id) or ""
    assert "<title>&lt;Título&gt;</title>" in pagina and '<body class="zk">' in pagina
    assert "default-src 'none'" in pagina and "form-action 'none'" in pagina
    assert ".zk-slide" in pagina and "zk:param" in pagina  # o estilo e o script do kit
    assert "data:font/woff2;base64," in pagina  # a fonte vai junto: a página não tem rede
    assert "sandbox allow-scripts" in visuais.CSP and "frame-ancestors 'self'" in visuais.CSP


def test_imagem_anexada_entra_embutida_num_cartao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fotos = anexos.Anexos(tmp_path / "anexos")
    monkeypatch.setattr(anexos, "PADRAO", fotos)
    saida = io.BytesIO()
    Image.new("RGB", (40, 30), (30, 150, 160)).save(saida, "PNG")
    nome = fotos.guardar("fachada.png", saida.getvalue())
    loja = Visuais(tmp_path / "visuais")
    v = loja.criar(
        "Foto", f'<img src="zk:anexo/{nome}"><img src="zk:anexo/20261125-000000-aaaaaa-x.png">'
    )
    pagina = loja.pagina(v.id) or ""
    assert 'src="data:image/jpeg;base64,' in pagina
    assert 'src="" data-sem-imagem' in pagina  # o anexo que não existe some, sem quebrar


def test_png_e_pdf_saem_do_chromium(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[list[str]] = []

    def chromium(args: list[str], **_: Any) -> None:
        chamadas.append(args)
        alvo = next(a for a in args if a.startswith(("--screenshot=", "--print-to-pdf=")))
        Path(alvo.split("=", 1)[1]).write_bytes(b"%PDF-1.7" if "pdf" in alvo else b"\x89PNG")

    monkeypatch.setattr("zervis.visuais.shutil.which", lambda nome: f"/usr/bin/{nome}")
    monkeypatch.setattr("zervis.visuais.subprocess.run", chromium)
    loja = Visuais(tmp_path)
    v = loja.criar("Deck", SLIDES)
    assert loja.servir(f"{v.id}.png") == ("image/png", b"\x89PNG")
    assert loja.servir(f"{v.id}.pdf") == ("application/pdf", b"%PDF-1.7")
    assert "--window-size=1280,720" in chamadas[0]
    pagina = Path(chamadas[0][-1].removeprefix("file://")).name
    assert pagina == "visual.html"


def test_visual_antigo_sai(tmp_path: Path) -> None:
    loja = Visuais(tmp_path)
    velho = loja.criar("Velho", SLIDES)
    antes = time.time() - (visuais.DIAS_GUARDADOS + 1) * 86400
    for arquivo in tmp_path.glob(f"{velho.id}.*"):
        os.utime(arquivo, (antes, antes))
    loja.criar("Novo", SLIDES)
    assert loja.ler(velho.id) is None


def test_ferramenta_cria_e_passa_sem_perguntar(tmp_path: Path) -> None:
    loja = Visuais(tmp_path)
    (ferramenta,) = g_visuais.ferramentas(loja)

    async def chamar(args: dict[str, Any]) -> dict[str, Any]:
        resposta: dict[str, Any] = await ferramenta.handler(args)
        return resposta

    feito = asyncio.run(chamar({"titulo": "Simulador", "html": SLIDES, "especie": "painel"}))
    assert '"onde": "no chat do Início"' in feito["content"][0]["text"]
    assert [v.titulo for v in loja.do_dia(agora().date())] == ["Simulador"]
    assert asyncio.run(chamar({"titulo": "x", "html": ""}))["is_error"] is True
    assert "mcp__jarvis__visual_criar" in ferramentas.LIVRES
    assert ferramentas.de_fora("mcp__jarvis__visual_criar") == ""
    assert rapido.precisa_do_completo("monta uma apresentação da auditoria")


def test_o_chat_traz_os_visuais_do_dia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loja = Visuais(tmp_path / "visuais")
    monkeypatch.setattr(visuais, "PADRAO", loja)
    v = loja.criar("Auditoria", SLIDES)
    n = SimpleNamespace(
        conversas=SimpleNamespace(do_dia=lambda _dia: []),
        linha=SimpleNamespace(entre=lambda *_: []),
    )
    itens = Acoes(n, tmp_path, tmp_path).conversa()["itens"]
    assert itens == [
        {
            "quando": v.criado.isoformat(timespec="seconds"),
            "tipo": "visual",
            "visual": {"id": v.id, "titulo": "Auditoria", "especie": "apresentacao"},
        }
    ]


def test_a_rota_serve_isolado_so_para_quem_entrou(tmp_path: Path) -> None:
    loja = Visuais(tmp_path)
    v = loja.criar("Deck", SLIDES)
    portal = Portal({}, {}, porta=0, fluxos={"visual": loja.fluxo})
    portal.iniciar()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
        local = {"Host": f"127.0.0.1:{portal.porta}"}
        conn.request("GET", f"/fluxo/visual?id={v.id}", headers=local)
        r = conn.getresponse()
        corpo = r.read()
        assert r.status == 200 and b"zk-slides" in corpo
        assert r.getheader("Content-Security-Policy") == visuais.CSP
        assert r.getheader("X-Content-Type-Options") == "nosniff"
        conn.request("GET", "/fluxo/visual?id=0123456789abcdef", headers=local)
        r = conn.getresponse()
        r.read()
        assert r.status == 400
        # De fora, sem o cookie da senha: recusado, sem o visual.
        conn.request("GET", f"/fluxo/visual?id={v.id}", headers={"Host": "ze.exemplo.invalid"})
        r = conn.getresponse()
        assert r.status in (303, 401, 403) and b"zk-slides" not in r.read()
    finally:
        portal.parar()
