"""Configuração validada na carga e instância única."""

from pathlib import Path

import pytest

from zervis.config import ConfigInvalida, carregar
from zervis.nucleo.instancia import JaRodando, travar


def test_sem_arquivo_usa_os_padroes(tmp_path: Path) -> None:
    cfg = carregar(tmp_path / "nao-existe.toml")
    assert cfg["cerebro"]["provedor"] == "claude"
    assert cfg.caminho("ativacao", "modelo").is_absolute()


def test_omniroute_em_loopback_e_aceito(tmp_path: Path) -> None:
    arquivo = tmp_path / "c.toml"
    arquivo.write_text(
        '[cerebro]\nprovedor = "omniroute"\nomniroute_endereco = "http://localhost:9"\n'
    )
    assert carregar(arquivo)["cerebro"]["provedor"] == "omniroute"


def test_arquivo_sobrescreve_so_o_que_traz(tmp_path: Path) -> None:
    arquivo = tmp_path / "c.toml"
    arquivo.write_text("versao = 1\n[escuta]\nconversa_s = 5\n")
    cfg = carregar(arquivo)
    assert cfg["escuta"]["conversa_s"] == 5.0
    assert cfg["escuta"]["limiar_vad"] == 0.35


@pytest.mark.parametrize(
    ("conteudo", "erro"),
    [
        ("[vozes]\nx = 1\n", "seção desconhecida"),
        ("[escuta]\nfim_silencio = 1\n", "chave desconhecida"),
        ('[escuta]\nconversa_s = "2"\n', "precisa ser float"),
        ("[ativacao]\npaciencia = true\n", "precisa ser int"),
        ('[cerebro]\nprovedor = "gemini"\n', "cerebro.provedor"),
        ("[cerebro]\nferramentas = [1]\n", "lista de textos"),
        ('[cerebro]\nreserva = "omniroute"\n', "cerebro.reserva"),
        ("[cerebro]\ntempo_limite_s = 0\n", "positivo"),
        ('[cerebro]\nomniroute_endereco = "http://192.168.0.5:20128"\n', "loopback"),
        # https vale em qualquer lugar; http, só na própria máquina (a chave não vai aberta)
        ('[cerebro]\nomniroute_endereco = "http://omniroute.exemplo.com:20128"\n', "loopback"),
        ("versao = 2\n", "versao"),
        ("isto não é toml", "TOML inválido"),
    ],
)
def test_config_invalida_para_com_mensagem_clara(tmp_path: Path, conteudo: str, erro: str) -> None:
    arquivo = tmp_path / "c.toml"
    arquivo.write_text(conteudo)
    with pytest.raises(ConfigInvalida, match=erro):
        carregar(arquivo)


def test_segunda_instancia_e_recusada(tmp_path: Path) -> None:
    primeira = travar(tmp_path / "jarvisd.lock")
    with pytest.raises(JaRodando):
        travar(tmp_path / "jarvisd.lock")
    primeira.close()
    travar(tmp_path / "jarvisd.lock").close()
