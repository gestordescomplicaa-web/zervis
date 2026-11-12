"""O Modo TV (ADR 0084): a configuração com a chave, a página servida só com ela, o que a TV
mostra (uma peça do Acervo, nada fora dele), abrir e fechar o navegador da TV e a voz. Nenhuma
TV de verdade: abrir e fechar são de mentira, e o servidor escuta numa porta livre."""

import asyncio
import json
import socket
import stat
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_projetos3d import cubo, stl_binario  # type: ignore[import-not-found]

from zervis import projetos3d, tv
from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import tela_tv as g_tela_tv
from zervis.portal.acoes.pagina import Servicos
from zervis.portal.acoes.tela_tv import AcoesTelaTV
from zervis.portal.servidor import PedidoInvalido


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def tela(tmp_path: Path) -> Any:
    (tmp_path / "acervo" / "3d" / "projetos").mkdir(parents=True)
    (tmp_path / "acervo" / "3d" / "peca.glb").write_bytes(b"glTF peca")
    (tmp_path / "acervo" / "imagens").mkdir()
    (tmp_path / "acervo" / "imagens" / "foto.glb").write_bytes(b"fora do 3d")
    arquivo = tmp_path / "tv.json"
    arquivo.write_text(json.dumps({"porta": porta_livre()}))
    abertas: list[str] = []
    fechadas: list[str] = []
    t = tv.TelaTV(arquivo, tmp_path / "acervo", lambda: True, abertas.append, fechadas.append)
    t.abertas, t.fechadas = abertas, fechadas  # type: ignore[attr-defined]
    yield t
    t.desligar()


def pegar(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 (o servidor do teste)
            return r.status, r.read()
    except urllib.error.HTTPError as erro:
        return erro.code, b""


def test_a_configuracao_tem_chave_e_e_so_do_dono(tela: Any) -> None:
    assert not tela.ajustes()["ligado"] and tela.para_tela()["endereco"] == ""
    with pytest.raises(tv.TVErro, match="IP"):
        tela.guardar("", True)
    with pytest.raises(tv.TVErro, match="rede local"):
        tela.guardar("8.8.8.8", True)
    tela.guardar("192.168.0.30", True)
    a = tela.ajustes()
    assert a["ip_tv"] == "192.168.0.30" and len(a["chave"]) >= 20
    assert stat.S_IMODE(tela.arquivo.stat().st_mode) == 0o600
    assert tela.para_tela()["endereco"].endswith(f":{a['porta']}/tv?chave={a['chave']}")
    tela.guardar("192.168.0.31", True)
    assert tela.ajustes()["chave"] == a["chave"]  # a chave fica: a TV guarda o endereço


def test_a_pagina_so_com_a_chave_e_so_o_que_e_do_3d(tela: Any) -> None:
    tela.guardar("192.168.0.30", True)
    base, chave = f"http://127.0.0.1:{tela.ajustes()['porta']}", tela.ajustes()["chave"]
    assert pegar(f"{base}/tv.js")[0] == 200  # o código da página não tem nada de quem usa
    assert pegar(f"{base}/tv")[0] == 403
    assert pegar(f"{base}/tv?chave=errada")[0] == 403
    codigo, pagina = pegar(f"{base}/tv?chave={chave}")
    assert codigo == 200 and b'src="/tv.js"' in pagina
    assert not tela.aberta()
    codigo, estado = pegar(f"{base}/tv/estado?chave={chave}")
    assert json.loads(estado) == {"cena": {"tipo": "relogio"}, "falando": True}
    assert tela.aberta()  # a página perguntou: está aberta na TV
    assert pegar(f"{base}/tv/modelo?chave={chave}&arquivo=3d/peca.glb") == (200, b"glTF peca")
    for fora in ("imagens/foto.glb", "../tv.json", "3d/nada.glb"):
        assert pegar(f"{base}/tv/modelo?chave={chave}&arquivo={fora}")[0] == 404
    tela.guardar("192.168.0.30", False)  # desligado: o servidor sai da rede
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"{base}/tv.js", timeout=2)  # noqa: S310


def test_o_que_a_tv_mostra_e_abrir_e_fechar(tela: Any) -> None:
    with pytest.raises(tv.TVErro, match="desligado"):
        tela.abrir()
    tela.guardar("192.168.0.30", True)
    with pytest.raises(tv.TVErro):
        tela.mostrar_modelo("imagens/foto.glb", "Foto")
    tela.mostrar_modelo("3d/peca.glb", "Peça", "20 × 20 × 20 mm")  # noqa: RUF001
    cena = tela.estado()["cena"]
    assert cena["tipo"] == "modelo" and cena["titulo"] == "Peça" and cena["seq"] == 1
    tela._visto = 0.0
    tela.abrir()
    assert tela.abertas == ["192.168.0.30"]
    tela.estado()  # a página respondeu
    tela.abrir()
    assert tela.abertas == ["192.168.0.30"]  # já aberta: não abre de novo
    tela.fechar()
    assert tela.fechadas == ["192.168.0.30"] and tela.estado()["cena"]["tipo"] == "relogio"


def test_a_voz_mostra_a_peca_na_tv_com_as_medidas(tela: Any, tmp_path: Path) -> None:
    tela.guardar("192.168.0.30", True)
    projetos = projetos3d.Projetos3D(tmp_path / "p", tela.acervo, tmp_path / "a.json")
    pasta = Path(projetos.criar("Suporte celular", "peca", "8 cm")["pasta"])
    (pasta / "modelo.stl").write_bytes(stl_binario(cubo(20)))
    fs: dict[str, Any] = {f.name: f.handler for f in g_tela_tv.ferramentas(tela, projetos)}
    r = asyncio.run(fs["tela_tv_mostrar"]({"projeto": "suporte-celular"}))
    assert json.loads(r["content"][0]["text"]) == {"mostrado": "Suporte celular", "na_tv": True}
    cena = tela.estado()["cena"]
    assert cena["arquivo"] == "3d/projetos/suporte-celular/modelo.glb"
    assert cena["detalhe"] == "20 × 20 × 20 mm"  # noqa: RUF001
    assert asyncio.run(fs["tela_tv_mostrar"]({}))["is_error"]
    asyncio.run(fs["tela_tv_fechar"]({}))
    assert tela.fechadas == ["192.168.0.30"]
    assert {"mcp__jarvis__tela_tv_mostrar", "mcp__jarvis__tela_tv_fechar"} <= set(LIVRES)
    assert g_tela_tv.ferramentas(None, None) == []


def test_o_cartao_em_perfil(tela: Any) -> None:
    pagina = AcoesTelaTV(SimpleNamespace(), Servicos({"tela_tv": lambda: tela}))
    assert pagina.modo_tv()["ligado"] is False
    r = pagina.salvar_modo_tv({"ip_tv": "192.168.0.30", "ligado": True})
    assert r["aviso"] == "Salvo." and r["endereco"].startswith("http://")
    assert "chave" not in json.dumps({k: v for k, v in r.items() if k != "endereco"})
    with pytest.raises(PedidoInvalido):
        pagina.salvar_modo_tv({"ip_tv": "nada", "ligado": True})
    assert pagina.abrir_tv({})["aviso"] == "Abrindo na TV."
    assert pagina.fechar_tv({})["aviso"] == "Fechado."
