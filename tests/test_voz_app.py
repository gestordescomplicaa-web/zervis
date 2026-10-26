"""O app de voz do Android (`zervis/portal/voz_app.py`): pareamento e o canal de voz dele."""

import json
import queue
import stat
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from websockets.exceptions import InvalidHandshake
from websockets.sync.client import connect

from zervis.nucleo import estados as e
from zervis.nucleo.servicos.remoto import ServicoRemoto
from zervis.portal import voz_app
from zervis.portal.servidor import Portal
from zervis.transporte.navegador import BYTES_QUADRO, VozNavegador
from zervis.transporte.websocket import Conexao


def test_codigo_de_uso_unico_vira_uma_chave_so_guardada_como_resumo(tmp_path: Path) -> None:
    arquivo = tmp_path / "voz-app.json"
    a = voz_app.AparelhosDeVoz(arquivo)
    codigo = a.novo_codigo()
    assert len(codigo) == voz_app.TAMANHO and set(codigo) <= set(voz_app.LETRAS)
    chave = a.parear(f"{codigo[:4].lower()}-{codigo[4:]}", "Pixel")  # digitado de qualquer jeito
    assert chave not in arquivo.read_text() and stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    aparelho = a.aparelho(chave)
    assert aparelho is not None and aparelho["nome"] == "Pixel" and "resumo" not in aparelho
    assert a.aparelho("outra") is None and a.aparelho("") is None
    with pytest.raises(voz_app.PareamentoErro, match="vencido"):
        a.parear(codigo, "de novo")  # uma vez só
    assert [x["nome"] for x in a.lista()] == ["Pixel"]
    assert a.remover(aparelho["id"]) and a.aparelho(chave) is None


def test_codigo_vence_e_erros_seguidos_o_invalidam(tmp_path: Path) -> None:
    relogio = [1000.0]
    a = voz_app.AparelhosDeVoz(tmp_path / "voz-app.json", agora=lambda: relogio[0])
    codigo = a.novo_codigo()
    for _ in range(voz_app.TENTATIVAS):
        with pytest.raises(voz_app.PareamentoErro, match="errado"):
            a.parear("AAAAAAAA", "x")
    with pytest.raises(voz_app.PareamentoErro, match="vencido"):
        a.parear(codigo, "x")  # depois das tentativas, nem o certo vale
    codigo = a.novo_codigo()
    relogio[0] += voz_app.VALIDADE_S + 1
    with pytest.raises(voz_app.PareamentoErro, match="vencido"):
        a.parear(codigo, "x")


