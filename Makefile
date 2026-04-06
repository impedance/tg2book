run:
	docker compose up -d tg2book tg2book-userbot

test:
	docker compose exec tg2book pytest

userbot-login:
	docker compose run --rm --entrypoint python tg2book-userbot userbot_listener.py

logs:
	docker compose logs -f tg2book tg2book-userbot

logs-bot:
	docker compose logs -f tg2book

logs-userbot:
	docker compose logs -f tg2book-userbot

build:
	docker compose up -d --build tg2book tg2book-userbot
