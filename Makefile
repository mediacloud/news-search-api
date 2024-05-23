.PHONY: down deploy shell

#setup image tag to latest for dev
DEPLOY_TYPE?=dev

# stop containers
down:
	docker compose down

# run the deploy script, passing in deployment type
deploy:
	./deploy.sh -d $(DEPLOY_TYPE)

# exec into api container
shell:
	docker compose exec api sh
