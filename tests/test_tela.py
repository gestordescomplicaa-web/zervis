"""O JARVIS na própria tela: comando pela pasta, resposta da página, janela trazida."""

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from jarvis.rosto import tela


def batimento(pasta: Path) -> None:
    """A página publica o estado a cada 5 s: é o que diz que o Núcleo está aberto."""
    (pasta / "tela-estado.json").write_text(json.dumps({"estado": {}, "ts": time.time()}))


def pagina_falsa(pasta: Path, estado: dict[str, Any], vezes: int = 1) -> threading.Thread:
    """Faz o papel do jarvis-controle.js: lê o comando e responde com o mesmo id."""

    def responder() -> None:
        vistos: set[str] = set()
        fim = time.monotonic() + 5
        while time.monotonic() < fim and len(vistos) < vezes:
            try:
                cmd = json.loads((pasta / "tela-comando.json").read_text())
            except (OSError, ValueError):
                time.sleep(0.02)
                continue
            if cmd["id"] in vistos:
                time.sleep(0.02)
                continue
            vistos.add(cmd["id"])
            resultados = [{"acao": a["acao"], "ok": True} for a in cmd["acoes"]]
            (pasta / "tela-estado.json").write_text(
                json.dumps(
                    {
                        "resposta": cmd["id"],
                        "resultados": resultados,
                        "estado": estado,
                        "ts": time.time(),
                    }
                )
            )

    t = threading.Thread(target=responder, daemon=True)
    t.start()
    return t


def test_agir_escreve_o_comando_e_devolve_a_resposta_da_pagina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trazidas: list[int] = []
    t = tela.Tela(tmp_path)
    monkeypatch.setattr(t, "trazer", lambda: trazidas.append(1))
    batimento(tmp_path)
    pagina_falsa(tmp_path, {"cerebro": {"aberto": True, "modo": "brain"}})
    acoes: list[dict[str, Any]] = [
        {"acao": "abrir_mapa"},
        {"acao": "aguardar", "valor": 200},
        {"acao": "focar", "alvo": "projetos"},
    ]
    resposta = t.agir(acoes)
    assert resposta["estado"]["cerebro"]["aberto"] is True
    assert [r["acao"] for r in resposta["resultados"]] == ["abrir_mapa", "aguardar", "focar"]
    assert trazidas == [1]  # a janela vem para a frente antes de mostrar
    comando = json.loads((tmp_path / "tela-comando.json").read_text())
    assert comando["acoes"] == acoes and comando["id"] == resposta["resposta"]


def test_acao_desconhecida_nem_chega_na_tela(tmp_path: Path) -> None:
    with pytest.raises(tela.TelaErro, match="desconhecida"):
        tela.Tela(tmp_path).agir([{"acao": "apagar_tudo"}])
    assert not (tmp_path / "tela-comando.json").exists()


def test_janela_fechada_vira_erro_claro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = tela.Tela(tmp_path)
    monkeypatch.setattr(t, "trazer", lambda: None)
    batimento(tmp_path)
    with pytest.raises(tela.TelaErro, match="não respondeu"):
        t.agir([{"acao": "enquadrar"}], espera_s=0.3)


def test_janela_fechada_e_detectada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = tela.Tela(tmp_path)
    monkeypatch.setattr(t, "trazer", lambda: pytest.fail("fechado: não traz nada"))
    assert t.resumo() == "Janela do JARVIS: fechada (não há Núcleo na tela)."
    with pytest.raises(tela.TelaErro, match="janela do JARVIS está fechada"):
        t.agir([{"acao": "abrir_mapa"}])
    with pytest.raises(tela.TelaErro, match="janela do JARVIS está fechada"):
        t.ver()


def test_resumo_diz_onde_esta_e_o_que_mostra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = tela.Tela(tmp_path)
    estado = {
        "nucleo": {
            "aberto": True,
            "orbes": ["Mapa", "Guia", "Identidade", "Acervo", "Orca"],
            "orbes_abertos": ["Mapa", "Guia"],
            "notas_abertas": ["Comece aqui"],
        },
        "cerebro": {"aberto": True, "modo": "focus", "foco": {"nome": "Projeto Alfa"}},
        "menu_configuracoes": {"aberto": False},
        "maos_em_uso": True,
    }
    (tmp_path / "tela-estado.json").write_text(json.dumps({"estado": estado, "ts": time.time()}))
    monkeypatch.setattr(t, "em_foco", lambda: True)
    assert t.resumo() == (
        "Janela do JARVIS: aberta, é a janela ativa; "
        "Núcleo aberto (orbes Mapa, Guia, Identidade, Acervo, Orca); "
        "abertos: Mapa, Guia, nota Comece aqui; Mapa na vista foco, mostrando Projeto Alfa; "
        "o usuário está usando as mãos agora."
    )


def test_em_foco_le_a_janela_ativa_do_hyprland(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ativa = {"class": "chrome-127.0.0.1__stage.html-Default"}
    monkeypatch.setattr(tela, "_hyprctl", lambda *a: json.dumps(ativa))
    assert tela.Tela(tmp_path).em_foco()
    ativa = {"class": "chromium"}
    assert not tela.Tela(tmp_path).em_foco()


def test_passeio_volta_quando_a_pagina_confirma_o_inicio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = tela.Tela(tmp_path)
    monkeypatch.setattr(t, "trazer", lambda: None)
    (tmp_path / "tela-estado.json").write_text(json.dumps({"estado": {}, "ts": time.time()}))

    def so_confirma() -> None:
        fim = time.monotonic() + 3
        while time.monotonic() < fim:
            try:
                cmd = json.loads((tmp_path / "tela-comando.json").read_text())
            except (OSError, ValueError):
                time.sleep(0.02)
                continue
            (tmp_path / "tela-estado.json").write_text(
                json.dumps({"recebido": cmd["id"], "estado": {}, "ts": time.time()})
            )
            return

    threading.Thread(target=so_confirma, daemon=True).start()
    inicio = time.monotonic()
    r = t.agir(
        [{"acao": "abrir_mapa"}, {"acao": "aguardar", "valor": 5000}, {"acao": "fechar_mapa"}]
    )
    assert r["resultados"] == "em andamento na tela" and time.monotonic() - inicio < 2


def test_ver_le_o_estado_publicado_sem_mexer_na_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = tela.Tela(tmp_path)
    monkeypatch.setattr(t, "trazer", lambda: pytest.fail("ver não deve mexer na janela"))
    monkeypatch.setattr(t, "em_foco", lambda: False)
    (tmp_path / "tela-estado.json").write_text(
        json.dumps({"estado": {"tema": "roxo"}, "ts": time.time()})
    )
    assert t.ver() == {"tema": "roxo", "em_foco": False}


def test_trazer_usa_o_hyprctl_com_comando_fixo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[list[str]] = []

    def rodar(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", rodar)
    tela.Tela(tmp_path).trazer()
    tela.Tela(tmp_path).fechar()
    assert chamadas == [
        ["/usr/bin/hyprctl", "dispatch", "focuswindow", tela.JANELA],
        ["/usr/bin/systemctl", "--user", "stop", "barehands-window.service"],
    ]
