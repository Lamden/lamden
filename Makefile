# test_db_conf.ini:
# 	./scripts/make_test_config.py

start-db:# test_db_conf.ini
	./scripts/start_mongo.sh &

start: start-db

console-db: start-db
	mongo

stop-db:
	# pkill -9 mongo* 2>/dev/null
	# docker kill `docker ps --format "table {{.Names}}" --filter "ancestor=lamden/cilantro-db"| tail -n +2` 2>/dev/null; sleep 2

stop: stop-db

restart-db: stop-db start-db

test: restart-db
	./tests/run_tests.py -v

install:
	pip3 install -r requirements.txt --upgrade --no-cache-dir && pip3 install -r dev-requirements.txt --upgrade --no-cache-dir

build-base:
	docker build -t cilantro_base.dev -f vmnet_configs/images/cilantro_base.dev .

build-mn:
	docker build -t cilantro_mn.dev -f vmnet_configs/images/cilantro_master.dev .

clean-logs:
	./scripts/clean-logs.sh

clean-temps:
	./scripts/clean-temp-files.sh

clean-certs:
	./scripts/clean-certs.sh

clean-dbs:
	./scripts/clean-db.sh

clean: clean-logs clean-temps clean-certs clean-dbs

pump:
	python3 ./tests/vmnet/test_pump.py

dump:
	python3 ./tests/vmnet/test_dump.py

kill-docker:
	docker kill `docker ps -q` || true; sleep 2

build-testnet-json:
	python3 -c "from cilantro.utils.test.testnet_config import *; generate_testnet_json()"

help:
	echo '\n\n'; cat Makefile; echo '\n\n'
