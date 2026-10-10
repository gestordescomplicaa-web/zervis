"""Ponto de entrada do `jarvisd`."""

import logging
import signal
import sys
import threading

from jarvis import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--version"]:
        print(f"jarvisd {__version__}")
        return 0
    if args:
        print(f"jarvisd: argumento desconhecido: {' '.join(args)}", file=sys.stderr)
        return 2
    return rodar()


def rodar() -> int:
    # Importações pesadas (onnxruntime, numpy) só quando o serviço sobe de fato.
    from jarvis.config import ConfigInvalida, carregar
    from jarvis.nucleo.instancia import JaRodando, travar
    from jarvis.nucleo.laco import ESTADO, Nucleo

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("jarvisd")
    try:
        cfg = carregar()
    except ConfigInvalida as erro:
        log.error("configuração inválida: %s", erro)
        return 78  # EX_CONFIG: o systemd não fica reiniciando uma config quebrada
    from jarvis.preparar import PrepararErro, garantir

    try:
        if baixados := garantir(cfg.caminho("ativacao", "modelos_onnx")):
            log.info("primeira vez: baixei %s", ", ".join(baixados))
    except PrepararErro as erro:
        log.error("%s (rode `python -m jarvis.preparar` com internet)", erro)
        return 69  # EX_UNAVAILABLE
    from jarvis.memoria import aimemory

    try:  # opcional: sem ele, o Zé segue sem memória longa
        if aimemory.garantir():
            log.info("primeira vez: baixei o ai-memory %s", aimemory.VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("ai-memory não baixou (%s): o Zé segue sem memória longa", erro)
    try:
        trava = travar(ESTADO / "jarvisd.lock")
    except JaRodando as erro:
        log.error("%s", erro)
        return 75
    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: parar.set())
    signal.signal(signal.SIGINT, lambda *_: parar.set())
    log.info("jarvisd %s subindo", __version__)
    with trava:
        Nucleo(cfg, parar).rodar()
    log.info("jarvisd parado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
