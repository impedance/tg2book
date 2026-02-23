run:
	docker compose restart tg2book

test:
	docker compose exec tg2book pytest

logs:
	docker compose logs -f tg2book

build:
	docker compose up -d --build
