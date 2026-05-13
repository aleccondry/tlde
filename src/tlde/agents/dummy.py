from tlde.config import AgentConfig


class Dummy(AgentConfig):
    def __init__(self, **overrides):
        defaults = dict(
            name="dummy",
            description="A simple test agent to verify the infrastructure works.",
        )
        defaults.update(overrides)
        super().__init__(**defaults)
