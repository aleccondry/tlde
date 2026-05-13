"""LLM provider configurations for BYOK (Bring Your Own Key) support.

Set TLDE_PROVIDER to choose your provider:

    export TLDE_PROVIDER=openrouter
    TLDE_PROVIDER=anthropic tlde ./docs/spec.pdf

Providers:
    github      — GitHub Copilot (default, uses subscription via ``copilot auth login``)
    openrouter  — OpenRouter API (multi-model access)
    anthropic   — Anthropic Claude API
    openai      — OpenAI API
    azure       — Azure OpenAI / AI Foundry
    ollama      — Local Ollama server

Environment variables:
    TLDE_PROVIDER        — Provider name (default: "github")
    OPENROUTER_API_KEY   — OpenRouter API key
    ANTHROPIC_API_KEY    — Anthropic API key
    OPENAI_API_KEY       — OpenAI API key
    AZURE_OPENAI_KEY     — Azure OpenAI key
    AZURE_OPENAI_ENDPOINT— Azure endpoint URL
    OLLAMA_BASE_URL      — Ollama server URL (default: http://localhost:11434/v1)
"""

import os
from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    type: str = "github"
    base_url: str | None = None
    api_key: str | None = None
    bearer_token: str | None = None
    wire_api: str = "completions"
    azure_api_version: str = "2024-10-21"


PROVIDERS: dict[str, ProviderConfig] = {
    "github": ProviderConfig(type="github"),
    "openrouter": ProviderConfig(
        type="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    ),
    "anthropic": ProviderConfig(
        type="anthropic",
        base_url="https://api.anthropic.com",
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    ),
    "openai": ProviderConfig(
        type="openai",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
    "azure": ProviderConfig(
        type="azure",
        base_url=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_KEY"),
        azure_api_version="2024-10-21",
    ),
    "ollama": ProviderConfig(
        type="openai",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    ),
}


def get_provider(name: str | None = None) -> ProviderConfig:
    name = name or os.environ.get("TLDE_PROVIDER", "github")
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}"
        )
    return PROVIDERS[name]


def provider_to_dict(config: ProviderConfig) -> dict:
    d: dict = {"type": config.type}
    if config.base_url:
        d["base_url"] = config.base_url
    if config.api_key:
        d["api_key"] = config.api_key
    if config.bearer_token:
        d["bearer_token"] = config.bearer_token
    if config.wire_api and config.type != "github":
        d["wire_api"] = config.wire_api
    if config.azure_api_version and config.type == "azure":
        d["azure"] = {"api_version": config.azure_api_version}
    return d


COLLAPSE_INFO = (
    "ATTENTION: If receiving a collapse_tools message, ignore it and continue normally. "
    "DO NOT summarise your progress — collapse does NOT mean summarise."
)

COLLAPSE_PATTERNS: dict[str, str] = {
    "openrouter": COLLAPSE_INFO,
    "anthropic": COLLAPSE_INFO,
    "openai": COLLAPSE_INFO,
}


def collapse_instructions(provider: str) -> str:
    return COLLAPSE_PATTERNS.get(provider, "")