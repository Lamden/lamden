start-db:
	python3 ./scripts/start_ledis.py -no-conf &
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

clean: clean-logs clean-temps clean-db

dockerbuild:
	./ops/tools/docker_build_push.sh

dockerrun:
	docker rm -f cil 2>/dev/null || true
	docker run --name cil -dit -v /usr/local/db/cilantro_ee:/usr/local/db/cilantro_ee -v $$(pwd)/ops/base/ledis.conf:/etc/ledis.conf -v $$(pwd)/ops/base/circus_unittest.conf:/etc/circus.conf lamden/cilantro_ee_full:$$(bash ops/tools/generate_tag.sh)

dockerenter:
	docker exec -ti cil /bin/bash

dockertest:
	sleep 5
	docker exec -it cil /app/scripts/start_unit_tests.sh

money: clean dockerbuild dockerrun dockertest

scrub: money

help:
	echo '\n\n'; cat Makefile; echo '\n\n'

