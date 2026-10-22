"""A senha de acesso de outro aparelho (roteiro, passo 4.1): a tela Entrar e o cookie."""

import http.client
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from zervis.portal.senha import (
    LEMBRAR_S,
    PASSO_S,
    SESSAO_S,
    Acesso,
    SenhaErro,
    codigo_totp,
    nome_do_aparelho,
)
from zervis.portal.servidor import Portal


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
    assert a.entrar("uma senha boa", origem="203.0.113.9")  # outro endereço continua entrando
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


def test_codigo_do_autenticador_segue_a_rfc_6238() -> None:
    # Vetor da RFC 6238 (SHA-1, semente "12345678901234567890", t = 59 s): 94287082 -> 287082.
    semente = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert codigo_totp(semente, 59 // PASSO_S) == "287082"


def test_com_codigo_ligado_a_senha_sozinha_nao_entra(tmp_path: Path) -> None:
    relogio = Relogio()
    avisos: list[str] = []
    a = Acesso(tmp_path / "p.json", tmp_path / "a.json", relogio, ao_entrar=avisos.append)
    a.definir("uma senha boa")
    endereco = a.preparar_codigo("Ana")
    assert endereco.startswith("otpauth://totp/Z%C3%A9rvis%3AAna?secret=")
    semente = a.semente_pendente
    with pytest.raises(SenhaErro, match="incorreto"):
        a.confirmar_codigo("000000")
    a.confirmar_codigo(codigo_totp(semente, int(relogio.t // PASSO_S)))
    assert a.tem_codigo and "totp" in json.loads((tmp_path / "p.json").read_text())
    with pytest.raises(SenhaErro, match="Senha ou código"):
        a.entrar("uma senha boa", "", lembrar=True)
    relogio.t += PASSO_S
    certo = codigo_totp(semente, int(relogio.t // PASSO_S))
    agente = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/155.0 Mobile Safari"
    assert a.entrar("uma senha boa", certo, lembrar=True, aparelho=agente, origem="198.51.100.4")
    assert avisos == ["Android · Chrome"]
    with pytest.raises(SenhaErro, match="Senha ou código"):
        a.entrar("uma senha boa", certo, lembrar=True)  # o mesmo código não vale duas vezes
    a.definir("outra senha boa")
    assert a.tem_codigo  # trocar a senha não desliga o código
    a.desligar_codigo()
    assert not a.tem_codigo


def test_lista_de_aparelhos_e_desconectar_um(tmp_path: Path) -> None:
    relogio = Relogio()
    a = _acesso(tmp_path, relogio)
    a.definir("uma senha boa")
    primeiro, _ = a.entrar("uma senha boa", aparelho="iPhone Safari/605", origem="1.2.3.4")
    relogio.t += 10
    segundo, _ = a.entrar("uma senha boa", aparelho="X11; Linux Firefox/130")
    lista = a.lista()
    assert [x["aparelho"] for x in lista] == ["Linux · Firefox", "iPhone · Safari"]
    assert lista[1]["origem"] == "1.2.3.4" and primeiro not in json.dumps(lista)
    a.desconectar_por_id(lista[1]["id"])
    assert not a.valido(primeiro) and a.valido(segundo)
    with pytest.raises(SenhaErro):
        a.desconectar_por_id("curto")
    assert nome_do_aparelho("algo estranho") == "Aparelho"


def test_ajuste_de_acesso_so_pelo_proprio_pc(tmp_path: Path) -> None:
    a = _acesso(tmp_path)
    a.definir("uma senha boa")
    trocas: list[str] = []

    def trocar(dados: dict[str, Any]) -> dict[str, Any]:
        trocas.append("x")
        return {}

    p = Portal(
        {},
        {"acesso/senha": trocar},
        porta=0,
        acesso=a,
        so_no_pc={"acesso/senha"},
    )
    p.permitir("pc.rede.ts.net")
    p.iniciar()
    try:
        codigo, _ = a.entrar("uma senha boa")
        token = {"X-Ze-Token": p.token, "Content-Type": "application/json"}
        remoto = _pedir(
            p,
            "POST",
            "/api/acesso/senha",
            "pc.rede.ts.net",
            cab={**token, "Cookie": f"ze_acesso={codigo}"},
        )
        assert remoto[0] == 403 and trocas == []
        local = _pedir(p, "POST", "/api/acesso/senha", f"127.0.0.1:{p.porta}", cab=token)
        assert local[0] == 200 and trocas == ["x"]
    finally:
        p.parar()


def test_convite_cria_a_senha_uma_vez_so_e_vence(tmp_path: Path) -> None:
    """Primeiro acesso num servidor: não há o próprio PC para definir a senha."""
    relogio = Relogio()
    a = _acesso(tmp_path, relogio)
    convite = a.criar_convite()
    assert len(convite) == 9 and convite[4] == "-" and a.convite_valido
    assert convite not in (tmp_path / "painel.json").read_text()  # só o resumo
    with pytest.raises(SenhaErro, match="inválido"):
        a.criar_acesso("AAAA-AAAA", "uma senha boa", origem="1.2.3.4")
    with pytest.raises(SenhaErro, match="8 caracteres"):
        a.criar_acesso(convite, "curta")
    codigo, _ = a.criar_acesso(convite.lower().replace("-", " "), "uma senha boa")
    assert a.tem_senha and a.valido(codigo) and not a.confiavel(codigo)  # sem o código, ainda
    assert not a.convite_valido
    with pytest.raises(SenhaErro, match="inválido"):
        a.criar_acesso(convite, "outra senha boa")  # usado: não vale de novo
    with pytest.raises(SenhaErro, match="já foi criado"):
        a.criar_convite()
    b = _acesso(tmp_path / "b", relogio)
    vencido = b.criar_convite()
    relogio.t += 3601
    with pytest.raises(SenhaErro, match="vencido"):
        b.criar_acesso(vencido, "uma senha boa")


def test_entrar_com_o_codigo_do_autenticador_marca_o_aparelho_como_confiavel(
    tmp_path: Path,
) -> None:
    relogio = Relogio()
    a = _acesso(tmp_path, relogio)
    a.definir("uma senha boa")
    so_senha, _ = a.entrar("uma senha boa")
    assert a.valido(so_senha) and not a.confiavel(so_senha)
    a.preparar_codigo()
    semente = a.semente_pendente
    a.confirmar_codigo(codigo_totp(semente, int(relogio.t // PASSO_S)))
    relogio.t += PASSO_S
    com_codigo, _ = a.entrar("uma senha boa", codigo_totp(semente, int(relogio.t // PASSO_S)))
    assert a.confiavel(com_codigo)


@pytest.fixture
def servidor(tmp_path: Path) -> Any:
    """Um Zé num servidor: o túnel repassa todos os pedidos, nenhum é do próprio PC."""
    a = _acesso(tmp_path)
    feitos: list[str] = []

    def fazer(nome: str) -> Any:
        def escrita(dados: dict[str, Any]) -> dict[str, Any]:
            feitos.append(nome)
            return {}

        return escrita

    rotas = ("acesso/senha", "acesso/codigo/preparar", "acesso/codigo/desligar", "ze/sessao")
    p = Portal(
        {"estado": lambda: {}},
        {r: fazer(r) for r in rotas},
        porta=0,
        acesso=a,
        so_no_pc=set(rotas),
        servidor=True,
    )
    p.permitir("ze.trycloudflare.com")
    p.iniciar()
    yield p, a, feitos
    p.parar()


def test_primeiro_acesso_pelo_convite_e_ajustes_de_fora_num_servidor(servidor: Any) -> None:
    p, a, feitos = servidor
    host, fora = "ze.trycloudflare.com", {"Cf-Connecting-Ip": "203.0.113.7"}
    convite = a.criar_convite()
    tela = _pedir(p, "GET", "/entrar", host, cab=fora)[2].decode()
    assert "Primeiro acesso" in tela and 'name="convite"' in tela
    status, cab, _ = _pedir(
        p, "POST", "/entrar", host, f"convite={convite}&senha=uma+senha+boa", cab=fora
    )
    assert status == 303 and cab["Location"] == "/#voz"
    cookie = {"Cookie": cab["Set-Cookie"].split(";", 1)[0], **fora}
    pagina = _pedir(p, "GET", "/", host, cab=cookie)[2].decode()
    assert 'name="ze-ajustes" content="0"' in pagina  # ainda sem o código do autenticador
    api = {"X-Ze-Token": p.token, "Content-Type": "application/json", **cookie}

    def pedir(rota: str) -> int:
        return _pedir(p, "POST", f"/api/{rota}", host, cab=api)[0]

    # Só com a senha: pode ligar o código (só aumenta a proteção), mais nada.
    assert pedir("acesso/codigo/preparar") == 200
    assert pedir("acesso/senha") == 403 and pedir("ze/sessao") == 403
    # Com o código ligado e a entrada com ele, os ajustes valem de fora...
    a.preparar_codigo()
    semente = a.semente_pendente
    a.confirmar_codigo(codigo_totp(semente, int(a.agora() // PASSO_S)))
    a.agora = lambda: 1000.0 + PASSO_S
    certo = codigo_totp(semente, int(a.agora() // PASSO_S))
    status, cab, _ = _pedir(
        p, "POST", "/entrar", host, f"senha=uma+senha+boa&codigo={certo}", cab=fora
    )
    api["Cookie"] = cab["Set-Cookie"].split(";", 1)[0]
    pagina = _pedir(p, "GET", "/", host, cab={"Cookie": api["Cookie"], **fora})[2].decode()
    assert 'name="ze-ajustes" content="1"' in pagina
    assert pedir("acesso/senha") == 200 and pedir("ze/sessao") == 200
    # ...menos desligar a proteção pela qual se entrou.
    assert pedir("acesso/codigo/desligar") == 403
    assert feitos == ["acesso/codigo/preparar", "acesso/senha", "ze/sessao"]


def test_num_computador_os_ajustes_continuam_so_no_proprio_pc(tmp_path: Path) -> None:
    a = _acesso(tmp_path)
    a.definir("uma senha boa")
    p = Portal({}, {"ze/sessao": lambda d: {}}, porta=0, acesso=a, so_no_pc={"ze/sessao"})
    p.permitir("ze.trycloudflare.com")
    p.iniciar()
    try:
        relogio = Relogio()
        a.agora = relogio
        a.preparar_codigo()
        a.confirmar_codigo(codigo_totp(a.semente_pendente, int(relogio.t // PASSO_S)))
        semente = json.loads((tmp_path / "painel.json").read_text())["totp"]
        relogio.t += PASSO_S
        codigo, _ = a.entrar("uma senha boa", codigo_totp(semente, int(relogio.t // PASSO_S)))
        cab = {
            "X-Ze-Token": p.token,
            "Content-Type": "application/json",
            "Cookie": f"ze_acesso={codigo}",
            "Cf-Connecting-Ip": "203.0.113.7",
        }
        assert _pedir(p, "POST", "/api/ze/sessao", "ze.trycloudflare.com", cab=cab)[0] == 403
    finally:
        p.parar()
