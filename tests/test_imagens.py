"""Imagens e vídeos reais na Imersão (ADR 0058): buscar, baixar com o crédito e o print de página
atrás da trava de rede."""

import json
import socket
import threading
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro import rapido
from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas.tela import TIPOS
from zervis.imersivo import capturas as cap
from zervis.imersivo import imagens as im

JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 3000
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 3000
MINIATURA = "//thumb.wikimedia.org/x/thumb/2/20/Marina.jpg/60px-Marina.jpg"
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"webm" + b"\x00" * 3000


class Wikimedia:
    """A Wikimedia, o bastante: responde pela URL e anota o que foi pedido."""

    def __init__(self, nao_livre: bool = False) -> None:
        self.pedidos: list[str] = []
        self.nao_livre = nao_livre

    def __call__(self, url: str, limite: int) -> bytes:
        im._conferir(url)  # a trava de domínio vale também aqui
        self.pedidos.append(url)
        p = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(p.query))
        if p.path.endswith("/search/page"):
            paginas = [] if p.hostname == "pt.wikipedia.org" and q["q"] == "Kilauea" else [
                {"title": "Marina Silva", "description": "ambientalista e política brasileira",
                 "thumbnail": {"url": MINIATURA}},
                {"title": "Sem foto", "description": "x", "thumbnail": None},
            ]  # fmt: skip
            return json.dumps({"pages": paginas}).encode()
        if "/page/summary/" in p.path:
            original = "https://upload.wikimedia.org/wikipedia/commons/2/20/Marina_Silva_crop.jpg"
            return json.dumps(
                {"description": "ambientalista", "originalimage": {"source": original}}
            ).encode()
        if p.path == "/w/api.php" and q.get("generator") == "search":
            video = "filetype:video" in q["gsrsearch"]
            nomes = ["File:Lava.webm"] if video else ["File:Rio.jpg", "File:Logo.png"]
            return json.dumps({"query": {"pages": [
                {"title": n, "imageinfo": [{"thumburl": "https://upload.wikimedia.org/t/240px-a.jpg",
                 "descriptionurl": "https://commons.wikimedia.org/wiki/" + n,
                 "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"},
                                 "NonFree": {"value": str(n == "File:Logo.png").lower()}}}]}
                for n in nomes]}}).encode()  # fmt: skip
        if p.path == "/w/api.php":
            meta = {
                "LicenseShortName": {"value": "CC BY 2.0"},
                "Artist": {"value": '<a href="//x">Sir.Leo Cabral</a>'},
                "ImageDescription": {"value": "Marina Silva em março de 2018."},
                "NonFree": {"value": "true" if self.nao_livre else "false"},
            }
            info: dict[str, Any] = {
                "extmetadata": meta,
                "descriptionurl": "https://commons.wikimedia.org/wiki/F",
            }
            if q["prop"] == "videoinfo":
                info["derivatives"] = [
                    {"type": 'video/webm; codecs="vp9"', "height": 1080, "src": "https://upload.wikimedia.org/1080.webm"},
                    {"type": 'video/webm; codecs="vp9"', "height": 480, "src": "https://upload.wikimedia.org/480.webm"},
                    {"type": "video/quicktime", "height": 360, "src": "https://upload.wikimedia.org/360.mov"},
                ]  # fmt: skip
                return json.dumps({"query": {"pages": [{"videoinfo": [info]}]}}).encode()
            info["thumburl"] = (
                "https://upload.wikimedia.org/thumb/2/20/Marina.jpg/1280px-Marina.jpg"
            )
            return json.dumps({"query": {"pages": [{"imageinfo": [info]}]}}).encode()
        if p.path.endswith(".webm"):
            return WEBM
        return JPG


def test_busca_a_wikipedia_primeiro_e_o_commons_sem_o_que_nao_e_livre() -> None:
    wm = Wikimedia()
    achados = im.buscar("Marina Silva", ler=wm)
    ids = [a.id for a in achados]
    assert ids == ["wiki:pt:Marina Silva", "commons:File:Rio.jpg"]  # sem foto e não livre: fora
    assert (
        achados[0].previa.startswith("https://thumb.wikimedia.org/")
        and "/240px-" in achados[0].previa
    )
    assert [a.id for a in im.buscar("Kilauea", "video", wm)] == ["commons:File:Lava.webm"]
    assert im.buscar("Kilauea", ler=wm)[0].id == "wiki:en:Marina Silva"  # sem nada em português
    with pytest.raises(im.ImagemErro):
        im.buscar("  ", ler=wm)


