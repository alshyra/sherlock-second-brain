# sherlock-second-brain

[![PyPI - Version](https://img.shields.io/pypi/v/sherlock-second-brain)](https://pypi.org/project/sherlock-second-brain)
[![CI](https://github.com/alshyra/sherlock-second-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/alshyra/sherlock-second-brain/actions/workflows/ci.yml)

> Named after the famous detective of Baker Street who inspired this project: the
> same way, we run rigorous investigations (symptoms, clues, hypotheses, evidence,
> conclusion) to **debug**, analyze code, and **remember** what we learn across
> multiple projects.

MCP server + skill for **Sherlock's second brain**: validated knowledge lives in MD
fiches and skills; everything **not yet validated** lives in **cases** (JSON
investigation files for debugging and troubleshooting). Standalone notes worth
remembering without an investigation live in **memories** (MD + YAML frontmatter).
A resolved case is promoted into a fiche or a skill through the MCP; a memory can
also be promoted into a fiche.

```
source of truth (files)                      derived index (rebuildable)
────────────────────────────────────             ────────────────────────────
<data_dir>/
  cases/<case-id>/case.json          ──→   vector/ (chromadb, gitignored)
  cases/<case-id>/evidence/*.log           hybrid search: vector (Chroma)
  memories/<id>.md                           + lexical (RRF)
  fiches/*.md
  skills/<slug>/SKILL.md
```

## Stack

- Python 3.12+, `uv`
- [FastMCP](https://github.com/jlowin/fastmcp) (stdio)
- ChromaDB + fastembed (vector index, multilingual MiniLM-L12 model)
- jsonschema (case validation)
- jinja2 (rendering of promoted fiches / skills)
- PyYAML (memory frontmatter)
- Hexagonal architecture: `domain/` (pure pydantic) · `application/` (use cases + ports) · `adapters/` (filesystem, chroma, lexical, hybrid RRF, MCP DTO, templates)

## Installation (in a project)

```bash
uv init
uv add sherlock-second-brain
```

Or from the repo:

```bash
cd sherlock-second-brain
uv sync
```

## Two ways to run it

Your data (cases, fiches, skills, vector index) always lives on the machine where
the server process runs. The server is local-first (stdio), so you choose where
that machine is:

### A. Self-hosted (data stays on your machine)

Install the package and run the stdio server locally — no third party ever touches
your data. Configure `SHERLOCK_BRAIN_DATA_DIR` to choose where the files live
(default `~/sherlock-second-brain-data`).

### B. Managed on Glama (opt-in)

Deploy your own instance on Glama's hosting from the [Glama listing](https://glama.ai/mcp/servers/alshyra/sherlock-second-brain):
Glama builds the image, wraps the stdio transport into Streamable HTTP, and mounts
a persistent volume at `/data`. Set `SHERLOCK_BRAIN_DATA_DIR=/data` so your
knowledge survives redeploys. This is a paid managed option — the code itself is
free and open source (MIT).

## Configuration

| Variable | Role | Default |
|----------|------|---------|
| `SHERLOCK_BRAIN_DATA_DIR` | Root data directory (cases + memories + kb + vector) | `~/sherlock-second-brain-data` |

## Wire the MCP server into opencode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "sherlock-second-brain": {
      "type": "local",
      "command": ["/opt/sherlock-second-brain/.venv/bin/python", "-m", "sherlock_second_brain.server"],
      "enabled": true,
      "environment": {
        "SHERLOCK_BRAIN_DATA_DIR": "/opt/infra/kb"
      }
    }
  }
}
```

## Install the agent globally

The agent is versioned in this repo (`agent/sherlock-second-brain.md`). To make it
available to all opencode agents:

```bash
ln -s /opt/sherlock-second-brain/agent/sherlock-second-brain.md ~/.config/opencode/agent/sherlock-second-brain.md
```

> On another machine, clone the repo then create the same symlink pointing to the checkout.
> Restart opencode after installation.

## MCP tools

### Cases
| Tool | Role |
|------|------|
| `case_create` | Create an investigation (unvalidated topic) |
| `case_get` / `case_list` | Read / list (status, tag filters) |
| `case_search` | Semantic search (cases + KB) |
| `case_update` | Add findings / steps / hypotheses / conclusion / hypothesis result |
| `case_add_evidence` | Attach evidence (log, output, note) |
| `case_set_status` | open / in_progress / resolved / abandoned |
| `case_delete` | Delete a case and its evidence |
| `case_promote` | Promote a resolved case → fiche or skill |

### Memories
| Tool | Role |
|------|------|
| `memory_add` | Add a standalone note to remember (no case) |
| `memory_get` / `memory_list` | Read / list memories (tag filter) |
| `memory_search` | Semantic search restricted to memories (hydrated) |
| `memory_update` | Update summary / content / tags / references / source |
| `memory_delete` | Delete a memory |
| `memory_promote` | Promote a memory → validated fiche |

### KB
| Tool | Role |
|------|------|
| `fiche_list` / `fiche_read` / `fiche_write` / `fiche_delete` | CRUD validated fiches |
| `skill_list` / `skill_read` / `skill_write` / `skill_delete` | CRUD validated skills |
| `index_rebuild` | Rebuild the vector index from source files |

## Hybrid search

`case_search` (and `memory_search`) combines two engines via **Reciprocal Rank
Fusion** (`adapters/hybrid.py`) over four sources: **fiches**, **cases**,
**skills** and **memories**.

- **Vector** (`adapters/chroma.py`): **multilingual** embeddings (MiniLM-L12, ~0.22GB, French included), persistent collection in `vector/`, rebuildable via `index_rebuild`.
- **Lexical** (`adapters/lexical.py`): token overlap, zero dependency — a doc relevant for an exact term but missed by the vector engine still surfaces.

RRF fusion: `score(d) = 1/(k + vector_rank) + 1/(k + lexical_rank)`, `k = 60`. The first `index_rebuild` downloads the model.

## Memories

A memory is a low-friction capture ("remember that the NAS runs Fedora 44"), with
no case workflow. It is stored as `memories/<id>.md` with YAML frontmatter
(metadata) and a free-form markdown body. Memories are indexed on every mutation
(create included) so they are immediately searchable. A memory is **not**
validated; promote it with `memory_promote` once it becomes validated knowledge.

## Case schema

Defined in
[`src/sherlock_second_brain/schema/case.schema.json`](src/sherlock_second_brain/schema/case.schema.json)
— source of truth, shipped inside the package. Every case written through the MCP
is validated against this schema (works from PyPI installs too).

## Tests

```bash
uv run ruff check src/ tests/        # lint
uv run ty check                      # type checking
uv run pytest tests/ -v              # tests
```
