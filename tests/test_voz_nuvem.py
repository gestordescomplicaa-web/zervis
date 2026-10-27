"""As vozes da nuvem (ADR 0041): ElevenLabs e Fish Audio, opcionais, em streaming, com o Cadu de
reserva. Um servidor falso faz o papel das duas APIs: mesmas rotas, cabeçalhos de chave e recusas
no formato de cada uma."""

import io
import json
import stat
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest

from zervis import atividade
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido
from zervis.voz import elevenlabs, fish, nuvem
from zervis.voz.saida import FluxoPronto, Voz

CHAVE_11 = "sk_teste_0123456789abcdef"
CHAVE_FISH = "fish0123456789abcdef"
VOZES_11 = [
    {
        "voice_id": "v-ingles",
        "name": "Rachel",
        "labels": {"gender": "female", "accent": "american"},
    },
    {
        "voice_id": "v-feminina-pt",
        "name": "Ana",
        "labels": {"gender": "female"},
        "verified_languages": [{"language": "pt", "model_id": "eleven_v4_turbo"}],
    },
    {
        "voice_id": "v-masculina-pt",
        "name": "Bruno",
        "labels": {"gender": "male", "accent": "brazilian", "age": "middle_aged"},
        "verified_languages": [{"language": "pt", "model_id": "eleven_v4_turbo"}],
    },
]
PROPRIA = {"_id": "a" * 32, "type": "tts", "title": "Minha voz", "tags": []}
POPULARES = [
    {"_id": "b" * 32, "type": "tts", "title": "Narrador BR", "tags": ["male", "narration"]},
    {"_id": "a" * 32, "type": "tts", "title": "Minha voz", "tags": []},  # repetida: some
    {"_id": "c" * 32, "type": "svc", "title": "Conversão de voz"},  # não é TTS
]
DA_BIBLIOTECA = {"_id": "d" * 32, "type": "tts", "title": "Locutora", "tags": ["female"]}
AUDIO = (np.sin(np.arange(4801) / 9) * 12000).astype("<i2")  # número ímpar de bytes no fim


class Api:
    """O que o servidor falso recebeu e como deve responder."""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.conexoes = 0
        self.recusa: tuple[int, dict[str, Any]] | None = None
        self.audio = AUDIO.tobytes() + b"\x01"
        self.saldo = "3.2"


