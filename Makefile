start-db:
	python3 ./scripts/start_redis.py &
	python3 ./scripts/start_mongo.py &
	python3 ./scripts/create_user.py &

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

upload-base:
	docker tag cilantro_base lamden/cilantro:latest
	docker push lamden/cilantro:latest

upload-mn:
	docker tag cilantro_mn lamden/cilantro-mn:latest
	docker push lamden/cilantro-mn:latest


build-test: clean
	docker build -t lamden/cilantro_base:latest -f docker/cilantro_base .
	docker build -t lamden/cilantro_light:test -f docker/cilantro_light .
	docker build -t lamden/cilantro_full:test -f docker/cilantro_full .

run-test:
	docker run -it -v /Users/davishaba/Developer/cilantro/good_d.conf:/etc/circus.conf -p 443:443 -p 80:80 -p 10000-10100:10000-10100 lamden/cilantro_full:test

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
