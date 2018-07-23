from cilantro import Constants
from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.protocol.statemachine import *
from cilantro.protocol.interpreters import VanillaInterpreter
from cilantro.db import *
from cilantro.messages import *


DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


@Delegate.register_state
class DelegateCatchupState(DelegateBaseState):
    pass