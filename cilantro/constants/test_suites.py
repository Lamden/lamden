import os

if os.getenv('CIRCLECI'):
    CI_FACTOR = 4
else:
    CI_FACTOR = 1
