"""O app de voz do Android (`zervis/portal/voz_app.py`): pareamento e o canal de voz dele."""

import base64
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
from zervis.nucleo.laco import Nucleo
from zervis.nucleo.servicos.remoto import ServicoRemoto
from zervis.portal import voz_app
from zervis.portal.servidor import Portal
from zervis.transporte.entrada import Entrada
from zervis.transporte.navegador import ASSUMIDA, BYTES_QUADRO, MAX_IMAGEM, VozNavegador
from zervis.transporte.websocket import Conexao


class _Local:
    """O microfone do PC, falso: só diz se está aberto."""

    def __init__(self) -> None:
        self.quadros: queue.Queue[bytes] = queue.Queue(maxsize=10)
        self.aberto = False

    def abrir(self) -> None:
        self.aberto = True

    def fechar(self) -> None:
        self.aberto = False


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


class _Nucleo(SimpleNamespace):
    """O núcleo falso: o microfone travado segue a regra de verdade (Silencioso, menos o app)."""

    microfone_travado = Nucleo.microfone_travado


def _remoto(ao_vivo_agora: bool = False, modo_fala: str = "avisos") -> tuple[ServicoRemoto, Any]:
    n: Any = _Nucleo(
        _fonte=None,
        modo_fala=modo_fala,
        captura=Entrada(_Local()),  # type: ignore[arg-type]
        voz=SimpleNamespace(destino=None, muda=modo_fala == "silencioso", parar=lambda: None),
        rostos=SimpleNamespace(marcar=lambda *_a: None),
        eventos=queue.Queue(),
        maquina=SimpleNamespace(ao_vivo=ao_vivo_agora, estado=e.Estado.ATIVO),
    )
    servico = ServicoRemoto(n)
    n._fonte_remota = servico._fonte_remota
    n._quadro_remoto = lambda _f, _q: None
    n.leads_pedidos = []
    n._leads_ao_celular = lambda: n.leads_pedidos.append("estado")
    n.ouvir_lead = lambda ident: n.leads_pedidos.append(f"ouvir {ident}")
    n.dispensar_lead = lambda ident: n.leads_pedidos.append(f"visto {ident}")
    return servico, n


class ConexaoQueFecha:
    """Uma conexão do app que manda o botão do fone e fecha."""

    def __init__(self, mensagens: list[str]) -> None:
        self.aberta = True
        self.mensagens = mensagens
        self.codigo = 0
        self.enviadas: list[dict[str, Any]] = []

    def receber(self) -> tuple[int, bytes]:
        from zervis.transporte.websocket import TEXTO, FechouErro

        if not self.mensagens:
            raise FechouErro
        return TEXTO, self.mensagens.pop(0).encode()

    def fechar(self, codigo: int = 0) -> None:
        self.aberta = False
        self.codigo = codigo

    def texto(self, m: str) -> None:
        self.enviadas.append(json.loads(m))


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


def test_app_recebe_os_leads_ao_conectar_e_os_botoes_da_notificacao_valem() -> None:
    servico, n = _remoto()
    conexao = ConexaoQueFecha(
        [
            json.dumps({"tipo": "whatsapp_ouvir", "id": "ab12cd34"}),
            json.dumps({"tipo": "whatsapp_visto", "id": "ab12cd34"}),
        ]
    )
    servico.voz_pelo_app(conexao, 16000, "chamado", {"nome": "Pixel"})  # type: ignore[arg-type]
    assert n.leads_pedidos == ["estado", "ouvir ab12cd34", "visto ab12cd34"]


def test_app_ao_vivo_liga_e_desliga_o_ao_vivo() -> None:
    servico, n = _remoto()
    servico.voz_pelo_app(ConexaoQueFecha([]), 16000, "ao_vivo", {"nome": "Pixel"})  # type: ignore[arg-type]
    assert _eventos(n) == [e.AoVivo(True), e.AoVivo(False)]


class ConexaoQueOlha(ConexaoQueFecha):
    """Anota, com o app ainda conectado, se o Zé ouve e fala."""

    def __init__(self, n: Any) -> None:
        super().__init__([json.dumps({"tipo": "apertar"})])
        self.n = n
        self.durante: tuple[bool, bool, bool] | None = None

    def receber(self) -> tuple[int, bytes]:
        if self.durante is None:
            self.durante = (self.n.captura.aberta, self.n.voz.muda, self.n.captura.local.aberto)
        return super().receber()


def test_app_fala_e_ouve_no_silencioso_e_ao_sair_o_pc_continua_mudo() -> None:
    servico, n = _remoto(modo_fala="silencioso")
    conexao = ConexaoQueOlha(n)
    servico.voz_pelo_app(conexao, 16000, "chamado", {"nome": "Pixel"})  # type: ignore[arg-type]
    assert conexao.durante == (True, False, False)  # ouve o app, fala, e o microfone do PC fecha
    assert e.Apertou() in _eventos(n)  # o botão do fone vale no Silencioso
    assert not n.captura.aberta and not n.captura.local.aberto and n.voz.muda


def test_o_navegador_continua_recusado_no_silencioso() -> None:
    servico, n = _remoto(modo_fala="silencioso")
    conexao = ConexaoQueFecha([])
    servico.voz_pelo_navegador(conexao, 16000)  # type: ignore[arg-type]
    assert not conexao.aberta and n._fonte is None and _eventos(n) == []


