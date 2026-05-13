from tlde.config import AgentConfig


class EmuTestAgg(AgentConfig):
    """Firmware emulation test aggregator agent.

    Builds sample binaries for the target board, generates Robot Framework
    test suites that exercise the emulated peripherals, runs them under
    Renode, and reports pass/fail results with unexpected-failure analysis.
    """

    def __init__(self, **overrides):
        defaults = dict(
            name="emu_test_agg",
            agent_type="emu_test_agg",
            description=(
                "Builds sample firmware, writes Robot Framework test suites, "
                "runs them in Renode against the generated .repl and peripheral "
                "models, and reports whether any unexpected failures occurred."
            ),
            model="claude-sonnet-4.6",
            skills=[
                "renode-robot-test-generation",
                "renode-feedback-schema",
                "renode-debugging",
            ],
        )
        defaults.update(overrides)
        super().__init__(**defaults)
