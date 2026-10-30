"""Modelos 3D prontos (ADR 0049): busca, travas do download e o que vai para o Acervo."""

import asyncio
import json
import struct
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro.ferramentas import LEITURA
from zervis.cerebro.ferramentas import modelos as ferramentas_de_modelos
from zervis.imersivo import modelos3d as m
from zervis.rosto.tela import Tela


def glb(gltf: dict[str, Any] | None = None) -> bytes:
    """Um .glb mínimo: cabeçalho, o JSON (alinhado em 4) e nada mais."""
    corpo = json.dumps(
        gltf if gltf is not None else {"asset": {"version": "2.0"}, "meshes": [{}]}
    ).encode()
    corpo += b" " * (-len(corpo) % 4)
    return (
        b"glTF"
        + struct.pack("<II", 2, 20 + len(corpo))
        + struct.pack("<I4s", len(corpo), b"JSON")
        + corpo
    )


def asset(slug: str, **stats: Any) -> dict[str, Any]:
    return {
        "slug": slug, "title": slug.title(), "summary": "um modelo", "url": f"https://3dassets.dev/assets/{slug}",
        "cdnUrl": f"https://cdn.3dassets.dev/assets/1/v1/{slug}.glb", "aiGenerated": False,
        "license": {"name": "CC0 1.0 Universal", "attributionRequired": False},
        "contributor": {"name": "Ana"}, "stats": {"triangles": 1000, **stats},
    }  # fmt: skip


class Fonte:
    """A internet de mentira: o que cada URL devolve, e o que foi pedido."""

    def __init__(self, respostas: dict[str, bytes]) -> None:
        self.respostas = respostas
        self.pedidos: list[str] = []

    def __call__(self, url: str, limite: int) -> bytes:
        self.pedidos.append(url)
        for prefixo, corpo in self.respostas.items():
            if url.startswith(prefixo):
                if len(corpo) > limite:
                    raise m.ModeloErro("arquivo grande demais")
                return corpo
        raise m.ModeloErro("404")


def test_a_busca_tira_o_que_a_imersao_nao_le_e_mantem_a_ordem_da_fonte() -> None:
    dados = [asset("cavalo-hd", triangles=20000), asset("cavalo-draco", hasDraco=True),
             asset("cavalo-meshopt", extensionsUsed=["EXT_meshopt_compression"]),
             asset("../fora"), asset("potro", triangles=500)]  # fmt: skip
    fonte = Fonte({m.API + "/assets?": json.dumps({"data": dados}).encode()})
    achados = m.buscar("  horse  ", ler=fonte)
    assert [a.id for a in achados] == ["3dassets:cavalo-hd", "3dassets:potro"]
    assert achados[0].licenca == "CC0 1.0 Universal" and achados[0].triangulos == 20000
    assert "q=horse" in fonte.pedidos[0]
    with pytest.raises(m.ModeloErro):
        m.buscar("   ", ler=fonte)


def test_so_entra_glb_inteiro_em_si_e_sem_compressao_nao_lida() -> None:
    assert m.conferir_glb(glb())["meshes"]
    ruins = [
        b"PK\x03\x04 um zip qualquer",
        glb({"meshes": [{}], "buffers": [{"uri": "fora.bin"}]}),
        glb({"meshes": [{}], "extensionsRequired": ["KHR_draco_mesh_compression"]}),
        glb({"asset": {}}),
        glb()[:30],
    ]
    for dados in ruins:
        with pytest.raises(m.ModeloErro):
            m.conferir_glb(dados)
    assert m.conferir_glb(
        glb({"meshes": [{}], "buffers": [{"uri": "data:application/octet-stream;base64,AA=="}]})
    )


