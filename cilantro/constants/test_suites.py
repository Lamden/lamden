import os

if os.getenv('CIRCLECI'):
    CI_FACTOR = 3
else:
    CI_FACTOR = 1
