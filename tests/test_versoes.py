"""Atualizações pelo painel (`zervis/versoes.py`): um repositório Git de verdade, com origem e
etiquetas; o systemd e o `zervis update` falsos."""

import asyncio
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import cli, versoes
from zervis.cerebro.ferramentas import atualizacoes as ferramenta
from zervis.portal.acoes.atualizacoes import AcoesAtualizacoes
from zervis.portal.acoes.pagina import Servicos
from zervis.portal.servidor import PedidoInvalido


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 (repositórios sintéticos, argumentos fixos)
        ["git", "-C", str(pasta), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(pasta: Path, changelog: str, mensagem: str) -> None:
    (pasta / "CHANGELOG.md").write_text(changelog)
    _git(pasta, "add", "CHANGELOG.md")
    _git(pasta, "commit", "-q", "-m", mensagem)


V010 = "# Changelog\n\n## 0.1.0\n\n- Primeira versão.\n"
V020 = (
    "# Changelog\n\n## 0.2.0\n\n- Atualizações pelo painel: procurar e atualizar com\n"
    "  um clique.\n- Documentos revisados.\n\n## 0.1.0\n\n- Primeira versão.\n"
)
MASTER = V020.replace("## 0.2.0", "## Não lançado\n\n- Algo ainda sem versão.\n\n## 0.2.0")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A origem com v0.1.0, v0.2.0 e a master um commit à frente; o Zé clonado na v0.1.0."""
    for variavel, valor in {
        "GIT_AUTHOR_NAME": "Teste",
        "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
        "GIT_COMMITTER_NAME": "Teste",
        "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }.items():
        monkeypatch.setenv(variavel, valor)
    trabalho = tmp_path / "trabalho"
    trabalho.mkdir()
    _git(trabalho, "init", "-q", "-b", "master")
    _commit(trabalho, V010, "0.1.0")
    _git(trabalho, "tag", "v0.1.0")
    _commit(trabalho, V020, "0.2.0")
    _git(trabalho, "tag", "v0.2.0")
    _commit(trabalho, MASTER, "depois da 0.2.0")
    origem = tmp_path / "origem.git"
    _git(tmp_path, "clone", "-q", "--bare", str(trabalho), str(origem))
    ze = tmp_path / "ze"
    _git(tmp_path, "clone", "-q", str(origem), str(ze))
    _git(ze, "reset", "-q", "--hard", "v0.1.0")
    monkeypatch.setattr(cli, "REPO", ze)
    return ze


class Lancador:
    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.pedidos: list[list[str]] = []

    def __call__(self, comando: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.pedidos.append(list(comando))
        return subprocess.CompletedProcess(comando, self.codigo, "", "sem systemd")


def _versoes(tmp_path: Path, lancar: Lancador | None = None, **extra: Any) -> versoes.Versoes:
    return versoes.Versoes(
        tmp_path / "estado", tmp_path / "config", lancar=lancar or Lancador(), **extra
    )


def test_procura_a_versao_publicada_com_o_que_muda_no_changelog(repo: Path, tmp_path: Path) -> None:
    v = _versoes(tmp_path)
    achado = v.procurar()
    assert achado["canal"] == "versoes" and achado["disponivel"]
    assert achado["destino"] == "v0.2.0" and achado["mudancas"] == 1
    assert achado["novidades"] == [
        "Atualizações pelo painel: procurar e atualizar com um clique.",
        "Documentos revisados.",
    ]
    assert v.foto() == {"disponivel": True, "rodando": False}


def test_canal_desenvolvimento_segue_a_master(repo: Path, tmp_path: Path) -> None:
    _git(repo, "reset", "-q", "--hard", "v0.2.0")
    v = _versoes(tmp_path)
    assert v.procurar()["motivo"] == "em_dia"
    v.mudar_canal("desenvolvimento")
    assert v.ultima() == {}  # a procura de antes era do outro canal
    achado = v.procurar()
    assert achado["disponivel"] and achado["novidades"] == ["Algo ainda sem versão."]
    assert json.loads((tmp_path / "config" / "atualizacoes.json").read_text()) == {
        "canal": "desenvolvimento"
    }
    with pytest.raises(ValueError):
        v.mudar_canal("beta")


def test_a_frente_da_versao_publicada_aponta_o_desenvolvimento(repo: Path, tmp_path: Path) -> None:
    _git(repo, "reset", "-q", "--hard", "origin/master")
    achado = _versoes(tmp_path).procurar()
    assert not achado["disponivel"] and achado["motivo"] == "a_frente"
    assert "canal Desenvolvimento" in achado["texto"]


def test_alteracoes_locais_nao_oferecem_atualizacao(repo: Path, tmp_path: Path) -> None:
    (repo / "CHANGELOG.md").write_text("mexido\n")
    achado = _versoes(tmp_path).procurar()
    assert not achado["disponivel"] and achado["motivo"] == "alteracoes"


def test_aplicar_roda_fora_do_ze_numa_unidade_propria(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZERVIS_PERFIL", "teste")
    lancar = Lancador()
    v = _versoes(tmp_path, lancar)
    v.mudar_canal("desenvolvimento")
    assert v.aplicar().startswith("Atualizando")
    systemd_run = next(p for p in lancar.pedidos if p[0] == "systemd-run")
    assert "--unit=zervis-atualizar" in systemd_run
    assert "--setenv=ZERVIS_PERFIL=teste" in systemd_run  # as mesmas pastas do serviço
    assert systemd_run[-3:] == ["-m", "zervis.versoes", "desenvolvimento"]
    assert v.rodando()
    assert v.aplicar() == "Já há uma atualização em andamento."


def test_sem_systemd_a_falha_fica_registrada(repo: Path, tmp_path: Path) -> None:
    v = _versoes(tmp_path, Lancador(codigo=1))
    assert "Não consegui" in v.aplicar()
    assert not v.rodando()
    assert v.ultimo_resultado()["estado"] == "falhou"
    assert "sem systemd" in v.ultimo_resultado()["registro"]


def test_um_rodando_antigo_morreu_sem_escrever_o_fim(repo: Path, tmp_path: Path) -> None:
    relogio = [1000.0]
    v = _versoes(tmp_path, agora=lambda: relogio[0])
    v.aplicar()
    relogio[0] += versoes.RODANDO_MAXIMO_S + 1
    assert not v.rodando()


@pytest.mark.parametrize(
    ("codigo", "saida", "avanca", "estado"),
    [
        (0, "Atualizado para v0.2.0. O painel respondeu.", True, "ok"),
        (0, "Já está na versão mais nova (v0.2.0).", False, "nada"),
        (1, "O painel não voltou na versão nova: voltando para a anterior.", False, "voltou"),
        (1, "Sem conexão com a origem do código.", False, "falhou"),
    ],
)
def test_executar_guarda_o_resultado_e_o_ze_avisa_uma_vez(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    codigo: int,
    saida: str,
    avanca: bool,
    estado: str,
) -> None:
    def update(_rodar: Any, desenvolvimento: bool = False) -> int:
        assert not desenvolvimento
        if avanca:
            _git(repo, "merge", "-q", "--ff-only", "v0.2.0")
        print(saida)
        return codigo

    monkeypatch.setattr(cli, "update", update)
    v = _versoes(tmp_path)
    v.aplicar()
    assert v.executar("versoes") == codigo
    resultado = v.ultimo_resultado()
    assert resultado["estado"] == estado and not resultado["rodando"]
    assert saida in resultado["registro"]
    assert v.resultado_novo() == versoes.RESULTADOS[estado].format(para=resultado["para"])
    assert v.resultado_novo() is None  # uma vez só


def test_executar_registra_ate_uma_excecao(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebra(*_a: Any, **_k: Any) -> int:
        raise OSError("disco cheio")

    monkeypatch.setattr(cli, "update", quebra)
    v = _versoes(tmp_path)
    assert v.executar("versoes") == 1
    assert "disco cheio" in v.ultimo_resultado()["registro"]


def test_procura_do_dia_avisa_so_um_destino_novo(repo: Path, tmp_path: Path) -> None:
    v = _versoes(tmp_path)
    assert v.procurar_do_dia() == "Tem versão nova do Zé, a v0.2.0. Está em Atualizações."
    assert v.procurar_do_dia() is None
    _git(repo, "reset", "-q", "--hard", "v0.2.0")
    v.mudar_canal("desenvolvimento")
    assert v.procurar_do_dia() == "Tem atualização do Zé: 1 mudanças. Está em Atualizações."


def _pagina(v: versoes.Versoes, trabalhando: list[str], reserva: object = None) -> Any:
    servicos = {
        "versoes": lambda: v,
        "sessoes": lambda: SimpleNamespace(trabalhando=lambda: trabalhando),
        "atualizacao": lambda: SimpleNamespace(reserva=lambda: reserva),
    }
    pagina = AcoesAtualizacoes(SimpleNamespace(), Servicos(servicos))
    pagina.painel = pagina  # type: ignore[assignment]
    return pagina


@pytest.mark.parametrize(
    ("trabalhando", "reserva", "erro"),
    [
        (["s1"], None, "Uma sessão está trabalhando"),
        (["s1", "s2"], None, "2 sessões estão trabalhando"),
        ([], object(), "autodesenvolvimento"),
    ],
)
def test_painel_nao_atualiza_cortando_alguem(
    repo: Path, tmp_path: Path, trabalhando: list[str], reserva: object, erro: str
) -> None:
    lancar = Lancador()
    with pytest.raises(PedidoInvalido, match=erro):
        _pagina(_versoes(tmp_path, lancar), trabalhando, reserva).aplicar_atualizacao({})
    assert lancar.pedidos == []


def test_painel_atualiza_quando_ha_o_que_aplicar(repo: Path, tmp_path: Path) -> None:
    lancar = Lancador()
    pagina = _pagina(_versoes(tmp_path, lancar), [])
    resposta = pagina.aplicar_atualizacao({})
    assert resposta["aviso"].startswith("Atualizando") and resposta["resultado"]["rodando"]
    _git(repo, "reset", "-q", "--hard", "v0.2.0")
    with pytest.raises(PedidoInvalido, match="versão mais nova"):
        _pagina(_versoes(tmp_path / "outro", Lancador()), []).aplicar_atualizacao({})
    with pytest.raises(PedidoInvalido, match="Canal desconhecido"):
        pagina.canal_de_atualizacao({"canal": "beta"})


def test_a_voz_so_le(repo: Path, tmp_path: Path) -> None:
    v = _versoes(tmp_path)
    (ver,) = ferramenta.ferramentas(v)

    async def chamar() -> dict[str, Any]:
        return await ver.handler({})

    resposta = asyncio.run(chamar())
    dados = json.loads(resposta["content"][0]["text"])
    assert dados["disponivel"] and dados["diga"].startswith("Há uma versão nova (v0.2.0)")
    assert dados["onde"] == "Atualizações, no painel"
