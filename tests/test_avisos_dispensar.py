"""O Dispensar do sino e os links para fora no painel do PC (ADR 0142).

Caso de 25/11/2026: um lead que não pedia resposta ficava no sino sem
como tirar, e "Responder" abria o WhatsApp no lugar do Zérvis, na janela do Zé, sem como voltar.
"""

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos import lidos
from zervis.nucleo import precisa
from zervis.portal.acoes import Acoes, inicio
from zervis.portal.servidor import PedidoInvalido
from zervis.sistema import navegador_padrao

LEAD = precisa.Item(
    "lead:l1", "atendimento", "WhatsApp", "Responder Ana", "“Combinado, obrigada”", 10.0,
    "alerta", "Responder", "https://wa.me/5581999990000",
)  # fmt: skip
VIDEO = precisa.Item("video:v1", "marketing", "Marketing", "Revisar o vídeo", "Tema")
APROVACAO = precisa.Item("aprovacao:a1", "inicio", "WhatsApp", "Aprovação pendente", aprovacao="a1")


@pytest.fixture
def marcas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> lidos.Lidos:
    m = lidos.Lidos(tmp_path / "lidos.db")
    monkeypatch.setattr(lidos, "PADRAO", m)
    return m


def test_dispensado_conta_como_visto_e_lido() -> None:
    assert lidos.COMO == ("visto", "lido", "dispensado")


def test_dispensar_tira_da_lista_ate_o_item_mudar(
    marcas: lidos.Lidos, monkeypatch: pytest.MonkeyPatch
) -> None:
    lista = [VIDEO, LEAD]
    monkeypatch.setattr(precisa, "FONTES", (lambda _: list(lista),))
    fontes: Any = None
    marcas.marcar([precisa.chave(VIDEO)], "dispensado")
    assert marcas.estado([precisa.chave(VIDEO)])[precisa.chave(VIDEO)] == {
        "visto", "lido", "dispensado",
    }  # fmt: skip
    assert precisa.montar(fontes) == [LEAD]  # no sino, no Início e na voz
    lista[0] = VIDEO._replace(detalhe="Outro tema")  # mudou: volta
    assert [i.id for i in precisa.montar(fontes)] == ["lead:l1", "video:v1"]


def _acoes(tmp_path: Path, dispensados: list[str]) -> Acoes:
    def dispensar_lead(ident: str) -> str:
        dispensados.append(ident)
        return "Certo."

    n = SimpleNamespace(linha=SimpleNamespace(entre=lambda *a: []), dispensar_lead=dispensar_lead)
    return Acoes(n, tmp_path, tmp_path)


def test_o_x_do_lead_e_o_ja_vi_e_a_aprovacao_nao_se_dispensa(
    tmp_path: Path, marcas: lidos.Lidos, monkeypatch: pytest.MonkeyPatch
) -> None:
    lista = [APROVACAO, LEAD, VIDEO]
    monkeypatch.setattr(precisa, "FONTES", (lambda _: list(lista),))
    monkeypatch.setattr(inicio.AcoesInicio, "_fontes", lambda self: None)
    dispensados: list[str] = []
    acoes = _acoes(tmp_path, dispensados)
    dispensar = acoes.escritas()["avisos/dispensar"]

    sino = dispensar({"chave": precisa.chave(LEAD)})
    assert dispensados == ["l1"]  # o lead para de lembrar, também no celular
    assert [i["id"] for i in sino["itens"]] == ["aprovacao:a1", "video:v1"]
    sino = dispensar({"chave": precisa.chave(VIDEO)})
    assert [i["id"] for i in sino["itens"]] == ["aprovacao:a1"]
    with pytest.raises(PedidoInvalido):
        dispensar({"chave": precisa.chave(APROVACAO)})
    assert dispensar({"chave": "0" * 16})["itens"]  # já saiu ou não existe: nada muda
    with pytest.raises(PedidoInvalido):  # o "visto" e o "lido" continuam os únicos por lá
        acoes.escritas()["avisos/marcar"]({"chaves": ["0" * 16], "como": "dispensado"})


def test_no_computador_o_whatsapp_abre_no_whatsapp_web() -> None:
    assert navegador_padrao.no_computador("https://wa.me/5581999990000") == (
        "https://web.whatsapp.com/send?phone=5581999990000"
    )
    maps = "https://maps.google.com/?cid=1"
    assert navegador_padrao.no_computador(maps) == maps
    for ruim in ("javascript:alert(1)", "file:///etc/passwd", "https://", ""):
        with pytest.raises(navegador_padrao.LinkErro):
            navegador_padrao.validar(ruim)


def test_abre_no_navegador_padrao_fora_do_servico(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[list[str]] = []

    def rodar(comando: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        chamadas.append(comando)
        return subprocess.CompletedProcess(comando, 0)

    monkeypatch.setattr(subprocess, "run", rodar)
    monkeypatch.setattr(shutil, "which", lambda nome: f"/usr/bin/{nome}")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    aberto = navegador_padrao.abrir("https://wa.me/5581999990000")
    assert aberto == "https://web.whatsapp.com/send?phone=5581999990000"
    # Pelo systemd-run: reiniciar o Zé não fecha o navegador de quem usa.
    assert chamadas == [
        [
            "/usr/bin/systemd-run",
            "--user",
            "--collect",
            "--quiet",
            "--",
            "/usr/bin/xdg-open",
            aberto,
        ]
    ]
    monkeypatch.delenv("WAYLAND_DISPLAY")
    with pytest.raises(navegador_padrao.LinkErro):  # a VPS, sem tela: o painel abre sozinho
        navegador_padrao.abrir("https://wa.me/5581999990000")
