PY_RUN = python3
COMPOSE_DEV = docker compose
COMPOSE_PROD = docker compose
USE_DOCKER = 1
ARTIFACTS_DIR = artifacts

run:
	docker compose up -d --remove-orphans tg2book

up: run

test:
	docker compose exec tg2book pytest

userbot-login:
	docker compose run --rm --entrypoint python tg2book userbot_listener.py

logs:
	docker compose logs -f tg2book

logs-bot:
	docker compose logs -f tg2book

logs-userbot:
	docker compose logs -f tg2book

stop:
	docker compose stop

down:
	docker compose down

build:
	docker compose up -d --build --remove-orphans tg2book

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

.PHONY: run up test stop down build prod-build prod-up prod-logs prod-down typecheck format lint preflight doctor

doctor:
	@echo "Targets: smoke, agent-smoke, preflight"; \
	echo "USE_DOCKER=$(USE_DOCKER)  ARTIFACTS_DIR=$(ARTIFACTS_DIR)"; \
	test -f AGENTS.md && echo "AGENTS.md: ok" || echo "AGENTS.md: missing"; \
	test -f docs/index.md && echo "docs/index.md: ok" || echo "docs/index.md: missing"; \
	test -f docs/testing.md && echo "docs/testing.md: ok" || echo "docs/testing.md: missing"; \
	test -f docs/harness_plan.md && echo "docs/harness_plan.md: ok" || echo "docs/harness_plan.md: missing"; \
	test -f .github/workflows/agent-harness.yml && echo ".github/workflows/agent-harness.yml: ok" || echo ".github/workflows/agent-harness.yml: missing"
