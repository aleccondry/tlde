# Renode Emulation Builder — Architecture Document

**Version:** 0.1-draft  
**Status:** Pre-planning  
**Audience:** Planning agent, contributors, human reviewers

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [System Inputs](#2-system-inputs)
3. [System Outputs](#3-system-outputs)
4. [Input Schema — `renode-builder.yaml`](#4-input-schema--renode-builderyaml)
5. [Phase Machine](#5-phase-machine)
6. [Agent Roster](#6-agent-roster)
7. [MCP Server Layer — Specifications](#7-mcp-server-layer--specifications)
8. [MCP Implementation Track (Phase 0a)](#8-mcp-implementation-track-phase-0a)
9. [The Feedback Loop](#9-the-feedback-loop)
10. [Human-in-the-Loop Gates](#10-human-in-the-loop-gates)
11. [The Doubt Log](#11-the-doubt-log)
12. [Multipass Execution Environment](#12-multipass-execution-environment)
13. [Deliverable Layout](#13-deliverable-layout)
14. [Cross-Cutting Principles](#14-cross-cutting-principles)
15. [Failure Mode Coverage](#15-failure-mode-coverage)
16. [Source-of-Truth Precedence](#16-source-of-truth-precedence)
17. [Fidelity Tier Model](#17-fidelity-tier-model)
18. [Use-Case Detection Matrix](#18-use-case-detection-matrix)
19. [Known Renode Gotchas](#19-known-renode-gotchas)

---

## 1. System Overview

The Renode Emulation Builder is a fully LLM-driven agentic pipeline that accepts an embedded target description and a pre-built firmware project, and produces a complete, working Antmicro Renode emulation package for it — including platform models, peripheral C# implementations, execution scripts, Robot Framework tests, and documentation.

The system is designed to run inside an isolated Multipass instance and is orchestrated by a Claude-based planning agent. All code, models, scripts, and tests are LLM-generated. A human approves decisions at defined gates.

### Architecture Style: Hybrid

The architecture is a **hybrid** of two complementary patterns:

- **Claude Code-style agentic pipeline** — an orchestrator that owns the phase machine, dispatches specialist sub-tasks, manages state, and enforces budgets and gates.
- **MCP server layer** — stateful, reusable capability servers that expose deterministic tool interfaces to the orchestrator. The LLM reasons; the MCP servers act.

```
┌─────────────────────────────────────────────────────────┐
│              Claude Orchestrator                        │
│  (phase machine · budget · doubt log · HITL gates)      │
└────────┬───────────────┬──────────────┬─────────────────┘
         │               │              │
         ▼               ▼              ▼
  ┌────────────┐  ┌────────────┐  ┌───────────────┐
  │  Renode    │  │  PDF/Doc   │  │  Peripheral   │
  │  Control   │  │  Index     │  │  Inspector    │
  │  MCP       │  │  MCP       │  │  MCP          │
  └────────────┘  └────────────┘  └───────────────┘
```

---

## 2. System Inputs

| Input | Format | Required | Notes |
|---|---|---|---|
| Target description | `renode-builder.yaml` | Yes | Full schema in §4 |
| MCU reference manual | PDF | Yes | Primary source of truth |
| Board datasheet | PDF | Yes | Secondary source |
| Errata sheet | PDF | No | Logged in doubt log if absent |
| SVD file | XML | No | Used for tag generation if present |
| Existing `.repl` community model | File | No | Inspect-before-trust |
| Pre-built firmware | ELF / HEX / BIN | Yes | See format rules §4.2 |
| MCUboot bootloader binary | ELF / HEX / BIN | If MCUboot | See §4.2 |
| Signed application binary | BIN / HEX | If MCUboot | Packaged with `imgtool.py` |
| Vendor app notes / URLs | URL | No | Optional supplementary docs |

---

## 3. System Outputs

```
<board>-renode/
  ├── Makefile
  ├── README.md
  ├── platform/
  │   ├── <soc>.repl          # SoC-level platform description
  │   └── <board>.repl        # Board-level, includes <soc>.repl
  ├── peripherals/
  │   └── <Peripheral>.cs     # Custom C# peripheral models
  ├── scripts/
  │   └── run.resc            # Renode execution script
  ├── tests/
  │   ├── golden_path.robot   # Golden path test (positive)
  │   └── negative.robot      # Negative test (fault detection)
  ├── DOUBT_LOG.md            # All assumptions with confidence and blast radius
  ├── LIMITATIONS.md          # Unmodeled peripherals with rationale
  └── ATTRIBUTION.md          # License attribution for forked stock peripherals
```

### Makefile Targets

| Target | Description |
|---|---|
| `emulate` | Launch interactive Renode session with platform loaded |
| `test` | Run `renode-test` on both robot files |
| `test-golden` | Run golden path test only |
| `test-negative` | Run negative test only |
| `clean` | Remove run artifacts and snapshots |
| `shell` | Drop into Renode monitor with platform loaded |
| `tap-up` / `tap-down` | Create / destroy TAP interface (networking targets only) |
| `build-mcuboot` | Re-sign the app binary (MCUboot targets only) |

---

## 4. Input Schema — `renode-builder.yaml`

### 4.1 Full Schema

```yaml
# renode-builder.yaml
version: "1.0"

# ── Target Identity ──────────────────────────────────────────────
target:
  board: "nucleo_f446re"           # Zephyr board name (canonical)
  soc: "stm32f446re"               # MCU identifier
  arch: "arm"                      # arm | riscv | xtensa | x86
  cpu: "cortex-m4"                 # core variant

# ── Pre-built Application ────────────────────────────────────────
application:
  build_dir: "./build"             # path to west build output

  primary:
    elf: "./build/zephyr/zephyr.elf"       # preferred
    hex: "./build/zephyr/zephyr.hex"       # alternative
    bin: "./build/zephyr/zephyr.bin"       # alternative; requires load_address
    load_address: null                     # required if bin only; ignored for elf/hex

  # MCUboot: omit entire block if not used
  mcuboot:
    bootloader:
      elf: "./build/mcuboot/zephyr/zephyr.elf"
      hex: "./build/mcuboot/zephyr/zephyr.hex"
      bin: "./build/mcuboot/zephyr/zephyr.bin"
      load_address: "0x00000000"
    signed_app:
      bin: "./build/zephyr/zephyr.signed.bin"
      hex: "./build/zephyr/zephyr.signed.hex"
      load_address: "0x00020000"           # auto-detected from DTS if omitted

# ── Documentation Sources ────────────────────────────────────────
documentation:
  - kind: "mcu_reference_manual"
    path: "./docs/rm0390-stm32f446.pdf"
    vendor: "ST"
  - kind: "board_datasheet"
    path: "./docs/nucleo-f446re-um.pdf"
    vendor: "ST"
  - kind: "errata"
    path: "./docs/stm32f446-errata.pdf"
    vendor: "ST"
    optional: true
  - kind: "vendor_appnote"
    url: "https://example.com/appnote.pdf"
    optional: true

# ── Additional Resources ─────────────────────────────────────────
resources:
  - kind: "existing_repl"
    path: "./reference/nucleo_f446re.repl"
    note: "Community model, inspect before use"
  - kind: "zephyr_dts_upstream"
    url: "https://github.com/zephyrproject-rtos/zephyr/blob/main/boards/..."
  - kind: "svd"
    path: "./docs/STM32F446.svd"
    optional: true

# ── Use-Case Hints ───────────────────────────────────────────────
# Profiler validates these against resolved .config and zephyr.dts.
# Contradictions become doubt-log entries.
hints:
  networking: false
  bluetooth: false
  mcuboot: true
  filesystem: false
  shell: true
  multi_binary: false

# ── Golden Path Definition ───────────────────────────────────────
golden_path:
  description: "Device boots, MCUboot chains to app, shell prompt appears"
  console_markers:
    - "*** Booting Zephyr OS"
    - "I: Starting bootloader"
    - "I: Jumping to the first image slot"
    - "*** Booting Zephyr OS"
    - "uart:~$"
  timeout_virtual_seconds: 30

# ── Fidelity Overrides ───────────────────────────────────────────
fidelity:
  force_tier1: []
  force_tier2: ["stm32_rng"]
  force_tier3: ["stm32_crc"]

# ── Known Limitations (pre-declared) ────────────────────────────
known_limitations:
  - peripheral: "stm32_qspi"
    reason: "External flash not wired on this board variant"
    mitigation: "DTS overlay disables node; safe to omit"

# ── Pipeline Configuration ───────────────────────────────────────
pipeline:
  max_iterations_per_milestone: 15
  max_iterations_per_signature: 3
  max_wall_clock_minutes: 480
  determinism_runs: 5
  renode_version: "1.15.0"
  zephyr_version: "3.6.0"

  # MCP server versions — pinned. Health check fails if installed version
  # differs from these, triggering regeneration via Phase 0a.
  mcp_versions:
    pdf_doc_index: "1.0.0"
    peripheral_inspector: "1.0.0"
    renode_control: "1.0.0"

  # MCP Phase 0a budgets (per server)
  mcp_phase0a:
    max_iterations_per_stage: 3
    max_wall_clock_minutes_per_server: 90

# ── Output ────────────────────────────────────────────────────────
output:
  directory: "./renode-nucleo_f446re"
  overwrite: false
```

### 4.2 Binary Format Rules

| Format | Renode Command | Load Address Required | Notes |
|---|---|---|---|
| ELF | `sysbus LoadELF` | No — embedded in file | Preferred. Contains symbols and section info. |
| HEX | `sysbus LoadHEX` | No — embedded in file | Used when ELF unavailable. |
| BIN | `sysbus LoadBinary` | **Yes — mandatory** | Raw bytes. Address from DTS or explicit `load_address`. |

**Format precedence (when multiple provided):** ELF > HEX > BIN.

**Validation rule:** BIN without a `load_address` resolvable from either the YAML or the DTS partition table is a **hard intake error**. The pipeline stops before any modeling work begins.

**Cross-validation:** `load_address` declared in YAML is validated against the DTS `flash_partitions` node during the Profiler pass. Disagreement → doubt-log entry + HITL flag before the loop starts.

---

## 5. Phase Machine

The pipeline runs as a strict phase machine. Each phase has a defined input contract, output contract, and (for some) a HITL gate before the next phase begins.

```
Phase 0: BOOTSTRAP
  └─► Validate YAML · verify Multipass environment · verify binary format rules
          │
          ▼
Phase 0a: MCP IMPLEMENTATION  (skipped if cached & passing health checks)
  ├─► PDF/Doc Index MCP        → spec → implement → self-test → install
  ├─► Peripheral Inspector MCP → spec → implement → self-test → install
  └─► Renode Control MCP       → spec → implement → self-test → install
          │
          ▼ [HITL Gate A0: MCP Approval]  (one-time per Multipass instance)
          │
Phase 1: ANALYSIS  (parallel workers)
  ├─► Documentation Miner     → peripherals.json
  ├─► Application Profiler    → capability_manifest.json
  └─► Renode Recon Agent      → recon_report.json
          │
          ▼
Phase 2: PLAN
  └─► Architect               → plan.md + plan.json
          │
          ▼ [HITL Gate A: Plan Approval]
          │
Phase 3: SCAFFOLD
  └─► Modeler + Test Author   → initial .repl, .cs stubs, .resc, .robot skeletons
          │
          ▼
Phase 4: BRING-UP LOOP
  ├─► M1: Binary loads, CPU executes       [HITL Gate B]
  ├─► M2: Zephyr reaches main()            [HITL Gate C]
  ├─► M3: UART console output works        [HITL Gate D]
  ├─► M4: Golden path completes            [HITL Gate E]
  └─► M5: Robot test stable across N runs  [HITL Gate F]
          │
          ▼
Phase 5: PACKAGE
  └─► Packager                → final deliverable + README + DOUBT_LOG
          │
          ▼ [HITL Gate G: Final Delivery]
          │
          ▼
      DELIVERABLE
```

### Phase 0a — MCP Implementation

**Triggered when:** At least one required MCP server is missing from `/tools/mcp-servers/` or fails its health check at Phase 0 startup.

**Skipped when:** All three servers are present at the expected versions and pass health checks. This is the **build-once, reuse-forever** path — the first target build in a Multipass instance pays this cost; subsequent target builds skip Phase 0a entirely.

**Output:** Three validated Python MCP servers installed at `/tools/mcp-servers/<name>/`, each with its own self-test suite that passes. See §8 for the full implementation track specification.

**HITL Gate A0:** One-time approval gate (per Multipass instance, not per target build). Reviewed once when the MCP servers are first built; the human's approval is persisted and not re-prompted unless the servers are regenerated.

### Phase 0a Implementation Sequence

The three MCP servers are built in **increasing-risk order** so that the meta-pipeline (LLM building infrastructure for itself) is validated on the lowest-risk server first:

1. **PDF/Doc Index MCP** — lowest risk (well-understood RAG pattern).
2. **Peripheral Inspector MCP** — medium risk (transformation + file inspection).
3. **Renode Control MCP** — highest risk (interactive protocol with session state; feedback loop correctness depends on it).

If the PDF/Doc Index build fails, the entire pipeline aborts before attempting the harder servers — that's a strong signal the meta-pipeline isn't working.

### Phase 1 Parallelism

Documentation Miner, Application Profiler, and Renode Recon Agent run in parallel. The Architect cannot start until all three complete and their outputs are validated.

### Phase 3 Strategy

Scaffolding produces **minimum-viable stubs** — not polished models. The goal is to reach M1 (binary executes) as fast as possible. Stubs are replaced by full models through the bring-up loop, driven by actual failure signals.

---

## 6. Agent Roster

### 6.1 Orchestrator

**Role:** Owns the phase machine. Dispatches specialists. Holds the doubt log, failure-signature log, and budget ledger. Surfaces HITL gates.

**Authorities:**
- Only agent that can advance or abort phases.
- Only agent that can trigger HITL.
- Only agent that writes to the doubt log and budget ledger.

**Constraints:**
- Never edits C#, `.repl`, `.resc`, or `.robot` files directly.
- Must re-read `plan.md` at every phase boundary.
- Must update the doubt log when surfacing HITL.

---

### 6.2 Documentation Miner

**Role:** Phase 1. Ingests MCU RM + board datasheet PDFs via the PDF/Doc Index MCP. Produces structured peripheral data.

**Output:** `peripherals.json`

```json
{
  "soc": { "name": "...", "arch": "...", "memory_map": [...], "interrupts": [...] },
  "peripherals": [
    {
      "name": "USART1",
      "base_addr": "0x40011000",
      "size": "0x400",
      "irq": 37,
      "registers": [...],
      "chapter_ref": "RM0090 §30.6",
      "confidence": "confirmed"
    }
  ],
  "board": { "name": "...", "soc_ref": "...", "external_components": [...] }
}
```

**Confidence levels:**

| Level | Meaning |
|---|---|
| `confirmed` | Directly copied from a table in the document |
| `inferred` | Cross-referenced across multiple document sections |
| `assumed` | Not found; a default was applied |

Anything `assumed` flows immediately to the doubt log.

**Constraints:**
- Must cite chapter/section for every claim.
- Must never invent register addresses. Unknown → mark `unknown` and flag.

---

### 6.3 Application Profiler

**Role:** Phase 1. Analyzes the pre-built application artifacts to produce the capability manifest and Tier-1 peripheral set.

**Inputs:** `build/zephyr/zephyr.dts` (resolved), `build/zephyr/.config` (resolved), ELF symbol table, YAML hints.

**Output:** `capability_manifest.json`

```json
{
  "zephyr_version": "3.6.0",
  "toolchain": "zephyr-sdk-0.16.1",
  "use_cases": {
    "networking": { "enabled": false },
    "bluetooth": { "enabled": false },
    "mcuboot": { "enabled": true, "slot_layout": {...}, "sysbuild": false },
    "filesystem": { "enabled": false },
    "shell": { "enabled": true, "uart_backend": "uart0" }
  },
  "tier1_peripherals": ["USART1", "RCC", "FLASH", "NVIC", "SYSTICK"],
  "tier2_peripherals": ["GPIO_A", "GPIO_B"],
  "golden_path": "Device boots MCUboot, chains to app, shell prompt on uart0",
  "expected_console_markers": ["*** Booting Zephyr OS", "uart:~$"]
}
```

**Key rule:** The `expected_console_markers` array is the most load-bearing output. It directly becomes the robot test's `Wait For Line` assertions. If the Profiler cannot identify markers, it must escalate to HITL before Phase 2 starts — a test with no assertions is worse than no test.

**Constraints:**
- Uses resolved build artifacts, not source files. Overrides from YAML hints are validated against resolved DTS. Contradictions → doubt-log entry.

---

### 6.4 Renode Recon Agent

**Role:** Phase 1. For each Tier-1 peripheral, searches Renode upstream and Renodepedia via the Peripheral Inspector MCP, then diffs the candidate against the reference manual data.

**Output:** `recon_report.json`

```json
{
  "peripherals": [
    {
      "name": "USART1",
      "renode_candidate": "Peripherals/UART/STM32_UART.cs",
      "diff_vs_refmanual": [
        { "register": "CR1", "verdict": "match" },
        { "register": "ISR", "verdict": "partial", "missing_bits": ["TEACK", "REACK"] }
      ],
      "verdict": "fork_and_patch",
      "confidence": "medium"
    }
  ]
}
```

**Verdict options:**

| Verdict | Meaning |
|---|---|
| `reuse_as_is` | Diff is clean; justified in doubt log |
| `fork_and_patch` | Exists but has specific known issues; list changes needed |
| `replace` | Exists but is too broken to patch |
| `scaffold_new` | No candidate found; use `peakrdl-renode` |
| `stub` | Peripheral too simple or too risky; use a logging stub |

**Constraints:**
- `reuse_as_is` is **never** the default. Every reuse requires a documented diff entry. No exceptions.

---

### 6.5 Architect

**Role:** Phase 2. Synthesizes all Phase 1 outputs into the plan.

**Output:** `plan.md` (human-readable) + `plan.json` (machine-readable)

The plan file is the **single source of truth** for all downstream agents. It captures:
- File layout of the deliverable.
- Per-peripheral strategy (reuse / fork / scaffold / stub / tag).
- Milestone definitions with concrete, measurable success criteria.
- Feedback-loop budgets per milestone and per failure signature.
- Open assumptions with blast radius.
- Kill-switch trigger per milestone.

**Constraints:**
- Plan must be approved at **HITL Gate A** before any code is written. No exceptions.
- Must list every assumption with its blast radius.
- Must list a kill-switch trigger per milestone.

---

### 6.6 Modeler

**Role:** Phase 4 worker. Produces and modifies C# peripheral models, `.repl` files, and `.resc` peripheral-load lines.

**Sub-modes:**

| Mode | Trigger | Mechanism |
|---|---|---|
| `scaffold` | `recon_report` verdict = `scaffold_new` | `peakrdl-renode` on SystemRDL extracted from PDF |
| `fork` | verdict = `fork_and_patch` | Copy from Renode upstream → project tree → patch |
| `stub` | verdict = `stub` | Minimal `IDoubleWordPeripheral` that logs accesses |
| `tag` | verdict = `tag` | Pure `.repl` tag entry, no C# |
| `replace` | verdict = `replace` | Write from scratch based on RM |

**Constraints:**
- Implements minimum behavior the application observes plus interrupts the driver waits on. No speculative behavior.
- Every non-trivial register behavior must have an inline citation: `// RM0090 §30.6.4 CR1 bit 13: TXEIE`.
- Forked stock peripherals go to `peripherals/` in the project tree and are listed in `ATTRIBUTION.md`.

---

### 6.7 Test Author

**Role:** Phase 4 worker. Produces and modifies `.robot` and `.resc` orchestration lines.

**Boundary with Modeler:** Modeler owns peripheral-related `.resc` lines (load addresses, peripheral connections). Test Author owns test-orchestration lines (network setup, BLE medium, snapshot save/load, monitor assertions).

**Constraints:**
- Every test file must have at least one positive assertion (golden path) and one negative assertion (e.g., unmapped access faults as expected).
- All `Wait For Line` timeouts use virtual-time budgets from the plan, not wall-clock.
- Snapshot saved at M2 (`sysbus Save snapshot_m2`) for fast subsequent iterations.
- Tests must pass deterministically across N runs (N from `pipeline.determinism_runs`).

---

### 6.8 Emulation Runner

**Role:** Phase 4. Builds the emulation run (not the firmware — that's pre-built), launches Renode via the Renode Control MCP, and captures all artifacts.

**This agent is largely non-LLM.** It is deterministic shell execution. The LLM only interprets the output bundle.

**Output bundle per run:**
```
artifacts/runs/run_<timestamp>/
  ├── renode.log
  ├── uart.log
  ├── robot_report.html
  ├── robot_output.xml
  ├── exit_codes.json
  └── artifacts_used.json     # which .repl, .cs, .resc, .robot versions
```

---

### 6.9 Diagnostician

**Role:** Phase 4. Classifies the failure from the run bundle and proposes a concrete fix.

**Failure taxonomy:**

| Signature Class | Description | Auto-escalate to HITL? |
|---|---|---|
| `unmapped_access` | Peripheral missing or at wrong address | No |
| `wrong_register_value` | Peripheral returns wrong value; driver loops | No |
| `missing_interrupt` | State changed but IRQ not raised | No |
| `wrong_irq_number` | IRQ raised on wrong vector | No |
| `wrong_load_address` | Binary at offset that doesn't match linker | No |
| `flash_persistence` | `reset` macro re-erasing flash (MCUboot trap) | No |
| `network_setup` | TAP / HCI bridge misconfigured | No |
| `timing` | Robot timeout too tight vs virtual-time progression | No |
| `assertion_logic` | Test asserts the wrong thing | No |
| `build_failure` | Renode C# compilation error | No |
| `documentation_gap` | Driver behavior unreconcilable with available docs | **Yes — always** |

**Output per diagnosis:**
```json
{
  "signature": "unmapped_access@0x40023800",
  "classification": "unmapped_access",
  "milestone": "M2",
  "evidence": ["renode.log:142: [WARNING] ... 0x40023800"],
  "hypothesis": "RCC peripheral not in .repl",
  "proposed_fix": {
    "agent": "modeler",
    "action": "Add RCC stub at 0x40023800 to <soc>.repl",
    "expected_impact": "Eliminates unmapped access warning; driver proceeds past clock enable"
  },
  "confidence": 0.85,
  "retry_count_for_signature": 1
}
```

**Constraints:**
- Cannot propose a fix without naming the specific agent and concrete action.
- Per-signature retry budget enforced here (default 3). Exhausted → HITL.
- Same signature appearing unchanged after a fix counts as a regression, not a new attempt.

---

### 6.10 Reviewer

**Role:** Cross-phase quality gate. Runs at milestone boundaries and at final delivery. **Must be logically separate from Modeler and Test Author** — this is LLM-judges-LLM-output and author/reviewer separation is mandatory.

**Checks at milestone boundaries:**
- Every C# file has citations for non-trivial behavior.
- No `TODO` or `NotImplementedException` in code that the golden path exercises.
- No stock peripheral reused without a doubt-log entry.
- Snapshot saved correctly at M2.

**Checks at final delivery:**
- Robot test passes deterministically across N=5 runs.
- README accurately describes what is and isn't modeled.
- `LIMITATIONS.md` lists every Tier-3 peripheral with rationale.
- `ATTRIBUTION.md` present for every forked stock peripheral.
- Doubt log complete.

**Constraints:**
- Read-only access to all artifacts.
- Must escalate to HITL if it disagrees with the orchestrator's completion claim.

---

### 6.11 Packager

**Role:** Phase 5. Assembles the final deliverable, generates Makefile, README, DOUBT_LOG, LIMITATIONS, and ATTRIBUTION.

---

### 6.12 MCP Specifier

**Role:** Phase 0a. Produces a formal specification for each MCP server before any implementation begins.

**Output per server:** `/tools/mcp-servers/<name>/SPEC.md` containing:
- Tool list with exact signatures (name, parameters with types, return type).
- Per-tool behavior contract: preconditions, postconditions, error conditions.
- State model: what state the server keeps, what triggers state changes, what persists across calls.
- Protocol-level requirements (MCP protocol version, transport).
- Test fixtures and expected outputs for the self-test suite.

**Constraints:**
- Spec is approval-blocking. The Implementer cannot start until the Spec is complete.
- Spec must be detailed enough that the Implementer never needs to invent tool semantics.
- Cite MCP protocol documentation and Renode/Antmicro docs as sources for any non-obvious choice.

---

### 6.13 MCP Implementer

**Role:** Phase 0a. Implements an MCP server in Python from the approved Spec.

**Output per server:**
```
/tools/mcp-servers/<name>/
  ├── SPEC.md                  # from Specifier
  ├── server.py                # main server implementation
  ├── tools/                   # per-tool implementation modules
  ├── pyproject.toml           # dependencies, version pin
  ├── tests/                   # self-test suite (from Tester)
  ├── HEALTH_CHECK.md          # how the orchestrator validates the install
  └── VERSION                  # semver string
```

**Constraints:**
- Implementation must match the Spec exactly. Deviations require Specifier sign-off, not Implementer judgment.
- Python 3.11+. Uses the official MCP Python SDK.
- All external process invocations (Renode binary, peakrdl, etc.) go through a single subprocess wrapper with deterministic argument handling.
- All file I/O paths come from the request; no hardcoded paths.
- Every tool call logs its input, output, and wall-clock duration to `/tools/mcp-servers/<name>/runtime.log`.

---

### 6.14 MCP Tester

**Role:** Phase 0a. Builds and runs the self-test suite for each MCP server. **Must be logically separate from MCP Implementer** — same author/reviewer separation as Modeler vs Reviewer.

**Output per server:** `tests/` directory with:
- `test_protocol.py` — verifies MCP protocol compliance (tool list, schema validation, error handling).
- `test_<tool>.py` — one file per tool, exercising preconditions, postconditions, error conditions from the Spec.
- `test_integration.py` — end-to-end scenarios using fixtures.
- `fixtures/` — minimal test inputs (a tiny PDF, a tiny Renode platform, a tiny C# peripheral file).
- `test_health_check.py` — the health check the orchestrator runs at every pipeline startup.

**Constraints:**
- Every tool listed in SPEC.md must have at least three test cases: happy path, error path, edge case.
- Tests must run offline (no internet, no network beyond localhost).
- Total test suite per server must run in under 60 seconds wall-clock.
- Pass rate required for HITL Gate A0: 100%.

---

### 6.15 MCP Reviewer

**Role:** Phase 0a. Independent review of each MCP server before HITL Gate A0. Same logical separation rules as the Reviewer in Phase 4.

**Checks per server:**
- Implementation matches Spec (no missing tools, no extra undocumented tools).
- Test suite covers every tool with the three required cases.
- No hardcoded paths, no hardcoded credentials, no surprising network behavior.
- Server starts cleanly, responds to MCP `initialize`, and shuts down without leaking processes.
- Health check works and returns structured status.

**Output:** `/tools/mcp-servers/<name>/REVIEW.md` with pass/fail per check and any concerns.

---

## 7. MCP Server Layer — Specifications

Three MCP servers expose stateful, deterministic capabilities. They run as persistent processes in the Multipass instance. **All three are LLM-generated** during Phase 0a (see §8) and cached across target builds in the same Multipass instance.

This section defines **what** each server does. §8 defines **how** they are built and validated.

### 7.1 Renode Control MCP

The most critical server. Wraps the Renode Monitor protocol so the LLM has direct, structured control over the emulator rather than scraping log files.

**Tools:**

| Tool | Description |
|---|---|
| `renode_start(resc_file)` | Launch Renode, load platform → session handle |
| `renode_load_elf(session, path)` | Load ELF at embedded addresses |
| `renode_load_hex(session, path)` | Load Intel HEX |
| `renode_load_bin(session, path, address)` | Load raw binary at explicit address |
| `renode_run(session, virtual_seconds)` | Advance simulation |
| `renode_get_uart_log(session, uart_name)` | Retrieve UART output as string |
| `renode_get_peripheral_accesses(session)` | Structured list of sysbus accesses |
| `renode_get_warnings(session)` | All WARNING/ERROR lines from Renode log |
| `renode_save_snapshot(session, name)` | Save emulation state |
| `renode_load_snapshot(session, name)` | Restore emulation state |
| `renode_get_register(session, cpu, reg)` | Read CPU register value |
| `renode_monitor_command(session, cmd)` | Send arbitrary monitor command |
| `renode_stop(session)` | Shut down session |

**Why this matters:** The Diagnostician gets structured data (`get_peripheral_accesses` returns JSON, not a log string). This makes failure classification reliable rather than regex-based.

### 7.2 PDF/Doc Index MCP

Stateful document index. Index once, query many times across loop iterations.

**Tools:**

| Tool | Description |
|---|---|
| `index_document(path_or_url)` → `doc_id` | Ingest and index a PDF |
| `query_peripheral(doc_id, name)` | Return register table for named peripheral |
| `query_memory_map(doc_id)` | Return full memory map table |
| `query_interrupt_table(doc_id)` | Return IRQ assignments |
| `query_chapter(doc_id, chapter_query)` | Full-text search within a chapter |
| `list_indexed_documents()` | List all currently indexed documents |

**Why this matters:** Avoids re-ingesting large PDFs on every loop iteration. Cache is preserved across phase boundaries.

### 7.3 Peripheral Inspector MCP

Wraps the Renode Model Analyzer to enable programmatic inspection of existing Renode peripherals.

**Tools:**

| Tool | Description |
|---|---|
| `list_available_peripherals(query)` | Search Renode built-ins by name/type |
| `get_peripheral_registers(cs_path)` | Extract register layout as structured JSON |
| `diff_peripheral_vs_spec(cs_path, spec_json)` | Diff a peripheral against a spec |
| `get_peripheral_source(name)` | Fetch source of a built-in peripheral |
| `check_compilation(cs_path)` | Validate C# compiles in Renode's context |

**Why this matters:** Makes the "inspect-before-trust" rule enforceable. The Recon Agent gets a structured diff, not a manual read-through.

---

## 8. MCP Implementation Track (Phase 0a)

The MCP servers are infrastructure the rest of the pipeline depends on. They are themselves LLM-generated and validated before any target-specific work begins. This section defines the sub-pipeline that builds them.

### 8.1 When Phase 0a Runs

Phase 0a runs **on demand**, triggered at Phase 0 startup when:

- One or more required MCP servers are absent from `/tools/mcp-servers/`, OR
- A present server fails its health check (`HEALTH_CHECK.md` returns non-pass), OR
- A present server's `VERSION` is older than the version pinned in `renode-builder.yaml` (`pipeline.mcp_versions`).

If all three servers pass health checks at the pinned versions, Phase 0a is **skipped entirely** — the orchestrator advances directly to Phase 1.

This is the **build-once, reuse-forever** path. The first target build in a Multipass instance pays the Phase 0a cost; every subsequent target build skips it.

### 8.2 Per-Server Sub-Pipeline

Each MCP server is built via its own mini-pipeline:

```
Spec → Implement → Test (build) → Test (run) → Review → Install
  │        │            │             │           │         │
  │        │            │             │           │         └─► Health check passes
  │        │            │             │           │             → server registered
  │        │            │             │           └─► Independent review
  │        │            │             │                checks SPEC compliance
  │        │            │             └─► All tests pass; 100% pass rate
  │        │            └─► Self-test suite generated from SPEC
  │        └─► Python implementation matching SPEC exactly
  └─► Formal specification — approval-blocking
```

Each step is a dispatch to the corresponding agent role:

| Step | Agent | Output |
|---|---|---|
| 1. Spec | MCP Specifier (§6.12) | `SPEC.md` |
| 2. Implement | MCP Implementer (§6.13) | `server.py`, `tools/`, `pyproject.toml` |
| 3. Test build | MCP Tester (§6.14) | `tests/` |
| 4. Test run | MCP Tester (§6.14) | Test report; 100% pass required |
| 5. Review | MCP Reviewer (§6.15) | `REVIEW.md`; pass/fail per check |
| 6. Install | Orchestrator | Health check, version registration |

### 8.3 Build Order — Increasing Risk

Servers are built sequentially in **increasing-risk order**, validating the meta-pipeline on the lowest-risk server first:

| Order | Server | Risk Level | Justification |
|---|---|---|---|
| 1 | PDF/Doc Index MCP | Low | Well-understood RAG pattern; PyPDF2 + simple indexing |
| 2 | Peripheral Inspector MCP | Medium | Transformation + file inspection; wraps Renode Model Analyzer |
| 3 | Renode Control MCP | High | Interactive protocol with session state; feedback loop correctness depends on it |

**Failure cascade rule:** If server N's sub-pipeline fails (after retries), do not attempt server N+1. The pipeline aborts with a structured infeasibility report. A failure on PDF/Doc Index is a strong signal the meta-pipeline isn't working, and pushing forward to the harder servers wastes budget.

### 8.4 Per-Server Iteration Budget

| Stage | Budget | Notes |
|---|---|---|
| Spec writing | 1 iteration | Spec failures are HITL-escalated, not retried |
| Implementation | 3 iterations | Driven by Tester failures |
| Test authoring | 2 iterations | Driven by Reviewer feedback |
| Total wall-clock per server | 90 minutes | Exhausted → HITL |

### 8.5 Caching Strategy

Successfully installed servers persist on the Multipass instance disk at `/tools/mcp-servers/`. Their state:

- `server.py` and dependencies are present.
- `VERSION` file matches `pipeline.mcp_versions` in the YAML.
- `HEALTH_CHECK.md` returns pass when executed by the orchestrator.

A cached server is **revalidated** at every Phase 0 startup via health check. A failing health check on a cached server triggers regeneration of that server (the others are not affected).

### 8.6 Health Check Specification

Each MCP server's `HEALTH_CHECK.md` defines a deterministic command sequence the orchestrator runs at Phase 0 to verify the server works:

```markdown
# Health Check — <Server Name>

## Procedure
1. Start the server as a subprocess.
2. Send MCP `initialize` request.
3. Send `tools/list` request.
4. Send one canonical happy-path tool call (e.g., `query_memory_map` with a fixture doc_id).
5. Verify response matches the expected schema.
6. Shut the server down cleanly.

## Pass Criteria
- All five steps complete within 30 seconds wall-clock.
- Step 3 returns the exact tool list from SPEC.md.
- Step 4 returns a valid response per the SPEC contract.
- No subprocess leaks; no open file handles.

## Failure Modes
- Server fails to start → regenerate server.
- Tool list mismatch → regenerate server.
- Tool call returns malformed response → regenerate server.
- Timeout → regenerate server.
```

### 8.7 What Happens at HITL Gate A0

This gate is reviewed **once per Multipass instance**. The orchestrator presents:

```
## HITL Gate A0 — MCP Server Approval

**Servers built this session:** PDF/Doc Index, Peripheral Inspector, Renode Control
**Total time:** <minutes>
**Cached for future runs:** Yes

### Per-server reports
For each server:
  - SPEC.md summary
  - Implementation statistics (files, LOC, dependencies)
  - Test results (X/X passing, runtime)
  - Reviewer's report

### Doubt-log entries from Phase 0a
<any assumptions made during MCP development>

### Decision
1. [Approve] — register servers, proceed to Phase 1, do not re-prompt on future target builds
2. [Reject server X] — regenerate specified server
3. [Reject all] — abort pipeline; manual MCP development required
```

The human's approval is persisted at `/tools/mcp-servers/.approved_<sha>` where `<sha>` is a hash of the combined server VERSIONs. Future Phase 0 runs check for this file and skip Gate A0 if the same versions are still installed.

### 8.8 MCP Failure Mid-Pipeline

If an MCP server crashes during Phase 1 through Phase 5, the orchestrator:

1. Catches the failed tool call.
2. Attempts to restart the server (up to 2 retries).
3. Re-runs the failed tool call.
4. On persistent failure, escalates to HITL with a new failure signature `mcp_crash:<server_name>:<tool_name>`.
5. HITL options: regenerate the server (returns to Phase 0a for that server), continue with a workaround, or abort.

A crashing MCP server **never** results in silent data corruption — the failed tool call is treated as a hard failure, not a recoverable error.

---

## 9. The Feedback Loop

The bring-up loop is the integration oracle for the entire pipeline. An artifact that looks correct in isolation but fails the loop is, by definition, wrong.

### Loop Iteration

```
┌────────────────────────────────────────────────────────────────┐
│  CURRENT MILESTONE TARGET (e.g. M2: Zephyr reaches main())     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Emulation Runner                                           │
│     └─► run + capture output bundle                            │
│                │                                               │
│                ▼                                               │
│  2. Diagnostician                                              │
│     └─► classify outcome                                       │
│                │                                               │
│     ┌──────────┼────────────┐                                  │
│     ▼          ▼            ▼                                  │
│  SUCCESS    FIXABLE     ESCALATE                               │
│     │          │            │                                  │
│     │          ▼            │                                  │
│     │   3a. Budget check    │                                  │
│     │       (signature +    │                                  │
│     │        milestone)     │                                  │
│     │          │            │                                  │
│     │          ▼            │                                  │
│     │   3b. Dispatch fix    │                                  │
│     │       to Modeler or   │                                  │
│     │       Test Author     │                                  │
│     │          │            │                                  │
│     │          ▼            │                                  │
│     │   3c. Update          │                                  │
│     │       doubt log       │                                  │
│     │          │            │                                  │
│     │          └──► back to 1                                  │
│     ▼                       ▼                                  │
│  Reviewer              HITL Gate                               │
│  confirms              (structured report)                     │
│     │                                                          │
│     ▼                                                          │
│  Advance to next milestone                                     │
└────────────────────────────────────────────────────────────────┘
```

### Budget Rules

| Budget Type | Default | Configurable via |
|---|---|---|
| Per failure signature | 3 fix attempts | `pipeline.max_iterations_per_signature` |
| Per milestone | 15 total iterations | `pipeline.max_iterations_per_milestone` |
| Per iteration wall-clock | 10 minutes | (internal constant) |
| Total project | 480 minutes | `pipeline.max_wall_clock_minutes` |
| Early warning threshold | 80% total budget consumed with milestone < M4 | (triggers HITL) |

### Regression Detection

If a failure signature reappears unchanged after a fix attempt, it is classified as a **regression** and counts against the per-signature budget as a used attempt, not a new signature. Two regressions on the same signature → immediate HITL escalation regardless of remaining budget.

### Snapshot Reuse

After M2 is confirmed, the Emulation Runner saves a snapshot (`renode_save_snapshot("m2_confirmed")`). All subsequent loop iterations for M3, M4, M5 load this snapshot instead of booting from scratch. This eliminates boot time from the inner loop for later milestones.

---

## 10. Human-in-the-Loop Gates

Eight defined gates plus on-demand escalation. Gate A0 fires only when the MCP servers are (re)built; once approved and cached for the Multipass instance, Gate A0 is skipped on subsequent target builds.

| Gate | Phase | Trigger | Human Reviews | Outcome |
|---|---|---|---|---|
| **A0 — MCP Approval** | 0a → 1 | MCP servers built or regenerated | Per-server SPEC, test results, Reviewer report | Approve / Reject specific server / Abort |
| **A — Plan Approval** | 2 → 3 | End of Phase 2 | `plan.md`, capability manifest, peripheral strategy, fidelity tiers, open assumptions | Approve / Amend / Abort |
| **B — M1 Reached** | 4 | Binary loads, CPU executes | First boot log, peripheral access trace | Continue / Debug |
| **C — M2 Reached** | 4 | Zephyr reaches `main()` | Boot log, doubt log delta | Continue / Debug |
| **D — M3 Reached** | 4 | Console output works | Full UART transcript | Continue / Debug |
| **E — M4 Reached** | 4 | Golden path completes | Full test run, all artifacts | Continue / Refine |
| **F — M5 Reached** | 4 | Robot test stable N times | Robot report HTML, Reviewer's sign-off | Proceed to packaging |
| **G — Final Delivery** | 5 → done | Phase 5 complete | Deliverable bundle, DOUBT_LOG, LIMITATIONS, Reviewer's final report | Accept / Request changes |

### On-Demand Escalation Triggers

The orchestrator triggers an unscheduled HITL when any of the following occur:

- Per-signature retry budget exhausted (3 attempts, no progress).
- Per-milestone iteration budget exhausted (15 iterations).
- Diagnostician classifies failure as `documentation_gap`.
- Reviewer disagrees with orchestrator's completion claim.
- Same failure signature appears twice post-fix (regression).
- Total budget reaches 80% with current milestone below M4.
- Any `assumed`-confidence claim has blast radius classified as `high`.
- **MCP server crashes during Phases 1–5 and cannot be auto-restarted (signature `mcp_crash:<server>:<tool>`).**
- **MCP Phase 0a sub-pipeline fails after retries.**

### HITL Report Structure

Each HITL escalation presents:

```
## HITL Escalation Report — <timestamp>

**Gate/Trigger:** <gate name or escalation rule>
**Current Milestone:** M<N>
**Budget Used:** <X>% of wall-clock, <Y>% of iterations

### What Was Tried
<failure history for current signature or milestone>

### Current Hypothesis
<Diagnostician's best current theory>

### Doubt Log Delta Since Last Gate
<new entries since last human review>

### Recommended Decision
<orchestrator's recommendation>

### Options
1. [Continue] — accept hypothesis, apply proposed fix
2. [Amend plan] — redirect approach
3. [Abort milestone] — accept limitation, stub and document
4. [Abort project] — generate structured infeasibility report
```

---

## 11. The Doubt Log

`DOUBT_LOG.md` is an append-only file maintained exclusively by the orchestrator. Every assumption made when sources were silent or contradictory gets a structured entry.

### Entry Format

```markdown
## DL-<NNNN> — <short title>

- **Origin:** <agent>, <phase>, <milestone iteration>
- **Claim:** <what was assumed>
- **Evidence:** <what documentation says, or "not found">
- **Confidence:** assumed | inferred | confirmed
- **Blast radius:** low | medium | high
  - *Explanation:* <what breaks if this assumption is wrong>
- **Mitigation:** <what was done to reduce the risk>
- **Status:** open | resolved | accepted-risk
```

### Blast Radius Classification

| Level | Meaning |
|---|---|
| `low` | Wrong assumption causes a log warning; execution continues |
| `medium` | Wrong assumption causes driver to misbehave; may not surface until M4 |
| `high` | Wrong assumption causes boot hang or silent incorrect behavior |

All `high` blast-radius entries are surfaced at every HITL gate regardless of age.

---

## 12. Multipass Execution Environment

### Instance Layout

```
multipass instance: renode-builder
├── /workspace/                      # project being built
│   └── renode-<board>/              # deliverable output directory
├── /tools/
│   ├── renode/                      # Renode install (pinned version)
│   ├── peakrdl-renode/              # C# scaffolding tool
│   ├── renode-model-analyzer/       # peripheral inspection tool
│   └── mcp-servers/                 # LLM-generated MCP server installs
│       ├── pdf-doc-index/
│       │   ├── SPEC.md
│       │   ├── server.py
│       │   ├── tools/
│       │   ├── tests/
│       │   ├── HEALTH_CHECK.md
│       │   ├── REVIEW.md
│       │   ├── VERSION
│       │   └── runtime.log
│       ├── peripheral-inspector/
│       │   └── (same layout as above)
│       ├── renode-control/
│       │   └── (same layout as above)
│       └── .approved_<sha>           # HITL Gate A0 approval marker
├── /input/
│   ├── renode-builder.yaml          # user-provided YAML
│   ├── docs/                        # user-provided PDFs
│   └── binaries/                    # user-provided ELF/HEX/BIN
├── /artifacts/
│   ├── runs/                        # immutable run bundles (never deleted)
│   ├── snapshots/                   # Renode state snapshots
│   ├── peripherals_json/            # Doc Miner intermediate output
│   ├── capability_manifest.json
│   └── recon_report.json
└── /agent-state/
    ├── plan.md
    ├── plan.json
    ├── doubt_log.md
    ├── failure_signatures.json
    └── budget_ledger.json
```

### Capability Requirements

| Capability | Required when |
|---|---|
| `CAP_NET_ADMIN` | `hints.networking: true` (TAP interface creation) |
| Internet egress | PDF fetching from URLs, Renode model fetching, Python package install for MCP servers |
| Minimum 20 GB disk | Zephyr workspace + Renode install + run artifacts + MCP servers |
| Minimum 4 GB RAM | Renode emulation headroom |
| Python 3.11+ | MCP server runtime |

### MCP Server Lifecycle

All three MCP servers (PDF/Doc Index, Peripheral Inspector, Renode Control) are launched by the orchestrator at the start of Phase 0 (after health checks pass) and remain running for the duration of the target build. They are not restarted between phases or loop iterations. State (document index, active Renode sessions) persists within a run.

A crash mid-pipeline triggers the auto-restart sequence described in §8.8.

### Network Policy

- **Inbound:** Deny all.
- **Outbound:** Allow (for doc fetching, model fetching, package install).
- **HITL channel:** The only human-facing interface is structured output written to `/agent-state/hitl_<timestamp>.md` and surfaced to the user via the orchestrator's terminal output.

---

## 13. Deliverable Layout

```
<board>-renode/
  ├── Makefile
  ├── README.md
  ├── platform/
  │   ├── <soc>.repl
  │   └── <board>.repl
  ├── peripherals/
  │   ├── <Peripheral1>.cs
  │   └── <Peripheral2>.cs
  ├── scripts/
  │   └── run.resc
  ├── tests/
  │   ├── golden_path.robot
  │   └── negative.robot
  ├── DOUBT_LOG.md
  ├── LIMITATIONS.md
  └── ATTRIBUTION.md
```

### `.repl` Two-File Convention

- `<soc>.repl` — defines the SoC: CPU, memory regions, all peripherals at their bus addresses.
- `<board>.repl` — includes the SoC file and adds board-specific wiring: LEDs, buttons, external components, UART routing.

This matches Renode upstream conventions and makes the SoC model reusable across boards.

### README Sections

1. Prerequisites (Renode version, dependencies)
2. Repository layout
3. How to run the emulation (`make emulate`)
4. How to run the tests (`make test`)
5. How to extend for a new peripheral
6. Unmodeled peripherals and known limitations (summarized; full list in `LIMITATIONS.md`)
7. Debugging tips (Renode monitor commands, log levels, snapshot usage)
8. License and attribution

---

## 14. Cross-Cutting Principles

These apply to all agents at all phases.

1. **Plan-first protocol.** No code before Gate A clears.
2. **Vertical-slice progression.** M1 must be reached before any peripheral is refined. A working stub beats a perfect-on-paper model.
3. **Cite or admit.** Every non-trivial decision cites a document section, or is logged in the doubt log as an assumption.
4. **Mandatory plan reading.** Every specialist re-reads the relevant plan section before acting.
5. **Block-at-submit, not block-at-write.** Validators run after coherent edits complete.
6. **Budget transparency.** Every agent reports budget usage; the orchestrator aborts before silent exhaustion.
7. **Inspect-before-trust.** No Renode stock peripheral is used without a documented diff against the reference manual.
8. **Determinism contract.** Virtual time, fixed seeds, no wall-clock dependencies, stable across N runs.
9. **Source-of-truth precedence.** See §16.
10. **Fail loudly, abort cleanly.** When infeasible, produce a structured abort report — never fake it.

---

## 15. Failure Mode Coverage

| Risk | Defence |
|---|---|
| Hallucinated register addresses | Doc Miner cites every claim; Modeler cites in code; Reviewer checks |
| Stock peripheral silently broken | Recon Agent diffs every candidate; doubt-log entry required for any reuse |
| Test passes vacuously | Negative test required; Reviewer runs N=5 for determinism |
| Agent flails on one bug | Per-signature retry budget; regression detection |
| Use-case missed (BT/network/MCUboot) | Profiler manifest at Phase 1; HITL Gate A reviews it |
| MCUboot flash-persistence trap | Diagnostician has `flash_persistence` signature in taxonomy |
| Context window exhaustion | Specialist agents with scoped context; MCP servers externalize state |
| Token budget runaway | Hard budgets per agent and per loop; 80% trigger for HITL |
| Cascading "fix made it worse" | Reviewer checks plan; regression detection; doubt log diff at each gate |
| BIN file at wrong address | Cross-validated at intake against DTS; hard error before loop starts |
| Documentation gap | Automatic HITL escalation; never silent |
| Robot timeout mismatch | Timeouts expressed in virtual seconds from plan, not wall-clock |
| **MCP server returns wrong data** | MCP Tester self-tests (3+ cases per tool); MCP Reviewer independent check; health check at every Phase 0 |
| **MCP server crashes mid-pipeline** | Auto-restart (2 retries); persistent failure → HITL with regeneration option |
| **MCP server SPEC drift** | Implementation must match SPEC exactly; MCP Reviewer verifies |
| **Meta-pipeline broken (Phase 0a failure)** | Cascade rule — fail fast on first server, abort before harder servers |
| **Stale cached MCP server** | Version pinning; health check on every Phase 0 startup |

---

## 16. Source-of-Truth Precedence

When sources disagree on a register address, peripheral behavior, or memory layout, the following precedence applies. Lower number wins.

1. MCU vendor reference manual (primary PDF)
2. Board datasheet
3. Resolved `zephyr.dts` from the build output
4. MCU errata sheet (overrides RM for specific silicon revisions)
5. Vendor SVD file
6. Inspected Renode upstream peripheral (after diff)
7. Zephyr upstream board DTS (pre-build)
8. Community Renode models / samples

Disagreements between sources at adjacent levels → doubt-log entry.  
Disagreements between sources more than two levels apart → HITL escalation.

---

## 17. Fidelity Tier Model

Every peripheral in the system is assigned a tier. Tier assignment is driven by what the application's golden path actually exercises.

| Tier | Implementation | Assigned when |
|---|---|---|
| **Tier 1 — Full model** | Complete C# behavioral model | Peripheral is accessed on the golden path |
| **Tier 2 — Stub** | Logs accesses, returns sane defaults, may generate interrupts | Peripheral is initialized by Zephyr drivers but not exercised by the app |
| **Tier 3 — Omit** | Not in `.repl`; unmapped access faults are acceptable | Peripheral not touched by the application at all |

Tier assignment is computed by the Application Profiler and can be overridden in `renode-builder.yaml` via `fidelity.force_tier1/2/3`.

**Implementation strategies by tier:**

| Tier | Strategy options |
|---|---|
| 1 | C# model (scaffolded from SystemRDL or written from scratch) |
| 2 | C# stub, Python peripheral, or `.repl` tag with sensible return values |
| 3 | Absent from `.repl`; optionally a `.repl` tag that logs access and returns 0 |

---

## 18. Use-Case Detection Matrix

The Application Profiler detects use cases from the resolved build artifacts. Each detected use case has implications for `.resc`, `.robot`, and host infrastructure.

| Use Case | Detection Signal | `.resc` Addition | `.robot` Addition | Host Requirement |
|---|---|---|---|---|
| **Networking** | `CONFIG_NETWORKING=y` in `.config` | `emulation CreateSwitch`; `emulation CreateTap`; `connector Connect host.tap switch` | Network-up assertion; `Wait For Line` for IP address | `CAP_NET_ADMIN`; Makefile `tap-up/tap-down` |
| **Bluetooth (in-Renode)** | `CONFIG_BT=y`; radio peripheral in DTS | `emulation CreateBLEMedium "wireless"`; `connector Connect sysbus.radio wireless` | BT init assertion; multi-machine setup | `emulation SetGlobalQuantum "0.00001"` |
| **Bluetooth (HCI bridge)** | `CONFIG_BT_HCI_UART=y` | `emulation CreateServerSocketTerminal 3456 "ble_hci_uart"`; `connector Connect sysbus.uart1 ble_hci_uart` | External controller setup instructions in README | BlueZ / btvirt on host |
| **MCUboot** | `CONFIG_BOOTLOADER_MCUBOOT=y` | `sysbus LoadELF $bootloader_elf`; `sysbus LoadBinary $signed_app $slot0_offset`; rename `reset` macro to `load` | `Wait For Line "I: Jumping to the first image slot"`; two-stage boot assertions | `imgtool.py` for re-signing |
| **Filesystem** | `CONFIG_FILE_SYSTEM=y` | Flash region in `.repl`; optional persistence config | Filesystem mount assertion | None |
| **Shell** | `CONFIG_SHELL=y` | UART analyzer for shell UART | `Wait For Line "uart:~$"`; optional interactive command test | None |
| **Multi-binary** | `sysbuild.conf` present | Multiple `sysbus LoadELF` at distinct offsets | Multi-stage wait assertions | Sysbuild in build env |

---

## 19. Known Renode Gotchas

Documented failure modes from real-world usage, pre-loaded into the Diagnostician's failure taxonomy.

### 18.1 MCUboot Flash Persistence

**Problem:** The `macro reset` in `.resc` is automatically called on MCU reboot. This reloads the binary images and erases flash state, preventing MCUboot from ever seeing a valid image.

**Symptom:** MCUboot boots, validates flash, finds no valid image, loops forever.

**Fix:** Rename the macro from `reset` to `load` in the `.resc` file. The macro must be called explicitly by the user, not triggered by CPU reset.

### 18.2 Unmodeled External Peripherals Hanging the App

**Problem:** If the application initializes a peripheral that isn't in the `.repl` (e.g., external QSPI flash, a sensor on I2C), the CPU will spin reading from an unmapped address.

**Symptom:** `[WARNING] sysbus: Read from non existing peripheral at 0x...` followed by a CPU halt or infinite loop.

**Fix:** Add a Tier-2 stub or a `.repl` tag for the peripheral. If the peripheral can be disabled via DTS overlay without breaking the golden path, that's preferable.

### 18.3 Virtual Time vs. Robot Timeouts

**Problem:** Renode runs in virtual time, which is typically slower than wall-clock. Robot `Wait For Line` timeouts set in wall-clock seconds will expire before the simulated system reaches the expected output.

**Fix:** Use `emulation SetGlobalQuantum` to tune virtual-time granularity. Express all timeouts in the robot test as virtual-seconds-equivalent, not wall-clock seconds.

### 18.4 BIN Load Address Mismatch

**Problem:** A raw binary loaded at the wrong offset will produce either a silent wrong execution (if the address is mapped) or an immediate CPU fault (if not).

**Fix:** Always cross-validate BIN load addresses against the DTS `flash_partitions` node before running. This is enforced at intake validation in Phase 0.

### 18.5 Serial Recovery (MCUboot)

**Known issue:** MCUboot serial recovery mode does not function correctly in Renode as of current versions. Some underlying peripheral is unimplemented.

**Mitigation:** Do not test serial recovery via Renode. Document in `LIMITATIONS.md`. Test only the normal boot path.

### 18.6 C# Compilation Errors Are Runtime, Not Build-Time

**Problem:** Renode compiles C# peripheral files at runtime via `include @file.cs`. Compilation errors appear as Renode startup failures, not as build errors.

**Fix:** Use the `check_compilation` tool of the Peripheral Inspector MCP before adding a new peripheral to `.resc`. This catches syntax errors before a full run.

---

*End of Architecture Document*

*Generated by pre-planning session. Approved for use as planning-agent context.*
