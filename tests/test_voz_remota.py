"""A voz remota (plano da voz remota, etapa 1): sala, token, entrada e saída de áudio."""

import asyncio
import base64
import hashlib
import hmac
import json
import queue
import stat
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from livekit import rtc

from jarvis.transporte import local as local_
from jarvis.transporte import remoto as remoto_
from jarvis.transporte import servidor_livekit as lk
from jarvis.transporte.entrada import Entrada
from jarvis.transporte.remoto import TAXA_SAIDA, TocadorRemoto
from jarvis.voz.saida import FluxoPronto, Voz


def _decodificar(parte: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4)))


def test_token_assinado_so_para_a_sala_e_o_microfone() -> None:
    t = lk.token("chave", "s" * 32, "pessoa-1", "Ana", agora=1000, validade_s=600)
    cabeca, corpo, assinatura = t.split(".")
    esperado = hmac.new(b"s" * 32, f"{cabeca}.{corpo}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(assinatura + "=" * (-len(assinatura) % 4)) == esperado
    assert _decodificar(cabeca) == {"alg": "HS256", "typ": "JWT"}
    carga = _decodificar(corpo)
    assert (carga["iss"], carga["sub"], carga["name"]) == ("chave", "pessoa-1", "Ana")
    assert carga["exp"] == 1600 and carga["nbf"] <= 1000
    assert carga["video"]["room"] == lk.SALA and carga["video"]["roomJoin"]
    assert carga["video"]["canPublishSources"] == ["microphone"]
    assert not carga["video"]["canPublishData"]


def test_credenciais_criadas_uma_vez_e_so_do_usuario(tmp_path: Path) -> None:
    arquivo = tmp_path / "livekit.json"
    chave, segredo = lk.credenciais(arquivo)
    assert len(segredo) >= 32 and chave.startswith("ze")
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert lk.credenciais(arquivo) == (chave, segredo)
    arquivo.write_text("{quebrado")
    assert lk.credenciais(arquivo) != (chave, segredo)


def test_servidor_so_no_endereco_local() -> None:
    rede = json.loads(lk.configuracao(7880, "100.64.0.7"))
    assert rede["bind_addresses"] == ["127.0.0.1"] and "node_ip" not in rede["rtc"]
    assert rede["rtc"]["ips"]["includes"] == ["127.0.0.1/32", "100.64.0.7/32"]
    casa = json.loads(lk.configuracao(7880, "100.64.0.7", "192.168.0.6"))
    assert casa["rtc"]["ips"]["includes"][-1] == "192.168.0.6/32"
    cfg = json.loads(lk.configuracao(7880))
    assert cfg["bind_addresses"] == ["127.0.0.1"]
    assert not cfg["rtc"]["use_external_ip"]
    assert (cfg["rtc"]["tcp_port"], cfg["rtc"]["udp_port"]) == (0, 7882)
    assert cfg["rtc"]["ips"]["includes"] == ["127.0.0.1/32"]
    assert cfg["rtc"]["enable_loopback_candidate"]


def test_sem_binario_a_voz_remota_fica_indisponivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lk, "porta_ocupada", lambda porta: False)
    monkeypatch.setattr(lk, "binario", lambda pasta=lk.PASTA: None)
    assert not lk.ServidorLiveKit(arquivo=tmp_path / "lk.json").iniciar()


class CapturaFalsa:
    def __init__(self) -> None:
        self.quadros: queue.Queue[bytes] = queue.Queue(maxsize=3)
        self.aberta = False

    def abrir(self) -> None:
        self.aberta = True

    def fechar(self) -> None:
        self.aberta = False


def test_voz_remota_tem_a_vez_e_o_microfone_local_volta() -> None:
    local = CapturaFalsa()
    entrada = Entrada(local)  # type: ignore[arg-type]
    entrada.receber(b"a")
    assert entrada.quadros.empty()  # fechada: nada entra
    entrada.abrir()
    assert local.aberta
    entrada.remota(True)
    assert not local.aberta and entrada.aberta
    for q in (b"1", b"2", b"3", b"4"):
        entrada.receber(q)
    assert [entrada.quadros.get_nowait() for _ in range(3)] == [b"2", b"3", b"4"]
    entrada.remota(False)
    assert local.aberta
    entrada.fechar()
    entrada.remota(True)
    entrada.remota(False)
    assert not local.aberta  # fechada continua fechada


