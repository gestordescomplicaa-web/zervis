"""O painel do Zé: só local, com token, e a chave colada nunca volta para a tela."""

import base64
import http.client
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import config, usuario
from zervis.cerebro import acesso, rapido
from zervis.oficina.progresso import ETAPAS, Progresso
from zervis.oficina.sessoes import Sessoes
from zervis.oficina.terminal import Terminal
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido, Portal
from zervis.voz import deepgram


def pedir(
    portal: Portal,
    metodo: str,
    caminho: str,
    corpo: dict[str, Any] | None = None,
    cracha: str | None = "certo",
    host: str | None = None,
) -> tuple[int, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
    cab = {"Host": host or f"127.0.0.1:{portal.porta}"}
    if cracha is not None:
        cab["X-Ze-Token"] = portal.token if cracha == "certo" else cracha
    dados = json.dumps(corpo).encode() if corpo is not None else None
    if dados is not None:
        cab["Content-Type"] = "application/json"
    conn.request(metodo, caminho, body=dados, headers=cab)
    resp = conn.getresponse()
    bruto = resp.read()
    conn.close()
    try:
        return resp.status, json.loads(bruto)
    except ValueError:
        return resp.status, bruto.decode()


@pytest.fixture
def portal() -> Any:
    def recusar(dados: dict[str, Any]) -> Any:
        raise PedidoInvalido("modelo vazio")

    p = Portal(
        {"estado": lambda: {"ze": "ativo"}},
        {"eco": lambda dados: {"recebi": dados}, "recusa": recusar},
        porta=0,
        envios={"anexo": lambda corpo, consulta: {"bytes": len(corpo), **consulta}},
    )
    p.iniciar()
    yield p
    p.parar()


def test_a_pagina_traz_o_token_e_a_api_exige_o_token(portal: Portal) -> None:
    status, pagina = pedir(portal, "GET", "/", cracha=None)
    assert status == 200 and portal.token in pagina and "__TOKEN__" not in pagina
    assert pedir(portal, "GET", "/painel.js", cracha=None)[0] == 200
    assert pedir(portal, "GET", "/api/estado") == (200, {"ze": "ativo"})
    assert pedir(portal, "GET", "/api/estado", cracha=None)[0] == 403
    assert pedir(portal, "GET", "/api/estado", cracha="outro")[0] == 403
    assert pedir(portal, "POST", "/api/eco", {"a": 1}) == (200, {"recebi": {"a": 1}})
    assert pedir(portal, "POST", "/api/eco", {"a": 1}, cracha=None)[0] == 403
    assert pedir(portal, "GET", "/api/nada")[0] == 404
    assert pedir(portal, "POST", "/api/recusa", {}) == (400, {"erro": "modelo vazio"})


def test_outro_host_e_recusado_mesmo_com_token(portal: Portal) -> None:
    """DNS rebinding: um site de fora apontando para 127.0.0.1 chega com outro Host."""
    assert pedir(portal, "GET", "/", host="malicioso.com")[0] == 403
    assert pedir(portal, "GET", "/api/estado", host="malicioso.com")[0] == 403


def test_terminal_novo_reinicia_cursor_da_leitura(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,))
    s = sessoes.criar("Teste", str(tmp_path))
    terminal = Terminal(["cat"], tmp_path, {})
    sessoes.terminais[s.id] = terminal
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path, tmp_path)
    try:
        terminal.escrever(b"retomada\n")
        terminal.ler(0, 2)
        resposta = acoes.ler_terminal(
            {"id": s.id, "desde": 99999, "geracao": terminal.pid + 1, "espera": 0}
        )
        assert resposta["reiniciado"] and resposta["geracao"] == terminal.pid
        assert b"retomada" in base64.b64decode(resposta["dados"])
    finally:
        terminal.encerrar()


