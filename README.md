# tlde — Too Long Didn't Emulate

> Point it at a datasheet. Get a working Renode emulation.

**tlde** is a multi-agent pipeline that reads MCU vendor documentation (reference manuals, datasheets, schematics) and automatically produces a complete [Renode](https://renode.io/) emulation package — including platform descriptions, C# peripheral models, execution scripts, Robot Framework tests, and a verification report.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  $ tlde "Emulate the nRF52833 using ./docs/nrf52833_rm.pdf"     │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Phase 1 · Manager  │  Reads PDFs · Decomposes into
              │  (claude-opus-4.6)  │  work units (one per peripheral)
              └──────────┬──────────┘
                         │  JSON work plan
              ┌──────────▼──────────────────────────┐
              │  Phase 2 · Engineer–Verifier loops  │
              │  (parallel, dependency-aware)       │
              │                                     │
              │  fw_emu_eng ──────► fw_verif_eng    │  Up to 3 retries
              │  (sonnet-4.6)       (sonnet-4.6)    │  per work unit
              │       ▲                  │          │
              │       └──── feedback ────┘          │
              └──────────┬──────────────────────────┘
                         │  .repl · .cs · run.resc · verification_report.json
              ┌──────────▼──────────┐
              │  Phase 3 · Testing  │  Builds firmware · Writes Robot tests
              │  (emu_test_agg)     │  Runs renode-test · Reports results
              └──────────┬──────────┘
                         │
              output/<board>/
                ├── *.repl
                ├── *.cs
                ├── run.resc
                ├── verification_report.json
                ├── doubt_log.json
                └── tests/
                    ├── *.robot
                    └── report.txt
```

### Agents

| Agent | Model | Role |
|---|---|---|
| `firmware_emulation_manager` | claude-opus-4.6 | Reads PDFs via MCP, decomposes the full MCU into self-contained work units (one per peripheral family). Outputs a topologically-sorted JSON work plan. |
| `fw_emu_eng` | claude-sonnet-4.6 | Implements one work unit: writes the `.repl` entry and any required C# peripheral model. Iterates on verifier feedback. |
| `fw_verif_eng` | claude-sonnet-4.6 | Cross-checks the engineer's `.repl` against the vendor reference manual. Assigns per-peripheral verdicts (`verified`, `mismatch_fixed`, `mismatch_escalated`, `unverifiable`). Generates `run.resc`. |
| `emu_test_agg` | claude-sonnet-4.6 | Builds Zephyr sample firmware, writes Robot Framework test suites, runs them under Renode, classifies failures as expected (per verifier report) vs unexpected. |

---

## Quickstart

### Requirements

- Python 3.12+
- [Copilot CLI](https://githubnext.com/projects/copilot-cli/) authenticated (`gh copilot`)
- Node.js (for the pdf-reader MCP: `npx @sylphx/pdf-reader-mcp`)
- [west](https://docs.zephyrproject.org/latest/develop/west/) + Zephyr SDK (for sample builds)
- [Renode](https://renode.io/) with `renode-test` on `$PATH` (for Phase 3)

### Install

```bash
pip install -e .
```

### Install skills (recommended)

Skills pre-load domain knowledge into each agent, reducing token usage and improving output quality. Install them once to `~/.copilot/skills/`:

```bash
# From the project root — installs all skills from docs/skills/
for skill in docs/skills/*.md; do
  name=$(basename "$skill" .md)
  mkdir -p ~/.copilot/skills/$name
  cat > ~/.copilot/skills/$name/SKILL.md << FRONT
---
name: $name
description: "$(head -3 $skill | tail -1)"
---
FRONT
  cat "$skill" >> ~/.copilot/skills/$name/SKILL.md
done
```

Or copy individual skills manually from `docs/skills/` with a YAML frontmatter header.

### Run

```bash
tlde "Emulate the nRF52833 micro:bit v2 using the specs in ./docs/nrf52833_rm.pdf and ./docs/microbit_v2_schematic.pdf"
```

All outputs land in `output/<board>/` (the board name is extracted by the manager from the docs).

---

## Project structure

```
tlde/
├── src/tlde/
│   ├── pipeline/
│   │   └── firmware_emulation.py   # Three-phase pipeline orchestrator
│   ├── agents/
│   │   ├── firmware_emulation_manager.py
│   │   ├── fw_emu_eng.py
│   │   ├── fw_verif_eng.py
│   │   └── emu_test_agg.py
│   ├── agent.py                    # Copilot SDK session factory + permission handler
│   ├── config.py                   # AgentConfig dataclass + AGENTS registry
│   └── observability.py            # PipelineTrace / SessionObserver
├── prompts/                        # System prompt .txt files (one per agent)
├── docs/
│   ├── RENODE_BUILDER_ARCHITECTURE.md
│   └── skills/                     # Skill reference documents
├── samples/                        # Zephyr sample applications
│   ├── hello/
│   ├── flash_rw/
│   └── mcuboot_flash_img_copy/
└── specs/                          # Input PDFs (per board)
```

---

## Skills

Skills are markdown reference documents injected into agent context at startup. They are stored in `docs/skills/` and installed to `~/.copilot/skills/`.

| Skill | Used by | Purpose |
|---|---|---|
| `renode-repl-generation` | `fw_emu_eng` | `.repl` format, registration syntax, IRQ wiring |
| `renode-peripheral-model-generation` | `fw_emu_eng` | C# peripheral model API, Register Framework |
| `renode-peripheral-model-patterns` | `fw_emu_eng` | Advanced templates: GPIO, SPI, DMA, sensors |
| `mcuboot-emulation` | `fw_emu_eng`, `fw_verif_eng` | MCUboot partition layout, binary loading order |
| `zephyr-dts-analysis` | `fw_emu_eng`, `fw_verif_eng` | Extracting addresses and IRQs from resolved DTS |
| `renode-resc-generation` | `fw_verif_eng` | `.resc` script patterns and verified load sequences |
| `renode-debugging` | `fw_verif_eng`, `emu_test_agg` | Failure diagnosis, log levels, access tracing |
| `renode-feedback-schema` | `fw_verif_eng`, `emu_test_agg` | `verification_report.json` schema and verdict types |
| `renode-robot-test-generation` | `emu_test_agg` | Robot Framework test patterns for Renode |
| `renode-peripheral-catalogue` | `firmware_emulation_manager` | Stock Renode models by MCU family |

---

## Output artefacts

| File | Produced by | Description |
|---|---|---|
| `output/<board>/*.repl` | `fw_emu_eng` | Renode platform description |
| `output/<board>/*.cs` | `fw_emu_eng` | C# peripheral models |
| `output/<board>/run.resc` | `fw_verif_eng` | Validated Renode execution script |
| `output/<board>/verification_report.json` | `fw_verif_eng` | Per-peripheral verdicts with doc citations |
| `output/<board>/doubt_log.json` | `fw_verif_eng` | Escalated / unresolvable mismatches |
| `output/<board>/tests/*.robot` | `emu_test_agg` | Robot Framework test suites |
| `output/<board>/tests/report.txt` | `emu_test_agg` | Pass/fail summary with expected vs unexpected failures |

---

## Adding a new board

1. Place the reference manual and board datasheet PDFs under `specs/<board_name>/` or `docs/<board_name>/`.
2. Run:
   ```bash
   tlde "Emulate the <SoC> <board> using the specs in ./docs/<board_name>/<rm>.pdf and ./docs/<board_name>/<ds>.pdf. Place all outputs in output/<board_name>/"
   ```
3. Outputs appear in `output/<board_name>/`.

---

## Development

### Adding an agent

1. Create `src/tlde/agents/<name>.py` with a class extending `AgentConfig`.
2. Create `prompts/<name>.txt` following the guidelines in `prompts/README.MD`.
3. The agent auto-registers in `AGENTS["<name>"]` on import.

### Adding a skill

1. Write the reference document as `docs/skills/<skill-name>.md`.
2. Install it locally:
   ```bash
   mkdir -p ~/.copilot/skills/<skill-name>
   printf -- '---\nname: <skill-name>\ndescription: >\n  <one-line description>\n---\n' > ~/.copilot/skills/<skill-name>/SKILL.md
   cat docs/skills/<skill-name>.md >> ~/.copilot/skills/<skill-name>/SKILL.md
   ```
3. Add the skill name to the relevant agent's `skills` list in its class definition.

### Permission model

The Copilot SDK session factory in `agent.py` enforces an allowlist for shell commands:

| Handler | Allowed commands |
|---|---|
| `_permission_handler` (default) | `mkdir [-p] [-v] <path>` only |
| `_test_permission_handler` | Above + `make`, `renode-test`, `python -m robot`, `west build` |

Pass `permission_handler=_test_permission_handler` to `run_agent()` for agents that need to build firmware or run tests.

