# System Prompt Guidelines

This directory contains system prompts for agents in the TLDE pipeline. Each prompt is a `.txt` file that can be injected as-is into an LLM's system message.

## Writing a good system prompt

### Structure

A system prompt should follow this general skeleton:

1. **Role statement** — One sentence. Who is this agent and what is its job? Start with "You are a …".
2. **Trust boundaries** — What inputs are trusted, what are not. Agents that consume generated artifacts (`.repl`, `.json`) should explicitly state the trust level.
3. **Source-of-truth precedence** — When sources conflict, which one wins? Reference the precedence list from `RENODE_BUILDER_ARCHITECTURE.md` §16 and tailor it to the agent's scope.
4. **Inputs** — Enumerate every artifact the agent receives, whether it is required or optional, and what the agent should do with it.
5. **Process / workflow** — Step-by-step instructions for the agent's core task. Be explicit about what to check, in what order, and what to do on mismatch.
6. **Output format** — Exactly what files or JSON structures the agent produces. Include a concrete example so the LLM can pattern-match.
7. **Known pitfalls** — Domain-specific gotchas the agent must watch for (e.g., Renode runtime C# compilation, MCUboot flash persistence).
8. **Constraints** — Hard rules the agent must never violate. Use "NEVER" and "ALWAYS" for non-negotiable items.

### Principles

- **Be concrete, not abstract.** "Cross-check the base address against RM Table 1" is better than "verify correctness".
- **Cite the architecture doc.** Reference specific sections of `RENODE_BUILDER_ARCHITECTURE.md` so prompts stay aligned with the pipeline design.
- **Assume no prior context.** Each prompt must be self-contained — the agent has no memory of previous runs or other agents' prompts.
- **Define trust explicitly.** If an input comes from another LLM agent, say so and state the verification expectation.
- **Include examples in outputs.** Show the JSON schema or file structure the agent must produce. LLMs follow examples far more reliably than prose descriptions.
- **Keep constraints scannable.** Use short imperative sentences. One rule per line.
- **Separate concerns.** One agent, one prompt, one file. Don't combine roles.

### Naming convention

```
<role_in_snake_case>.txt
```

Examples: `firmware_verification_engineer.txt`, `documentation_miner.txt`, `modeler.txt`

### Size guidelines

- **Sweet spot: 1,500–4,000 tokens** (~800–2,500 words). Precise enough to be useful, short enough that the model doesn't lose instructions in the middle.
- **Below 500 tokens** — too vague; the model fills gaps with assumptions and hallucinations.
- **Above 6,000 tokens** — diminishing returns. Models deprioritize instructions in the middle zone (*lost-in-the-middle* effect).
- Put **hard constraints first and last** in the prompt — those positions get the most attention.
- If a prompt exceeds ~4K tokens, split it: keep the core role, rules, and constraints in the system prompt, and move large JSON schemas or reference tables into a **companion document** injected as user context.

### Testing a prompt

1. Feed the prompt as a system message along with sample inputs.
2. Verify the agent produces all listed outputs in the correct format.
3. Deliberately introduce errors in the inputs (wrong addresses, missing peripherals) and confirm the agent catches them.
4. Check that citations are present and reference real document sections.