def test_continuar_por_alerta_antigo_nao_troca_nem_reenvia(tmp_path: Path) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *args: None)
    s = sessoes.criar("Teste", str(tmp_path))
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path, tmp_path)
    with pytest.raises(PedidoInvalido, match="Não há limite confirmado"):
        acoes.trocar_sessao({"id": s.id, "motor": "codex", "continuar": True})
    assert sessoes.ler(s.id).motor == "claude" and not sessoes.tarefas


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_painel_exclui_sessao_com_agente_ativo_e_preserva_projeto(tmp_path: Path) -> None:
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    arquivo = projeto / "trabalho.txt"
    arquivo.write_text("manter")
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,))
    s = sessoes.criar("ativa", str(projeto))
    t = Terminal(["sleep", "30"], projeto, {})
    sessoes.terminais[s.id] = t
    sessoes._mudar(s.id, estado="trabalhando")
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path / "latencias", tmp_path / "teste")
    p = Portal({"sessoes": acoes.sessoes}, {"sessao/excluir": acoes.excluir_sessao}, porta=0)
    p.iniciar()
    try:
        assert pedir(p, "GET", "/api/sessoes")[1][0]["estado"] == "trabalhando"
        assert pedir(p, "POST", "/api/sessao/excluir", {"id": s.id}) == (
            200,
            {"aviso": "", "sessoes": []},
        )
        assert not t.vivo and not t.leitor.is_alive()
        assert not (sessoes.pasta / s.id).exists()
        assert arquivo.read_text() == "manter"
    finally:
        p.parar()
        t.encerrar()


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
@pytest.mark.parametrize("origem", ["painel", "manutencao"])
@pytest.mark.parametrize("resultado", ["falhou", "pronto", "voltou"])
def test_atualizacao_bloqueia_comandos_mas_preserva_leitura_e_libera_no_fim(
    tmp_path: Path, origem: str, resultado: str
) -> None:
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,))
    s = sessoes.criar("Sessão", str(tmp_path), origem=origem)
    outro_projeto = tmp_path / "outro-projeto"
    outro_projeto.mkdir()
    fechada = sessoes.criar("Fechada", str(outro_projeto), origem=origem)
    progresso = Progresso(tmp_path / "atualizacao")
    sessoes.reservada = progresso.reserva
    terminal = Terminal(["cat"], tmp_path, {})
    sessoes.terminais[s.id] = terminal
    sessoes._mudar(s.id, interrompida="pedido preservado")
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path, tmp_path)
    p = Portal(
        {},
        {
            "sessao/ler": acoes.ler_sessao,
            "sessao/interrompida": acoes.tarefa_interrompida,
            "terminal/abrir": acoes.abrir_terminal,
            "terminal/ler": acoes.ler_terminal,
            "terminal/escrever": acoes.escrever_terminal,
        },
        porta=0,
    )
    p.iniciar()
    try:
        terminal.escrever(b"historia preservada\n")
        terminal.ler(0, 2)
        progresso.aguardar()
        estados = ["aguardando", *(e[0] for e in ETAPAS)]
        for estado in estados:
            if estado != "aguardando":
                if estado == "testes_copia":
                    progresso.comecar()
                progresso.etapa(estado)
            status, resposta = pedir(
                p, "POST", "/api/sessao/interrompida", {"id": s.id, "continuar": True}
            )
            assert status == 400 and "Atualização em andamento" in resposta["erro"]
            assert sessoes.ler(s.id).interrompida == "pedido preservado"
            status, resposta = pedir(
                p, "POST", "/api/terminal/escrever", {"id": s.id, "dados": "novo\r"}
            )
            assert status == 400 and "Atualização em andamento" in resposta["erro"]
            status, resposta = pedir(p, "POST", "/api/terminal/abrir", {"id": fechada.id})
            assert status == 400 and "Atualização em andamento" in resposta["erro"]
            assert fechada.id not in sessoes.terminais
            assert pedir(p, "POST", "/api/terminal/abrir", {"id": s.id})[0] == 200
            assert pedir(p, "POST", "/api/sessao/ler", {"id": s.id})[0] == 200
            status, leitura = pedir(
                p, "POST", "/api/terminal/ler", {"id": s.id, "desde": 0, "espera": 0}
            )
            assert status == 200
            texto = base64.b64decode(leitura["dados"])
            assert b"historia preservada" in texto and b"novo" not in texto
        if resultado == "falhou":
            progresso.falhou("Falha simulada.")
        else:
            progresso.etapa(resultado)
        assert (
            pedir(p, "POST", "/api/terminal/escrever", {"id": s.id, "dados": "liberado\r"})[0]
            == 200
        )
        assert progresso.reserva() is None
        assert terminal.vivo
    finally:
        p.parar()
        terminal.encerrar()


