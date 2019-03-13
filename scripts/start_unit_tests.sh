#!/bin/bash
#CIL_PATH='/Users/davishaba/Developer/cilantro_ee'
#docker run --name cil -dit -v /usr/local/db/cilantro_ee/:/usr/local/db/cilantro_ee -v ~/cilantro_ee/ops/base/circus_unittest.conf:/etc/circus.conf lamden/cilantro_ee_full:$(bash ~/cilantro_ee/ops/tools/generate_tag.sh)

source /app/venv/bin/activate
python3 /app/tests/run_tests.py --integration 0 --unit 1
