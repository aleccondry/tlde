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

# Shell commands that are safe to allow — directory creation only.
# Matches: mkdir [-p] [-v] <path>  with no shell metacharacters (&&, ||, ;, |, $, `)
_ALLOWED_SHELL = re.compile(r"^\s*mkdir(\s+-[pv]+)?\s+[^;&|$`]+$")


def _permission_handler(request, invocation):
    """Approve all requests except shell commands.

    mkdir (with optional -p / -v flags) is allowed so agents can create
    output directories. All other shell commands are denied.
    """
    if request.kind == PermissionRequestKind.SHELL:
        cmd = request.full_command_text or ""
        if _ALLOWED_SHELL.match(cmd):
            return PermissionRequestResult(kind="approve-once")
        print(f"[BLOCKED] shell: {cmd[:80]}")
        return PermissionRequestResult(kind="deny")
    return PermissionRequestResult(kind="approve-once")


async def run_agent(
    config: AgentConfig,
    prompt: str,
    pipeline_trace: PipelineTrace | None = None,
) -> str:
    """Run a single-turn Copilot agent session.

    Args:
        config: Agent configuration.
        prompt: The user prompt to send.
        pipeline_trace: If provided, the session trace is added to it.

    Returns:
        The agent's final text response.
    """
    async with CopilotClient() as client:
        async with await client.create_session(
            on_permission_request=_permission_handler,
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

    Returns:
        The agent's final accepted response.
    """
    async with CopilotClient() as client:
        async with await client.create_session(
            on_permission_request=_permission_handler,
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
