test_db_conf.ini:
	./scripts/make_test_config.py

start-db: test_db_conf.ini
	./scripts/start_test_db.sh

start: start-db

console-db:
	./scripts/connect-mysql-client.sh

stop-db:
	docker kill `docker ps --format "table {{.Names}}" --filter "ancestor=lamden/cilantro-db"| tail -n +2` || true; sleep 2

stop: stop-db

restart-db: stop-db start-db

test: restart-db
	./tests/run_tests.py --integration 0 -v

install:
	pip3 install -r requirements.txt --upgrade --no-cache-dir && pip3 install -r dev-requirements.txt --upgrade --no-cache-dir

build-image:
	docker build -f vmnet_configs/images/cilantro_base.dev .

clean-logs:
	./scripts/clean-logs.sh

clean-temps:
	./scripts/clean-temp-files.sh

clean: clean-logs clean-temps

pump:
	python3 ./tests/vmnet/test_pump.py

dump:
	python3 ./tests/vmnet/test_dump.py

kill-docker:
	docker kill $(docker ps -q)

help:
	echo '\n\n'; cat Makefile; echo '\n\n'
