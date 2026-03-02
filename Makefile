VENV = .venv
PYTHON = $(VENV)/bin/python
COMPOSE_BASE = docker compose -f docker-compose.yml
COMPOSE_DEV = $(COMPOSE_BASE) -f docker-compose.dev.yml
COMPOSE_PROD = $(COMPOSE_BASE) -f docker-compose.prod.yml
DOCKER_PYTHON = $(COMPOSE_DEV) exec tg2book python -m
USE_DOCKER ?= 1
ARTIFACTS_DIR ?= artifacts

ifeq ($(USE_DOCKER),1)
PY_RUN = $(DOCKER_PYTHON)
else
PY_RUN = $(PYTHON) -m
endif

.PHONY: run stop down login-userbot test smoke agent-smoke epub-validate preflight logs build up prod-build prod-up prod-logs prod-down typecheck format lint structural

run:
	$(COMPOSE_DEV) up -d tg2book

up:
	$(COMPOSE_DEV) up -d

stop:
	$(COMPOSE_DEV) stop tg2book

down:
	$(COMPOSE_DEV) down

login-userbot:
	$(PYTHON) login_userbot.py

test:
	@mkdir -p "$(ARTIFACTS_DIR)"
	$(PY_RUN) pytest tests --junitxml="$(ARTIFACTS_DIR)/pytest.xml"

structural:
	@bash tools/structural_check.sh

smoke: structural
	$(PY_RUN) ruff check .
	@mkdir -p "$(ARTIFACTS_DIR)"
	$(PY_RUN) pytest \
		tests/test_optimization.py \
		tests/test_epub_golden.py \
		tests/test_epub_service_guardrails.py \
		--junitxml="$(ARTIFACTS_DIR)/pytest-smoke.xml"

agent-smoke: smoke
	@mkdir -p "$(ARTIFACTS_DIR)"
	$(PY_RUN) pytest tests/test_integration.py --junitxml="$(ARTIFACTS_DIR)/pytest-agent-smoke.xml"

epub-validate:
	@test -n "$(FILE)" || (echo "Usage: make epub-validate FILE=path/to/book.epub" && exit 2)
	$(COMPOSE_DEV) exec tg2book python utils/epub_validate.py "$(FILE)"

logs:
	$(COMPOSE_DEV) logs -f tg2book

build:
	$(COMPOSE_DEV) up -d --build

prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up -d --build

prod-logs:
	$(COMPOSE_PROD) logs -f tg2book

prod-down:
	$(COMPOSE_PROD) down

typecheck:
	$(PY_RUN) mypy \
		bot.py \
		config.py \
		dropbox_module.py \
		epub_functions.py \
		services/epub_service.py \
		userbot_db.py \
		utils \
		src

format:
	$(PY_RUN) ruff check --fix . && $(PY_RUN) ruff format .

lint:
	$(PY_RUN) ruff check .

preflight: structural format lint typecheck test
