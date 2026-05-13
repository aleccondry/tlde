from tlde.config import AgentConfig


class FirmwareEmulationManager(AgentConfig):
    def __init__(self, **overrides):
        defaults = dict(
            name="firmware_emulation_manager",
            agent_type="firmware_emulation_manager",
            model="claude-opus-4.6",
            description=(
                "Reads microcontroller PDF specs and decomposes the Renode "
                "emulation work into self-contained units for "
                "FirmwareEmulationEngineer agents."
            ),
            mcp_servers={
                "pdf-reader": {
                    "command": "npx",
                    "args": ["@sylphx/pdf-reader-mcp"],
                    "tools": ["*"],
                },
            },
            skills=["renode-peripheral-catalogue"],
        )
        defaults.update(overrides)
        super().__init__(**defaults)
