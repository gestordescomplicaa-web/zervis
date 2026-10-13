"""A senha de acesso de outro aparelho (roteiro, passo 4.1): a tela Entrar e o cookie."""

import http.client
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from jarvis.portal.senha import LEMBRAR_S, SESSAO_S, Acesso, SenhaErro
from jarvis.portal.servidor import Portal


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _acesso(tmp_path: Path, relogio: Relogio | None = None) -> Acesso:
    return Acesso(tmp_path / "painel.json", tmp_path / "acessos.json", relogio or Relogio())


def test_senha_guardada_so_como_resumo(tmp_path: Path) -> None:
    a = _acesso(tmp_path)
    assert not a.tem_senha
    with pytest.raises(SenhaErro, match="8 caracteres"):
        a.definir("curta")
    a.definir("uma senha boa")
    texto = (tmp_path / "painel.json").read_text()
    assert "uma senha boa" not in texto and json.loads(texto)["hash"]
    assert stat.S_IMODE((tmp_path / "painel.json").stat().st_mode) == 0o600


def test_aparelho_lembrado_vale_30_dias_e_sem_lembrar_12_horas(tmp_path: Path) -> None:
    relogio = Relogio()
    a = _acesso(tmp_path, relogio)
    a.definir("uma senha boa")
    lembrado, validade = a.entrar("uma senha boa", lembrar=True)
    curto, validade_curta = a.entrar("uma senha boa", lembrar=False)
    assert (validade, validade_curta) == (LEMBRAR_S, SESSAO_S)
    assert a.valido(lembrado) and a.valido(curto) and a.aparelhos() == 2
    assert lembrado not in (tmp_path / "acessos.json").read_text()  # só o resumo
    relogio.t += SESSAO_S + 1
    assert a.valido(lembrado) and not a.valido(curto)
    a.sair(lembrado)
    assert not a.valido(lembrado)


def test_trocar_a_senha_encerra_os_acessos(tmp_path: Path) -> None:
    a = _acesso(tmp_path)
    a.definir("uma senha boa")
    codigo, _ = a.entrar("uma senha boa", lembrar=True)
    a.definir("outra senha boa")
    assert not a.valido(codigo)


def test_cinco_erros_bloqueiam_por_quinze_minutos(tmp_path: Path) -> None:
    relogio = Relogio()
    a = _acesso(tmp_path, relogio)
    a.definir("uma senha boa")
    for _ in range(5):
        with pytest.raises(SenhaErro, match="incorreta"):
            a.entrar("chute", lembrar=False)
    with pytest.raises(SenhaErro, match="Muitas tentativas"):
        a.entrar("uma senha boa", lembrar=False)  # nem a certa entra durante o bloqueio
    relogio.t += 15 * 60 + 1
    assert a.entrar("uma senha boa", lembrar=False)


def test_sem_senha_definida_ninguem_entra(tmp_path: Path) -> None:
    a = _acesso(tmp_path)
    with pytest.raises(SenhaErro, match="Defina a senha"):
        a.entrar("qualquer coisa", lembrar=True)
    assert not a.valido("qualquer")


def _pedir(
    p: Portal,
    metodo: str,
    caminho: str,
    host: str,
    corpo: str = "",
    cab: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", p.porta, timeout=5)
    cabecalhos = {"Host": host, **(cab or {})}
    if corpo:
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(metodo, caminho, body=corpo.encode() or None, headers=cabecalhos)
    r = conn.getresponse()
    resposta = (r.status, dict(r.getheaders()), r.read())
    conn.close()
    return resposta


@pytest.fixture
def portal(tmp_path: Path) -> Any:
    a = _acesso(tmp_path)
    a.definir("uma senha boa")
    p = Portal({"estado": lambda: {"ze": "ativo"}}, {}, porta=0, acesso=a)
    p.permitir("pc.rede.ts.net")
    p.iniciar()
    yield p
    p.parar()


def test_proprio_pc_entra_direto_e_outro_aparelho_passa_pela_senha(portal: Portal) -> None:
    local = f"127.0.0.1:{portal.porta}"
    assert _pedir(portal, "GET", "/", local)[0] == 200
    remoto = "pc.rede.ts.net"
    status, cab, _ = _pedir(portal, "GET", "/", remoto)
    assert status == 303 and cab["Location"] == "/entrar"
    assert _pedir(portal, "GET", "/entrar", remoto)[0] == 200
    assert _pedir(portal, "GET", "/painel.css", remoto)[0] == 200  # a tela Entrar usa
    token = {"X-Ze-Token": portal.token}
    assert _pedir(portal, "GET", "/api/estado", remoto, cab=token)[0] == 401
    status, _, corpo = _pedir(portal, "POST", "/entrar", remoto, "senha=chute&lembrar=1")
    assert status == 200 and "Senha incorreta." in corpo.decode()
    status, cab, _ = _pedir(portal, "POST", "/entrar", remoto, "senha=uma+senha+boa&lembrar=1")
    assert status == 303 and "HttpOnly" in cab["Set-Cookie"] and "Secure" in cab["Set-Cookie"]
    cookie = cab["Set-Cookie"].split(";", 1)[0]
    assert _pedir(portal, "GET", "/", remoto, cab={"Cookie": cookie})[0] == 200
    estado = _pedir(portal, "GET", "/api/estado", remoto, cab={**token, "Cookie": cookie})
    assert estado[0] == 200
    status, _, _ = _pedir(portal, "POST", "/sair", remoto, cab={"Cookie": cookie})
    assert status == 303
    assert _pedir(portal, "GET", "/", remoto, cab={"Cookie": cookie})[0] == 303


def test_nome_nao_permitido_continua_barrado(portal: Portal) -> None:
    assert _pedir(portal, "GET", "/entrar", "malicioso.com")[0] == 403


def test_pedido_repassado_por_tunel_nunca_vale_como_o_proprio_pc(portal: Portal) -> None:
    local = f"127.0.0.1:{portal.porta}"
    for cabecalho in ("Cf-Connecting-Ip", "X-Forwarded-For"):
        status, cab, _ = _pedir(portal, "GET", "/", local, cab={cabecalho: "203.0.113.9"})
        assert status == 303 and cab["Location"] == "/entrar"
