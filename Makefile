.PHONY: down deploy shell up

#setup image tag to latest for dev
IMAGE_TAG?=latest
DEPLOY_TYPE?=dev

# stop containers
down:
	sudo docker compose down

# run the deploy script, passing in deployment type
deploy:
	sudo ./deploy.sh -d $(DEPLOY_TYPE)

# exec into api container
shell:
	sudo docker compose exec api sh

# (local) development
up:
	IMAGE_TAG=$(IMAGE_TAG) sudo docker compose up --build -d
