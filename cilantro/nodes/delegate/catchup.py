from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


@Delegate.register_state
class DelegateCatchupState(DelegateBaseState):
    pass