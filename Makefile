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

# dev-deploy
# I would want to deploy the containers in dev
dev-deploy:
	IMAGE_TAG=$(IMAGE_TAG) docker-compose up -d
