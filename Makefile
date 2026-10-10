# Porta única de qualidade (docs/06-qualidade.md): formatação, lint, tipos e testes.
.PHONY: check fmt lint tipos testes check-imersivo

check: lint tipos testes

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

tipos:
	uv run mypy

testes:
	uv run pytest

# O modo imersivo num Chromium de verdade, sem tela (uns minutos): antes de mexer na página.
check-imersivo:
	ZE_TESTES_IMERSIVO=1 uv run --with websockets --with pytest-xdist pytest -q -n 2 tests/imersivo

# Instala o serviço (sem iniciar no login). Os modelos de som são baixados e conferidos pelo
# próprio Zé na primeira subida (jarvis/preparar.py).

PORTA ?= 8795

.PHONY: instalar
instalar:
	uv sync --inexact
	install -d $(HOME)/.config/systemd/user
	sed 's#@REPO@#$(CURDIR)#' systemd/zervis.service > $(HOME)/.config/systemd/user/zervis.service
	install -Dm644 deploy/zervis.svg $(HOME)/.local/share/icons/hicolor/scalable/apps/zervis.svg
	install -d $(HOME)/.local/share/applications
	sed -e 's#@REPO@#$(CURDIR)#' -e 's#@PORTA@#$(PORTA)#' -e 's#@ICONE@#zervis#' \
		deploy/zervis.desktop > $(HOME)/.local/share/applications/zervis.desktop
	systemctl --user daemon-reload
