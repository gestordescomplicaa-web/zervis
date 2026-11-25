"""Os anexos do chat do Início (ADR 0137): guardar com trava, ler para o cérebro e mostrar."""

import asyncio
import io
import os
import queue
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from zervis.cerebro import ferramentas, rapido
from zervis.cerebro.ferramentas import anexos as g_anexos
from zervis.memoria import anexos
from zervis.memoria.anexos import AnexoErro, Anexos
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido


def _png(largura: int = 40, altura: int = 30) -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), (30, 150, 160)).save(saida, "PNG")
    return saida.getvalue()


def _pdf(texto: str) -> bytes:
    """Um PDF mínimo de verdade, com uma linha de texto (os deslocamentos do xref certos)."""
    fluxo = f"BT /F1 18 Tf 72 720 Td ({texto}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R"
        b" >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida, posicoes = bytearray(b"%PDF-1.4\n"), []
    for i, corpo in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += b"%d 0 obj\n" % i + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    saida += b"".join(b"%010d 00000 n \n" % p for p in posicoes)
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        xref,
    )
    return bytes(saida)


def test_guarda_com_nome_unico_sem_caminho_e_so_para_quem_usa(tmp_path: Path) -> None:
    loja = Anexos(tmp_path / "anexos")
    guardado = loja.guardar("../../etc/minha foto.PNG", _png())
    assert anexos.GUARDADO.match(guardado) and guardado.endswith("-minha-foto.png")
    alvo = loja.caminho(guardado)
    assert alvo is not None and alvo.parent == tmp_path / "anexos"
    assert oct(alvo.stat().st_mode & 0o777) == "0o600"
    assert loja.info(guardado)["nome"] == "minha-foto.png"
    assert loja.info(guardado)["miniatura"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    ("nome", "dados", "erro"),
    [
        ("programa.exe", b"MZ...", "Tipo não aceito"),
        ("contrato.pdf", b"<html>nao sou pdf</html>", "não é do tipo"),
        ("foto.jpg", _png(), "não é do tipo"),  # PNG com nome de JPEG
        ("notas.txt", "olá".encode("latin-1"), "UTF-8"),
        ("vazio.png", b"", "vazio"),
    ],
)
def test_recusa_o_que_nao_e_do_tipo_aceito(
    tmp_path: Path, nome: str, dados: bytes, erro: str
) -> None:
    with pytest.raises(AnexoErro, match=erro):
        Anexos(tmp_path).guardar(nome, dados)


def test_recusa_arquivo_grande(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anexos, "MAX_BYTES", 10)
    with pytest.raises(AnexoErro, match="20 MB"):
        Anexos(tmp_path).guardar("a.txt", b"x" * 11)


def test_so_le_nomes_guardados_dentro_da_pasta(tmp_path: Path) -> None:
    loja = Anexos(tmp_path / "anexos")
    (tmp_path / "segredo.txt").write_text("não")
    for nome in ("../segredo.txt", "segredo.txt", "20261125-151000-a1b2c3-../../x", ""):
        assert loja.caminho(nome) is None
        with pytest.raises(AnexoErro, match="não encontrado"):
            loja.ler(nome)


def test_ler_imagem_reduzida_pdf_e_texto(tmp_path: Path) -> None:
    loja = Anexos(tmp_path)
    tipo, foto = loja.ler(loja.guardar("grande.png", _png(3000, 2000)))
    assert tipo == "imagem" and isinstance(foto, bytes)
    with Image.open(io.BytesIO(foto)) as imagem:
        assert imagem.format == "JPEG" and max(imagem.size) == anexos.LADO_PARA_O_MODELO
    tipo, texto = loja.ler(loja.guardar("contrato.pdf", _pdf("Renova por 12 meses")))
    assert tipo == "texto" and "[página 1]" in str(texto) and "Renova por 12 meses" in str(texto)
    assert loja.ler(loja.guardar("notas.md", "# Lista\n- pão".encode()))[1] == "# Lista\n- pão"


def test_anexo_antigo_sai_ao_guardar_um_novo(tmp_path: Path) -> None:
    loja = Anexos(tmp_path)
    velho = loja.guardar("velho.txt", b"a")
    antes = time.time() - (anexos.DIAS_GUARDADOS + 1) * 86400
    os.utime(tmp_path / velho, (antes, antes))
    loja.guardar("novo.txt", b"b")
    assert loja.caminho(velho) is None


