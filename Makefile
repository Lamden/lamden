start-db:
	python3 ./scripts/start_redis_mongo.py

mongo: start-db
	mongo

redis: start-db
	redis-cli

stop-db: kill-docker
	pkill mongod || true
	pkill redis-server || true

restart-db: stop-db start-db

test: restart-db
	python3 ./tests/run_tests.py -v

test-unit: restart-db
	python3 ./tests/run_tests.py -v --integration 0 --unit 1

test-integration: restart-db
	python3 ./tests/run_tests.py -v --integration 1 --unit 0

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
	bash ./scripts/clean-logs.sh

clean-temps:
	bash ./scripts/clean-temp-files.sh

clean-certs:
	bash ./scripts/clean-certs.sh

clean-dbs:
	bash ./scripts/clean-db.sh

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
