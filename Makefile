.PHONY: build up down

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

publish:
	docker push mcsystems/news-search-api:staging

bash:
	docker-compose exec api bash
