from cilantro.nodes import Witness
import os

slot = os.getenv('SLOT_NUM')
w = Witness(slot=int(slot))

