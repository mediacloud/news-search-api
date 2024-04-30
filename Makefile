.PHONY: down deploy api-exec

#setup image tag to latest for dev
IMAGE_TAG?=latest

# stop containers
down:
	docker-compose down

# run the deploy script
deploy:
	sudo ./deploy.sh

# exec into api container
shell:
	docker-compose exec api sh

# (local) development
up:
	IMAGE_TAG=$(IMAGE_TAG) docker-compose up --build -d