# --- a via rápida pelo painel ---------------------------------------------------------------


class NucleoFalso:
    def __init__(self) -> None:
        self.cfg = config.validar({}, "teste")
        self.cerebro = SimpleNamespace(modelo="claude-sonnet-5-5")
        self.provedor = "claude"
        self.aplicadas = 0
        self.modelos_do_omniroute: Callable[[], list[str]] = lambda: []
        self._chave_do_omniroute: Callable[[], str | None] = lambda: None
        self.deepgram: deepgram.Deepgram
        self.modelo_ativacao = SimpleNamespace(treinada=False)
        self.sessoes = SimpleNamespace(listar=lambda: [])
        self.perfis: list[usuario.Perfil] = []
        self.acessos = 0

    def aplicar_escuta(self) -> None:
        self.deepgram.recarregar()

    def aplicar_perfil(self, perfil: usuario.Perfil) -> str:
        self.perfis.append(perfil)
        return ""

    def aplicar_acesso(self) -> str:
        self.acessos += 1
        return ""

    def aplicar_via_rapida(self) -> str:
        self.aplicadas += 1
        return ""

    def persona_rapida(self) -> str:
        return "P"


@pytest.fixture
def acoes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Acoes, NucleoFalso]:
    monkeypatch.setattr(rapido, "CHAVES", tmp_path / "chaves")
    monkeypatch.setattr(rapido, "ESCOLHA", tmp_path / "via-rapida.json")
    monkeypatch.setattr(usuario, "ARQUIVO", tmp_path / "config" / "perfil.json")
    monkeypatch.setattr(acesso, "ORIGINAL", {acesso.TOKEN: "", acesso.CHAVE: ""})
    monkeypatch.setattr(acesso, "LOGIN", tmp_path / "sem-login.json")
    for variavel in rapido.VARIAVEIS.values():
        monkeypatch.delenv(variavel, raising=False)
    n = NucleoFalso()
    n.deepgram = deepgram.Deepgram(tmp_path / "config" / "deepgram.key")
    return Acoes(n, tmp_path / "latencias", tmp_path / "teste"), n


def test_a_chave_vai_para_um_arquivo_so_do_usuario_e_nunca_volta(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path
) -> None:
    a, n = acoes
    resposta = a.guardar_chave({"motor": "openai", "chave": "sk-segredo-1234"})
    texto = json.dumps(resposta)
    assert "sk-segredo" not in texto
    assert resposta["chaves"]["openai"] == {
        "usa": True,
        "tem": True,
        "origem": "painel",
        "fim": "1234",
    }
    arquivo = tmp_path / "chaves" / "openai.key"
    assert arquivo.read_text() == "sk-segredo-1234\n"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert stat.S_IMODE(arquivo.parent.stat().st_mode) == 0o700
    assert n.aplicadas == 0  # o motor em uso é o plano: nada a trocar
    with pytest.raises(PedidoInvalido):
        a.guardar_chave({"motor": "openai", "chave": "com espaço"})
    with pytest.raises(PedidoInvalido):
        a.guardar_chave({"motor": "plano", "chave": "x"})
    a.apagar_chave({"motor": "openai"})
    assert not arquivo.exists()


