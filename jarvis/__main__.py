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
    from jarvis import caminhos

    caminhos.completar()  # o serviço sobe com PATH mínimo: acha os agentes nas pastas pessoais
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
        # Falha por função (ADR 0034): o painel e o texto sobem; o que precisa do modelo que
        # faltou fica indisponível até o próximo início com internet.
        log.warning("%s: a voz fica limitada (rode `python -m jarvis.preparar`)", erro)
    from jarvis.memoria import aimemory

    try:  # opcional: sem ele, o Zé segue sem memória longa
        if aimemory.garantir():
            log.info("primeira vez: baixei o ai-memory %s", aimemory.VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("ai-memory não baixou (%s): o Zé segue sem memória longa", erro)
    from jarvis.transporte import servidor_livekit

    try:  # opcional: sem ele, a voz remota fica indisponível
        if servidor_livekit.garantir():
            log.info("primeira vez: baixei o LiveKit %s", servidor_livekit.VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("LiveKit não baixou (%s): a voz remota fica indisponível", erro)
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
