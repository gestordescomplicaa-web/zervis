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
