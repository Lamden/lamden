import os

if os.getenv('CIRCLECI'):
    CI_FACTOR = 5
else:
    CI_FACTOR = 1
