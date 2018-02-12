from collections import namedtuple

BALANCE_KEY = 'BALANCE'
SCRATCH_KEY = 'SCRATCH'
QUEUE_KEY = 'QUEUE'
TRANSACTION_KEY = 'TRANSACTION'
SWAP_KEY = 'SWAP'
VOTE_KEY = 'VOTE'
STAMP_KEY = 'STAMP'

# Named tuple for specifying voting types for vote transactions
# To use, import VOTE_TYPES and call VOTE_TYPES.delegate or VOTE_TYPES.transaction_fee, ect
VT = namedtuple('VotingTypes', 'delegate transaction_fee')
VOTE_TYPES = VT('DELEGATE', 'TX_FEE')