def test_mudar_o_motor_grava_por_cima_da_config_e_aplica_na_hora(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path
) -> None:
    a, n = acoes
    assert a.cerebro()["via"]["motor"] == "plano"
    resposta = a.mudar_cerebro({"motor": "openai", "modelo": "gpt-5.4-mini", "ligada": True})
    assert resposta["via"]["motor"] == "openai" and n.aplicadas == 1
    assert json.loads((tmp_path / "via-rapida.json").read_text())["modelo"] == "gpt-5.4-mini"
    for errado in (
        {"motor": "groq"},
        {"modelo": ""},
        {"endereco": "http://site-de-fora.com/v1"},
        {"arquivo_chave": "/etc/passwd"},
        {"ligada": "sim"},
    ):
        with pytest.raises(PedidoInvalido):
            a.mudar_cerebro(errado)
    # A ponte sem endereço não vale: fica a config.
    a.mudar_cerebro({"motor": "ponte"})
    assert rapido.efetiva(n.cfg["via_rapida"])["motor"] == "plano"


def test_testar_sem_chave_avisa_sem_chamar_ninguem(acoes: tuple[Acoes, NucleoFalso]) -> None:
    a, _ = acoes
    assert a.testar({"motor": "anthropic", "modelo": "claude-haiku-4-5"}) == {
        "ok": False,
        "erro": "falta a chave deste motor",
    }


def test_a_chave_do_deepgram_liga_a_escuta_na_hora_e_nunca_volta(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, n = acoes
    conferidas: list[str] = []

    def conferir(chave: str) -> tuple[bool, str]:
        conferidas.append(chave)
        return chave.endswith("9876"), "Chave inválida."

    monkeypatch.setattr(deepgram, "conferir", conferir)
    assert a.escuta()["deepgram"] == {"tem": False, "fim": ""}
    assert a.escuta()["ativacao"] is False
    resposta = a.guardar_chave_escuta({"chave": "dg-segredo-9876"})
    assert "dg-segredo" not in json.dumps(resposta)
    assert resposta["deepgram"] == {"tem": True, "fim": "9876"} and resposta["valida"]
    assert n.deepgram.disponivel  # sem reiniciar
    arquivo = tmp_path / "config" / "deepgram.key"
    assert arquivo.read_text() == "dg-segredo-9876\n"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert not a.guardar_chave_escuta({"chave": "errada-0000"})["valida"]
    assert a.testar_chave_escuta({}) == {"ok": False, "mensagem": "Chave inválida."}
    assert conferidas[-1] == "errada-0000"  # sem chave colada, confere a guardada
    with pytest.raises(PedidoInvalido):
        a.guardar_chave_escuta({"chave": "com espaço"})
    a.apagar_chave_escuta({})
    assert not arquivo.exists() and not n.deepgram.disponivel


def test_conferir_a_chave_do_deepgram_distingue_recusa_de_rede() -> None:
    import urllib.error

    def recusa(pedido: Any, timeout: float) -> Any:
        raise urllib.error.HTTPError(pedido.full_url, 401, "Unauthorized", {}, None)  # type: ignore[arg-type]

    def sem_rede(pedido: Any, timeout: float) -> Any:
        raise OSError("sem rede")

    assert deepgram.conferir("x", recusa) == (False, "Chave inválida.")
    assert deepgram.conferir("x", sem_rede)[0] is False


def test_os_arquivos_da_pagina_sao_leves() -> None:
    web = Path(__file__).resolve().parents[1] / "zervis/portal/web"
    import re

    html = (web / "index.html").read_text()
    scripts = re.findall(r'<script src="/([^"\n]+)"', html)
    abertura = sum((web / f).stat().st_size for f in ("index.html", "painel.css", *scripts))
    assert abertura < 130_000, abertura  # docs/plano-painel.md: o que carrega ao abrir
    for pagina in (web / "paginas").glob("*.js"):  # páginas sob demanda, cada uma pequena
        assert pagina.stat().st_size < 20_000, pagina
    imagens = sum(f.stat().st_size for f in web.iterdir() if f.suffix in (".webp", ".png", ".svg"))
    assert imagens < 20_000, imagens  # o ícone do Zé, pequeno
    assert "http" not in (web / "index.html").read_text().replace("http://www.w3.org", "")
    assert os.access(web / "painel.js", os.R_OK)


def test_envio_de_arquivo_cru_com_token(portal: Portal) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=5)
    cab = {"Host": f"127.0.0.1:{portal.porta}", "X-Ze-Token": portal.token}
    conn.request("POST", "/api/anexo?id=ab12cd34&nome=foto.png", body=b"\x89PNG" * 10, headers=cab)
    resp = conn.getresponse()
    assert resp.status == 200
    assert json.loads(resp.read()) == {"bytes": 40, "id": "ab12cd34", "nome": "foto.png"}
    conn.request("POST", "/api/anexo?id=x", body=b"x", headers={"Host": cab["Host"]})
    assert conn.getresponse().status == 403


