.PHONY: down prod staging dev shell

# stop containers
down:
	docker compose down

# run the deploy script, for prod,dev and staging environments
prod:
	./deploy.sh -d prod

staging:
	./deploy.sh -d staging

dev:
	./deploy.sh -d dev

# deploy dev in without github tag using latest tag
dev-latest:
	./deploy.sh -a -d dev

# exec into api container
shell:
	docker compose exec api sh
