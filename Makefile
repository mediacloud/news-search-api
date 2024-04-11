.PHONY: build up down

IMAGE_TAG?=0.0.1 #set Image tag from release version

build:
	IMAGE_TAG=${IMAGE_TAG} docker-compose build

up:
	IMAGE_TAG=${IMAGE_TAG} docker-compose up -d

down:
	docker-compose down

deploy:
	sudo ./deploy.sh

bash:
	docker-compose exec api sh
