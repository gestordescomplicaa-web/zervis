"""Claude Code e Codex vêm com o Zé: numa VPS nova, nenhum dos dois estava instalado (ADR 0035)."""

import hashlib
import io
import tarfile
from pathlib import Path
from typing import Any

import pytest

from zervis.cerebro import agentes_nativos as an
from zervis.preparar import Modelo, PrepararErro


class _Resposta(io.BytesIO):
    def __enter__(self) -> "_Resposta":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _pacote(*arquivos: tuple[str, bytes]) -> bytes:
    saida = io.BytesIO()
    with tarfile.open(fileobj=saida, mode="w:gz") as tar:
        for nome, dados in arquivos:
            info = tarfile.TarInfo(nome)
            info.size = len(dados)
            tar.addfile(info, io.BytesIO(dados))
    return saida.getvalue()


AUXILIAR = _pacote(("codex-code-mode-host-x86_64-unknown-linux-musl", b"#!/bin/sh\necho host\n"))


def _falso(nome: str, conteudo: bytes) -> Modelo:
    return Modelo(nome, f"https://exemplo/{nome}", hashlib.sha256(conteudo).hexdigest(), "t")


def _servir(**pacotes: bytes) -> Any:
    """`abrir` falso: cada URL devolve o pacote com aquele nome."""
    return lambda url, timeout: _Resposta(pacotes[url.rsplit("/", 1)[1].split("-x86")[0]])


def _com_pacote(monkeypatch: pytest.MonkeyPatch, conteudo: bytes) -> None:
    falso = _falso("codex-x86_64-unknown-linux-musl.tar.gz", conteudo)
    auxiliar = _falso("codex-code-mode-host-x86_64-unknown-linux-musl.tar.gz", AUXILIAR)
    monkeypatch.setattr(an, "CODEX_PACOTES", {"x86_64": falso})
    monkeypatch.setattr(an, "CODEX_AUXILIAR_PACOTES", {"x86_64": auxiliar})
    monkeypatch.setattr("zervis.cerebro.agentes_nativos.platform.machine", lambda: "x86_64")
    monkeypatch.setattr("zervis.cerebro.agentes_nativos.shutil.which", lambda nome, path=None: None)


def test_baixa_o_codex_oficial_conferido_e_o_deixa_executavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conteudo = _pacote(("codex-x86_64-unknown-linux-musl", b"#!/bin/sh\necho codex\n"))
    _com_pacote(monkeypatch, conteudo)
    pasta = tmp_path / "codex" / "0.0.1"
    assert an.garantir_codex(pasta, _servir(codex=conteudo, **{"codex-code-mode-host": AUXILIAR}))
    binario = pasta / "codex"
    assert binario.read_bytes().startswith(b"#!/bin/sh") and binario.stat().st_mode & 0o111
    # As ferramentas dos modelos novos rodam no auxiliar, ao lado do binário.
    auxiliar = pasta / "codex-code-mode-host"
    assert auxiliar.read_bytes().endswith(b"host\n") and auxiliar.stat().st_mode & 0o111
    assert list(pasta.parent.iterdir()) == [pasta]  # o pacote baixado não fica
    assert not an.garantir_codex(pasta, lambda url, timeout: _Resposta(b""))  # já tem


def test_instalacao_antiga_so_com_o_binario_ganha_o_auxiliar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A VPS de 16/10/2026: o Codex baixado sem o auxiliar, e nenhuma ferramenta funcionava."""
    _com_pacote(monkeypatch, b"")
    pasta = tmp_path / "codex" / "0.0.1"
    pasta.mkdir(parents=True)
    (pasta / "codex").write_text("antigo")
    monkeypatch.setattr(
        "zervis.cerebro.agentes_nativos.shutil.which", lambda nome, path=None: str(pasta / nome)
    )
    assert an.garantir_codex(pasta, _servir(**{"codex-code-mode-host": AUXILIAR}))
    assert (pasta / "codex").read_text() == "antigo"
    assert (pasta / "codex-code-mode-host").is_file()


def test_pacote_com_outra_coisa_que_nao_o_binario_e_recusado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conteudo = _pacote(("codex-a", b"1"), ("codex-b", b"2"))
    _com_pacote(monkeypatch, conteudo)
    with pytest.raises(PrepararErro, match="esperava um binário"):
        an.garantir_codex(tmp_path / "c" / "v", _servir(codex=conteudo))


def test_o_codex_da_maquina_tem_a_vez(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "zervis.cerebro.agentes_nativos.shutil.which", lambda nome, path=None: "/usr/bin/codex"
    )
    assert not an.garantir_codex(tmp_path, lambda url, timeout: pytest.fail("baixou"))


def test_os_agentes_que_faltam_entram_no_fim_do_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem claude nem codex na máquina, o painel e as sessões passam a achar os do Zé."""
    claude = tmp_path / "sdk" / "claude"
    codex = tmp_path / "codex" / "codex"
    for arquivo in (claude, codex):
        arquivo.parent.mkdir(parents=True)
        arquivo.write_text("#!/bin/sh\n")
        arquivo.chmod(0o755)
    monkeypatch.setattr(an, "claude_embutido", lambda: claude)
    monkeypatch.setattr(an, "codex_proprio", lambda: codex)
    ambiente = {"PATH": "/usr/bin:/bin"}
    assert an.no_path(ambiente) == [str(claude.parent), str(codex.parent)]
    assert (
        ambiente["PATH"] == f"/usr/bin:/bin:{claude.parent}:{codex.parent}"
    )  # os da máquina antes
    assert an.no_path(ambiente) == []  # de novo: nada repetido


def test_o_claude_code_vem_no_sdk() -> None:
    embutido = an.claude_embutido()
    assert embutido is not None and embutido.name == "claude"
