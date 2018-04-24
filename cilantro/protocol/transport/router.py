from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.statemachine import StateMachine


class Router:
    def __init__(self, sm: StateMachine):
        super().__init__()
        self.sm = sm
