.PHONY: down deploy bash

down:
	docker-compose down

deploy:
	sudo ./deploy.sh

bash:
	docker-compose exec api sh
