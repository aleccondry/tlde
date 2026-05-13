"""Agent configuration dataclass and registry."""

import os
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt from prompts/<name>.txt (or .md fallback)."""
    for ext in (".txt", ".md"):
        path = PROMPTS_DIR / f"{name}{ext}"
        if path.exists():
            return path.read_text().strip()
    raise FileNotFoundError(
        f"No prompt file found at {PROMPTS_DIR / name}.txt or .md"
    )


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
        provider: BYOK provider name ("github", "openrouter", "anthropic", etc.).
            Defaults to TLDE_PROVIDER env var or "github".
        provider_config: Full provider dict passed directly to the Copilot SDK.
            Takes precedence over ``provider``.
    """

    name: str
    model: str = "claude-sonnet-4.5"
    prompt: str = ""
    description: str = ""
    tools: list[str] | None = None
    mcp_servers: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    agent_type: str = ""
    provider: str = ""
    provider_config: dict | None = None

    def __post_init__(self):
        if not self.agent_type:
            self.agent_type = self.name
        if not self.prompt:
            self.prompt = load_prompt(self.agent_type)
        if not self.provider:
            self.provider = os.environ.get("TLDE_PROVIDER", "github")

    def get_provider_dict(self) -> dict | None:
        """Return the provider dict for the Copilot SDK, or None for GitHub."""
        if self.provider_config is not None:
            return self.provider_config
        if self.provider == "github":
            return None
        from tlde.providers import get_provider, provider_to_dict
        return provider_to_dict(get_provider(self.provider))