"""O túnel do Cloudflare (roteiro, passo 4.3): o endereço lido e a escolha guardada."""

import base64
import io
import json
import stat
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from zervis.portal import tunel


def test_le_o_endereco_que_o_cloudflared_imprime() -> None:
    linha = (
        "2026-10-12T21:50:01Z INF |  https://utilize-inline-baby-simulations.trycloudflare.com  |"
    )
    achado = tunel.ENDERECO.search(linha)
    assert achado and achado.group(0) == "https://utilize-inline-baby-simulations.trycloudflare.com"


def test_escolha_sobrevive_ao_reinicio(tmp_path: Path) -> None:
    arquivo = tmp_path / "tunel.json"
    assert not tunel.escolhido(arquivo)
    tunel.escolher(True, arquivo)
    assert tunel.escolhido(arquivo)
    tunel.escolher(False, arquivo)
    assert not tunel.escolhido(arquivo)


def _falso(pasta: Path) -> Path:
    """Um cloudflared de mentira: a primeira subida cai logo; a segunda fica de pé."""
    programa = pasta / "cloudflared"
    programa.write_text(
        "#!/bin/sh\n"
        f'n=$(cat "{pasta}/n" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{pasta}/n"\n'
        'echo "INF |  https://tunel-$n.trycloudflare.com  |" >&2\n'
        '[ "$n" -ge 2 ] && exec sleep 30\n'
    )
    programa.chmod(0o755)
    return programa


def _esperar(condicao: Callable[[], bool]) -> None:
    fim = time.monotonic() + 10
    while not condicao():
        assert time.monotonic() < fim
        time.sleep(0.02)


def test_sobe_de_novo_sozinho_quando_cai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tunel, "ESPERA_S", (0.05,))
    prontos: list[str] = []
    caidos: list[str] = []
    t = tunel.Tunel(prontos.append, caidos.append, tunel.Direto(), tmp_path / "cf.log")
    t.iniciar(8795, _falso(tmp_path))
    try:
        _esperar(lambda: t.endereco == "https://tunel-2.trycloudflare.com")
        assert prontos == ["https://tunel-1.trycloudflare.com", "https://tunel-2.trycloudflare.com"]
        assert caidos == ["https://tunel-1.trycloudflare.com"]
    finally:
        t.parar()
    assert not t.ativo and t.endereco == ""


def test_parado_de_proposito_nao_sobe_de_novo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tunel, "ESPERA_S", (0.05,))
    (tmp_path / "n").write_text("1")  # já na subida que fica de pé
    caidos: list[str] = []
    t = tunel.Tunel(lambda _: None, caidos.append, tunel.Direto(), tmp_path / "cf.log")
    t.iniciar(8795, _falso(tmp_path))
    _esperar(lambda: bool(t.endereco))
    t.parar()
    time.sleep(0.3)
    assert not t.ativo and caidos == []
    assert (tmp_path / "n").read_text().strip() == "2"


def test_binario_da_maquina_tem_preferencia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zervis.portal.tunel.shutil.which", lambda nome: "/usr/bin/cloudflared")
    assert tunel.binario(tmp_path) == Path("/usr/bin/cloudflared")
    monkeypatch.setattr("zervis.portal.tunel.shutil.which", lambda nome: None)
    assert tunel.binario(tmp_path) is None
    (tmp_path / "cloudflared").write_text("")
    assert tunel.binario(tmp_path) == tmp_path / "cloudflared"


