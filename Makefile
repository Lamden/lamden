.PHONY: start teardown upgrade login-node login-ws login-events clean

start:
	@docker compose -f docker/docker-compose.yml build --no-cache && \
	docker compose -f docker/docker-compose.yml down && \
	docker compose -f docker/docker-compose.yml up -d && \
	nohup python upgrade_manager.py > /var/log/uman.log &
teardown:
	@docker compose -f docker/docker-compose.yml down && \
	pkill -f upgrade_manager
upgrade:
	@docker compose -f docker/docker-compose.yml build --no-cache && \
	docker compose -f docker/docker-compose.yml down && \
	docker compose -f docker/docker-compose.yml up -d
login-node:
	@docker compose -f docker/docker-compose.yml exec node /bin/bash
login-ws:
	@docker compose -f docker/docker-compose.yml exec webserver /bin/bash
login-events:
	@docker compose -f docker/docker-compose.yml exec events /bin/bash
clean:
	@docker compose -f docker/docker-compose.yml down
	@docker rmi lamden
