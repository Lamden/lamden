# test_db_conf.ini:
# 	./scripts/make_test_config.py

start-db:# test_db_conf.ini
	python3 ./scripts/start_redis_mongo.py

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

build-base: clean
	docker build -t cilantro_base -f vmnet_configs/images/cilantro_base.dev .

build-mn: clean
	docker build -t cilantro_mn -f vmnet_configs/images/cilantro_mn .

upload-base:
	docker tag cilantro_base lamden/cilantro:latest
	docker push lamden/cilantro:latest

upload-mn:
	docker tag cilantro_mn lamden/cilantro-mn:latest
	docker push lamden/cilantro-mn:latest

clean-logs:
	sudo bash ./scripts/clean-logs.sh

clean-temps:
	sudo bash ./scripts/clean-temp-files.sh

clean-certs:
	sudo bash ./scripts/clean-certs.sh

clean-dbs:
	sudo bash ./scripts/clean-db.sh

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
