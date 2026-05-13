"""Factory for building Copilot SDK sessions from AgentConfig."""

import asyncio
import re
from typing import Callable

from copilot import CopilotClient
from copilot.generated.session_events import (
    AssistantMessageData,
    PermissionRequestKind,
    SessionIdleData,
)
from copilot.session import PermissionRequestResult

from tlde.config import AgentConfig
from tlde.observability import PipelineTrace, SessionObserver, SessionTrace

# mkdir with optional -p / -v flags; no shell metacharacters in the path
_ALLOWED_MKDIR = re.compile(r"^\s*mkdir(\s+-[pv]+)?\s+[^;&|$`]+$")

# Safe token: any non-whitespace character that is NOT a shell metacharacter.
# Blocks ; & | $ ` ( ) < > { }
_SAFE_TOKEN = r"[^;&|$`()<>{}\s]+"

# make -C <dir> with optional variables; renode-test <path>; west build <args>
_ALLOWED_BUILD_AND_TEST = re.compile(
    rf"^\s*("
    rf"make(\s+-C\s+{_SAFE_TOKEN})?(\s+\w+={_SAFE_TOKEN})*(\s+-p\s+always)?(\s+{_SAFE_TOKEN})?"
    rf"|renode-test(\s+{_SAFE_TOKEN})+"
    rf"|python\s+-m\s+robot(\s+{_SAFE_TOKEN})+"
    rf"|west\s+build(\s+{_SAFE_TOKEN})*"
    rf")\s*$"
)


def _make_shell_handler(allow_build: bool = False):
    """Return a permission handler that optionally allows build/test commands."""

    def handler(request, invocation):
        if request.kind != PermissionRequestKind.SHELL:
            return PermissionRequestResult(kind="approve-once")

        cmd = request.full_command_text or ""

        if _ALLOWED_MKDIR.match(cmd):
            return PermissionRequestResult(kind="approve-once")

        if allow_build and _ALLOWED_BUILD_AND_TEST.match(cmd):
            return PermissionRequestResult(kind="approve-once")

        print(f"[BLOCKED] shell: {cmd[:80]}")
        return PermissionRequestResult(kind="deny")

    return handler


def _approve_all_handler(request, invocation):
    """Approve every permission request, including shell commands."""
    return PermissionRequestResult(kind="approve-once")


# Default handler — approve everything.
_permission_handler = _approve_all_handler

# Extended handler for the test aggregator — also allows make / renode-test / west.
_test_permission_handler = _make_shell_handler(allow_build=True)


async def run_agent(
    config: AgentConfig,
    prompt: str,
    pipeline_trace: PipelineTrace | None = None,
    permission_handler=None,
) -> str:
    """Run a single-turn Copilot agent session.

    Args:
        config: Agent configuration.
        prompt: The user prompt to send.
        pipeline_trace: If provided, the session trace is added to it.
        permission_handler: Override the default shell permission handler.
            Use ``_test_permission_handler`` for agents that need to run
            builds and test commands.

    Returns:
        The agent's final text response.
    """
    handler = permission_handler or _permission_handler
    async with CopilotClient() as client:
        async with await client.create_session(
            on_permission_request=handler,
            model=config.model,
            mcp_servers=config.mcp_servers or None,
            skill_directories=["~/.copilot/skills"],
            custom_agents=[_agent_dict(config)],
            agent=config.name,
        ) as session:
            observer = SessionObserver(config.name)
            observer.attach(session)

            response = await _send_and_wait(session, prompt)

            trace = observer.finish()
            if pipeline_trace is not None:
                pipeline_trace.add(trace)

            return response


async def run_agent_interactive(
    config: AgentConfig,
    initial_prompt: str,
    get_feedback: Callable[[str], str | None],
    pipeline_trace: PipelineTrace | None = None,
    permission_handler=None,
) -> str:
    """Run a multi-turn Copilot agent session with a user feedback loop.

    The agent sends its initial response, then `get_feedback` is called
    with that response. If it returns a string, that feedback is sent back
    to the agent for another turn. If it returns None, the loop ends.

    Args:
        config: Agent configuration.
        initial_prompt: The first prompt to send.
        get_feedback: Called with the agent's response each turn.
            Return a string to continue iterating, or None to accept.
        pipeline_trace: If provided, the session trace is added to it.
        permission_handler: Override the default shell permission handler.
            Use ``_test_permission_handler`` for agents that need to run
            builds and test commands.

    Returns:
        The agent's final accepted response.
    """
    handler = permission_handler or _permission_handler
    async with CopilotClient() as client:
        async with await client.create_session(
            on_permission_request=handler,
            model=config.model,
            mcp_servers=config.mcp_servers or None,
            skill_directories=["~/.copilot/skills"],
            custom_agents=[_agent_dict(config)],
            agent=config.name,
        ) as session:
            observer = SessionObserver(config.name)
            observer.attach(session)

            response = await _send_and_wait(session, initial_prompt)

            while True:
                feedback = get_feedback(response)
                if feedback is None:
                    break
                response = await _send_and_wait(session, feedback)

            trace = observer.finish()
            if pipeline_trace is not None:
                pipeline_trace.add(trace)

            return response


async def _send_and_wait(session, prompt: str) -> str:
    """Send a prompt and wait for the agent to finish, returning its response."""
    done = asyncio.Event()
    response_parts: list[str] = []

    def on_event(event):
        match event.data:
            case AssistantMessageData() as data:
                response_parts.append(data.content)
            case SessionIdleData():
                done.set()

    unsubscribe = session.on(on_event)
    try:
        await session.send(prompt)
        await done.wait()
    finally:
        unsubscribe()

    return "\n".join(response_parts)


def _agent_dict(config: AgentConfig) -> dict:
    """Convert an AgentConfig to the dict format expected by the SDK."""
    d: dict = {
        "name": config.name,
        "description": config.description,
        "prompt": config.prompt,
    }
    if config.tools is not None:
        d["tools"] = config.tools
    if config.mcp_servers:
        d["mcp_servers"] = config.mcp_servers
    if config.skills:
        d["skills"] = config.skills
    return d