def test_baixa_a_foto_da_pagina_com_o_credito_e_reusa(tmp_path: Path) -> None:
    wm = Wikimedia()
    r = im.baixar("wiki:pt:Marina Silva", tmp_path, wm)
    assert r["arquivo"] == "imagens/web/marina-silva.jpg" and not r["reusado"]
    assert (tmp_path / r["arquivo"]).read_bytes() == JPG
    assert (r["licenca"], r["autor"], r["legenda"]) == (
        "CC BY 2.0",
        "Sir.Leo Cabral",
        "ambientalista",
    )
    assert im.credito(r) == "Foto: Sir.Leo Cabral · CC BY 2.0 · Wikipédia"
    assert any("titles=File%3AMarina+Silva+crop.jpg" in u for u in wm.pedidos)  # o arquivo certo
    antes = len(wm.pedidos)
    assert im.baixar("wiki:pt:Marina Silva", tmp_path, wm)["reusado"]
    assert len(wm.pedidos) == antes


def test_video_na_versao_leve(tmp_path: Path) -> None:
    wm = Wikimedia()
    r = im.baixar("commons:File:Lava.webm", tmp_path, wm)
    assert r["arquivo"] == "videos/web/lava.webm" and r["tipo"] == "video"
    assert "https://upload.wikimedia.org/480.webm" in wm.pedidos  # nem o 1080p nem o .mov
    assert im.credito(r) == "Vídeo: Sir.Leo Cabral · CC BY 2.0 · Wikimedia Commons"


def test_recusa_o_que_nao_e_livre_o_que_nao_e_imagem_e_fora_da_wikimedia(tmp_path: Path) -> None:
    with pytest.raises(im.ImagemErro, match="não livre"):
        im.baixar("commons:File:Logo.png", tmp_path, Wikimedia(nao_livre=True))

    def html(url: str, limite: int) -> bytes:
        return b"<html>" if url.endswith(".jpg") else Wikimedia()(url, limite)

    with pytest.raises(im.ImagemErro, match="não é uma imagem"):
        im.baixar("commons:File:Rio.jpg", tmp_path, html)
    for ruim in ("../x", "wiki:fr:Paris", "http://x"):
        with pytest.raises(im.ImagemErro, match="desconhecida"):
            im.baixar(ruim, tmp_path, Wikimedia())
    for url in ("https://example.com/a.jpg", "http://upload.wikimedia.org/a.jpg"):
        with pytest.raises(im.ImagemErro, match="fora das fontes"):
            im._conferir(url)
    assert not list(tmp_path.rglob("*.jpg"))


def test_tipo_pelo_conteudo() -> None:
    assert [im.tipo_do_arquivo(x) for x in (JPG, PNG, WEBM, b"GIF89a..", b"<svg")] == [
        "jpg", "png", "webm", "gif", None,
    ]  # fmt: skip


# --- o print de página ----------------------------------------------------------------------


def test_endereco_publico_so() -> None:
    for ip in ("8.8.8.8", "2001:4860:4860::8888", "200.147.67.142"):
        assert cap.publico(ip), ip
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.3.4", "100.64.1.2", "169.254.1.1",
               "::1", "fc00::1", "::ffff:127.0.0.1", "0.0.0.0", "224.0.0.1", "lixo"):  # noqa: S104  # fmt: skip
        assert not cap.publico(ip), ip


def test_conferir_url_recusa_http_e_rede_local() -> None:
    publico = lambda host, porta: ["93.184.216.34"]  # noqa: E731
    local = lambda host, porta: ["192.168.0.10"]  # noqa: E731
    assert cap.conferir_url("https://exemplo.com/a", publico) == "exemplo.com"
    for url, resolve, frase in (
        ("http://exemplo.com", publico, "https"),
        ("https://user:senha@exemplo.com", publico, "https"),
        ("https://roteador.casa", local, "rede local"),
        ("https://sumiu.invalid", lambda h, p: [], "não foi encontrado"),
    ):
        with pytest.raises(cap.CapturaErro, match=frase):
            cap.conferir_url(url, resolve)


