"""Fase 5: catálogo do Omarchy pelos cabeçalhos, política de risco e execução sem shell."""

import json
from pathlib import Path

import pytest

from jarvis.sistema.catalogo import buscar, carregar, classificar
from jarvis.sistema.politica import FERRAMENTA, Sistema, frase_confere


def _script(pasta: Path, nome: str, cabecalho: str, corpo: str = 'echo "ok $*"') -> None:
    arquivo = pasta / f"omarchy-{nome}"
    arquivo.write_text(f"#!/bin/bash\n{cabecalho}\n{corpo}\n")
    arquivo.chmod(0o755)


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    _script(
        tmp_path,
        "audio-output-volume",
        "# omarchy:summary=Adjust output volume\n# omarchy:args=<raise|lower|+N|-N>",
    )
    _script(tmp_path, "system-stats", "# omarchy:summary=Print CPU and memory stats")
    _script(tmp_path, "system-reboot", "# omarchy:summary=Reboot after closing windows")
    _script(tmp_path, "system-factory-reset", "# omarchy:summary=Reset everything")
    _script(tmp_path, "pkg-install", "# omarchy:summary=Install a package", "sudo pacman -S $1")
    _script(tmp_path, "font-set", "# omarchy:summary=Set the system font")
    _script(tmp_path, "interno", "# omarchy:summary=Internal\n# omarchy:hidden=true")
    _script(tmp_path, "sem-cabecalho", "# só um script")
    _script(
        tmp_path, "launch-browser", "# omarchy:summary=Launch the browser\n# omarchy:args=[url]"
    )
    return tmp_path


def test_catalogo_pelos_cabecalhos_com_risco(pasta: Path) -> None:
    acoes = carregar(pasta)
    assert set(acoes) == {
        "audio-output-volume", "system-stats", "system-reboot", "system-factory-reset",
        "pkg-install", "font-set", "launch-browser",
    }  # fmt: skip
    riscos = {n: a.risco for n, a in acoes.items()}
    assert riscos == {
        "audio-output-volume": 1,
        "system-stats": 0,
        "system-reboot": 3,
        "system-factory-reset": 4,
        "pkg-install": 4,  # usa sudo
        "font-set": 2,  # nenhuma regra: confirmação
        "launch-browser": 1,
    }
    assert classificar("update", False, {"update": 4}) == 4
    assert [a.nome for a in buscar(acoes, "volume")] == ["audio-output-volume"]
    assert "system-factory-reset" not in [a.nome for a in buscar(acoes, "reset")]


def test_politica_libera_leve_recusa_proibido_e_exige_frase(pasta: Path) -> None:
    s = Sistema(carregar(pasta))
    volume = {"acao": "audio-output-volume", "argumentos": ["+5"]}
    assert s.prechecar(FERRAMENTA, volume) is None and s.autoaprovar(FERRAMENTA, volume)
    assert "proibida" in str(s.prechecar(FERRAMENTA, {"acao": "system-factory-reset"}))
    assert "sudo" in str(s.prechecar(FERRAMENTA, {"acao": "pkg-install", "argumentos": ["vim"]}))
    assert "desconhecida" in str(s.prechecar(FERRAMENTA, {"acao": "rm"}))
    assert "inválidos" in str(
        s.prechecar(FERRAMENTA, {"acao": "audio-output-volume", "argumentos": ["$(rm -rf ~)"]})
    )
    fonte = {"acao": "font-set", "argumentos": ["JetBrains"]}
    assert not s.autoaprovar(FERRAMENTA, fonte) and s.frase_exata(FERRAMENTA, fonte) is None
    reboot = {"acao": "system-reboot"}
    assert s.frase_exata(FERRAMENTA, reboot) == "confirmo reiniciar"
    assert s.descrever(FERRAMENTA, reboot) == (
        "Isso vai reiniciar o computador. Para confirmar, diga: confirmo reiniciar."
    )
    assert s.prechecar("WebSearch", {}) is None and not s.autoaprovar("WebSearch", {})


def test_frase_exata() -> None:
    assert frase_confere("Confirmo reiniciar.", "confirmo reiniciar")
    assert frase_confere("pode, confirmo reiniciar sim", "confirmo reiniciar")
    assert not frase_confere("Sim, pode.", "confirmo reiniciar")
    assert not frase_confere("reiniciar, confirmo", "confirmo reiniciar")


def test_executa_sem_shell_e_recusa_proibido(pasta: Path) -> None:
    s = Sistema(carregar(pasta))
    feito = s.executar({"acao": "audio-output-volume", "argumentos": ["+5"]})
    assert feito["ok"] and feito["saida"] == "ok +5"
    with pytest.raises(ValueError, match="não permitida"):
        s.executar({"acao": "system-factory-reset"})


def test_cerebro_exige_a_frase_exata(tmp_path: Path) -> None:
    import asyncio

    from jarvis.cerebro.base import Resposta
    from jarvis.cerebro.claude import ClaudeBrain

    def frase(nome: str, entrada: dict[str, object]) -> str | None:
        return "confirmo reiniciar" if nome == FERRAMENTA else None

    async def rodar(fala: str) -> object:
        cerebro = ClaudeBrain("m", [], tmp_path, frase_exata=frase)

        async def aprovar(_: str) -> Resposta:
            return Resposta(True, fala)

        cerebro.aprovar = aprovar
        return await cerebro._pode_usar(FERRAMENTA, {"acao": "system-reboot"}, None)  # type: ignore[arg-type]

    assert type(asyncio.run(rodar("sim, pode"))).__name__ == "PermissionResultDeny"
    assert type(asyncio.run(rodar("confirmo reiniciar"))).__name__ == "PermissionResultAllow"


