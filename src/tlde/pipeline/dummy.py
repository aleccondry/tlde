"""Dummy pipeline to verify the agent infrastructure works end-to-end."""

import asyncio

from tlde.agent import run_agent
from tlde.agents import AGENTS
from tlde.observability import PipelineTrace


async def main():
    trace = PipelineTrace()

    dummy = AGENTS["dummy"]()
    print(f"Running agent: {dummy.name} (model: {dummy.model})")
    print("-" * 40)

    response = await run_agent(
        dummy,
        "What is 2 + 2? Reply in one sentence.",
        pipeline_trace=trace,
    )

    print(f"\nAgent response:\n{response}")
    trace.finish()
    print(f"\n{trace.summary()}")


if __name__ == "__main__":
    asyncio.run(main())
