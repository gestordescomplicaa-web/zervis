"""Projetos 3D (ADR 0082): as medidas do STL, a prévia sólida para a Imersão, a pasta do projeto
com as instruções da sessão, as ferramentas da voz e a página do painel."""

import asyncio
import json
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from zervis import projetos3d
from zervis.cerebro import claude
from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import projetos3d as g_projetos3d
from zervis.portal.acoes.pagina import Servicos
from zervis.portal.acoes.projetos3d import AcoesProjetos3D
from zervis.portal.servidor import PedidoInvalido


def cubo(lado: float = 10.0) -> np.ndarray:
    """Os 12 triângulos de um cubo apoiado em Z=0."""
    v = np.array([[x, y, z] for x in (0, lado) for y in (0, lado) for z in (0, lado)], float)
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]  # fmt: skip
    triangulos: np.ndarray = v[np.array(faces)]
    return triangulos


def stl_binario(triangulos: np.ndarray) -> bytes:
    corpo = b"".join(
        struct.pack("<3f", 0, 0, 0) + t.astype("<f4").tobytes() + b"\0\0" for t in triangulos
    )
    return b"\0" * 80 + struct.pack("<I", len(triangulos)) + corpo


def stl_texto(triangulos: np.ndarray) -> bytes:
    linhas = ["solid cubo"]
    for t in triangulos:
        linhas += ["facet normal 0 0 0", "outer loop"]
        linhas += [f"vertex {x} {y} {z}" for x, y, z in t]
        linhas += ["endloop", "endfacet"]
    return ("\n".join([*linhas, "endsolid cubo"]) + "\n").encode()


# ---- o STL e a prévia ----


@pytest.mark.parametrize("formato", [stl_binario, stl_texto])
def test_as_medidas_saem_do_proprio_stl(tmp_path: Path, formato: Any) -> None:
    arquivo = tmp_path / "cubo.stl"
    arquivo.write_bytes(formato(cubo(20)))
    m = projetos3d.medir(projetos3d.ler_stl(arquivo))
    assert m.tamanho_mm == (20, 20, 20) and m.triangulos == 12 and m.fechada
    assert m.volume_mm3 == pytest.approx(8000)
    assert m.para_json() == {
        "tamanho_mm": [20.0, 20.0, 20.0], "volume_cm3": 8.0, "triangulos": 12, "fechada": True,
    }  # fmt: skip
    aberta = projetos3d.medir(cubo(20)[:-1])  # sem um triângulo: há aresta de uma face só
    assert not aberta.fechada


