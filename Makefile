# Porta única de qualidade (docs/06-qualidade.md): formatação, lint, tipos e testes.
.PHONY: check fmt lint tipos testes

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

# Instala o serviço (sem iniciar no login). Os modelos de som são baixados e conferidos pelo
# próprio Zé na primeira subida (jarvis/preparar.py).

.PHONY: instalar
instalar:
	uv sync --inexact
	install -d $(HOME)/.config/systemd/user
	sed 's#@REPO@#$(CURDIR)#' systemd/zervis.service > $(HOME)/.config/systemd/user/zervis.service
	systemctl --user daemon-reload