# --- configuração da primeira vez ---------------------------------------------------------------


def test_sem_perfil_a_configuracao_nao_esta_feita_e_o_perfil_salva_validado(
    acoes: tuple[Acoes, NucleoFalso],
) -> None:
    a, n = acoes
    c = a.configuracao()
    assert not c["feita"] and c["perfil"] == {"nome": "", "sobre": "", "fuso": ""}
    assert c["fuso_sistema"] and "America/Sao_Paulo" in c["fusos"]
    r = a.salvar_perfil({"nome": " Ana ", "sobre": "Designer.", "fuso": "America/Sao_Paulo"})
    assert r["feita"] and r["perfil"]["nome"] == "Ana" and r["aviso"].startswith("Perfil salvo.")
    assert n.perfis == [usuario.Perfil("Ana", "Designer.", "America/Sao_Paulo")]
    for errado in ({"fuso": "Lua/Base"}, {"nome": "x" * 61}, {"sobre": "x" * 2001}):
        with pytest.raises(PedidoInvalido):
            a.salvar_perfil(errado)


def test_o_acesso_ao_claude_pelo_painel_nunca_devolve_o_segredo(
    acoes: tuple[Acoes, NucleoFalso], tmp_path: Path
) -> None:
    a, n = acoes
    c = a.configuracao()
    assert c["acesso"]["metodo"] == "" and [x["id"] for x in c["agentes"]] == ["claude", "codex"]
    assert a.testar_acesso({}) == {"ok": False, "mensagem": "Acesso não configurado."}
    r = a.guardar_chave_claude({"chave": "sk-ant-5678"})
    assert "sk-ant" not in json.dumps(r) and r["aviso"] == "Chave salva."
    assert r["acesso"] == {"metodo": "chave", "origem": "painel", "fim": "5678"}
    assert a.remover_acesso({})["acesso"]["metodo"] == ""
    assert n.acessos == 2
    with pytest.raises(PedidoInvalido):
        a.guardar_chave_claude({"chave": "com espaço"})


def test_conexao_codex_usa_a_conta_do_codex(
    acoes: tuple[Acoes, NucleoFalso], monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.cerebro import codex

    a, n = acoes
    n.provedor = "codex"
    chamados: list[str] = []

    async def testar(modelo: str, pasta: Path) -> tuple[bool, str]:
        chamados.append(modelo)
        return True, "Conectado."

    monkeypatch.setattr(codex, "testar", testar)
    assert a.testar_acesso({}) == {"ok": True, "mensagem": "Conectado."}
    assert chamados == [""]
    assert any(x["id"] == "codex" and x["disponivel"] for x in a.cerebro()["agentes"])


def test_terminal_e_paginas_carregam_sob_demanda() -> None:
    from zervis.portal.servidor import ARQUIVOS, WEB

    html = (WEB / "index.html").read_text()
    assert "/vendor/xterm/" not in html
    assert "/paginas/" not in html
    for rota, arquivo in ARQUIVOS.items():
        if rota.startswith(("/modulos/", "/paginas/")):
            assert (WEB / arquivo).is_file(), rota