def _connect(porta: int, destino: str) -> bytes:
    with socket.create_connection(("127.0.0.1", porta), timeout=5) as s:
        s.sendall(f"CONNECT {destino} HTTP/1.1\r\nHost: {destino}\r\n\r\n".encode())
        resposta = s.recv(200)
        if b" 200 " in resposta:
            s.sendall(b"ping")
            resposta += s.recv(10)
        return resposta


def test_a_trava_recusa_a_rede_local_e_deixa_passar_o_publico() -> None:
    # a página não chega à máquina nem à rede de casa, e só na porta 443, só por CONNECT
    nomes = {"roteador.casa": ["192.168.0.1"], "site.teste": ["93.184.216.34"]}
    with cap.trava(lambda h, p: nomes.get(h) or cap.resolver(h, p)) as t:
        for destino in ("127.0.0.1:443", "localhost:443", "roteador.casa:443", "site.teste:80"):
            assert b" 403 " in _connect(t.porta, destino), destino
        assert b" 403 " in _connect(t.porta, "GET http://site.teste/")
        assert t.recusados[:3] == ["127.0.0.1", "localhost", "roteador.casa"]
    # o público passa, e a conexão vai ao IP conferido (aqui, um eco local no lugar do site)
    eco = socket.create_server(("127.0.0.1", 0))
    threading.Thread(target=_eco_uma, args=(eco,), daemon=True).start()
    destinos: list[tuple[str, int]] = []

    def conectar(destino: tuple[str, int]) -> socket.socket:
        destinos.append(destino)
        return socket.create_connection(eco.getsockname(), timeout=5)

    with cap.trava(lambda h, p: nomes[h], conectar=conectar) as t:
        resposta = _connect(t.porta, "site.teste:443")
    eco.close()
    assert b" 200 " in resposta and resposta.endswith(b"PING")
    assert destinos == [("93.184.216.34", 443)]


def _eco_uma(servidor: socket.socket) -> None:
    conexao, _ = servidor.accept()
    with conexao:
        conexao.sendall(conexao.recv(10).upper())


def test_capturar_guarda_o_print_com_a_origem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cap, "conferir_url", lambda url, resolve=None: "loja.exemplo")
    monkeypatch.setattr(cap, "navegador", lambda: "/usr/bin/chromium")
    comandos: list[list[str]] = []

    def chromium(comando: list[str], **_: Any) -> None:
        comandos.append(comando)
        saida = next(a for a in comando if a.startswith("--screenshot=")).split("=", 1)[1]
        Path(saida).write_bytes(PNG)

    r = cap.capturar("https://loja.exemplo/produtos", tmp_path, chromium)
    assert r["arquivo"].startswith("imagens/capturas/loja-exemplo-") and r["arquivo"].endswith(
        ".png"
    )
    assert (tmp_path / r["arquivo"]).read_bytes() == PNG and r[
        "pagina"
    ] == "https://loja.exemplo/produtos"
    [comando] = comandos
    assert any(a.startswith("--proxy-server=http://127.0.0.1:") for a in comando)
    assert "--proxy-bypass-list=<-loopback>" in comando and "--disable-quic" in comando
    assert any(a.startswith("--user-data-dir=") for a in comando)  # perfil descartável
    with pytest.raises(cap.CapturaErro, match="não abriu"):
        cap.capturar("https://loja.exemplo", tmp_path, lambda c, **_: None)
    monkeypatch.setattr(cap, "navegador", lambda: None)
    with pytest.raises(cap.CapturaErro, match="Chromium"):
        cap.capturar("https://loja.exemplo", tmp_path, chromium)


def test_quem_e_vai_ao_cerebro_completo_com_a_janela_aberta() -> None:
    aberta = "[segunda, 03/11/2026, 10:00] (janela do Zé aberta) "
    assert rapido.precisa_do_completo(aberta + "Quem é a Marina Silva e o que ela faz na política?")
    assert rapido.precisa_do_completo(aberta + "Zé, quem foi Santos Dumont?")
    assert not rapido.precisa_do_completo(aberta + "Quem é você?")
    assert not rapido.precisa_do_completo("[segunda, 03/11/2026, 10:00] Quem é a Marina Silva?")


def test_habilidade_nativa_e_livre() -> None:
    for nome in ("imagem_buscar", "imagem_baixar", "pagina_capturar"):
        assert f"mcp__jarvis__{nome}" in LIVRES
    assert {"foto", "video"} <= set(TIPOS)
