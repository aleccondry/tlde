"""Firmware emulation pipeline.

Runs the full emulation workflow:
  Phase 1: Manager decomposes MCU specs into work units.
  Phase 2: Engineer–Verifier loops per work unit (parallel where deps allow).
           Each unit gets an engineer that builds artifacts, then a verifier
           that cross-checks against vendor docs. Mismatches loop back to the
           engineer for revision, up to MAX_VERIFY_RETRIES times.
  Phase 3: Test aggregator builds firmware samples, runs Robot Framework tests.
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass

from tlde.agent import run_agent, _approve_all_handler
from tlde.agents import AGENTS
from tlde.observability import PipelineTrace

MAX_VERIFY_RETRIES = 3


def _model_override():
    return os.environ.get("TLDE_MODEL")


@dataclass
class WorkUnitResult:
    """Outcome of the engineer–verifier loop for one work unit."""

    name: str
    engineer_response: str
    verifier_response: str
    verified: bool
    attempts: int
    skipped: bool = False
    skip_reason: str = ""


async def main():
    if len(sys.argv) < 2:
        print("Usage: tlde <prompt>")
        print('\nExample: tlde "Emulate the nRF52833 using the specs in ./docs/"')
        sys.exit(1)

    user_prompt = " ".join(sys.argv[1:])
    trace = PipelineTrace()

    # --- Phase 1: Manager decomposes the work ---
    work_plan = await phase_manager(user_prompt, trace)
    target = work_plan["target"]
    work_units = work_plan["work_units"]
    board = target["board"]

    # --- Phase 2: Engineer–Verifier loops (parallel where deps allow) ---
    results = await phase_engineer_verifier(target, work_units, user_prompt, trace)

    # --- Phase 3: Test aggregator builds + runs Robot Framework tests ---
    test_report = await phase_testing(board, trace)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Target: {board} ({target['soc']})")
    verified = sum(1 for r in results.values() if r.verified)
    failed = sum(1 for r in results.values() if not r.verified and not r.skipped)
    skipped = sum(1 for r in results.values() if r.skipped)
    print(f"Work units: {verified} verified, {failed} failed, {skipped} skipped")
    print(f"Testing: done")

    trace.finish()
    print(f"\n{trace.summary()}")


# ---------------------------------------------------------------------------
# Phase 1: Manager
# ---------------------------------------------------------------------------

async def phase_manager(
    user_prompt: str, trace: PipelineTrace,
) -> dict:
    """Manager reads PDF specs and produces a structured work plan."""
    model = _model_override()
    manager = AGENTS["firmware_emulation_manager"](
        **({"model": model} if model else {}),
    )
    print(f"[Phase 1: Manager] Running {manager.name} (model: {manager.model})")
    print(f"[Phase 1: Manager] Prompt: {user_prompt}")
    print("-" * 60)

    prompt = build_manager_prompt(user_prompt)
    response = await run_agent(
        manager, prompt, pipeline_trace=trace,
        permission_handler=_approve_all_handler,
    )

    work_plan = parse_work_plan(response)
    target = work_plan["target"]
    work_units = work_plan["work_units"]

    print(f"[Phase 1: Manager] Target: {target['board']} ({target['soc']})")
    print(f"[Phase 1: Manager] Decomposed into {len(work_units)} work units:")
    for i, unit in enumerate(work_units, 1):
        deps = ", ".join(unit["dependencies"]) if unit["dependencies"] else "none"
        print(f"  {i}. {unit['name']} (deps: {deps})")
    print("-" * 60)

    return work_plan


# ---------------------------------------------------------------------------
# Phase 2: Engineer–Verifier loops (parallel with dependency awareness)
# ---------------------------------------------------------------------------

async def phase_engineer_verifier(
    target: dict,
    work_units: list[dict],
    user_prompt: str,
    trace: PipelineTrace,
) -> dict[str, WorkUnitResult]:
    """Run engineer–verifier pairs, parallelizing independent work units.

    Work units are dispatched as soon as all their dependencies have completed.
    Each unit runs an engineer→verifier loop: if the verifier finds mismatches,
    the feedback is sent back to the engineer for another attempt, up to
    MAX_VERIFY_RETRIES times.
    """
    board = target["board"]
    print(f"\n[Phase 2: Engineer–Verifier] Processing {len(work_units)} work units")
    print("-" * 60)

    results: dict[str, WorkUnitResult] = {}
    completed_events: dict[str, asyncio.Event] = {
        unit["name"]: asyncio.Event() for unit in work_units
    }
    async def process_unit(unit: dict) -> WorkUnitResult:
        name = unit["name"]

        # Wait for all dependencies to complete
        for dep in unit["dependencies"]:
            if dep in completed_events:
                await completed_events[dep].wait()
            if dep in results and results[dep].skipped:
                result = WorkUnitResult(
                    name=name,
                    engineer_response="",
                    verifier_response="",
                    verified=False,
                    attempts=0,
                    skipped=True,
                    skip_reason=f"dependency '{dep}' was skipped",
                )
                results[name] = result
                completed_events[name].set()
                print(f"[Phase 2] SKIPPED: {name} (dependency '{dep}' was skipped)")
                return result

        # Collect dependency context
        dep_context: dict[str, str] = {}
        for dep in unit["dependencies"]:
            if dep in results:
                dep_context[dep] = results[dep].engineer_response

        # Engineer–Verifier loop
        engineer_response = ""
        verifier_response = ""
        verified = False

        for attempt in range(1, MAX_VERIFY_RETRIES + 1):
            # --- Engineer ---
            print(f"\n[Phase 2: Engineer] {name} (attempt {attempt}/{MAX_VERIFY_RETRIES})")
            if attempt == 1:
                eng_prompt = build_engineer_prompt(unit, target, dep_context)
            else:
                eng_prompt = build_engineer_revision_prompt(
                    unit, target, engineer_response, verifier_response,
                )

            engineer = AGENTS["fw_emu_eng"](
                name=f"engineer-{name}-attempt{attempt}",
                **({"model": _model_override()} if _model_override() else {}),
            )
            engineer_response = await run_agent(
                engineer, eng_prompt, pipeline_trace=trace,
            )
            print(f"[Phase 2: Engineer] {name} built artifacts (attempt {attempt})")

            # --- Verifier ---
            print(f"[Phase 2: Verifier] {name} (attempt {attempt}/{MAX_VERIFY_RETRIES})")
            verifier = AGENTS["fw_verif_eng"](
                name=f"verifier-{name}-attempt{attempt}",
                **({"model": _model_override()} if _model_override() else {}),
            )
            ver_prompt = build_unit_verifier_prompt(unit, board, user_prompt)
            verifier_response = await run_agent(
                verifier, ver_prompt, pipeline_trace=trace,
            )

            verified = check_verification_passed(verifier_response)
            if verified:
                print(f"[Phase 2: Verifier] ✔ {name} verified on attempt {attempt}")
                break
            else:
                print(f"[Phase 2: Verifier] ✗ {name} has mismatches (attempt {attempt})")

        if not verified:
            print(f"[Phase 2] ✗ {name} NOT verified after {MAX_VERIFY_RETRIES} attempts")

        result = WorkUnitResult(
            name=name,
            engineer_response=engineer_response,
            verifier_response=verifier_response,
            verified=verified,
            attempts=attempt,
        )
        results[name] = result
        completed_events[name].set()
        return result

    # Launch all units concurrently — each waits for its own deps internally
    tasks = [asyncio.create_task(process_unit(unit)) for unit in work_units]
    await asyncio.gather(*tasks)

    verified_count = sum(1 for r in results.values() if r.verified)
    total = len(work_units)
    print(f"\n[Phase 2] {verified_count}/{total} work units verified")
    print("-" * 60)

    return results


# ---------------------------------------------------------------------------
# Phase 3: Testing
# ---------------------------------------------------------------------------

async def phase_testing(
    board: str,
    trace: PipelineTrace,
) -> str:
    """Test aggregator builds firmware, writes Robot tests, runs them."""
    print(f"\n[Phase 3: Testing] Building and testing emulation for {board}")
    print("-" * 60)

    tester = AGENTS["emu_test_agg"](
        **({"model": _model_override()} if _model_override() else {}),
    )
    prompt = build_tester_prompt(board)
    response = await run_agent(tester, prompt, pipeline_trace=trace)

    print(f"[Phase 3: Testing] Complete")
    print("-" * 60)

    return response


# ---------------------------------------------------------------------------
# Verification result parsing
# ---------------------------------------------------------------------------

def check_verification_passed(verifier_response: str) -> bool:
    """Determine if the verifier found the artifacts acceptable.

    Returns True when there are no mismatch_escalated or mismatch_fixed
    verdicts remaining (i.e. everything is verified or unverifiable).
    """
    # Try to parse the verification_report.json from the response
    report = _extract_json(verifier_response)
    if report and "summary" in report:
        summary = report["summary"]
        return (
            summary.get("mismatch_fixed", 0) == 0
            and summary.get("mismatch_escalated", 0) == 0
        )

    # Fallback: heuristic text matching
    lower = verifier_response.lower()
    if "mismatch_fixed" in lower or "mismatch_escalated" in lower:
        return False
    if "all peripherals verified" in lower or '"verified"' in lower:
        return True
    # Conservative: assume not verified if we can't tell
    return False


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from text (handles code fences)."""
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_manager_prompt(user_prompt: str) -> str:
    """Build the user prompt for the manager agent."""
    return (
        f"{user_prompt}\n\n"
        f"Read the specification documents to identify the target MCU, its "
        f"peripherals, memory map, and bus architecture. Then decompose the "
        f"emulation into work units as described in your instructions."
    )


