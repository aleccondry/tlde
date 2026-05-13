"""Firmware emulation pipeline.

Runs the FirmwareEmulationManager to decompose a microcontroller target into
work units, then dispatches a FirmwareEmulationEngineer for each unit.
"""

import asyncio
import json
import sys

from tlde.agent import run_agent
from tlde.agents import AGENTS
from tlde.observability import PipelineTrace


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m tlde.pipeline.firmware_emulation <pdf_path> [pdf_path ...]")
        print("\nProvide one or more PDF spec documents for the target MCU.")
        sys.exit(1)

    pdf_paths = sys.argv[1:]
    trace = PipelineTrace()

    # --- Phase 1: Manager decomposes the work ---
    manager = AGENTS["firmware_emulation_manager"]()
    print(f"[Manager] Running {manager.name} (model: {manager.model})")
    print(f"[Manager] PDF specs: {pdf_paths}")
    print("-" * 60)

    user_prompt = build_manager_prompt(pdf_paths)
    response = await run_agent(manager, user_prompt, pipeline_trace=trace)

    # Parse structured output
    work_plan = parse_work_plan(response)
    target = work_plan["target"]
    work_units = work_plan["work_units"]

    print(f"[Manager] Target: {target['board']} ({target['soc']})")
    print(f"[Manager] Decomposed into {len(work_units)} work units:")
    for i, unit in enumerate(work_units, 1):
        deps = ", ".join(unit["dependencies"]) if unit["dependencies"] else "none"
        print(f"  {i}. {unit['name']} (deps: {deps})")
    print("-" * 60)

    # --- Phase 2: Dispatch engineers ---
    # Run engineers respecting dependency order (units are pre-sorted by manager)
    completed: dict[str, str] = {}

    for unit in work_units:
        # Wait for dependencies
        missing_deps = [d for d in unit["dependencies"] if d not in completed]
        if missing_deps:
            print(f"[ERROR] {unit['name']} has unmet dependencies: {missing_deps}")
            print("  Work units should be topologically sorted. Skipping.")
            completed[unit["name"]] = "SKIPPED (unmet deps)"
            continue

        print(f"\n[Engineer] Dispatching: {unit['name']}")
        engineer_prompt = build_engineer_prompt(unit, target, completed)

        engineer = AGENTS["firmware_emulation_engineer"](
            name=f"engineer-{unit['name']}",
        )
        engineer_response = await run_agent(
            engineer, engineer_prompt, pipeline_trace=trace
        )

        completed[unit["name"]] = engineer_response
        print(f"[Engineer] Completed: {unit['name']}")

    # --- Summary ---
    print("\n" + "=" * 60)
    trace.finish()
    print(trace.summary())


def build_manager_prompt(pdf_paths: list[str]) -> str:
    """Build the user prompt for the manager agent."""
    paths_list = "\n".join(f"- {p}" for p in pdf_paths)
    return (
        f"Please analyze the following microcontroller specification documents "
        f"and produce an emulation work plan:\n\n"
        f"PDF documents:\n{paths_list}\n\n"
        f"Read each document to identify the target MCU, its peripherals, memory map, "
        f"and bus architecture. Then decompose the emulation into work units as "
        f"described in your instructions."
    )


def build_engineer_prompt(
    unit: dict,
    target: dict,
    completed: dict[str, str],
) -> str:
    """Build a self-contained prompt for an engineer agent."""
    prompt_parts = [
        f"# Work Unit: {unit['name']}",
        f"",
        f"## Target",
        f"- Board: {target['board']}",
        f"- SoC: {target['soc']}",
        f"- Architecture: {target['architecture']}",
        f"- CPU Core: {target['cpu_core']}",
        f"",
        f"## Assignment",
        f"Renode artifact to produce: {unit['renode_artifact']}",
        f"",
        f"## Description",
        unit["description"],
        f"",
        f"## Specification References",
    ]

    for ref in unit.get("spec_references", []):
        prompt_parts.append(
            f"- {ref['document']}, {ref['section']} (pages {ref['pages']}): "
            f"{ref['content']}"
        )

    prompt_parts.append("")
    prompt_parts.append("## Key Registers")
    for reg in unit.get("key_registers", []):
        prompt_parts.append(f"- {reg['name']} (offset {reg['offset']}): {reg['purpose']}")

    if unit.get("notes"):
        prompt_parts.append("")
        prompt_parts.append(f"## Notes")
        prompt_parts.append(unit["notes"])

    if unit["dependencies"]:
        prompt_parts.append("")
        prompt_parts.append("## Context from Dependencies")
        for dep_name in unit["dependencies"]:
            dep_output = completed.get(dep_name, "")
            if dep_output and dep_output not in ("SKIPPED (tier 3)", "SKIPPED (unmet deps)"):
                prompt_parts.append(f"### {dep_name} output:")
                # Truncate long outputs to keep context manageable
                truncated = dep_output[:4000]
                if len(dep_output) > 4000:
                    truncated += "\n... (truncated)"
                prompt_parts.append(truncated)

    return "\n".join(prompt_parts)


def parse_work_plan(response: str) -> dict:
    """Parse the manager's JSON response.

    Handles: raw JSON, markdown code fences, or JSON embedded in prose.
    """
    text = response.strip()

    # Try raw JSON first
    if text.startswith("{"):
        try:
            return _validate_plan(json.loads(text))
        except json.JSONDecodeError:
            pass

    # Strip markdown code fences
    if "```" in text:
        import re

        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return _validate_plan(json.loads(match.group(1)))
            except json.JSONDecodeError:
                pass

    # Last resort: find the outermost { ... } in the response
    start = text.find("{")
    if start != -1:
        # Find matching closing brace by counting nesting
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _validate_plan(json.loads(text[start : i + 1]))
                    except json.JSONDecodeError:
                        break

    print("[ERROR] Could not extract JSON from manager response.")
    print(f"[ERROR] Response starts with: {response[:300]}")
    sys.exit(1)


def _validate_plan(plan: dict) -> dict:
    """Basic validation of the work plan structure."""
    if "target" not in plan or "work_units" not in plan:
        raise ValueError("Missing 'target' or 'work_units' keys")
    return plan


if __name__ == "__main__":
    asyncio.run(main())
