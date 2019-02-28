import os, sys

# Add /messages/capnp to Python path. We need these loaded for capnp magic imports
sys.path.append(os.path.dirname(__file__) + '/messages/capnp')

# Set the decimal precision for floating point arithmetic
# from decimal import getcontext
# getcontext().prec = DECIMAL_PRECISION