def build_engineer_prompt(
    unit: dict,
    target: dict,
    completed: dict[str, str],
) -> str:
    """Build a self-contained prompt for an engineer's initial attempt."""
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
                truncated = dep_output[:4000]
                if len(dep_output) > 4000:
                    truncated += "\n... (truncated)"
                prompt_parts.append(truncated)

    return "\n".join(prompt_parts)


def build_engineer_revision_prompt(
    unit: dict,
    target: dict,
    previous_engineer_output: str,
    verifier_feedback: str,
) -> str:
    """Build a revision prompt with verifier feedback for the engineer."""
    return (
        f"# Revision Required: {unit['name']}\n\n"
        f"## Target\n"
        f"- Board: {target['board']}\n"
        f"- SoC: {target['soc']}\n"
        f"- Architecture: {target['architecture']}\n"
        f"- CPU Core: {target['cpu_core']}\n\n"
        f"## Original Assignment\n"
        f"{unit['description']}\n\n"
        f"## Your Previous Output\n"
        f"Your previous artifacts were reviewed by a verification engineer who "
        f"cross-checked them against the vendor reference manual PDFs. "
        f"The verifier found mismatches that need to be corrected.\n\n"
        f"### Verifier Feedback\n"
        f"{verifier_feedback}\n\n"
        f"## Your Task\n"
        f"Read the verifier's feedback carefully. For each mismatch:\n"
        f"1. Check the cited datasheet section to confirm the correct value.\n"
        f"2. Update your .repl and/or C# peripheral model to use the verified value.\n"
        f"3. Output complete, revised artifact files (not diffs).\n\n"
        f"Do NOT invent values. If the verifier's citation is unclear, "
        f"use the PDF reader to look up the section yourself."
    )


