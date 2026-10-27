"""A voz pelo ElevenLabs (ADR 0041): opcional, em streaming, com o Cadu de reserva. Um servidor
falso faz o papel da API: mesmas rotas, cabeçalho de chave e recusas no formato dela."""

import io
import json
import stat
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from zervis import atividade
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido
from zervis.voz import elevenlabs
from zervis.voz.saida import FluxoPronto, Voz

CHAVE = "sk_teste_0123456789abcdef"
VOZES = [
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
AUDIO = (np.sin(np.arange(4801) / 9) * 12000).astype("<i2")  # 0,2 s a 24 kHz, número ímpar de bytes


class Api:
    """O que o servidor falso recebeu e como deve responder."""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.conexoes = 0
        self.recusa: tuple[int, dict[str, Any]] | None = None
        self.audio = AUDIO.tobytes() + b"\x01"


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

        def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _recusar(self) -> bool:
            if self.headers.get("xi-api-key") != CHAVE:
                corpo = {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}
                self._responder(401, json.dumps(corpo).encode(), "application/json")
                return True
            if estado.recusa:
                codigo, corpo = estado.recusa
                self._responder(codigo, json.dumps(corpo).encode(), "application/json")
                return True
            return False

        def do_GET(self) -> None:
            estado.pedidos.append({"caminho": self.path})
            if self._recusar():
                return
            self._responder(200, json.dumps({"voices": VOZES}).encode(), "application/json")

        def do_POST(self) -> None:
            corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            estado.pedidos.append({"caminho": self.path, "corpo": corpo})
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


def _motor(tmp_path: Path, endereco: str, escolha: elevenlabs.Escolha | None = None) -> Any:
    chave = tmp_path / "elevenlabs.key"
    arquivo = tmp_path / "voz.json"
    if escolha is not None:
        chave.write_text(CHAVE + "\n")
        elevenlabs.gravar_escolha(escolha, arquivo)
    return elevenlabs.Motor(Cadu(), chave, arquivo, endereco)


def _ler(fluxo: Any) -> bytes:
    return b"".join(iter(fluxo.read1, b""))


ESCOLHIDA = elevenlabs.Escolha("elevenlabs", "v-masculina-pt", "Bruno")


def test_sem_chave_ou_sem_escolha_o_cadu_fala(tmp_path: Path, api: tuple[Api, str]) -> None:
    estado, endereco = api
    motor = _motor(tmp_path, endereco)
    assert motor.abrir_fluxo("Oi.")[0] == 22050
    (tmp_path / "elevenlabs.key").write_text(CHAVE)  # chave sem escolher o ElevenLabs
    motor.recarregar()
    motor.abrir_fluxo("Oi de novo.")
    assert motor.local.falou == ["Oi.", "Oi de novo."]
    assert estado.pedidos == []
    assert motor.situacao()["motor"] == "piper"


def test_a_fala_vem_em_streaming_no_formato_do_piper(tmp_path: Path, api: tuple[Api, str]) -> None:
    estado, endereco = api
    motor = _motor(tmp_path, endereco, ESCOLHIDA)
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
    assert motor.situacao()["caracteres_hoje"] == len("Bom dia, tudo certo por aqui.")
    assert motor.local.falou == []


def test_as_frases_seguintes_usam_a_mesma_conexao(tmp_path: Path, api: tuple[Api, str]) -> None:
    """O aperto de mão TLS custa caro: aquecida enquanto o cérebro pensa, a conexão serve a
    todas as frases da resposta."""
    estado, endereco = api
    motor = _motor(tmp_path, endereco, ESCOLHIDA)
    motor.aquecer()
    for _ in range(50):
        if motor._livre is not None:
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
    motor = _motor(tmp_path, endereco, ESCOLHIDA)
    _, fluxo = motor.abrir_fluxo("Uma resposta comprida.")
    fluxo.read1()
    fluxo.close()  # "Ei Zé" no meio da fala: `Voz.parar()` fecha o fluxo
    assert motor._livre is None
    estado.audio = AUDIO.tobytes()
    assert _ler(motor.abrir_fluxo("Depois.")[1])
    assert estado.conexoes == 2


def test_sem_credito_o_cadu_fala_e_o_zé_nao_insiste_a_cada_frase(
    tmp_path: Path, api: tuple[Api, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    registros: list[tuple[str, str, dict[str, Any]]] = []
    monkeypatch.setattr(atividade.PADRAO, "registrar", lambda *a, **k: registros.append((*a, k)))
    estado, endereco = api
    estado.recusa = (401, {"detail": {"status": "quota_exceeded", "message": "quota"}})
    motor = _motor(tmp_path, endereco, ESCOLHIDA)
    assert motor.abrir_fluxo("Primeira.")[0] == 22050
    assert motor.abrir_fluxo("Segunda.")[0] == 22050
    assert motor.local.falou == ["Primeira.", "Segunda."]
    assert len(estado.pedidos) == 1  # a segunda frase nem tentou: pausa de um minuto
    assert motor.situacao()["erro"] == "Sem créditos no ElevenLabs."
    assert registros == [
        (
            "falha",
            "A voz do ElevenLabs falhou; o Cadu falou no lugar",
            {"erro": "Sem créditos no ElevenLabs."},
        )
    ]
    estado.recusa = None
    motor.recarregar()  # o painel salvou de novo: tenta já
    assert motor.abrir_fluxo("Terceira.")[0] == 24000


def test_sem_rede_o_cadu_fala(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atividade.PADRAO, "registrar", lambda *a, **k: None)
    motor = _motor(tmp_path, "http://127.0.0.1:1", ESCOLHIDA)
    assert motor.abrir_fluxo("Oi.")[0] == 22050
    assert motor.ultimo == "piper"
    assert motor.situacao()["erro"] == "Sem conexão com o ElevenLabs."


def test_as_vozes_em_portugues_e_masculinas_vem_primeiro(api: tuple[Api, str]) -> None:
    _, endereco = api
    lista = elevenlabs.vozes(CHAVE, endereco)
    assert [v["id"] for v in lista] == ["v-masculina-pt", "v-feminina-pt", "v-ingles"]
    assert lista[0] == {
        "id": "v-masculina-pt",
        "nome": "Bruno",
        "detalhe": "masculina, brazilian, middle aged",
    }
    with pytest.raises(elevenlabs.ErroVoz, match="Chave inválida"):
        elevenlabs.vozes("chave-errada", endereco)


def test_a_chave_so_e_guardada_se_vale(tmp_path: Path, api: tuple[Api, str]) -> None:
    _, endereco = api
    motor = _motor(tmp_path, endereco)
    with pytest.raises(elevenlabs.ErroVoz, match="Chave inválida"):
        elevenlabs.guardar_chave(motor, "chave-errada")
    assert not motor.arquivo_chave.exists()
    with pytest.raises(elevenlabs.ErroVoz, match="espaços"):
        elevenlabs.guardar_chave(motor, "com espaco")
    assert len(elevenlabs.guardar_chave(motor, f"  {CHAVE}\n")) == 3
    assert motor.arquivo_chave.read_text().strip() == CHAVE
    assert stat.S_IMODE(motor.arquivo_chave.stat().st_mode) == 0o600


def test_escolha_desconhecida_ou_quebrada_volta_ao_cadu(tmp_path: Path) -> None:
    arquivo = tmp_path / "voz.json"
    arquivo.write_text("{quebrado")
    assert elevenlabs.ler_escolha(arquivo) == elevenlabs.Escolha()
    arquivo.write_text(json.dumps({"motor": "outro", "voz": "x"}))
    assert elevenlabs.ler_escolha(arquivo) == elevenlabs.Escolha()


def test_motivos_da_recusa_em_uma_linha() -> None:
    corpo = json.dumps({"detail": {"status": "voice_not_found", "message": "x"}}).encode()
    assert elevenlabs.motivo(400, corpo) == "Essa voz não existe mais na conta."
    assert elevenlabs.motivo(429, b"") == "Limite de pedidos do ElevenLabs."
    assert elevenlabs.motivo(500, b"<html>") == "Erro do ElevenLabs (500)."
    corpo = json.dumps({"detail": {"message": "algo   deu\nerrado"}}).encode()
    assert elevenlabs.motivo(422, corpo) == "Erro do ElevenLabs (422): algo deu errado."


# --- o painel -----------------------------------------------------------------------------------


def _painel(tmp_path: Path, endereco: str) -> tuple[Acoes, Any, list[str]]:
    faladas: list[str] = []
    motor = _motor(tmp_path, endereco)
    eventos = SimpleNamespace(put=lambda evento: faladas.append(evento.texto))
    nucleo = SimpleNamespace(motor_voz=motor, eventos=eventos)
    return Acoes(nucleo, tmp_path, tmp_path), motor, faladas


def test_colar_a_chave_ja_passa_a_falar_pelo_elevenlabs(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    _, endereco = api
    acoes, motor, faladas = _painel(tmp_path, endereco)
    with pytest.raises(PedidoInvalido, match="Chave inválida"):
        acoes.guardar_chave_sintese({"chave": "errada"})
    r = acoes.guardar_chave_sintese({"chave": CHAVE})
    assert r["aviso"] == "Chave salva. Voz: Bruno."
    assert (r["motor"], r["voz"], r["chave"]) == (
        "elevenlabs",
        "v-masculina-pt",
        {"tem": True, "fim": CHAVE[-4:]},
    )
    assert CHAVE not in json.dumps(r)
    assert motor.nuvem
    assert faladas == ["Oi! Agora eu falo com a voz Bruno."]  # ouve na hora como ficou

    r = acoes.escolher_sintese({"motor": "elevenlabs", "voz": "v-feminina-pt"})
    assert (r["voz"], r["nome"], r["aviso"]) == ("v-feminina-pt", "Ana", "Voz: Ana.")
    with pytest.raises(PedidoInvalido, match="Voz desconhecida"):
        acoes.escolher_sintese({"motor": "elevenlabs", "voz": "nao-existe"})

    r = acoes.escolher_sintese({"motor": "piper"})
    assert (r["motor"], r["aviso"]) == ("piper", "Voz: Cadu.")
    assert faladas[-1] == "Oi! Agora eu falo com a voz do Cadu."
    assert not motor.nuvem
    r = acoes.escolher_sintese({"motor": "elevenlabs"})  # volta para a voz de antes
    assert (r["motor"], r["nome"]) == ("elevenlabs", "Ana")

    r = acoes.apagar_chave_sintese({})
    assert (r["motor"], r["chave"]["tem"], r["vozes"]) == ("piper", False, [])
    with pytest.raises(PedidoInvalido, match="Cole a chave"):
        acoes.escolher_sintese({"motor": "elevenlabs"})


def test_a_tela_mostra_a_lista_de_vozes_da_chave_guardada(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    _, endereco = api
    acoes, motor, _ = _painel(tmp_path, endereco)
    (tmp_path / "elevenlabs.key").write_text(CHAVE)
    motor.recarregar()
    r = acoes.sintese()
    assert [v["nome"] for v in r["vozes"]] == ["Bruno", "Ana", "Rachel"]
    assert r["cadastro"].startswith("https://elevenlabs.io/")
    assert r["erro"] == ""


def test_fluxo_pcm_junta_bytes_partidos() -> None:
    """Um pedaço da rede pode partir uma amostra ao meio: o byte que sobra vai para o próximo."""

    class Resposta(io.BytesIO):
        def read1(self, n: int | None = -1, /) -> bytes:
            return super().read1(3)

    pcm = np.array([1000, -2000, 3000], "<i2").tobytes()
    devolvida: list[bool] = []
    fluxo = elevenlabs.FluxoPcm(Resposta(pcm), devolvida.append)  # type: ignore[arg-type]
    amostras = np.frombuffer(_ler(fluxo), "<f4")
    assert np.allclose(amostras * 32768, [1000, -2000, 3000])
    assert devolvida == [True]


def test_a_fila_de_fala_toca_o_elevenlabs_de_ponta_a_ponta(
    tmp_path: Path, api: tuple[Api, str]
) -> None:
    """A `Voz` de verdade (fila, folga, reprodutor) com o motor: as duas frases tocam inteiras,
    na taxa do ElevenLabs, pela mesma conexão."""
    estado, endereco = api
    motor = _motor(tmp_path, endereco, ESCOLHIDA)
    tocado = tmp_path / "tocado.raw"
    taxas: list[int] = []

    def reprodutor(taxa: int) -> list[str]:
        taxas.append(taxa)
        return ["/bin/sh", "-c", f"cat >> {tocado}"]

    ociosa = threading.Event()
    voz = Voz(abrir_fluxo=motor.abrir_fluxo, folga_s=0, reprodutor=reprodutor)
    voz.ao_ficar_ociosa = lambda n: ociosa.set()
    voz.falar("Primeira frase da resposta. Segunda frase, que vem logo depois.")
    assert ociosa.wait(5) and voz.ultimo_erro is None
    assert taxas == [24000, 24000]
    assert len(tocado.read_bytes()) == 2 * len(AUDIO) * 4  # float32, as duas frases
    assert [p["corpo"]["text"] for p in estado.pedidos] == [
        "Primeira frase da resposta.",
        "Segunda frase, que vem logo depois.",
    ]
    assert estado.conexoes == 1