def test_marca_e_separa_os_anexos_do_pedido() -> None:
    nomes = ["20261125-151000-a1b2c3-foto.jpg", "20261125-151001-d4e5f6-contrato.pdf"]
    pedido = anexos.marcar("O que acha?", nomes)
    assert pedido == f"O que acha? [anexos: {nomes[0]}, {nomes[1]}]"
    assert anexos.separar(pedido) == ("O que acha?", nomes)
    assert anexos.separar("Sem anexo") == ("Sem anexo", [])
    assert anexos.separar("Truque [anexos: ../../etc/passwd]") == ("Truque", [])


def test_pedido_com_anexo_vai_ao_cerebro_completo() -> None:
    """A via rápida não tem ferramentas: o pedido com anexo vai sempre ao cérebro."""
    pedido = anexos.marcar("legal?", ["20261125-151000-a1b2c3-foto.jpg"])
    assert rapido.precisa_do_completo(pedido)


def test_ferramenta_entrega_a_imagem_e_o_texto_e_deixa_o_turno_de_fora(tmp_path: Path) -> None:
    loja = Anexos(tmp_path)
    (ferramenta,) = g_anexos.ferramentas(loja)

    def ler(nome: str) -> dict[str, Any]:
        async def chamar() -> dict[str, Any]:
            return await ferramenta.handler({"nome": nome})

        return asyncio.run(chamar())

    foto = ler(loja.guardar("fachada.png", _png()))
    assert [c["type"] for c in foto["content"]] == ["text", "image"]
    assert foto["content"][1]["mimeType"] == "image/jpeg"
    texto = ler(loja.guardar("a.csv", b"nome,valor\nAna,10"))
    assert "Ana,10" in texto["content"][0]["text"]
    assert ler("../x")["is_error"] is True
    assert ferramentas.de_fora("mcp__jarvis__anexo_ler") == "um anexo do chat"
    assert "mcp__jarvis__anexo_ler" in ferramentas.LIVRES


def _nucleo(loja: Anexos, estado: e.Estado = e.Estado.ATIVO) -> tuple[Nucleo, "queue.Queue[Any]"]:
    n = Nucleo.__new__(Nucleo)
    n.maquina = e.Maquina()
    n.maquina.estado = estado
    eventos: queue.Queue[Any] = queue.Queue()
    n.eventos = eventos
    n.anexos = loja  # type: ignore[attr-defined]
    return n, eventos


def test_pedido_escrito_leva_os_anexos_no_fim(tmp_path: Path) -> None:
    loja = Anexos(tmp_path)
    foto = loja.guardar("fachada.png", _png())
    n, eventos = _nucleo(loja)
    assert n.escrever("Monte um post", [foto]) == "Enviado."
    assert eventos.get_nowait() == e.Digitado(f"Monte um post [anexos: {foto}]")
    assert n.escrever("", [foto]) == "Enviado."  # só a foto
    assert eventos.get_nowait() == e.Digitado(f"Veja o anexo. [anexos: {foto}]")
    assert n.escrever("Olha", ["20261125-151000-a1b2c3-sumiu.png"]) == "Anexo não encontrado."
    assert n.escrever("Olha", [foto] * 6) == "Anexo não encontrado."
    assert eventos.empty()
    confirmando, _ = _nucleo(loja, e.Estado.CONFIRMANDO)
    assert confirmando.escrever("sim", [foto]) == "Responda a confirmação antes de anexar."


def test_painel_guarda_o_anexo_e_o_chat_mostra_nome_e_miniatura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loja = Anexos(tmp_path / "anexos")
    monkeypatch.setattr(anexos, "PADRAO", loja)
    escritos: list[tuple[Any, ...]] = []

    def escrever(*args: Any) -> str:
        escritos.append(args)
        return "Enviado."

    n = SimpleNamespace(escrever=escrever)
    acoes = Acoes(n, tmp_path, tmp_path)
    guardado = acoes.anexar_conversa(_png(), {"nome": "fachada.png"})["anexo"]
    with pytest.raises(PedidoInvalido, match="Tipo não aceito"):
        acoes.anexar_conversa(b"x", {"nome": "virus.exe"})
    assert acoes.escrever({"texto": "Post", "anexos": [guardado]}) == {"aviso": "Enviado."}
    assert acoes.escrever({"texto": "Só texto"}) == {"aviso": "Enviado."}
    assert escritos == [("Post", [guardado]), ("Só texto",)]
    with pytest.raises(PedidoInvalido, match="No máximo 5"):
        acoes.escrever({"texto": "x", "anexos": [guardado] * 6})
    from zervis.portal.acoes.inicio import _pedido

    pedido = _pedido("2026-11-25T15:10:00-03:00", anexos.marcar("Post", [guardado]))
    assert pedido["texto"] == "Post"
    assert pedido["anexos"][0]["nome"] == "fachada.png"
    assert pedido["anexos"][0]["miniatura"].startswith("data:image/jpeg")
