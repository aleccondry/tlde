"""Auto-discovers agent classes from sibling modules.

Each module in this package should expose one or more AgentConfig subclasses.
They are automatically collected into the AGENTS registry on import, keyed
by their module name.

Usage:
    from tlde.agents import AGENTS

    # Look up and instantiate
    my_agent = AGENTS["my_agent"]()

    # Spawn multiple instances
    a1 = AGENTS["my_agent"](name="my_agent-1")
    a2 = AGENTS["my_agent"](name="my_agent-2")
"""

import importlib
import inspect
import pkgutil

from tlde.config import AgentConfig

AGENTS: dict[str, type[AgentConfig]] = {}

for _finder, module_name, _ispkg in pkgutil.iter_modules(__path__):
    module = importlib.import_module(f"{__name__}.{module_name}")
    for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, AgentConfig) and obj is not AgentConfig:
            AGENTS[module_name] = obj