def test_encerrado_de_fora_nao_e_queda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O serviço parando: o systemd encerra o cloudflared junto. Não é falha nem sobe de novo."""
    from zervis import atividade

    monkeypatch.setattr(tunel, "ESPERA_S", (0.05,))
    falhas: list[str] = []
    monkeypatch.setattr(atividade.PADRAO, "registrar", lambda tipo, *a, **k: falhas.append(tipo))
    (tmp_path / "n").write_text("1")
    t = tunel.Tunel(lambda _: None, None, tunel.Direto(), tmp_path / "cf.log")
    t.iniciar(8795, _falso(tmp_path))
    _esperar(lambda: bool(t.endereco))
    assert isinstance(t.lancador, tunel.Direto) and t.lancador.processo is not None
    t.lancador.processo.terminate()
    _esperar(lambda: t.endereco == "")
    time.sleep(0.3)
    assert falhas == [] and (tmp_path / "n").read_text().strip() == "2"
    t.parar()


class _Vivo:
    """Um lançador que diz que o cloudflared continua no ar (o serviço próprio sobreviveu)."""

    def __init__(self) -> None:
        self.iniciados = 0

    def ativo(self) -> bool:
        return True

    def codigo(self) -> int | None:
        return None

    def iniciar(self, comando: list[str], registro: Path) -> None:
        self.iniciados += 1

    def parar(self) -> None:
        pass


def test_ze_reinicia_e_reencontra_o_tunel_no_mesmo_endereco(tmp_path: Path) -> None:
    """14/10/2026: cada reinício do Zé trocava o endereço, e o celular pedia login de novo."""
    registro = tmp_path / "cf.log"
    registro.write_text("INF |  https://mesmo-endereco-de-antes.trycloudflare.com  |\n")
    prontos: list[str] = []
    lancador = _Vivo()
    t = tunel.Tunel(prontos.append, None, lancador, registro)  # type: ignore[arg-type]
    t.iniciar(8795, tmp_path / "cloudflared")
    assert prontos == ["https://mesmo-endereco-de-antes.trycloudflare.com"]
    assert lancador.iniciados == 0  # não subiu outro
    t.soltar()  # o Zé parando: o túnel fica


def test_tunel_de_pe_sem_endereco_anotado_sobe_de_novo(tmp_path: Path) -> None:
    """Reinstalação na VPS (16/10/2026): o registro foi apagado e o serviço do túnel continuou de
    pé. Sem parar, o novo, de mesmo nome, não subia, e o endereço nunca aparecia."""
    registro = tmp_path / "cf.log"

    class Orfao(_Vivo):
        def __init__(self) -> None:
            super().__init__()
            self.paradas = 0
            self.vivo = True

        def ativo(self) -> bool:
            return self.vivo

        def parar(self) -> None:
            self.paradas += 1
            self.vivo = False

        def iniciar(self, comando: list[str], registro: Path) -> None:
            self.iniciados += 1
            self.vivo = True

    lancador = Orfao()
    t = tunel.Tunel(lambda e: None, None, lancador, registro)  # type: ignore[arg-type]
    t.iniciar(8795, tmp_path / "cloudflared")
    assert lancador.paradas == 1 and lancador.iniciados == 1
    t.soltar()


# --- o túnel fixo, num domínio da pessoa (26/10/2026) ---

TOKEN_FALSO = base64.b64encode(
    json.dumps({"a": "conta-exemplo", "t": "0f0f0f0f-tunel", "s": "segredo-de-exemplo"}).encode()
).decode()


@pytest.mark.parametrize(
    "colado",
    [
        f"sudo cloudflared service install {TOKEN_FALSO}",
        f"cloudflared.exe service install {TOKEN_FALSO}",
        f"cloudflared tunnel run --token {TOKEN_FALSO}\n",
        TOKEN_FALSO.rstrip("="),
    ],
)
def test_le_o_token_do_comando_que_o_cloudflare_mostra(colado: str) -> None:
    assert tunel.ler_token(colado).rstrip("=") == TOKEN_FALSO.rstrip("=")


@pytest.mark.parametrize(
    "colado",
    [
        "",
        "cloudflared service install",
        "eyJ" + "A" * 60,
        base64.b64encode(b'{"x": 1}' * 8).decode(),
    ],
)
def test_recusa_o_que_nao_e_token_de_tunel(colado: str) -> None:
    with pytest.raises(tunel.TunelErro):
        tunel.ler_token(colado)


@pytest.mark.parametrize(
    ("digitado", "endereco"),
    [
        ("ze.exemplo.com.br", "https://ze.exemplo.com.br"),
        ("https://Ze.Exemplo.com.br/", "https://ze.exemplo.com.br"),
        ("http://ze.exemplo.com.br/entrar", "https://ze.exemplo.com.br"),
    ],
)
def test_endereco_digitado_vira_https(digitado: str, endereco: str) -> None:
    assert tunel.ler_endereco(digitado) == endereco


@pytest.mark.parametrize(
    "digitado", ["", "ze", "abc.trycloudflare.com", "ze exemplo.com", "-x.com"]
)
def test_recusa_endereco_que_nao_e_um_dominio(digitado: str) -> None:
    with pytest.raises(tunel.TunelErro):
        tunel.ler_endereco(digitado)


def test_token_fica_num_arquivo_0600_e_a_escolha_guarda_o_endereco(tmp_path: Path) -> None:
    escolha, token = tmp_path / "tunel.json", tmp_path / "tunel-token"
    assert tunel.fixo(escolha, token) == ""
    endereco = tunel.guardar_fixo(
        f"cloudflared service install {TOKEN_FALSO}", "ze.exemplo.com.br", escolha, token
    )
    assert endereco == tunel.fixo(escolha, token) == "https://ze.exemplo.com.br"
    assert token.read_text() == TOKEN_FALSO and stat.S_IMODE(token.stat().st_mode) == 0o600
    assert TOKEN_FALSO not in escolha.read_text()  # o segredo só no arquivo dele
    tunel.escolher(True, escolha)  # ligar e desligar não apaga o endereço fixo
    assert tunel.escolhido(escolha) and tunel.fixo(escolha, token)
    tunel.esquecer_fixo(escolha, token)
    assert not token.exists() and tunel.fixo(escolha, token) == "" and tunel.escolhido(escolha)


def test_tunel_fixo_sobe_pelo_arquivo_do_token_e_fica_pronto_ao_conectar(tmp_path: Path) -> None:
    escolha, token = tmp_path / "tunel.json", tmp_path / "tunel-token"
    tunel.guardar_fixo(TOKEN_FALSO, "ze.exemplo.com.br", escolha, token)
    programa = tmp_path / "cloudflared"
    programa.write_text(
        "#!/bin/sh\n"
        f'echo "$@" > "{tmp_path}/argumentos"\n'
        "echo 'INF Registered tunnel connection connIndex=0 location=gru' >&2\n"
        "exec sleep 30\n"
    )
    programa.chmod(0o755)
    prontos: list[str] = []
    t = tunel.Tunel(prontos.append, None, tunel.Direto(), tmp_path / "cf.log", escolha, token)
    t.iniciar(8796, programa)
    try:
        _esperar(lambda: t.endereco == "https://ze.exemplo.com.br")
        assert prontos == ["https://ze.exemplo.com.br"]
        argumentos = (tmp_path / "argumentos").read_text()
        assert f"run --token-file {token}" in argumentos
        assert TOKEN_FALSO not in argumentos  # nunca na linha de comando (ps, systemctl)
    finally:
        t.parar()


def test_confere_se_o_endereco_chega_a_este_painel() -> None:
    from zervis.nucleo.servicos.remoto import chega_ao_painel

    class Resposta(io.BytesIO):
        def __enter__(self) -> "Resposta":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    assert chega_ao_painel(
        "https://ze.exemplo.com.br", lambda *_a, **_k: Resposta('{"name": "Zérvis"}'.encode())
    )
    assert not chega_ao_painel(
        "https://ze.exemplo.com.br", lambda *_a, **_k: Resposta(b"<html>outro site")
    )

    def sem_rede(*_a: object, **_k: object) -> Resposta:
        raise OSError("sem rede")

    assert not chega_ao_painel("https://ze.exemplo.com.br", sem_rede)
