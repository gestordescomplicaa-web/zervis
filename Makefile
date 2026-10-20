# Porta única de qualidade (docs/06-qualidade.md): formatação, lint, tipos e testes.
.PHONY: check fmt lint tipos testes check-imersivo check-instalacao wacalls

check: lint tipos testes wacalls

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

tipos: node_modules/.package-lock.json
	uv run mypy
	npm run check

# O TypeScript do painel (só verificação), instalado ou atualizado quando o lock muda.
node_modules/.package-lock.json: package.json package-lock.json
	npm ci --no-audit --no-fund

testes:
	uv run pytest

# O WaCalls (Go) do atendimento. O instalador prepara o Go no espaço do usuário; na CI,
# ZE_SEM_PULOS=1 também garante que os testes não sejam ignorados.
wacalls:
	@if command -v go >/dev/null; then cd jarvis/atendimento/wacalls && go vet ./... && go test ./...; \
	elif [ -n "$$ZE_SEM_PULOS" ]; then echo "wacalls: sem Go (ZE_SEM_PULOS=1)"; exit 1; \
	else echo "wacalls: sem Go, testes do Go pulados"; fi

# O último commit numa pasta limpa, com HOME vazio, instala e passa no make check (uns minutos):
# antes de liberar uma versão e sempre que mudar dependência ou instalação.
check-instalacao:
	deploy/check-instalacao.sh

# O modo imersivo num Chromium de verdade, sem tela (uns minutos): antes de mexer na página.
check-imersivo:
	ZE_TESTES_IMERSIVO=1 uv run --with websockets --with pytest-xdist pytest -q -n 2 tests/imersivo

# Instala o serviço (sem iniciar no login). Os modelos de som são baixados e conferidos pelo
# próprio Zé na primeira subida (jarvis/preparar.py).

PORTA ?= 8795
CONFIG_HOME = $(or $(XDG_CONFIG_HOME),$(HOME)/.config)
DATA_HOME = $(or $(XDG_DATA_HOME),$(HOME)/.local/share)

.PHONY: instalar
instalar:
	uv sync --inexact
	install -d "$(CONFIG_HOME)/systemd/user"
	sed -e 's#@REPO@#$(CURDIR)#' -e 's#@PORTA@#$(PORTA)#' \
		systemd/zervis.service > "$(CONFIG_HOME)/systemd/user/zervis.service"
	install -Dm644 deploy/zervis.svg "$(DATA_HOME)/icons/hicolor/scalable/apps/zervis.svg"
	install -d "$(DATA_HOME)/applications"
	sed -e 's#@REPO@#$(CURDIR)#' -e 's#@PORTA@#$(PORTA)#' -e 's#@ICONE@#zervis#' \
		deploy/zervis.desktop > "$(DATA_HOME)/applications/zervis.desktop"
	# O comando `zervis` (status, doctor, update...): um atalho para o do projeto, sem
	# sobrescrever um `zervis` que não seja este.
	install -d "$(HOME)/.local/bin"
	if [ ! -e "$(HOME)/.local/bin/zervis" ] || [ -L "$(HOME)/.local/bin/zervis" ]; then \
		ln -sfn "$(CURDIR)/.venv/bin/zervis" "$(HOME)/.local/bin/zervis"; \
	else echo "Aviso: já existe um $(HOME)/.local/bin/zervis que não é do Zérvis; ficou como está."; fi
	systemctl --user daemon-reload