def test_sem_audio_na_maquina_a_voz_remota_continua(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """VPS sem PulseAudio: abrir o microfone derrubava o laço inteiro (lição de 16/10/2026)."""

    def sem_parec(dispositivo: str) -> Any:
        raise FileNotFoundError(2, "No such file or directory", "/usr/bin/parec")

    monkeypatch.setattr(local_, "fonte", lambda d: d)
    captura = local_.Captura()
    monkeypatch.setattr(captura, "_parec", sem_parec)
    entrada = Entrada(captura)
    entrada.abrir()
    entrada.abrir()  # de novo: o aviso sai uma vez só
    assert not captura.aberta and captura.indisponivel is not None
    assert caplog.text.count("microfone local indisponível") == 1
    entrada.remota(True)
    entrada.receber(b"q")
    assert entrada.quadros.get_nowait() == b"q"


class SalaFalsa:
    def __init__(self) -> None:
        self.quadros: list[rtc.AudioFrame] = []
        self.esperou = self.limpou = False

    def enviar(self, quadro: rtc.AudioFrame) -> None:
        self.quadros.append(quadro)

    def esperar_tocar(self) -> None:
        self.esperou = True

    def limpar(self) -> None:
        self.limpou = True


def test_tocador_remoto_converte_e_reamostra() -> None:
    sala = SalaFalsa()
    t = TocadorRemoto(sala, 22050)  # type: ignore[arg-type]
    onda = np.sin(np.linspace(0, 400, 22050)).astype("<f4").tobytes()
    t.stdin.write(onda[:5])  # pedaço quebrado no meio de uma amostra
    t.stdin.write(onda[5:])
    t.stdin.close()
    assert t.poll() is None and t.wait() == 0 and sala.esperou
    total = sum(q.samples_per_channel for q in sala.quadros)
    assert {q.sample_rate for q in sala.quadros} == {TAXA_SAIDA}
    assert abs(total - TAXA_SAIDA) < 2000  # um segundo de áudio continua um segundo
    t2 = TocadorRemoto(sala, TAXA_SAIDA)  # type: ignore[arg-type]
    t2.kill()
    assert sala.limpou and t2.wait() == -9
    with pytest.raises(BrokenPipeError):
        t2.stdin.write(b"\0" * 8)


def test_voz_sai_pelo_destino_quando_ha_um() -> None:
    sala = SalaFalsa()
    amostras = np.full(2205, 0.25, dtype="<f4").tobytes()
    voz = Voz(abrir_fluxo=lambda texto: (22050, FluxoPronto(amostras)), folga_s=0)
    voz.destino = lambda taxa: TocadorRemoto(sala, taxa)  # type: ignore[arg-type]
    falas: queue.Queue[int] = queue.Queue()
    voz.ao_ficar_ociosa = falas.put
    voz.falar("Oi.")
    assert falas.get(timeout=5) == 1
    assert voz.ultimo_erro is None and sala.quadros and sala.esperou


def test_segmentador_segurando_so_fecha_ao_soltar() -> None:
    from jarvis.voz.escuta import Segmentador

    s = Segmentador(fim_silencio_s=0.16, segurando=True)
    voz, silencio = b"\1\0" * 1280, b"\0\0" * 1280
    for q in (voz, voz, silencio, silencio, silencio, silencio):
        assert s.quadro(q, q is voz) is None  # a pausa não fecha com o botão apertado
    trecho = s.fechar()
    assert trecho is not None and trecho.startswith(voz)
    assert s.fechar() is None  # sem fala, nada


def test_ativacao_pelo_botao_guardada(tmp_path: Path) -> None:
    from jarvis.voz import chamado

    arquivo = tmp_path / "chamado.json"
    assert chamado.ler(arquivo) == "voz"
    assert chamado.gravar("botao", arquivo) == "botao" and chamado.ler(arquivo) == "botao"
    with pytest.raises(ValueError):
        chamado.gravar("assobio", arquivo)


def test_a_sala_espera_o_servidor_abrir_a_porta() -> None:
    """Entrar antes de o livekit-server abrir a porta deixava três erros a cada subida."""
    tentativas = iter([False, False, True])
    assert asyncio.run(remoto_.esperar(lambda: next(tentativas), 1.0, passo_s=0.01))
    assert not asyncio.run(remoto_.esperar(lambda: False, 0.05, passo_s=0.01))
