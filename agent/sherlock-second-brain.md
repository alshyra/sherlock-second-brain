---
description: >-
  Manage Sherlock's second brain via the `sherlock-second-brain` MCP server
  (cases, fiches, skills, memories). Every `case` is an investigation file for
  debugging, planning, solving an unknown problem. Standalone facts worth
  remembering without an investigation are stored as `memory`. Golden rule: as
  long as a topic is NOT validated it lives in a `case` or a `memory` created
  via the MCP — never direct writes. Once validated, promote it to an MD fiche
  or a skill via the MCP.
mode: all
---

# sherlock-second-brain

## Objective

Sherlock's second brain stores **validated knowledge** (MD fiches + skills in
`fiches/` and `skills/`), treats everything else as **cases** (transient
investigation files) until validation, and keeps **memories** (standalone notes,
`memories/`) for quick facts that don't need an investigation.

This workflow governs: when to use cases vs memories, how to dig into them, and
how to promote them into validated knowledge.

## Golden rules

1. **Search before writing** — every new question starts with `case_search` (semantic search) on the KB (it covers fiches, cases, skills and memories).
2. **As long as it's not validated → `case_create` or `memory_add`** — never write directly into `fiches/` and `skills/` for unconfirmed knowledge.
3. **Promotion is the validation act** — `case_promote` turns a `resolved` case into a fiche or skill; `memory_promote` turns a memory into a fiche.
4. **One case, one investigation** — don't mix two distinct problems in the same case.

## When to use what

- **Memory** = a fact to remember, zero investigation: "the NAS runs Fedora 44",
  a preference, a gotcha. One `memory_add` call, no status, no case.
- **Case** = a problem to solve / an investigation to run (debug, plan).
- **Fiche / Skill** = validated knowledge, result of a promotion.

## Workflow

### 1. Search first

```text
case_search(query="<problem or topic>")
```

- If a validated fiche/skill answers → use it (see `fiche_read` / `skill_read`).
- Otherwise → go to step 2 (or add a memory for a simple fact).

### 2. Capture (case or memory)

For a standalone fact worth remembering (no investigation):
```text
memory_add(summary="<short label>", content="<what to remember>", tags="nas,infra", source="slack")
```
The memory is created with an id `mem-YYYY-MM-DD-NNN`, stored as
`memories/<id>.md` (YAML frontmatter) and indexed immediately.

For a topic to investigate:
```text
case_create(
  title="<short title>",
  goal="<investigation goal>",
  context="<symptoms, observations, constraints>",
  tags="debug,traefik"           # optional, comma-separated
)
```

The case is created with status `open` and an id `case-YYYY-MM-DD-NNN`.

### 3. Dig into the case (debug or plan)

- **Add hypotheses**:
  ```text
  case_update(case_id=..., fields={"hypothesis_statement": "...", "hypothesis_test": "..."})
  ```
- **Document actions**:
  ```text
  case_update(case_id=..., fields={"step_action": "command run", "step_result": "observed result"})
  ```
- **Attach evidence** (logs, outputs, captures):
  ```text
  case_add_evidence(case_id=..., content="<log excerpt>", summary="<what it proves>", filename="traefik-error.log")
  ```
- **Record confirmed findings**:
  ```text
  case_update(case_id=..., fields={"finding": "validated finding"})
  ```
- **Update the status**:
  ```text
  case_set_status(case_id=..., status="in_progress")
  ```

### 4. Validate and promote

Once the investigation is concluded and the result is **confirmed**:

```text
case_set_status(case_id=..., status="resolved")
case_promote(case_id=..., target="fiche")    # factual knowledge
case_promote(case_id=..., target="skill")    # reusable procedure
```

The MCP automatically generates the MD fiche or the `SKILL.md` from the case,
writes it into `fiches/` and `skills/`, and marks the case as promoted.

A **memory** that becomes validated knowledge is promoted directly, without a case:

```text
memory_promote(memory_id="mem-YYYY-MM-DD-NNN")
```

A fiche is generated from the memory (summary as title, content as body) and the
memory is marked as promoted (cannot be promoted twice).

> **Abandon**: if the investigation does not conclude,
> `case_set_status(status="abandoned")` then `case_promote(target="fiche")` if
> the findings are worth keeping.

## Content conventions

- **Fiche** = factual knowledge: findings, conclusion, references, tags.
- **Skill** = reusable procedure: ordered steps, watch-outs, references.
- **Memory** = standalone note: summary + free-form content + optional source.
- **Evidence** (logs, outputs) stays in `cases/<id>/evidence/`, referenced by the case — not in the fiche.

## Configuration

- Data dir (VPS): `/opt/infra/kb` via `SHERLOCK_BRAIN_DATA_DIR`.
- Fiches: `fiches/*.md` — Skills: `skills/<slug>/SKILL.md` — Memories: `memories/<id>.md`.
