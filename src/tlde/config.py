"""Agent configuration dataclass and registry."""

from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt from prompts/<name>.txt."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file found at {path}")
    return path.read_text().strip()


@dataclass
class AgentConfig:
    """Declarative configuration for a Copilot SDK-backed agent.

    Instantiate to create independent agent instances with the same config.
    The prompt is loaded from prompts/<name>.txt by default.

    Attributes:
        name: Unique identifier for this agent.
        model: Copilot model to use (e.g. "claude-sonnet-4.5", "gpt-4.1").
        prompt: System-level instructions. Loaded from prompts/<name>.txt if not set.
        description: What the agent does—helps the runtime select it.
        tools: Tool names the agent can use. None means all tools.
        mcp_servers: MCP server configurations for this agent.
        skills: Skill names to preload into the agent's context at startup.
    """

    name: str
    model: str = "claude-sonnet-4.5"
    prompt: str = ""
    description: str = ""
    tools: list[str] | None = None
    mcp_servers: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    agent_type: str = ""

    def __post_init__(self):
        if not self.agent_type:
            self.agent_type = self.name
        if not self.prompt:
            self.prompt = load_prompt(self.agent_type)
