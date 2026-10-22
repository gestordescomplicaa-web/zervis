"""Acesso pelo celular (plano da voz remota, etapa 2): o Tailscale lido e o `serve` ligado."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from zervis.portal import remoto
from zervis.portal.servidor import Portal

STATUS = {
    "BackendState": "Running",
    "Self": {"DNSName": "omarchy.tail1234.ts.net.", "TailscaleIPs": ["100.64.0.7", "fd7a::7"]},
}
SERVE = {
    "Web": {"omarchy.tail1234.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8796"}}}}
}


def _falso(respostas: dict[str, Any], chamadas: list[list[str]], codigo: int = 0) -> Any:
    def rodar(*args: str, espera_s: float = 10.0) -> subprocess.CompletedProcess[str]:
        chamadas.append(list(args))
        chave = " ".join(a for a in args if a != "--json")
        saida = respostas.get(chave, "")
        texto = saida if isinstance(saida, str) else json.dumps(saida)
        return subprocess.CompletedProcess(["tailscale", *args], codigo, texto, texto)

    return rodar


def test_sem_tailscale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zervis.portal.remoto.shutil.which", lambda nome: None)
    assert remoto.rede(8796) == remoto.Rede()


def test_le_nome_ip_e_se_o_painel_esta_publicado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zervis.portal.remoto.shutil.which", lambda nome: "/usr/bin/tailscale")
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        remoto, "_tailscale", _falso({"status": STATUS, "serve status": SERVE}, chamadas)
    )
    r = remoto.rede(8796)
    assert (r.nome, r.ip, r.ativo) == ("omarchy.tail1234.ts.net", "100.64.0.7", True)
    assert r.para_tela()["endereco"] == "https://omarchy.tail1234.ts.net"
    assert not remoto.rede(9999).ativo  # publicado para outra porta: não é este painel


def test_tailscale_parado_e_instalado_mas_desconectado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zervis.portal.remoto.shutil.which", lambda nome: "/usr/bin/tailscale")
    parado = {"status": {"BackendState": "NeedsLogin", "Self": {}}}
    monkeypatch.setattr(remoto, "_tailscale", _falso(parado, []))
    assert remoto.rede(8796) == remoto.Rede(instalado=True)


def test_ativar_publica_painel_e_voz_e_explica_a_recusa(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(remoto, "_tailscale", _falso({}, chamadas))
    remoto.ativar(8796, 7880)
    assert chamadas == [
        ["serve", "--bg", "--https=443", "http://127.0.0.1:8796"],
        ["serve", "--bg", "--https=8443", "http://127.0.0.1:7880"],
    ]
    recusa = {"serve --bg --https=443 http://127.0.0.1:8796": "HTTPS is not enabled for tailnet"}
    monkeypatch.setattr(remoto, "_tailscale", _falso(recusa, [], codigo=1))
    with pytest.raises(remoto.RemotoErro, match="certificados HTTPS"):
        remoto.ativar(8796, 7880)


def test_painel_aceita_o_nome_da_rede_so_quando_permitido() -> None:
    p = Portal({}, {}, porta=0)
    try:
        assert "omarchy.tail1234.ts.net" not in p.hosts
        p.permitir("omarchy.tail1234.ts.net")
        assert {"omarchy.tail1234.ts.net", "omarchy.tail1234.ts.net:443"} <= p.hosts
        p.proibir("omarchy.tail1234.ts.net")
        assert "omarchy.tail1234.ts.net" not in p.hosts
    finally:
        p.http.server_close()


def test_firewall_que_barra_o_audio_mostra_o_comando(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zervis.portal.remoto.shutil.which", lambda nome: "/usr/bin/ufw")
    regras = tmp_path / "user.rules"
    assert remoto.firewall(regras=regras) == ""  # sem ufw configurado
    regras.write_text(
        "### tuple ### allow udp 53317\n-A ufw-user-input -p udp --dport 53317 -j ACCEPT\n"
    )
    assert "port 7882 proto udp" in remoto.firewall(regras=regras)
    regras.write_text(
        regras.read_text() + "-A ufw-user-input -i tailscale0 -p udp --dport 7882 -j ACCEPT\n"
    )
    assert remoto.firewall(regras=regras) == ""
    casa = remoto.firewall("192.168.0.0/24", regras)
    assert casa.startswith("sudo ufw allow from 192.168.0.0/24 to any port 7882")
    regras.write_text(
        regras.read_text() + "-A ufw-user-input -p udp --dport 7882 -s 192.168.0.0/24 -j ACCEPT\n"
    )
    assert remoto.firewall("192.168.0.0/24", regras) == ""


def test_rede_de_casa_ignora_vpn_e_conteineres() -> None:
    saida = (
        "2: eno1    inet 192.168.0.6/24 brd 192.168.0.255 scope global eno1\n"
        "3: tailscale0    inet 100.119.75.47/32 scope global tailscale0\n"
        "4: docker0    inet 172.17.0.1/16 scope global docker0\n"
    )
    assert remoto.rede_local(saida) == ("192.168.0.6", "192.168.0.0/24")
    assert remoto.rede_local("3: tailscale0    inet 100.119.75.47/32 scope global x\n") is None