@pytest.fixture
def api() -> Iterator[tuple[Api, str]]:
    estado = Api()

    class Manipulador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # mantém a conexão entre as frases

        def setup(self) -> None:
            estado.conexoes += 1
            super().setup()

        def log_message(self, *args: Any) -> None:
            pass

        def _json(self, codigo: int, corpo: Any) -> None:
            dados = json.dumps(corpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def _recusar(self) -> bool:
            fish_ = self.headers.get("Authorization") == f"Bearer {CHAVE_FISH}"
            if self.headers.get("xi-api-key") != CHAVE_11 and not fish_:
                if self.headers.get("Authorization"):
                    self._json(401, {"status": 401, "message": "Invalid token"})
                else:
                    self._json(401, {"detail": {"status": "invalid_api_key", "message": "x"}})
                return True
            if estado.recusa:
                self._json(*estado.recusa)
                return True
            return False

        def do_GET(self) -> None:
            estado.pedidos.append({"caminho": self.path})
            if self._recusar():
                return
            partes = urlsplit(self.path)
            consulta = parse_qs(partes.query)
            if partes.path == "/v2/voices":
                self._json(200, {"voices": VOZES_11})
            elif partes.path == "/wallet/self/api-credit":
                self._json(200, {"_id": "w", "credit": estado.saldo})
            elif partes.path == "/model" and consulta.get("self") == ["true"]:
                self._json(200, {"total": 1, "items": [PROPRIA]})
            elif partes.path == "/model":
                assert consulta["language"] == ["pt"] and consulta["sort_by"] == ["task_count"]
                self._json(200, {"total": 3, "items": POPULARES})
            elif partes.path == f"/model/{DA_BIBLIOTECA['_id']}":
                self._json(200, DA_BIBLIOTECA)
            else:
                self._json(404, {"status": 404, "message": "Not found"})

        def do_POST(self) -> None:
            corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            estado.pedidos.append(
                {"caminho": self.path, "corpo": corpo, "modelo": self.headers.get("model")}
            )
            if self._recusar():
                return
            # Em pedaços, como o streaming de verdade (chunked).
            self.send_response(200)
            self.send_header("Content-Type", "audio/pcm")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for i in range(0, len(estado.audio), 777):
                    pedaco = estado.audio[i : i + 777]
                    self.wfile.write(f"{len(pedaco):x}\r\n".encode() + pedaco + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            except ConnectionError:
                self.close_connection = True  # a fala foi cortada: o Zé fechou a conexão

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    threading.Thread(target=servidor.serve_forever, args=(0.02,), daemon=True).start()
    try:
        yield estado, f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()
        servidor.server_close()


class Cadu:
    def __init__(self) -> None:
        self.falou: list[str] = []

    def abrir_fluxo(self, texto: str) -> tuple[int, FluxoPronto]:
        self.falou.append(texto)
        return 22050, FluxoPronto(np.zeros(10, "<f4").tobytes())


BRUNO = {"id": "v-masculina-pt", "nome": "Bruno", "modelo": "eleven_v4_turbo"}
NARRADOR = {"id": "b" * 32, "nome": "Narrador BR", "modelo": "s2.1-pro"}


def _motor(tmp_path: Path, endereco: str, escolha: nuvem.Escolha | None = None) -> Any:
    if escolha is not None:
        (tmp_path / "elevenlabs.key").write_text(CHAVE_11 + "\n")
        (tmp_path / "fish.key").write_text(CHAVE_FISH + "\n")
        nuvem.gravar_escolha(escolha, tmp_path / "voz.json")
    enderecos = {"elevenlabs": endereco, "fish": endereco}
    return nuvem.Motor(Cadu(), tmp_path, enderecos=enderecos)


def _ler(fluxo: Any) -> bytes:
    return b"".join(iter(fluxo.read1, b""))


ELEVEN = nuvem.Escolha("elevenlabs", {"elevenlabs": BRUNO})
FISH = nuvem.Escolha("fish", {"fish": NARRADOR})


def test_sem_chave_ou_sem_escolha_o_cadu_fala(tmp_path: Path, api: tuple[Api, str]) -> None:
    estado, endereco = api
    motor = _motor(tmp_path, endereco)
    assert motor.abrir_fluxo("Oi.")[0] == 22050
    (tmp_path / "fish.key").write_text(CHAVE_FISH)  # chave sem escolher o Fish
    motor.recarregar()
    motor.abrir_fluxo("Oi de novo.")
    assert motor.local.falou == ["Oi.", "Oi de novo."]
    assert estado.pedidos == []
    assert motor.situacao()["motor"] == "piper"


def test_elevenlabs_em_streaming_no_formato_do_piper(tmp_path: Path, api: tuple[Api, str]) -> None:
    estado, endereco = api
    motor = _motor(tmp_path, endereco, ELEVEN)
    taxa, fluxo = motor.abrir_fluxo("Bom dia, tudo certo por aqui.")
    dados = _ler(fluxo)
    assert taxa == 24000
    esperado = AUDIO.astype("<f4") / 32768.0  # o byte ímpar do fim não vira amostra
    assert np.allclose(np.frombuffer(dados, "<f4"), esperado)
    pedido = estado.pedidos[-1]
    assert pedido["caminho"] == "/v1/text-to-speech/v-masculina-pt/stream?output_format=pcm_24000"
    assert pedido["corpo"] == {
        "text": "Bom dia, tudo certo por aqui.",
        "model_id": "eleven_v4_turbo",
        "language_code": "pt",
    }
    assert motor.ultimo == "elevenlabs"
    assert motor.caracteres_hoje("elevenlabs") == len("Bom dia, tudo certo por aqui.")
    assert motor.local.falou == []


def test_fish_em_streaming_com_a_voz_e_o_modelo_escolhidos(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    estado, endereco = api
    motor = _motor(tmp_path, endereco, FISH)
    taxa, fluxo = motor.abrir_fluxo("Pronto, terminei.")
    assert taxa == 44100
    assert np.allclose(np.frombuffer(_ler(fluxo), "<f4"), AUDIO.astype("<f4") / 32768.0)
    pedido = estado.pedidos[-1]
    assert (pedido["caminho"], pedido["modelo"]) == ("/v1/tts", "s2.1-pro")
    assert pedido["corpo"] == {
        "text": "Pronto, terminei.",
        "reference_id": "b" * 32,
        "format": "pcm",
        "sample_rate": 44100,
        "latency": "low",
        "language": "pt",
    }
    assert motor.ultimo == "fish"


def test_as_frases_seguintes_usam_a_mesma_conexao(tmp_path: Path, api: tuple[Api, str]) -> None:
    """O aperto de mão TLS custa caro: aquecida enquanto o cérebro pensa, a conexão serve a
    todas as frases da resposta."""
    estado, endereco = api
    motor = _motor(tmp_path, endereco, FISH)
    motor.aquecer()
    for _ in range(50):
        if "fish" in motor._livres:
            break
        threading.Event().wait(0.02)
    for texto in ("Primeira.", "Segunda.", "Terceira."):
        _ler(motor.abrir_fluxo(texto)[1])
    assert len(estado.pedidos) == 3
    assert estado.conexoes == 1


def test_a_fala_cortada_no_meio_nao_reaproveita_a_conexao(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    estado, endereco = api
    estado.audio = AUDIO.tobytes() * 40  # longa: o corte acontece antes do fim
    motor = _motor(tmp_path, endereco, ELEVEN)
    _, fluxo = motor.abrir_fluxo("Uma resposta comprida.")
    fluxo.read1()
    fluxo.close()  # "Ei Zé" no meio da fala: `Voz.parar()` fecha o fluxo
    assert motor._livres == {}
    estado.audio = AUDIO.tobytes()
    assert _ler(motor.abrir_fluxo("Depois.")[1])
    assert estado.conexoes == 2


@pytest.mark.parametrize(
    ("escolha", "recusa", "motivo", "titulo"),
    [
        (
            ELEVEN,
            (401, {"detail": {"status": "quota_exceeded", "message": "quota"}}),
            "Sem créditos no ElevenLabs.",
            "ElevenLabs",
        ),
        (
            FISH,
            (402, {"status": 402, "message": "Insufficient balance"}),
            "Sem saldo de API no Fish Audio (é separado do crédito da plataforma).",
            "Fish Audio",
        ),
    ],
)
def test_sem_credito_o_cadu_fala_e_o_zé_nao_insiste_a_cada_frase(
    tmp_path: Path,
    api: tuple[Api, str],
    monkeypatch: pytest.MonkeyPatch,
    escolha: nuvem.Escolha,
    recusa: tuple[int, dict[str, Any]],
    motivo: str,
    titulo: str,
) -> None:
    registros: list[tuple[Any, ...]] = []
    monkeypatch.setattr(atividade.PADRAO, "registrar", lambda *a, **k: registros.append((*a, k)))
    estado, endereco = api
    estado.recusa = recusa
    motor = _motor(tmp_path, endereco, escolha)
    assert motor.abrir_fluxo("Primeira.")[0] == 22050
    assert motor.abrir_fluxo("Segunda.")[0] == 22050
    assert motor.local.falou == ["Primeira.", "Segunda."]
    assert len(estado.pedidos) == 1  # a segunda frase nem tentou: pausa de um minuto
    assert motor.situacao()["erro"] == motivo
    assert registros == [
        ("falha", f"A voz do {titulo} falhou; o Cadu falou no lugar", {"erro": motivo})
    ]
    estado.recusa = None
    motor.recarregar()  # o painel salvou de novo: tenta já
    assert motor.abrir_fluxo("Terceira.")[0] != 22050


def test_sem_rede_o_cadu_fala(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atividade.PADRAO, "registrar", lambda *a, **k: None)
    motor = _motor(tmp_path, "http://127.0.0.1:1", FISH)
    assert motor.abrir_fluxo("Oi.")[0] == 22050
    assert motor.ultimo == "piper"
    assert motor.situacao()["erro"] == "Sem conexão com o Fish Audio."


def test_vozes_do_elevenlabs_em_portugues_e_masculinas_primeiro(api: tuple[Api, str]) -> None:
    _, endereco = api
    lista = elevenlabs.vozes(CHAVE_11, endereco)
    assert [v["id"] for v in lista] == ["v-masculina-pt", "v-feminina-pt", "v-ingles"]
    assert lista[0] == {
        "id": "v-masculina-pt",
        "nome": "Bruno",
        "detalhe": "masculina, brazilian, middle aged",
    }
    with pytest.raises(nuvem.ErroVoz, match="Chave inválida"):
        elevenlabs.vozes("chave-errada", endereco)


def test_vozes_do_fish_as_da_pessoa_e_as_mais_usadas_em_portugues(api: tuple[Api, str]) -> None:
    _, endereco = api
    lista = fish.vozes(CHAVE_FISH, endereco)
    assert lista == [
        {"id": "a" * 32, "nome": "Minha voz", "detalhe": "sua"},
        {"id": "b" * 32, "nome": "Narrador BR", "detalhe": "male, narration"},
    ]
    with pytest.raises(nuvem.ErroVoz, match="Chave inválida"):
        fish.vozes("chave-errada", endereco)


def test_saldo_do_fish_decide_o_modelo(api: tuple[Api, str]) -> None:
    estado, endereco = api
    assert fish.conta(CHAVE_FISH, endereco) == ("s2.1-pro", "Saldo de API: US$ 3,20 · S2.1 Pro.")
    estado.saldo = "0"
    assert fish.conta(CHAVE_FISH, endereco) == (
        "s2.1-pro-free",
        "Sem saldo de API: S2.1 Pro Free, grátis no uso justo.",
    )


def test_voz_do_fish_pelo_link_colado(api: tuple[Api, str]) -> None:
    _, endereco = api
    link = f"https://fish.audio/m/{'d' * 32}/"
    assert fish.voz_colada(link, CHAVE_FISH, endereco) == {
        "id": "d" * 32,
        "nome": "Locutora",
        "detalhe": "female",
    }
    assert fish.voz_colada("Locutora", CHAVE_FISH, endereco) is None  # sem id: não é link
    with pytest.raises(nuvem.ErroVoz, match="não existe"):
        fish.voz_colada("e" * 32, CHAVE_FISH, endereco)


def test_escolha_desconhecida_ou_quebrada_volta_ao_cadu(tmp_path: Path) -> None:
    arquivo = tmp_path / "voz.json"
    motores = ("elevenlabs", "fish")
    arquivo.write_text("{quebrado")
    assert nuvem.ler_escolha(arquivo, motores) == nuvem.Escolha()
    arquivo.write_text(json.dumps({"motor": "outro", "vozes": {"outro": {"id": "x"}}}))
    assert nuvem.ler_escolha(arquivo, motores) == nuvem.Escolha()


def test_motivos_da_recusa_em_uma_linha() -> None:
    corpo = json.dumps({"detail": {"status": "voice_not_found", "message": "x"}}).encode()
    assert elevenlabs.motivo(400, corpo) == "Essa voz não existe mais na conta."
    assert elevenlabs.motivo(429, b"") == "Limite de pedidos do ElevenLabs."
    assert elevenlabs.motivo(500, b"<html>") == "Erro do ElevenLabs (500)."
    corpo = json.dumps({"detail": {"message": "algo   deu\nerrado"}}).encode()
    assert elevenlabs.motivo(422, corpo) == "Erro do ElevenLabs (422): algo deu errado."
    assert fish.motivo(401, b'{"status": 401, "message": "x"}') == "Chave inválida."
    assert fish.motivo(503, b"") == "O Fish Audio está sobrecarregado."
    corpo = b'{"status": 422, "message": "text too long"}'
    assert fish.motivo(422, corpo) == "Erro do Fish Audio (422): text too long."


# --- o painel -----------------------------------------------------------------------------------


def _painel(tmp_path: Path, endereco: str) -> tuple[Acoes, Any, list[str]]:
    faladas: list[str] = []
    motor = _motor(tmp_path, endereco)
    eventos = SimpleNamespace(put=lambda evento: faladas.append(evento.texto))
    nucleo = SimpleNamespace(motor_voz=motor, eventos=eventos)
    return Acoes(nucleo, tmp_path, tmp_path), motor, faladas


def test_colar_a_chave_ja_passa_a_falar_pelo_provedor(tmp_path: Path, api: tuple[Api, str]) -> None:
    _, endereco = api
    acoes, _, faladas = _painel(tmp_path, endereco)
    with pytest.raises(PedidoInvalido, match="Chave inválida"):
        acoes.guardar_chave_sintese({"provedor": "elevenlabs", "chave": "errada"})
    assert not (tmp_path / "elevenlabs.key").exists()
    with pytest.raises(PedidoInvalido, match="espaços"):
        acoes.guardar_chave_sintese({"provedor": "elevenlabs", "chave": "com espaco"})
    r = acoes.guardar_chave_sintese({"provedor": "elevenlabs", "chave": f"  {CHAVE_11}\n"})
    assert r["aviso"] == "Chave salva. Voz: Bruno."
    eleven = r["provedores"]["elevenlabs"]
    assert (r["motor"], eleven["voz"], eleven["chave"]) == (
        "elevenlabs",
        "v-masculina-pt",
        {"tem": True, "fim": CHAVE_11[-4:]},
    )
    assert [v["nome"] for v in eleven["vozes"]] == ["Bruno", "Ana", "Rachel"]
    assert CHAVE_11 not in json.dumps(r)
    chave = tmp_path / "elevenlabs.key"
    assert chave.read_text().strip() == CHAVE_11
    assert stat.S_IMODE(chave.stat().st_mode) == 0o600
    assert faladas == ["Oi! Agora eu falo com a voz Bruno."]  # ouve na hora como ficou

    r = acoes.escolher_sintese({"motor": "elevenlabs", "voz": "v-feminina-pt"})
    assert (r["provedores"]["elevenlabs"]["nome"], r["aviso"]) == ("Ana", "Voz: Ana.")
    with pytest.raises(PedidoInvalido, match="Voz desconhecida"):
        acoes.escolher_sintese({"motor": "elevenlabs", "voz": "nao-existe"})

    r = acoes.escolher_sintese({"motor": "piper"})
    assert (r["motor"], r["aviso"]) == ("piper", "Voz: Cadu.")
    assert faladas[-1] == "Oi! Agora eu falo com a voz do Cadu."
    r = acoes.escolher_sintese({"motor": "elevenlabs"})  # volta para a voz de antes
    assert (r["motor"], r["provedores"]["elevenlabs"]["nome"]) == ("elevenlabs", "Ana")

    r = acoes.apagar_chave_sintese({"provedor": "elevenlabs"})
    assert (r["motor"], r["provedores"]["elevenlabs"]["chave"]["tem"]) == ("piper", False)
    assert r["aviso"] == "Chave removida. O Cadu volta a falar."
    with pytest.raises(PedidoInvalido, match="Cole a chave do ElevenLabs"):
        acoes.escolher_sintese({"motor": "elevenlabs"})


def test_fish_pelo_painel_com_saldo_e_voz_colada(tmp_path: Path, api: tuple[Api, str]) -> None:
    estado, endereco = api
    estado.saldo = "0"
    acoes, motor, faladas = _painel(tmp_path, endereco)
    r = acoes.guardar_chave_sintese({"provedor": "fish", "chave": CHAVE_FISH})
    assert r["aviso"] == "Chave salva. Voz: Minha voz."
    dados = r["provedores"]["fish"]
    assert dados["conta"] == "Sem saldo de API: S2.1 Pro Free, grátis no uso justo."
    assert motor.escolha.voz("fish") == {
        "id": "a" * 32,
        "nome": "Minha voz",
        "modelo": "s2.1-pro-free",
    }

    r = acoes.escolher_sintese({"motor": "fish", "voz": f"https://fish.audio/m/{'d' * 32}"})
    assert r["aviso"] == "Voz: Locutora."
    assert motor.escolha.voz("fish")["modelo"] == "s2.1-pro-free"  # o modelo segue o saldo
    _ler(motor.abrir_fluxo("Teste.")[1])
    assert (estado.pedidos[-1]["modelo"], estado.pedidos[-1]["corpo"]["reference_id"]) == (
        "s2.1-pro-free",
        "d" * 32,
    )
    assert faladas[-1] == "Oi! Agora eu falo com a voz Locutora."
    with pytest.raises(PedidoInvalido, match="não existe"):
        acoes.escolher_sintese({"motor": "fish", "voz": "e" * 32})

    # Com as duas chaves, apagar a de quem não fala não muda quem fala.
    acoes.guardar_chave_sintese({"provedor": "elevenlabs", "chave": CHAVE_11})
    r = acoes.apagar_chave_sintese({"provedor": "fish"})
    assert (r["motor"], r["aviso"]) == ("elevenlabs", "Chave removida.")
    with pytest.raises(PedidoInvalido, match="provedor de voz desconhecido"):
        acoes.apagar_chave_sintese({"provedor": "outro"})


def test_a_tela_mostra_as_vozes_e_a_conta_da_chave_guardada(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    _, endereco = api
    acoes, motor, _ = _painel(tmp_path, endereco)
    (tmp_path / "fish.key").write_text(CHAVE_FISH)
    motor.recarregar()
    r = acoes.sintese()
    assert [v["nome"] for v in r["provedores"]["fish"]["vozes"]] == ["Minha voz", "Narrador BR"]
    assert r["provedores"]["fish"]["conta"] == "Saldo de API: US$ 3,20 · S2.1 Pro."
    assert r["provedores"]["elevenlabs"]["vozes"] == []
    assert r["provedores"]["fish"]["cadastro"].startswith("https://fish.audio/")
    assert r["erro"] == ""


def test_fluxo_pcm_junta_bytes_partidos() -> None:
    """Um pedaço da rede pode partir uma amostra ao meio: o byte que sobra vai para o próximo."""

    class Resposta(io.BytesIO):
        def read1(self, n: int | None = -1, /) -> bytes:
            return super().read1(3)

    pcm = np.array([1000, -2000, 3000], "<i2").tobytes()
    devolvida: list[bool] = []
    fluxo = nuvem.FluxoPcm(Resposta(pcm), devolvida.append)  # type: ignore[arg-type]
    amostras = np.frombuffer(_ler(fluxo), "<f4")
    assert np.allclose(amostras * 32768, [1000, -2000, 3000])
    assert devolvida == [True]


@pytest.mark.parametrize(("escolha", "taxa"), [(ELEVEN, 24000), (FISH, 44100)])
def test_a_fila_de_fala_toca_a_voz_da_nuvem_de_ponta_a_ponta(
    tmp_path: Path, api: tuple[Api, str], escolha: nuvem.Escolha, taxa: int
) -> None:
    """A `Voz` de verdade (fila, folga, reprodutor) com o motor: as duas frases tocam inteiras,
    na taxa do provedor, pela mesma conexão."""
    estado, endereco = api
    motor = _motor(tmp_path, endereco, escolha)
    tocado = tmp_path / "tocado.raw"
    taxas: list[int] = []

    def reprodutor(t: int) -> list[str]:
        taxas.append(t)
        return ["/bin/sh", "-c", f"cat >> {tocado}"]

    ociosa = threading.Event()
    voz = Voz(abrir_fluxo=motor.abrir_fluxo, folga_s=0, reprodutor=reprodutor)
    voz.ao_ficar_ociosa = lambda n: ociosa.set()
    voz.falar("Primeira frase da resposta. Segunda frase, que vem logo depois.")
    assert ociosa.wait(5) and voz.ultimo_erro is None
    assert taxas == [taxa, taxa]
    assert len(tocado.read_bytes()) == 2 * len(AUDIO) * 4  # float32, as duas frases
    assert [p["corpo"]["text"] for p in estado.pedidos] == [
        "Primeira frase da resposta.",
        "Segunda frase, que vem logo depois.",
    ]
    assert estado.conexoes == 1
