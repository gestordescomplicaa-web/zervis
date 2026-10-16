"""A primeira vez: baixa o que falta e confere a impressão digital antes de usar."""

import hashlib
import io
from pathlib import Path
from typing import Any

import pytest

from jarvis import preparar


class Resposta(io.BytesIO):
    def __enter__(self) -> "Resposta":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def test_baixa_confere_e_recusa_arquivo_trocado(tmp_path: Path) -> None:
    bom = b"modelo de verdade"
    m = preparar.Modelo(
        "x.onnx", "https://exemplo/x.onnx", hashlib.sha256(bom).hexdigest(), "teste"
    )
    preparar.baixar(m, tmp_path, lambda url, timeout: Resposta(bom))
    assert (tmp_path / "x.onnx").read_bytes() == bom
    (tmp_path / "x.onnx").unlink()
    with pytest.raises(preparar.PrepararErro, match="impressão digital"):
        preparar.baixar(m, tmp_path, lambda url, timeout: Resposta(b"trocado no caminho"))
    assert list(tmp_path.iterdir()) == []  # nada pela metade nem errado fica


def test_as_fontes_sao_oficiais_e_fixas() -> None:
    assert len(preparar.MODELOS) == 6
    for m in preparar.MODELOS:
        assert m.url.startswith(("https://github.com/", "https://huggingface.co/"))
        assert len(m.sha256) == 64
    assert preparar.faltando(Path("/nao/existe")) == list(preparar.MODELOS)


def _modelo(conteudo: bytes) -> preparar.Modelo:
    return preparar.Modelo(
        "voz.onnx", "https://original.exemplo/voz.onnx", hashlib.sha256(conteudo).hexdigest(), "t"
    )


def test_o_espelho_tem_a_vez_e_a_fonte_original_e_a_alternativa(tmp_path: Path) -> None:
    bom = b"a voz"
    m = _modelo(bom)
    assert preparar.fontes(m) == [m.url]
    assert preparar.fontes(m, "https://espelho.exemplo/modelos/") == [
        "https://espelho.exemplo/modelos/voz.onnx",
        m.url,
    ]
    pedidos: list[str] = []

    def abrir(url: str, timeout: int) -> Resposta:
        pedidos.append(url)
        return Resposta(bom)

    preparar.baixar(m, tmp_path, abrir, espelho="https://espelho.exemplo/modelos")
    assert pedidos == ["https://espelho.exemplo/modelos/voz.onnx"]  # o original nem foi tentado


def test_espelho_fora_do_ar_ou_adulterado_cai_para_a_fonte_original(tmp_path: Path) -> None:
    """O espelho não precisa ser de confiança: a impressão digital é a do código."""
    bom = b"a voz"
    m = _modelo(bom)
    for estrago in (OSError("404"), Resposta(b"arquivo trocado no espelho")):
        pedidos: list[str] = []

        def abrir(
            url: str, timeout: int, estrago: object = estrago, pedidos: list[str] = pedidos
        ) -> Resposta:
            pedidos.append(url)
            if url.startswith("https://espelho"):
                if isinstance(estrago, OSError):
                    raise estrago
                return estrago  # type: ignore[return-value]
            return Resposta(bom)

        preparar.baixar(m, tmp_path, abrir, espelho="https://espelho.exemplo")
        assert [u.split("/")[2] for u in pedidos] == ["espelho.exemplo", "original.exemplo"]
        assert (tmp_path / "voz.onnx").read_bytes() == bom
        (tmp_path / "voz.onnx").unlink()
    assert list(tmp_path.iterdir()) == []


def test_sem_nenhuma_fonte_o_erro_e_o_da_ultima(tmp_path: Path) -> None:
    m = _modelo(b"x")

    def abrir(url: str, timeout: int) -> Resposta:
        raise OSError(f"sem rede para {url.split('/')[2]}")

    with pytest.raises(OSError, match=r"original\.exemplo"):
        preparar.baixar(m, tmp_path, abrir, espelho="https://espelho.exemplo")
    assert list(tmp_path.iterdir()) == []


def test_garantir_usa_o_espelho_do_ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rede que bloqueia o HuggingFace: com o espelho no ambiente, a voz baixa mesmo assim."""
    conteudo = {m.nome: f"conteúdo de {m.nome}".encode() for m in preparar.MODELOS}
    falsos = tuple(
        preparar.Modelo(m.nome, m.url, hashlib.sha256(conteudo[m.nome]).hexdigest(), m.para_que)
        for m in preparar.MODELOS
    )
    monkeypatch.setattr(preparar, "MODELOS", falsos)
    monkeypatch.setenv("ZE_MODELOS_URL", "https://espelho.exemplo/modelos")
    pedidos: list[str] = []

    def abrir(url: str, timeout: int) -> Resposta:
        pedidos.append(url)
        if "huggingface.co" in url or "github.com/dscripka" in url:
            raise OSError("403 Forbidden")  # a rede de quem instala bloqueia as fontes originais
        return Resposta(conteudo[url.rsplit("/", 1)[1]])

    monkeypatch.setattr("urllib.request.urlopen", abrir)
    assert sorted(preparar.garantir(tmp_path)) == sorted(conteudo)
    assert all(u.startswith("https://espelho.exemplo/modelos/") for u in pedidos)
    assert preparar.faltando(tmp_path) == []


def test_manifesto_traz_as_impressoes_digitais_fixas() -> None:
    linhas = preparar.manifesto().splitlines()
    assert len(linhas) == len(preparar.MODELOS)
    for linha, m in zip(linhas, preparar.MODELOS, strict=True):
        assert linha == f"{m.sha256}  {m.nome}"  # duas barras de espaço: formato do sha256sum -c
