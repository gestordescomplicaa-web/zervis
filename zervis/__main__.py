"""Ponto de entrada do `jarvisd`."""

import logging
import signal
import sys
import threading

from zervis import __version__


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
    from zervis.config import ConfigInvalida, carregar
    from zervis.nucleo.instancia import JaRodando, travar
    from zervis.nucleo.laco import ESTADO, Nucleo

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("jarvisd")
    from zervis import caminhos

    caminhos.completar()  # o serviço sobe com PATH mínimo: acha os agentes nas pastas pessoais
    try:
        cfg = carregar()
    except ConfigInvalida as erro:
        log.error("configuração inválida: %s", erro)
        return 78  # EX_CONFIG: o systemd não fica reiniciando uma config quebrada
    from zervis.preparar import PrepararErro, garantir

    try:
        if baixados := garantir(cfg.caminho("ativacao", "modelos_onnx")):
            log.info("primeira vez: baixei %s", ", ".join(baixados))
    except PrepararErro as erro:
        # Falha por função (ADR 0034): o painel e o texto sobem; o que precisa do modelo que
        # faltou fica indisponível até o próximo início com internet.
        log.warning("%s: a voz fica limitada (rode `python -m zervis.preparar`)", erro)
    from zervis.memoria import aimemory

    try:  # opcional: sem ele, o Zé segue sem memória longa
        if aimemory.garantir():
            log.info("primeira vez: baixei o ai-memory %s", aimemory.VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("ai-memory não baixou (%s): o Zé segue sem memória longa", erro)
    from zervis.transporte import servidor_livekit

    try:  # opcional: sem ele, a voz remota fica indisponível
        if servidor_livekit.garantir():
            log.info("primeira vez: baixei o LiveKit %s", servidor_livekit.VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("LiveKit não baixou (%s): a voz remota fica indisponível", erro)
    from zervis.cerebro import agentes_nativos

    try:  # o Codex vem com o Zé (ADR 0035); sem ele, o cérebro e as sessões ficam no Claude
        if agentes_nativos.garantir_codex():
            log.info("primeira vez: baixei o Codex %s", agentes_nativos.CODEX_VERSAO)
    except (PrepararErro, OSError) as erro:
        log.warning("Codex não baixou (%s): fica só o Claude", erro)
    agentes_nativos.no_path()
    try:
        trava = travar(ESTADO / "jarvisd.lock")
    except JaRodando as erro:
        log.error("%s", erro)
        return 75
    parar = threading.Event()

    def encerrar(*_: object) -> None:
        # O systemd manda o SIGTERM ao grupo inteiro: os agentes do cérebro e o servidor da sala
        # saem junto com o Zé, e os SDKs registravam isso como erro a cada parada (16/10/2026).
        for sdk in ("claude_agent_sdk", "livekit"):
            logging.getLogger(sdk).setLevel(logging.CRITICAL)
        parar.set()

    signal.signal(signal.SIGTERM, encerrar)
    signal.signal(signal.SIGINT, encerrar)
    log.info("jarvisd %s subindo", __version__)
    with trava:
        Nucleo(cfg, parar).rodar()
    log.info("jarvisd parado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