def test_baixa_para_o_acervo_com_a_ficha_e_reusa_na_segunda_vez(tmp_path: Path) -> None:
    fonte = Fonte({
        m.API + "/assets/cavalo-hd": json.dumps({"data": asset("cavalo-hd")}).encode(),
        "https://cdn.3dassets.dev/": glb(),
    })  # fmt: skip
    r = m.baixar("3dassets:cavalo-hd", tmp_path, ler=fonte)
    assert r["arquivo"] == "3d/baixados/cavalo-hd.glb" and not r["reusado"]
    assert (tmp_path / "3d/baixados/cavalo-hd.glb").read_bytes() == glb()
    ficha = json.loads((tmp_path / "3d/baixados/cavalo-hd.json").read_text())
    assert (
        ficha["licenca"] == "CC0 1.0 Universal"
        and ficha["autor"] == "Ana"
        and ficha["fonte"] == "3DAssets.dev"
    )
    pedidos = len(fonte.pedidos)
    assert (
        m.baixar("3dassets:cavalo-hd", tmp_path, ler=fonte)["reusado"]
        and len(fonte.pedidos) == pedidos
    )


def test_baixar_recusa_id_estranho_e_arquivo_que_nao_e_modelo(tmp_path: Path) -> None:
    for id_ in ("sketchfab:cavalo", "3dassets:../../etc", "cavalo"):
        with pytest.raises(m.ModeloErro):
            m.baixar(id_, tmp_path, ler=Fonte({}))
    fonte = Fonte({
        m.API + "/assets/falso": json.dumps({"data": asset("falso")}).encode(),
        "https://cdn.3dassets.dev/": b"<html>nao sou um modelo</html>",
    })  # fmt: skip
    with pytest.raises(m.ModeloErro, match=r"não é um arquivo \.glb"):
        m.baixar("3dassets:falso", tmp_path, ler=fonte)
    assert not (tmp_path / "3d/baixados/falso.glb").exists()


def test_so_https_e_so_os_dominios_da_fonte() -> None:
    m._conferir_url("https://cdn.3dassets.dev/assets/1/v1/model.glb")
    for url in (
        "http://3dassets.dev/x",
        "https://exemplo.invalid/x.glb",
        "file:///etc/passwd",
        "https://3dassets.dev.exemplo.invalid/",
    ):
        with pytest.raises(m.ModeloErro):
            m._conferir_url(url)


class TelaFalsa(Tela):
    def __init__(self) -> None:
        super().__init__(Path("/nao-existe"))
        self.acoes: list[dict[str, Any]] = []

    def agir(
        self,
        acoes: list[dict[str, Any]],
        trazer: bool = True,
        espera_s: float | None = None,
        esperar_fim: bool | None = None,
    ) -> dict[str, Any]:
        self.acoes += acoes
        return {"resultados": [{"acao": "mostrar_modelo", "ok": True}]}


def test_baixar_com_mostrar_poe_o_modelo_na_tela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "3d/baixados"
    pasta.mkdir(parents=True)
    (pasta / "cavalo-hd.glb").write_bytes(glb())
    (pasta / "cavalo-hd.json").write_text(
        json.dumps({"titulo": "Horse", "licenca": "CC0", "autor": "", "feito_por_ia": True})
    )
    tela = TelaFalsa()
    baixar = next(
        f for f in ferramentas_de_modelos.ferramentas(tmp_path, tela) if f.name == "modelo3d_baixar"
    )

    async def rodar() -> dict[str, Any]:
        return await baixar.handler(
            {"id": "3dassets:cavalo-hd", "titulo": "Cavalo", "mostrar": True}
        )

    r = json.loads(asyncio.run(rodar())["content"][0]["text"])
    assert r["arquivo"] == "3d/baixados/cavalo-hd.glb" and r["reusado"] and r["mostrado"] is True
    assert tela.acoes == [
        {"acao": "mostrar_modelo", "alvo": "3d/baixados/cavalo-hd.glb", "valor": "Cavalo"}
    ]
    assert {"modelo3d_buscar", "modelo3d_baixar"} <= set(LEITURA)
    assert ferramentas_de_modelos.ferramentas(None, tela) == []