def build_unit_verifier_prompt(
    unit: dict,
    board: str,
    user_prompt: str,
) -> str:
    """Build the prompt for a verifier checking a single work unit."""
    return (
        f"Verify the emulation artifacts for work unit `{unit['name']}` "
        f"on board `{board}`.\n\n"
        f"## Original request\n{user_prompt}\n\n"
        f"## Artifacts to verify\n"
        f"- Platform description: `output/{board}/*.repl` (entries related to {unit['name']})\n"
        f"- Custom peripherals: `output/{board}/*.cs` (related to {unit['name']})\n\n"
        f"## Your tasks\n"
        f"1. Read the artifacts produced for this work unit from `output/{board}/`.\n"
        f"2. For every peripheral in this unit, cross-check its base address, size, "
        f"and IRQ number against the reference manual PDF.\n"
        f"3. Produce a `verification_report.json` with per-peripheral verdicts.\n"
        f"4. If all peripherals are verified, generate a validated `.resc` snippet "
        f"for this unit.\n"
        f"5. Write any doubt-log entries for unresolvable mismatches.\n\n"
        f"Write all outputs to `output/{board}/`."
    )


def build_tester_prompt(board: str) -> str:
    """Build the prompt for the test aggregator."""
    return (
        f"Run the emulation test workflow for board `{board}`.\n\n"
        f"## Artifacts available\n"
        f"- Verified execution script: `output/{board}/run.resc`\n"
        f"- Verification report: `output/{board}/verification_report.json`\n"
        f"- Platform files: `output/{board}/*.repl`\n"
        f"- Peripheral models: `output/{board}/*.cs`\n"
        f"- Doubt log: `output/{board}/doubt_log.json` (if present)\n"
        f"- Sample firmware: `samples/`\n\n"
        f"## Your tasks\n"
        f"1. Read `verification_report.json` to identify expected-failure peripherals.\n"
        f"2. Build each sample under `samples/` for board `{board}`.\n"
        f"3. Write Robot Framework test suites in `output/{board}/tests/`.\n"
        f"4. Run the tests and classify failures as expected vs unexpected.\n"
        f"5. Write `output/{board}/tests/report.txt` with the results summary."
    )


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


def _cli():
    """CLI entry point for `tlde` command."""
    asyncio.run(main())


if __name__ == "__main__":
    _cli()
