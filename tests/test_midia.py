"""O Zé tem a vez: a mídia pausa enquanto ele ouve ou fala e volta depois (achado 8)."""

from types import SimpleNamespace
from typing import Any

from zervis.sistema.midia import Midia


class _Busctl:
    def __init__(self, estados: dict[str, str]) -> None:
        self.estados = estados
        self.chamadas: list[tuple[str, str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> SimpleNamespace:
        args = cmd[2:]
        if args[0] == "list":
            nomes = "\n".join(f"{n} 123 chromium" for n in self.estados) + "\n:1.5 99 outro"
            return SimpleNamespace(returncode=0, stdout=nomes)
        player = args[1]
        if args[0] == "get-property":
            return SimpleNamespace(returncode=0, stdout=f's "{self.estados[player]}"\n')
        acao = args[-1]
        self.chamadas.append((player, acao))
        self.estados[player] = "Paused" if acao == "Pause" else "Playing"
        return SimpleNamespace(returncode=0, stdout="")


def test_pausa_o_que_toca_e_retoma_so_o_que_pausou() -> None:
    yt, musica = "org.mpris.MediaPlayer2.chromium.instance1", "org.mpris.MediaPlayer2.spotify"
    busctl = _Busctl({yt: "Playing", musica: "Paused"})
    m = Midia(busctl)
    m.pausar()
    assert busctl.chamadas == [(yt, "Pause")] and m.pausados == [yt]
    m.retomar()
    assert busctl.chamadas[-1] == (yt, "Play") and busctl.estados[musica] == "Paused"


def test_nao_retoma_o_que_a_pessoa_mexeu() -> None:
    yt = "org.mpris.MediaPlayer2.chromium.instance1"
    busctl = _Busctl({yt: "Playing"})
    m = Midia(busctl)
    m.pausar()
    busctl.estados[yt] = "Stopped"  # a pessoa fechou o vídeo
    m.retomar()
    assert busctl.chamadas == [(yt, "Pause")]


def test_sem_busctl_nao_quebra() -> None:
    def falha(*_: Any, **__: Any) -> Any:
        raise OSError("sem busctl")

    m = Midia(falha)
    m.pausar()
    m.retomar()
    assert m.pausados == []


def test_a_escolha_vem_da_config_de_verdade(tmp_path: Any) -> None:
    """13/10/2026: a primeira versão tratou a Config como dict e derrubou o Zé ao subir."""
    from zervis.config import carregar
    from zervis.nucleo.laco import Nucleo

    n = SimpleNamespace(cfg=carregar(tmp_path / "nao-existe.toml"))
    assert Nucleo._pausar_midia(n) is True  # type: ignore[arg-type]
