"""O filho que volta sozinho: queda de verdade avisa com o código; saída ordenada não."""

import logging
import sys
import time
from pathlib import Path

import pytest

from zervis import filho


def _rodar_uma_vez(
    codigo: str, caplog: pytest.LogCaptureFixture, registro: Path | None = None
) -> list[logging.LogRecord]:
    f = filho.Filho("teste", [sys.executable, "-c", codigo], {}, registro=registro)
    with caplog.at_level(logging.INFO, logger="zervis.filho"):
        f.iniciar()
        fim = time.monotonic() + 10
        while not any("de novo" in r.getMessage() for r in caplog.records):
            assert time.monotonic() < fim
            time.sleep(0.02)
        f.parar()
    return [r for r in caplog.records if "de novo" in r.getMessage()]


def test_queda_avisa_com_codigo_e_ultima_linha(caplog: pytest.LogCaptureFixture) -> None:
    (r,) = _rodar_uma_vez("import sys; sys.exit('quebrou aqui')", caplog)
    assert r.levelno == logging.WARNING
    assert "código 1" in r.getMessage() and "quebrou aqui" in r.getMessage()


def test_saida_ordenada_nao_conta_como_queda(caplog: pytest.LogCaptureFixture) -> None:
    (r,) = _rodar_uma_vez("pass", caplog)
    assert r.levelno == logging.INFO and "encerrado (código 0)" in r.getMessage()


def test_saida_padrao_vai_para_o_registro(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    registro = tmp_path / "estado" / "filho.log"
    (r,) = _rodar_uma_vez("print('porta ocupada'); raise SystemExit(2)", caplog, registro)
    assert "código 2: porta ocupada" in r.getMessage()