def test_stl_invalido_nao_passa(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.stl"
    arquivo.write_bytes(b"<html>nada</html>")
    with pytest.raises(projetos3d.Projeto3DErro, match="inválido"):
        projetos3d.ler_stl(arquivo)


def test_a_previa_e_um_glb_solido_de_pe() -> None:
    t = cubo(10)
    t[..., 2] *= 3  # 10 x 10 x 30 mm, de pé na mesa
    glb = projetos3d.para_glb(t)
    magica, versao, total = struct.unpack_from("<4sII", glb, 0)
    assert (magica, versao, total) == (b"glTF", 2, len(glb))
    tamanho, tipo = struct.unpack_from("<I4s", glb, 12)
    assert tipo == b"JSON"
    gltf = json.loads(glb[20 : 20 + tamanho])
    posicao = gltf["accessors"][0]
    assert posicao["count"] == 36
    assert posicao["max"][1] == pytest.approx(30)  # o Z da impressão vira o Y (para cima)
    material = gltf["materials"][0]["pbrMetallicRoughness"]
    assert material["metallicFactor"] == 0 and material["baseColorFactor"] == projetos3d.MARMORE
    binario = struct.unpack_from("<I4s", glb, 20 + tamanho)
    assert binario[1] == b"BIN\0" and binario[0] == gltf["buffers"][0]["byteLength"]
    # uma placa (um relevo de 3 mm, impresso deitado) aparece de frente: o Z fica para quem vê
    placa = cubo(10)
    placa[..., 0] *= 10
    placa[..., 1] *= 5
    placa[..., 2] *= 0.3
    glb = projetos3d.para_glb(placa)
    gltf = json.loads(glb[20 : 20 + struct.unpack_from("<I", glb, 12)[0]])
    assert gltf["accessors"][0]["max"][1] == pytest.approx(50)


# ---- os projetos ----


@pytest.fixture
def projetos(tmp_path: Path) -> projetos3d.Projetos3D:
    return projetos3d.Projetos3D(tmp_path / "projetos-3d", tmp_path / "acervo", tmp_path / "a.json")


def test_criar_escreve_as_instrucoes_da_sessao(projetos: projetos3d.Projetos3D) -> None:
    p = projetos.criar("Suporte de Celular", "peca", "8 cm de altura, inclinado a 60 graus")
    pasta = Path(p["pasta"])
    assert p["id"] == "suporte-de-celular" and pasta.parent == projetos.raiz
    agentes = (pasta / "AGENTS.md").read_text()
    assert "8 cm de altura, inclinado a 60 graus" in agentes
    assert "build123d" in agentes and "Não imprima" in agentes
    assert "220 x 220 x 250" in agentes  # a mesa dos ajustes (o padrão, sem impressora)
    assert (pasta / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    with pytest.raises(projetos3d.Projeto3DErro, match="Já existe"):
        projetos.criar("Suporte de celular", "peca", "outro")
    for nome, tipo, pedido in (("", "peca", "x"), ("A", "nada", "x"), ("A", "peca", " ")):
        with pytest.raises(projetos3d.Projeto3DErro):
            projetos.criar(nome, tipo, pedido)


def test_a_arte_usa_a_imagem_e_a_pipeline_de_quem_usa(
    projetos: projetos3d.Projetos3D, tmp_path: Path
) -> None:
    pipeline = tmp_path / "minha-pipeline"
    pipeline.mkdir()
    projetos.guardar_ajustes("Impressora da oficina", [256, 256, 256], str(pipeline))
    p = projetos.criar("Galo", "arte", "Relevo de 100 mm", b"\x89PNG imagem", "galo.png")
    pasta = Path(p["pasta"])
    assert (pasta / "entrada" / "referencia.png").read_bytes() == b"\x89PNG imagem"
    agentes = (pasta / "AGENTS.md").read_text()
    assert "`entrada/referencia.png`" in agentes and f"`{pipeline}`" in agentes
    assert "Impressora da oficina: mesa de 256 x 256 x 256 mm" in agentes
    with pytest.raises(projetos3d.Projeto3DErro, match="Imagem inválida"):
        projetos.criar("Outro", "arte", "x", b"conteudo", "virus.exe")
    with pytest.raises(projetos3d.Projeto3DErro, match="pipeline"):
        projetos.guardar_ajustes("", [256, 256, 256], str(tmp_path / "nao-existe"))
    with pytest.raises(projetos3d.Projeto3DErro, match="mesa"):
        projetos.guardar_ajustes("", [10, 256, 256], "")


def test_a_lista_traz_os_arquivos_com_as_medidas(projetos: projetos3d.Projetos3D) -> None:
    p = projetos.criar("Caixa", "peca", "Caixa de 20 mm")
    pasta = Path(p["pasta"])
    (pasta / "modelo.stl").write_bytes(stl_binario(cubo(20)))
    (pasta / "gerar.py").write_text("print('oi')\n")
    (pasta / ".venv").mkdir()
    (pasta / ".venv" / "lixo.py").write_text("")
    [lido] = projetos.listar()
    assert [a["nome"] for a in lido["arquivos"]] == ["gerar.py", "modelo.stl"]  # sem AGENTS.md
    modelo = lido["arquivos"][1]
    assert modelo["medidas"]["tamanho_mm"] == [20.0, 20.0, 20.0] and modelo["medidas"]["fechada"]
    assert (pasta / ".ze" / "modelo.stl.medidas.json").is_file()  # guardadas: não relê o STL
    assert projetos.principal("caixa") == "modelo.stl"
    with pytest.raises(projetos3d.Projeto3DErro):
        projetos.ler("../fora")


def test_a_previa_vai_para_o_acervo_e_so_refaz_quando_muda(
    projetos: projetos3d.Projetos3D,
) -> None:
    pasta = Path(projetos.criar("Caixa", "peca", "Caixa")["pasta"])
    with pytest.raises(projetos3d.Projeto3DErro, match="ainda não tem modelo"):
        projetos.previa("caixa")
    (pasta / "pecas").mkdir()
    (pasta / "pecas" / "base.stl").write_bytes(stl_binario(cubo(10)))
    relativo = projetos.previa("caixa")
    assert relativo == "3d/projetos/caixa/pecas-base.glb"
    destino = projetos.acervo / relativo
    assert destino.read_bytes()[:4] == b"glTF"
    antes = destino.stat().st_mtime_ns
    projetos.previa("caixa", "pecas/base.stl")
    assert destino.stat().st_mtime_ns == antes  # o mesmo arquivo: não refaz
    for ruim in ("../../a.stl", "gerar.py", "nao-existe.stl"):
        with pytest.raises(projetos3d.Projeto3DErro):
            projetos.previa("caixa", ruim)


def test_comecar_cria_a_sessao_na_pasta_com_a_tarefa(projetos: projetos3d.Projetos3D) -> None:
    p = projetos.criar("Caixa", "peca", "Caixa de 20 mm para pilhas")
    feitas: list[Any] = []

    def criar(nome: str, pasta: str, motor: str, origem: str) -> Any:
        feitas.append(("criar", nome, pasta, motor))
        return SimpleNamespace(id="s1")

    sessoes = SimpleNamespace(
        criar=criar, enviar=lambda id_, texto: feitas.append(("enviar", id_, texto))
    )
    assert projetos3d.comecar(projetos, sessoes, "caixa", "claude", "voz") == "s1"
    assert feitas[0] == ("criar", "3D · Caixa", p["pasta"], "claude")
    assert feitas[1][2].startswith('Projeto 3D "Caixa" (peça funcional): Caixa de 20 mm')
    assert projetos.ler("caixa")["sessao"] == "s1"


# ---- a voz e o painel ----


class Tela:
    def __init__(self) -> None:
        self.acoes: list[Any] = []

    def agir(self, acoes: list[Any]) -> dict[str, Any]:
        self.acoes += acoes
        return {"resultados": [{"ok": True}]}


def test_a_voz_mostra_como_solido_e_criar_pede_o_sim(projetos: projetos3d.Projetos3D) -> None:
    pasta = Path(projetos.criar("Caixa", "peca", "Caixa")["pasta"])
    (pasta / "modelo.stl").write_bytes(stl_binario(cubo(10)))
    tela = Tela()
    fs: dict[str, Any] = {
        f.name: f.handler
        for f in g_projetos3d.ferramentas(projetos, None, tela)  # type: ignore[arg-type]
    }
    r = asyncio.run(fs["projeto3d_mostrar"]({"projeto": "caixa"}))
    assert json.loads(r["content"][0]["text"])["mostrado"] is True
    assert tela.acoes == [{"acao": "mostrar_modelo", "alvo": "3d/projetos/caixa/modelo.glb",
                           "valor": "Caixa", "estilo": "solido"}]  # fmt: skip
    listados = json.loads(asyncio.run(fs["projetos3d_listar"]({}))["content"][0]["text"])
    assert listados["projetos"][0]["id"] == "caixa"
    # listar e mostrar passam sem perguntar; criar (abre uma sessão que roda código) pede o sim
    assert "mcp__jarvis__projetos3d_listar" in LIVRES and "mcp__jarvis__projeto3d_mostrar" in LIVRES
    assert "mcp__jarvis__projeto3d_criar" not in LIVRES
    assert claude.descrever("mcp__jarvis__projeto3d_criar", {"nome": "Galo", "tipo": "arte"}) == (
        "Vou criar o projeto 3D Galo e uma sessão para modelar a arte."
    )
    assert g_projetos3d.ferramentas(None, None, None) == []


def test_a_pagina_cria_lista_e_mostra(projetos: projetos3d.Projetos3D) -> None:
    feitas: list[Any] = []
    sessoes = SimpleNamespace(
        criar=lambda nome, pasta, motor, origem: SimpleNamespace(id="s9"),
        enviar=lambda id_, texto: feitas.append(texto),
    )
    tela = Tela()
    pagina = AcoesProjetos3D(
        SimpleNamespace(),
        Servicos(
            {"projetos3d": lambda: projetos, "sessoes": lambda: sessoes, "tela": lambda: tela}
        ),
    )
    r = pagina.criar_projeto_3d({"nome": "Caixa", "tipo": "peca", "pedido": "Caixa de 20 mm"})
    assert r["aviso"] == "Projeto criado. A sessão começou a modelar."
    assert r["projetos"][0]["sessao"] == "s9" and len(feitas) == 1
    r = pagina.criar_projeto_3d_com_imagem(
        b"\x89PNG", {"nome": "Galo", "tipo": "arte", "pedido": "Relevo", "nome_imagem": "g.png"}
    )
    assert {p["id"] for p in r["projetos"]} == {"caixa", "galo"}
    with pytest.raises(PedidoInvalido, match="Já existe"):
        pagina.criar_projeto_3d({"nome": "Caixa", "tipo": "peca", "pedido": "x"})
    (projetos.raiz / "caixa" / "modelo.stl").write_bytes(stl_binario(cubo(10)))
    assert pagina.mostrar_projeto_3d({"id": "caixa"})["aviso"] == "Na Imersão."
    assert tela.acoes[0]["estilo"] == "solido"
    assert pagina.ajustes_projetos_3d(
        {"impressora": "A", "mesa_mm": [256, 256, 256], "pipeline_arte": ""}
    )["ajustes"]["mesa_mm"] == [256.0, 256.0, 256.0]
