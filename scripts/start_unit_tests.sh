#!/bin/bash
#CIL_PATH='/Users/davishaba/Developer/cilantro'
#docker run --name cil -dit -v /var/db/cilantro/:/var/db/cilantro -v ~/cilantro/ops/base/circus_unittest.conf:/etc/circus.conf lamden/cilantro_full:$(bash ~/cilantro/ops/tools/generate_tag.sh)

source /app/venv/bin/activate
python3 /app/tests/run_tests.py --integration 0 --unit 1
