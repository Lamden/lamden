test_db_conf.ini:
	./scripts/make_test_config.py

start-db: test_db_conf.ini
	./scripts/start_test_db.sh

console-db:
	./scripts/connect_mysql_client.sh

stop-db:
	docker kill `docker ps --format "table {{.Names}}" --filter "ancestor=cilantro-db"| tail -n +2` || true; sleep 2

stop: stop-db

help:
	echo '\n\n'; cat Makefile; echo '\n\n'