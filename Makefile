test_db_conf.ini:
	./scripts/make_test_config.py

run-db: test_db_conf.ini
	./scripts/start_test_db.sh

console-test-db-container: test-db-container
	docker run -it --entrypoint=/bin/bash lamden/cilantro-db

connect-db:
	./scripts/connect_mysql_client.sh

kill-db:
	docker kill `docker ps --format "table {{.Names}}" --filter "ancestor=seneca-myrocks-test"| tail -n +2` || true; sleep 2

kill: kill-db

help:
	echo '\n\n'; cat Makefile; echo '\n\n'