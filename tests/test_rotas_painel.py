"""A divisão das páginas preserva o contrato público e limita suas dependências."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.portal.acoes import Acoes
from jarvis.portal.acoes.pagina import Servicos


def test_rotas_iguais_ao_contrato_anterior(tmp_path: Path) -> None:
    acoes = Acoes(SimpleNamespace(), tmp_path, tmp_path)
    antes = json.loads(Path(__file__).with_name("rotas_painel.json").read_text())
    for grupo in ("leituras", "escritas", "envios"):
        assert sorted(getattr(acoes, grupo)()) == sorted(antes[grupo])


def test_pagina_nao_recebe_servicos_nao_declarados() -> None:
    servicos = Servicos({"memoria": lambda: "memoria"})
    assert servicos.memoria == "memoria"
    with pytest.raises(AttributeError, match="não declarado"):
        _ = servicos.sessoes
