.PHONY: build up down run test logs clean init-db

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

run:
	docker compose run --rm etl python3 -m src.pipeline

init-db:
	docker compose exec postgres psql -U etl_user -d financial -f /docker-entrypoint-initdb.d/create_tables.sql

test:
	python3 -m pytest tests/ -v --tb=short

logs:
	docker compose logs -f etl

clean:
	docker compose down -v --remove-orphans
	rm -rf logs/*.log