class Zé:
    """O Zé falso do canal do app: guarda o modo e devolve o primeiro quadro."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[int, str, str]] = []
        self.controles: list[dict[str, object]] = []

    def __call__(self, conexao: Conexao, taxa: int, modo: str, aparelho: dict[str, Any]) -> None:
        self.chamadas.append((taxa, modo, aparelho["nome"]))
        voz = VozNavegador(conexao, taxa, ao_vivo=modo == "ao_vivo")
        primeiro: list[bytes] = []

        def quadro(q: bytes) -> None:
            if not primeiro:
                primeiro.append(q)
                conexao.binario(q)

        voz.ouvir(quadro, self.controles.append)


@pytest.fixture
def portal(tmp_path: Path) -> Any:
    aparelhos = voz_app.AparelhosDeVoz(tmp_path / "voz-app.json")
    ze = Zé()
    p = Portal({}, {}, porta=0, voz_app=ze, aparelhos_voz=aparelhos)
    p.iniciar()
    yield p, aparelhos, ze
    p.parar()


def _parear(p: Portal, codigo: str) -> tuple[int, dict[str, Any]]:
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{p.porta}/voz-app/parear",
        data=json.dumps({"codigo": codigo, "nome": "Pixel"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=5) as r:  # noqa: S310 (o painel do teste)
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read())


def test_app_pareia_e_abre_so_a_voz_com_a_chave(portal: Any) -> None:
    p, aparelhos, ze = portal
    assert _parear(p, "ERRADO12")[0] == 403
    status, resposta = _parear(p, aparelhos.novo_codigo())
    assert status == 200
    chave = resposta["chave"]
    url = f"ws://127.0.0.1:{p.porta}/voz-app/ws"
    with pytest.raises(InvalidHandshake):  # sem a chave: 403
        connect(url)
    with pytest.raises(InvalidHandshake):
        connect(url, additional_headers={"Authorization": "Bearer outra"})
    with connect(url, additional_headers={"Authorization": f"Bearer {chave}"}) as ws:
        ws.send(json.dumps({"taxa": 16000, "modo": "chamado"}))
        ws.send(json.dumps({"tipo": "apertar"}))
        ws.send(b"\1\0" * (BYTES_QUADRO // 2))
        assert ws.recv(timeout=5) == b"\1\0" * (BYTES_QUADRO // 2)
    assert ze.chamadas == [(16000, "chamado", "Pixel")]
    assert ze.controles == [{"tipo": "apertar"}]


def test_a_chave_do_app_nao_abre_o_painel(portal: Any) -> None:
    p, aparelhos, _ = portal
    chave = _parear(p, aparelhos.novo_codigo())[1]["chave"]
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{p.porta}/api/estado",
        headers={"Authorization": f"Bearer {chave}", "Cf-Connecting-Ip": "203.0.113.9"},
    )
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(pedido, timeout=5)  # noqa: S310 (o painel do teste)
    assert erro.value.code == 401


def _remoto(ao_vivo_agora: bool = False) -> tuple[ServicoRemoto, Any]:
    n: Any = SimpleNamespace(
        _fonte=None,
        captura=SimpleNamespace(remota=lambda _l: None),
        voz=SimpleNamespace(destino=None),
        rostos=SimpleNamespace(marcar=lambda *_a: None),
        eventos=queue.Queue(),
        maquina=SimpleNamespace(ao_vivo=ao_vivo_agora),
        microfone_travado=False,
    )
    servico = ServicoRemoto(n)
    n._fonte_remota = servico._fonte_remota
    n._quadro_remoto = lambda _f, _q: None
    return servico, n


class ConexaoQueFecha:
    """Uma conexão do app que manda o botão do fone e fecha."""

    def __init__(self, mensagens: list[str]) -> None:
        self.aberta = True
        self.mensagens = mensagens

    def receber(self) -> tuple[int, bytes]:
        from zervis.transporte.websocket import TEXTO, FechouErro

        if not self.mensagens:
            raise FechouErro
        return TEXTO, self.mensagens.pop(0).encode()

    def fechar(self) -> None:
        self.aberta = False

    def texto(self, _m: str) -> None:
        pass


def _eventos(n: Any) -> list[Any]:
    lista = []
    while not n.eventos.empty():
        lista.append(n.eventos.get_nowait())
    return lista


def test_app_no_modo_chamado_nao_e_ao_vivo_e_o_botao_do_fone_vira_apertar() -> None:
    servico, n = _remoto()
    conexao = ConexaoQueFecha([json.dumps({"tipo": "apertar"}), json.dumps({"tipo": "soltar"})])
    servico.voz_pelo_app(conexao, 16000, "chamado", {"nome": "Pixel"})  # type: ignore[arg-type]
    assert _eventos(n) == [e.AoVivo(False), e.Apertou(), e.Soltou(), e.AoVivo(False)]


def test_app_ao_vivo_liga_e_desliga_o_ao_vivo() -> None:
    servico, n = _remoto()
    servico.voz_pelo_app(ConexaoQueFecha([]), 16000, "ao_vivo", {"nome": "Pixel"})  # type: ignore[arg-type]
    assert _eventos(n) == [e.AoVivo(True), e.AoVivo(False)]


def test_trocar_o_navegador_ao_vivo_pelo_app_no_chamado_desliga_o_ao_vivo() -> None:
    servico, n = _remoto(ao_vivo_agora=True)
    navegador = VozNavegador(ConexaoQueFecha([]))  # type: ignore[arg-type]
    n._fonte = navegador
    app = VozNavegador(ConexaoQueFecha([]), ao_vivo=False)  # type: ignore[arg-type]
    servico._fonte_remota(app, True)
    assert n._fonte is app and _eventos(n) == [e.AoVivo(False)]
    assert not navegador.conexao.aberta  # a anterior foi fechada
