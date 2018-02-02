# Redis for state changes but also for the 'proposed' state changes
# ID each tx or put them on a set?

'''

FIFO queue
SSET pending_tx
where is a data blob?
where it's the series of state changes?

'''

from cilantro.transactions import TestNetTransaction
from cilantro.interpreters import TestNetInterpreter

tx = TestNetTransaction()