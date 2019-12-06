DATADIR ?= /usr/local/db/cilantro_ee

start-db:
	python3 ./scripts/start_redis.py $$(pwd)/ops/base/redis.conf &
	python3 ./scripts/start_mongo.py &
	sleep 1
	python3 ./scripts/create_user.py &
	sleep 2

stop-db:
	pkill mongod || true
	pkill redis-server || true

restart-db: stop-db start-db

test: restart-db
	python3 ./tests/run_tests.py -v

test-unit: restart-db
	python3 ./tests/run_tests.py -v --integration 0 --unit 1

install:
	pip3 install -r requirements.txt --upgrade --no-cache-dir && pip3 install -r dev-requirements.txt --upgrade --no-cache-dir && pip3 install -r protocol-requirements.txt --upgrade --no-cache-dir

clean-logs:
	bash ./scripts/clean-logs.sh

clean-temps:
	bash ./scripts/clean-temp-files.sh

clean-db:
	bash ./scripts/clean-dbs.sh

clean-bld:
	bash ./scripts/clean-bld.sh

clean: clean-logs clean-temps clean-db clean-bld

pybuild:
	python3 setup.py sdist bdist_wheel

dockerbuild:
	./ops/tools/docker_build_push.sh

dockerrun:
	@echo "Running with data dir ${DATADIR}"
	docker rm -f cil 2>/dev/null || true
	docker run --name cil -dit -v ${DATADIR}:/usr/local/db/cilantro_ee -v $$(pwd)/ops/base/redis.conf:/etc/redis.conf -v $$(pwd)/ops/base/circus_unittest.conf:/etc/circus.conf lamden/cilantro_ee_full:$$(bash ops/tools/generate_tag.sh)

dockerenter:
	docker exec -ti cil /bin/bash

dockertest:
	sleep 8
	docker exec -it cil /app/scripts/start_unit_tests.sh

money: clean dockerbuild dockerrun dockertest

scrub: money

help:
	echo '\n\n'; cat Makefile; echo '\n\n'

