.PHONY: down deploy shell

#deploy.sh args (-a, -d)
ARGS?=

# stop containers
down:
	docker compose down

# run the deploy script, passing in deployment type
deploy:
	./deploy.sh $(ARGS)

# exec into api container
shell:
	docker compose exec api sh
