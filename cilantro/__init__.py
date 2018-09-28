import os
from decimal import getcontext
import sys
import hashlib
from os.path import dirname, abspath
from cilantro.constants.protocol import SIG_FLAGS

import cython
# if cython.compiled: print("Yep, I'm compiled.")
# else: print("Just a lowly interpreted script.")

os.environ['LOCAL_PATH'] = abspath(dirname(dirname(dirname(__file__))))

# Add /messages/capnp to Python path. We need these loaded for capnp magic imports
sys.path.append(os.path.dirname(__file__) + '/messages/capnp')

getcontext().prec = SIG_FLAGS
