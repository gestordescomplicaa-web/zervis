"""O PATH completado na subida do serviço (o Codex "não instalado" depois do boot)."""

from pathlib import Path

from jarvis import caminhos


def test_completa_com_shell_e_pastas_sem_repetir(tmp_path: Path) -> None:
    pessoal, do_shell, inexistente = tmp_path / "local-bin", tmp_path / "mise", tmp_path / "nada"
    pessoal.mkdir()
    do_shell.mkdir()
    ambiente = {"PATH": "/usr/local/bin:/usr/bin"}
    novas = caminhos.completar(
        ambiente, do_login=[str(do_shell), "/usr/bin"], pastas=(str(pessoal), str(inexistente))
    )
    assert novas == [str(do_shell), str(pessoal)]
    assert ambiente["PATH"] == f"/usr/local/bin:/usr/bin:{do_shell}:{pessoal}"
    assert caminhos.completar(ambiente, do_login=[], pastas=(str(pessoal),)) == []


def test_le_o_path_do_shell_de_login(tmp_path: Path) -> None:
    shell = tmp_path / "meu-shell"
    shell.write_text('#!/bin/sh\necho "mensagem de boas-vindas"\nprintf "/a:/b"\n')
    shell.chmod(0o755)
    assert caminhos.do_shell(str(shell)) == ["/a", "/b"]
    assert caminhos.do_shell(str(tmp_path / "nao-existe")) == []
