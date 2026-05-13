# Firmware Emulation Pipeline

This pipeline automatically generates working Renode microcontroller emulations from PDF datasheets using a multi-agent workflow built on the GitHub Copilot SDK.

## Architecture

```
PDF datasheets ──► Manager ──► Engineer–Verifier pairs (parallel) ──► Tester
```

## Phase 1: Manager (Opus 4.6)

A planning agent reads MCU PDF specs via a pdf-reader MCP tool and produces a **topologically-sorted JSON work plan**. Each work unit describes one peripheral or subsystem to emulate (UART, SPI, GPIO, timers, etc.), including spec references, key registers, dependencies on other units, and what Renode artifact to produce.

## Phase 2: Engineer–Verifier Loops (Sonnet 4.6, parallel)

Each work unit is processed by a **paired engineer + verifier**:

1. The **Emulation Engineer** reads the PDF datasheet and produces Renode `.repl` platform descriptions and C# peripheral models, citing register addresses and reset values from the spec.
2. The **Verification Engineer** treats the engineer's output as *untrusted* — cross-checks every base address, size, and IRQ against the reference manual PDF and produces a structured `verification_report.json` with per-peripheral verdicts (`verified`, `mismatch_fixed`, `mismatch_escalated`, `unverifiable`).
3. If mismatches are found, the verifier's feedback is sent back to a **fresh engineer** for revision, with the specific citations and corrections needed.
4. This loop repeats up to **3 attempts** per work unit.

**Parallelism**: All work units launch concurrently via `asyncio.gather`. Each unit internally awaits its dependency events (`asyncio.Event`) before starting, so independent peripherals (e.g., UART and SPI) run in parallel while dependent units (e.g., board-level wiring depends on all SoC peripherals) wait automatically.

## Phase 3: Testing (Sonnet 4.6)

After all engineer–verifier pairs complete, a **Test Aggregator** agent:
1. Reads the verification reports to identify expected-failure peripherals.
2. Builds sample firmware for the target board.
3. Writes Robot Framework test suites exercising the emulated hardware under Renode.
4. Runs the tests and classifies failures as **expected** (known limitation per verifier) vs **unexpected** (regression or modeling error).

## Agent Roster

| Agent | Model | Role |
|---|---|---|
| `firmware_emulation_manager` | Opus 4.6 | Reads PDFs, decomposes into work plan |
| `fw_emu_eng` | Sonnet 4.6 | Builds `.repl` + C# peripheral models per work unit |
| `fw_verif_eng` | Sonnet 4.5 | Cross-checks artifacts against vendor docs |
| `emu_test_agg` | Sonnet 4.6 | Builds firmware, writes + runs Robot Framework tests |

## Infrastructure

- **`AgentConfig`** — Declarative dataclass for agent configuration (model, prompt, MCP servers, skills).
- **`AGENTS` registry** — Auto-discovers agent classes from `src/tlde/agents/` modules.
- **`run_agent` / `run_agent_interactive`** — Copilot SDK session runners (single-turn and multi-turn with feedback).
- **`PipelineTrace`** — Observability layer capturing tool calls, token usage, timing, and costs per agent.