def test_trocar_o_navegador_ao_vivo_pelo_app_no_chamado_desliga_o_ao_vivo() -> None:
    servico, n = _remoto(ao_vivo_agora=True)
    navegador = VozNavegador(ConexaoQueFecha([]))  # type: ignore[arg-type]
    n._fonte = navegador
    app = VozNavegador(ConexaoQueFecha([]), ao_vivo=False)  # type: ignore[arg-type]
    servico._fonte_remota(app, True)
    assert n._fonte is app and _eventos(n) == [e.AoVivo(False)]
    assert not navegador.conexao.aberta  # a anterior foi fechada
    # ...com o motivo: sem ele, o app reconectava em 2 s e os dois aparelhos se derrubavam.
    assert navegador.conexao.codigo == ASSUMIDA  # type: ignore[attr-defined]


def test_a_imagem_vai_a_tela_de_quem_fala_de_outro_aparelho(tmp_path: Path) -> None:
    servico, n = _remoto()
    foto = tmp_path / "foto.jpg"
    foto.write_bytes(b"\xff\xd8 a mesa da impressora")
    assert servico.imagem_ao_aparelho(foto, "Câmera da impressora") == ""  # quem fala está no PC
    conexao = ConexaoQueFecha([])
    n._fonte = VozNavegador(conexao, do_app=True)  # type: ignore[arg-type]
    assert servico.imagem_ao_aparelho(foto, "Câmera da impressora") == "celular"
    (m,) = conexao.enviadas
    assert m["tipo"] == "imagem" and m["titulo"] == "Câmera da impressora" and m["id"]
    assert base64.b64decode(m["dados"]) == foto.read_bytes()
    n._fonte = VozNavegador(ConexaoQueFecha([]))  # type: ignore[arg-type]
    assert servico.imagem_ao_aparelho(foto, "Câmera da impressora") == "navegador"
    assert servico.imagem_ao_aparelho(tmp_path / "sumiu.jpg", "Câmera") == ""
    grande = tmp_path / "grande.jpg"
    grande.write_bytes(b"\0" * (MAX_IMAGEM + 1))
    assert servico.imagem_ao_aparelho(grande, "Câmera") == ""


def test_foto_da_camera_com_o_app_fora_espera_e_vai_ao_conectar(tmp_path: Path) -> None:
    """ADR 0087: o celular é a cópia que sai de casa. A foto de movimento tirada com o app
    desconectado espera na fila e vai quando ele conecta, para a galeria, com a hora dela."""
    from zervis.transporte.fila_imagens import FilaDoCelular

    servico, n = _remoto()
    n.fila_celular = FilaDoCelular(tmp_path / "celular" / "imagens.json")
    primeira, segunda = tmp_path / "20261113-101500-lente2.jpg", tmp_path / "b.jpg"
    primeira.write_bytes(b"\xff\xd8 alguem passou")
    segunda.write_bytes(b"\xff\xd8 de novo")
    titulo = "Movimento · Lente 2"
    assert servico.imagem_ao_aparelho(primeira, titulo, salvar=True, guardar=True) == ""
    assert servico.imagem_ao_aparelho(segunda, titulo, salvar=True, guardar=True) == ""
    assert servico.imagem_ao_aparelho(segunda, titulo, salvar=True) == ""  # sem guardar: não
    assert [p["caminho"] for p in n.fila_celular.pendentes()] == [str(primeira), str(segunda)]
    assert stat.S_IMODE((tmp_path / "celular" / "imagens.json").stat().st_mode) == 0o600
    n._fonte = VozNavegador(ConexaoQueFecha([]))  # type: ignore[arg-type]
    assert servico.entregar_pendentes() == 0  # o navegador do PC não é a cópia que sai de casa
    conexao = ConexaoQueFecha([])
    n._fonte = VozNavegador(conexao, do_app=True)  # type: ignore[arg-type]
    assert servico.entregar_pendentes() == 2
    assert n.fila_celular.pendentes() == []
    m1, m2 = conexao.enviadas
    assert base64.b64decode(m1["dados"]) == primeira.read_bytes()  # na ordem em que foram tiradas
    assert m1["salvar"] is True and m1["quando"] == round(primeira.stat().st_mtime)
    assert m1["titulo"] == titulo and m1["id"] != m2["id"]
    # A mesma foto leva o mesmo id: se chegar duas vezes, o app reconhece.
    servico.imagem_ao_aparelho(primeira, titulo, salvar=True)
    assert conexao.enviadas[-1]["id"] == m1["id"]


def test_fila_do_celular_para_na_primeira_falha_e_esquece_a_foto_que_sumiu(
    tmp_path: Path,
) -> None:
    from zervis.transporte.fila_imagens import FilaDoCelular

    fila = FilaDoCelular(tmp_path / "imagens.json", maximo=3)
    fotos = [tmp_path / f"{i}.jpg" for i in range(5)]
    for f in fotos:
        f.write_bytes(b"\xff\xd8")
        fila.guardar(f, "Movimento")
    assert [p["caminho"] for p in fila.pendentes()] == [str(f) for f in fotos[2:]]  # as 3 últimas
    fotos[2].unlink()  # apagada da pasta da câmera: sai da fila sem tentar
    enviadas: list[str] = []

    def enviar(p: dict[str, Any]) -> bool:
        enviadas.append(p["caminho"])
        return len(enviadas) < 2  # a segunda falha: o app caiu de novo

    assert fila.entregar(enviar) == 1
    assert enviadas == [str(fotos[3]), str(fotos[4])]
    assert [p["caminho"] for p in fila.pendentes()] == [str(fotos[4])]  # a que falhou espera
