# syntax=docker/dockerfile:1
# A imagem do Zé para a VPS (ADR 0096; ADR 0034, ponto 15): opcional, ao lado do instalador do
# servidor. Base Debian (glibc), um usuário comum, o tini como processo 1 e a casa do usuário
# num volume. Guia: docs/vps.md, "Pelo Docker".
#   docker compose up -d --build
FROM ghcr.io/astral-sh/uv:0.11.32 AS uv

FROM debian:13.7-slim

# git: o histórico local do autodesenvolvimento; make: o `make check` das sessões; tini: recolhe
# os processos que as sessões deixam (sem ele, zumbis contavam como vivos, ADR 0034, D18).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git make tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/

ARG UID=1000
RUN useradd --create-home --uid "${UID}" --shell /bin/bash ze \
    && install -d -o ze -g ze /opt/zervis /opt/uv-python /opt/ferramentas/bin

# O Python e o ambiente ficam na imagem (/opt); a casa (/home/ze) é o volume, com a
# configuração, os dados, os logins dos agentes e os projetos.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    ZERVIS_CONTEINER=1 \
    ZERVIS_PAINEL_PORTA=8795 \
    PATH=/opt/zervis/.venv/bin:/opt/ferramentas/bin:/home/ze/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin

USER ze
WORKDIR /opt/zervis

# As dependências antes do código: mudar o código não baixa tudo de novo.
COPY --chown=ze:ze pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-install-project
COPY --chown=ze:ze . .
RUN uv sync --frozen \
    # O Go do WhatsApp e das ligações, conferido pelo SHA-256 (zervis/atendimento/preparar_go.py),
    # fora do volume, e o mesmo histórico local que o instalador cria num pacote sem .git.
    && XDG_DATA_HOME=/opt/ferramentas .venv/bin/python -m zervis.atendimento.preparar_go \
    && ln -s /opt/ferramentas/zervis/ferramentas/go*/bin/go /opt/ferramentas/bin/go \
    && git init -q \
    && git add -A \
    && git -c user.name=Zérvis -c user.email=zervis@localhost commit -qm "Zé instalado nesta imagem"

VOLUME /home/ze
HEALTHCHECK --interval=30s --timeout=5s --start-period=5m \
    CMD curl --fail --silent --max-time 4 -o /dev/null "http://127.0.0.1:${ZERVIS_PAINEL_PORTA}/" || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/zervis/.venv/bin/python", "-m", "zervis.conteiner"]
