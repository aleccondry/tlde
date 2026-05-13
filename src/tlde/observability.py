"""Observability layer for agent sessions.

Captures tool calls, token usage, timing, errors, and full conversation
history. Designed for pipeline-level analysis and prompt refinement.
"""

import time
from dataclasses import dataclass, field

from copilot.generated.session_events import (
    AssistantMessageData,
    AssistantUsageData,
    SessionErrorData,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)


@dataclass
class ToolCall:
    """A single tool invocation."""

    tool_name: str
    tool_call_id: str
    arguments: dict | None = None
    mcp_server: str | None = None
    success: bool | None = None
    started_at: float = 0.0
    duration: float = 0.0


@dataclass
class LLMCall:
    """A single LLM API call."""

    model: str
    input_tokens: float = 0.0
    output_tokens: float = 0.0
    reasoning_tokens: float = 0.0
    cache_read_tokens: float = 0.0
    duration: float = 0.0
    cost: float = 0.0


@dataclass
class SessionTrace:
    """Complete trace of an agent session."""

    agent_name: str
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)
    llm_calls: list[LLMCall] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.ended_at - self.started_at if self.ended_at else 0.0

    @property
    def total_input_tokens(self) -> float:
        return sum(c.input_tokens for c in self.llm_calls)

    @property
    def total_output_tokens(self) -> float:
        return sum(c.output_tokens for c in self.llm_calls)

    @property
    def total_tokens(self) -> float:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(c.cost for c in self.llm_calls)

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    @property
    def failed_tool_calls(self) -> list[ToolCall]:
        return [t for t in self.tool_calls if t.success is False]

    def tool_call_breakdown(self) -> dict[str, int]:
        """Count of calls per tool name."""
        counts: dict[str, int] = {}
        for tc in self.tool_calls:
            counts[tc.tool_name] = counts.get(tc.tool_name, 0) + 1
        return counts

    def summary(self) -> str:
        """Human-readable summary of the session."""
        lines = [
            f"Agent: {self.agent_name}",
            f"Duration: {self.duration:.1f}s",
            f"Tokens: {self.total_input_tokens:.0f} in / {self.total_output_tokens:.0f} out",
            f"Tool calls: {self.tool_call_count} ({len(self.failed_tool_calls)} failed)",
            f"LLM calls: {len(self.llm_calls)}",
            f"Errors: {len(self.errors)}",
        ]
        breakdown = self.tool_call_breakdown()
        if breakdown:
            lines.append("Tool breakdown:")
            for tool, count in sorted(breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"  {tool}: {count}")
        return "\n".join(lines)


class SessionObserver:
    """Attaches to a Copilot session and records a SessionTrace.

    Usage:
        observer = SessionObserver("my-agent")
        observer.attach(session)
        # ... run the session ...
        trace = observer.finish()
        print(trace.summary())
    """

    def __init__(self, agent_name: str):
        self.trace = SessionTrace(agent_name=agent_name)
        self._pending_tools: dict[str, ToolCall] = {}
        self._unsubscribe = None

    def attach(self, session) -> None:
        """Subscribe to session events."""
        self._unsubscribe = session.on(self._on_event)

    def finish(self) -> SessionTrace:
        """Stop observing and return the completed trace."""
        self.trace.ended_at = time.time()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        return self.trace

    def _on_event(self, event) -> None:
        match event.data:
            case ToolExecutionStartData() as data:
                tc = ToolCall(
                    tool_name=data.tool_name,
                    tool_call_id=data.tool_call_id,
                    arguments=data.arguments,
                    mcp_server=data.mcp_server_name,
                    started_at=time.time(),
                )
                self._pending_tools[data.tool_call_id] = tc
                self.trace.tool_calls.append(tc)

            case ToolExecutionCompleteData() as data:
                tc = self._pending_tools.pop(data.tool_call_id, None)
                if tc:
                    tc.success = data.success
                    tc.duration = time.time() - tc.started_at

            case AssistantUsageData() as data:
                self.trace.llm_calls.append(LLMCall(
                    model=data.model,
                    input_tokens=data.input_tokens or 0,
                    output_tokens=data.output_tokens or 0,
                    reasoning_tokens=data.reasoning_tokens or 0,
                    cache_read_tokens=data.cache_read_tokens or 0,
                    duration=data.duration or 0,
                    cost=data.cost or 0,
                ))

            case AssistantMessageData() as data:
                self.trace.messages.append(data.content)

            case SessionErrorData() as data:
                self.trace.errors.append(f"{data.error_type}: {data.message}")


@dataclass
class PipelineTrace:
    """Aggregated trace across all agents in a pipeline run."""

    session_traces: list[SessionTrace] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0

    def add(self, trace: SessionTrace) -> None:
        self.session_traces.append(trace)

    def finish(self) -> "PipelineTrace":
        self.ended_at = time.time()
        return self

    @property
    def duration(self) -> float:
        return self.ended_at - self.started_at if self.ended_at else 0.0

    @property
    def total_tokens(self) -> float:
        return sum(t.total_tokens for t in self.session_traces)

    @property
    def total_cost(self) -> float:
        return sum(t.total_cost for t in self.session_traces)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "PIPELINE TRACE",
            "=" * 60,
            f"Total duration: {self.duration:.1f}s",
            f"Total tokens: {self.total_tokens:.0f}",
            f"Total cost: ${self.total_cost:.4f}",
            f"Agents run: {len(self.session_traces)}",
            "",
        ]
        for trace in self.session_traces:
            lines.append("-" * 40)
            lines.append(trace.summary())
            lines.append("")
        return "\n".join(lines)
