"""Firmware Verification Engineer agent.

Generates Renode .resc scripts and validates .repl platform descriptions
against vendor documentation. Uses Renode skills to test the .repl provided
by the firmware emulation engineer and provides structured feedback on
mismatches.
"""

from tlde.config import AgentConfig


class FirmwareVerificationEngineer(AgentConfig):
    def __init__(self, **overrides):
        defaults = dict(
            name="firmware_verification_engineer",
            agent_type="fw_verif_eng",
            description=(
                "Generates Renode .resc execution scripts and validates "
                ".repl platform descriptions against vendor documentation. "
                "Treats the .repl as untrusted input and cross-checks every "
                "peripheral against the reference manual."
            ),
            skills=[
                "renode-resc-generation",
                "renode-feedback-schema",
                "mcuboot-emulation",
                "renode-debugging",
                "zephyr-dts-analysis",
            ],
            tools=["read_file", "write_file", "search_files"],
        )
        defaults.update(overrides)
        super().__init__(**defaults)
