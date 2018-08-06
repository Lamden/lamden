test:
	./tests/run_tests.py --integration 0

clean:
	./clean-temp-files.sh

update-container-requirements:
	docker exec node_1 pip3 install -r requirements.txt --no-cache-dir --upgrade