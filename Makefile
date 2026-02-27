run:
	docker compose restart tg2book

test:
	docker compose exec tg2book pytest

logs:
	docker compose logs -f tg2book

build:
	docker compose up -d --build

typecheck:
	docker compose exec tg2book /home/botuser/.local/bin/mypy bot.py dropbox_module.py epub_functions.py

format:
	docker compose exec tg2book /home/botuser/.local/bin/ruff format .

lint:
	docker compose exec tg2book /home/botuser/.local/bin/ruff check --fix .
