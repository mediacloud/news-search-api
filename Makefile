.PHONY: down deploy api-exec

# stop containers
down:
	docker-compose down

# run the deploy script
deploy:
	sudo ./deploy.sh

# exec into api container
api-exec:
	docker-compose exec api sh

# (local) development
up:
	IMAGE_TAG=$(IMAGE_TAG) docker-compose up --build -d