def test_eventos_do_hook_viram_avisos_so_os_novos(tmp_path: Path) -> None:
    from jarvis.sistema.vigia import Eventos

    arquivo = tmp_path / "eventos.jsonl"
    arquivo.write_text('{"evento":"post-update","arg":"","ts":1}\n')  # antigo: não é novidade
    eventos = Eventos(arquivo)
    assert eventos.novos() == []
    with arquivo.open("a") as f:
        f.write('{"evento":"battery-low","arg":"15","ts":2}\n')
        f.write('{"evento":"theme-set","arg":"tokyo-night","ts":3}\n')
        f.write("lixo\n")
    assert eventos.novos() == ["Bateria fraca: 15 por cento."]
    assert eventos.novos() == []


def test_hook_do_omarchy_anota_o_evento_pelo_nome_da_pasta(tmp_path: Path) -> None:
    import shutil
    import subprocess

    pasta = tmp_path / "hooks" / "battery-low.d"
    pasta.mkdir(parents=True)
    script = pasta / "zervis-evento"
    shutil.copy(Path(__file__).parents[1] / "deploy/omarchy-hooks/zervis-evento", script)
    estado = tmp_path / "estado"
    subprocess.run(  # noqa: S603 (o próprio hook do repositório)
        [str(script), "12; rm -rf /"],
        env={"XDG_STATE_HOME": str(estado), "HOME": str(tmp_path), "PATH": "/usr/bin"},
        check=True,
    )
    linha = (estado / "zervis" / "eventos-sistema.jsonl").read_text()
    dado = json.loads(linha)
    assert dado["evento"] == "battery-low" and dado["arg"] == "12 rm -rf "  # sem ; nem /


def test_vigia_avisa_processo_pesado_uma_vez() -> None:
    from jarvis.sistema.vigia import TICKS, Vigia

    ticks = {"t": 0}

    def ler() -> dict[int, tuple[str, int]]:
        ticks["t"] += 60 * TICKS  # 100% de um núcleo por minuto
        return {42: ("codex", ticks["t"]), 7: ("whisper-server", ticks["t"])}

    vigia = Vigia(ler)
    avisos = [vigia.amostrar(60.0 * i) for i in range(8)]
    assert sum(len(a) for a in avisos) == 1
    assert "codex" in next(a for a in avisos if a)[0]


def test_acoes_comuns_vao_resumidas_e_menu_e_leve(pasta: Path) -> None:
    from jarvis.sistema.catalogo import resumo_comuns

    _script(
        pasta, "menu", "# omarchy:summary=Control the Omarchy menu\n# omarchy:args=[summon] [route]"
    )
    acoes = carregar(pasta)
    assert acoes["menu"].risco == 1
    resumo = resumo_comuns(acoes)
    assert resumo.startswith("audio-output-volume <raise|lower|+N|-N>: Adjust output volume")
    assert "menu [summon] [route]" in resumo and "factory" not in resumo


def test_aviso_falado_vai_como_contexto_do_proximo_pedido() -> None:
    import time

    from jarvis.nucleo.laco import Nucleo

    falso = type("N", (), {})()
    falso.avisos_falados = [(time.monotonic(), "Tenho uma sugestão para você aprovar.")]
    texto = Nucleo._com_avisos(falso, "Pode aprovar")
    assert texto == (
        "(Você acabou de avisar o usuário, por voz: Tenho uma sugestão para você aprovar.) "
        "Pode aprovar"
    )
    assert Nucleo._com_avisos(falso, "oi") == "oi"
    falso.avisos_falados = [(time.monotonic() - 3600, "velho")]
    assert Nucleo._com_avisos(falso, "oi") == "oi"


def test_o_navegador_abre_um_endereco_mas_nada_alem_disso(pasta: Path) -> None:
    s = Sistema(carregar(pasta))

    def nav(*args: str) -> str | None:
        return s.prechecar(FERRAMENTA, {"acao": "launch-browser", "argumentos": list(args)})

    # A frase real de 08/10/2026: a pesquisa foi recusada e o navegador abriu vazio.
    assert nav("https://www.google.com/search?q=automação") is None
    assert nav("https://duckduckgo.com/?q=automacao+e+ia&ia=web") is None
    assert nav() is None
    for ruim in (
        "https://x.com/$(rm -rf ~)",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://x.com/a b",
        "https://x.com/`id`",
        "https://x.com/;ls",
    ):
        assert "inválidos" in str(nav(ruim)), ruim
    assert "inválidos" in str(nav("https://a.com", "https://b.com"))
    # Só as ações de navegador aceitam endereço com ? e &:
    assert "inválidos" in str(
        s.prechecar(FERRAMENTA, {"acao": "font-set", "argumentos": ["https://x.com/?a=1&b=2"]})
    )
