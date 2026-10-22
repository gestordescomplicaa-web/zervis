"""Andamento real da atualização, inclusive depois de trocar o processo."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from zervis.oficina import progresso as mod
from zervis.oficina.progresso import Progresso


class Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> Relogio:
    r = Relogio()
    monkeypatch.setattr(time, "time", r)
    return r


def foto(p: Progresso) -> dict[str, Any]:
    f = p.foto()
    assert f is not None
    return f


def test_reinicio_retoma_pela_hora_da_etapa_e_sobrevive_a_duas_subidas(
    tmp_path: Path, relogio: Relogio
) -> None:
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("testes_copia")
    relogio.agora += 400  # testes demorados não expiram o reinício que ainda nem começou
    p.etapa("juntando")
    p.etapa("testes_ze")
    p.etapa("reiniciando")
    relogio.agora += 10
    for _ in range(2):
        p = Progresso(tmp_path)
        assert foto(p)["estado"] == "aplicando"
        assert foto(p)["etapas"][-1]["estado"] == "atual"
        assert p.reserva() is not None
    p.etapa("pronto")
    assert foto(p)["estado"] == "pronto"
    assert p.reserva() is None
    assert all(e["estado"] == "feita" for e in foto(p)["etapas"])
    assert foto(Progresso(tmp_path))["estado"] == "pronto"
    relogio.agora += mod.MOSTRAR_FIM_S + 1
    assert p.foto() is None


def test_queda_nos_testes_nao_vira_reinicio_nem_sucesso(tmp_path: Path, relogio: Relogio) -> None:
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("testes_copia")
    relogio.agora += 3
    assert foto(Progresso(tmp_path))["estado"] == "falhou"


def test_falha_e_volta_ficam_visiveis_ao_recarregar(tmp_path: Path, relogio: Relogio) -> None:
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("testes_copia")
    relogio.agora += 8
    p.falhou("Os testes falharam.")
    f = foto(Progresso(tmp_path))
    assert f["estado"] == "falhou" and f["texto"] == "Os testes falharam."
    assert f["etapas"][0]["estado"] == "falhou"
    p.comecar()
    p.etapa("reiniciando")
    p = Progresso(tmp_path)
    p.etapa("voltou")
    assert foto(Progresso(tmp_path))["estado"] == "voltou"


def test_reinicio_sem_confirmacao_expira_sem_dizer_que_aplicou(
    tmp_path: Path, relogio: Relogio
) -> None:
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("reiniciando")
    relogio.agora += mod.REINICIO_MAXIMO_S + 1
    assert foto(p)["estado"] == "falhou"
    assert p.reserva() is None
    assert foto(Progresso(tmp_path))["estado"] == "falhou"


def test_apenas_um_pedido_comeca_e_nao_e_substituido_por_espera(tmp_path: Path) -> None:
    p = Progresso(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = list(pool.map(lambda _: p.comecar(), range(16)))
    assert resultados.count(True) == 1
    assert p.aguardar() is False
    assert foto(p)["estado"] == "aplicando"


def test_cancelar_espera_nao_cancela_aplicacao(tmp_path: Path) -> None:
    p = Progresso(tmp_path)
    p.aguardar()
    assert p.reserva() is not None
    p.cancelar_espera()
    assert p.foto() is None
    assert p.reserva() is None
    p.comecar()
    p.cancelar_espera()
    assert foto(p)["estado"] == "aplicando"


def test_arquivo_invalido_nao_impede_subir(tmp_path: Path) -> None:
    (tmp_path / "tempos.json").write_text('{"testes_copia": "inválido", "reiniciando": NaN}')
    (tmp_path / "progresso.json").write_text('{"estado": "aplicando", "inicio": "inválido"}')
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("testes_copia")
    assert foto(p)["etapas"][0]["estimado"] > 0


def test_gravacao_privada_e_atomicidade_do_andamento(tmp_path: Path) -> None:
    p = Progresso(tmp_path)
    p.comecar()
    p.etapa("reiniciando")
    assert json.loads((tmp_path / "progresso.json").read_text())["atual"] == "reiniciando"
    assert (tmp_path / "progresso.json").stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob("*.tmp"))


def test_erro_de_gravacao_do_progresso_nao_interrompe_a_atualizacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Progresso(tmp_path)

    def falhar(*args: Any, **kwargs: Any) -> None:
        raise OSError("disco indisponível")

    monkeypatch.setattr(Path, "replace", falhar)
    p.comecar()
    p.etapa("reiniciando")
    assert foto(p)["estado"] == "aplicando"
    assert not list(tmp_path.glob("*.tmp"))
