VENV = .venv
PYTHON = $(VENV)/bin/python

run:
	docker compose restart tg2book

stop:
	docker compose stop tg2book

down:
	docker compose down

login-userbot:
	$(PYTHON) login_userbot.py

test:
	docker compose exec tg2book python -m pytest

logs:
	docker compose logs -f tg2book

build:
	docker compose up -d --build

typecheck:
	docker compose exec tg2book python -m mypy bot.py dropbox_module.py epub_functions.py

format:
	docker compose exec tg2book python -m ruff check --fix . && docker compose exec tg2book python -m ruff format .

lint:
	docker compose exec tg2book python -m ruff check .
