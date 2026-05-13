"""Firmware Emulation Engineer agent.

Receives a peripheral specification summary from a manager agent, optionally
reads the original PDF datasheet via the pdf-reader MCP, and produces Renode
platform description (.repl) files together with any required C# or Python
peripheral models.

The agent is designed to participate in a feedback pipeline: after initial
artefact generation it can accept structured feedback from an emulation
verification agent and revise its outputs accordingly.
"""

from tlde.config import AgentConfig

PDF_READER_MCP = {
    "pdf-reader": {
        "command": "npx",
        "args": ["@sylphx/pdf-reader-mcp"],
    }
}


class FwEmuEng(AgentConfig):
    # Board-agnostic skills: .repl generation, C# peripheral model generation,
    # and advanced peripheral type patterns. Board-specific skills (e.g.
    # microbit-v2-platform-context) should be added by the caller:
    #   FwEmuEng(skills=[*FwEmuEng.BASE_SKILLS, "microbit-v2-platform-context"])
    BASE_SKILLS = [
        "renode-repl-generation",
        "renode-peripheral-model-generation",
        "renode-peripheral-model-patterns",
        "mcuboot-emulation",
        "zephyr-dts-analysis",
    ]

    def __init__(self, **overrides):
        defaults = dict(
            name="fw_emu_eng",
            agent_type="fw_emu_eng",
            model="claude-sonnet-4.6",
            description=(
                "Firmware emulation engineer that produces Renode .repl platform "
                "descriptions and peripheral models (Python/C#) from MCU datasheet "
                "summaries. Accepts verification feedback to iteratively refine emulation."
            ),
            mcp_servers=PDF_READER_MCP,
            skills=self.BASE_SKILLS,
        )
        defaults.update(overrides)
        super().__init__(**defaults)
