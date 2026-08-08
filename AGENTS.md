# AGENTS.md

Sherlock's second brain MCP server: validated knowledge lives in `fiches/` and `skills/`;
everything unvalidated lives in `cases/` (JSON investigations — investigation files for
debugging and analysis) or `memories/` (standalone MD notes with YAML frontmatter). A
`resolved` case is promoted into a fiche or skill via the MCP; a memory can also be
promoted into a fiche.
Repo language is **English** (code, docs, generated output) — the `README.md` is in English
because it is parsed by Glama (https://glama.ai). Some tests keep French content
(`tests/test_vector.py`, `test_slugify`) to exercise multilingual support.

## Commands

```bash
uv run ruff check src/ tests/                    # lint (Astral, E,F,I,W,UP,B,ANN,PYI + preview)
uv run ty check                                  # type checking (Astral)
uv run pytest tests/ -v                          # all tests (no services needed, tmp_path fixtures)
uv run pytest tests/test_storage.py::test_slugify -v   # single test
uv sync                                           # installs deps (chromadb+fastembed inclus)
```

Required verification order: `ruff check` → `ty check` → `pytest`.

Run the server with `uv run python -m sherlock_second_brain.server` — this is a stdio MCP server,
it needs an MCP client to be useful (wired as `~/.config/opencode/opencode.json` →
`SHERLOCK_BRAIN_DATA_DIR=/opt/infra/kb`).

## Architecture (hexagonal)

- `src/sherlock_second_brain/`:
  - `server.py` — composition root: instantiates adapters+services, `@mcp.tool()` defs
  - `domain/` — **rich aggregates** enforcing their invariants: `models/case.py`
    (`Case` factory + mutations + `promote`) and `models/memory.py` (`Memory`
    factory + setters + `promote`), one file per class
    (`models/{case,hypothesis,step,evidence,memory,promotion}.py`), plus
    `errors.py` (StorageError hierarchy), `rules.py` (`VALID_STATUS`,
    `VALID_PROMOTION_TARGETS`) and `text.py` (`slugify`, `now_iso`,
    `CASE_ID_PATTERN`, `MEMORY_ID_PATTERN`)
  - `application/` — thin orchestration only (no business rules), depending on
    `ports.py` Protocols: `case_service.py` (`CaseService`), `memory_service.py`
    (`MemoryService`), `promotion_service.py` (`PromotionService`)
  - `adapters/` — persistence/IO only, no domain policy: `filesystem.py`
    (`Storage` persists by object: `save_*`/`get`/`list`/`delete`/`next_*_id`/
    `write_evidence`), `chroma.py` (`VectorIndex` +
    `FastembedEmbeddingFunction` multilingue), `lexical.py` (`LexicalIndex`),
    `hybrid.py` (`HybridIndex` RRF), `dto/case_update.py` (`CaseUpdateFields`
    for the `case_update` fields), `frontmatter.py` (memory MD + YAML frontmatter
    render/parse), `templates/` (Jinja2: `fiche.md.j2`, `skill.md.j2`,
    `memory_fiche.md.j2` rendered by `PromotionService`)
- Data layout under `SHERLOCK_BRAIN_DATA_DIR` (default `~/sherlock-second-brain-data`):
  - `cases/<case-id>/case.json` + `cases/<case-id>/evidence/*` — `case-id` = `case-YYYY-MM-DD-NNN` (per-day counter)
  - `memories/<id>.md` — `id` = `mem-YYYY-MM-DD-NNN` (per-day counter), YAML frontmatter + body
  - `fiches/<slug>.md`, `skills/<slug>/SKILL.md`
  - `vector/` — derived ChromaDB index, always rebuildable via the `index_rebuild` tool
- `schema/case.schema.json` is the source of truth: `Storage._save_case` validates every case
  against it (`SCHEMA_PATH` resolved by walking up to the repo root). If you touch the schema,
  keep writes compatible or `test_written_case_matches_json_schema` fails.
- Search is hybrid: `server.py` composes `HybridIndex(VectorIndex, LexicalIndex)` and
  fuses rankings by RRF. ChromaDB is a mandatory dependency (no fallback). The embedding
  model is multilingual (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
  downloaded at first `index_rebuild`). Doc IDs are `fiche:<slug>`, `case:<id>`,
  `skill:<slug>`, `memory:<id>`. Document enumeration is shared in `adapters/documents.py`.
- `CaseService` maintains the index on every mutation (update/evidence/status/delete);
  `MemoryService` maintains it on every mutation **including create** (a memory must be
  immediately searchable).

## Code conventions

- **No lazy imports**: imports live at the top of modules, never inside function bodies.
  Optional dependencies (none today: chromadb+fastembed are mandatory) would be handled
  at the composition root with a `try/except` import.

## Domain workflow (matches `agent/sherlock-second-brain.md`)

- Never direct-write validated knowledge. Unvalidated topics → `case_create`
  (investigation) or `memory_add` (standalone fact); promotion
  (`case_promote`, target `fiche`|`skill`, status must be `resolved` /
  `memory_promote`, target `fiche`) is the validation act.
- Tool API quirks: `case_create` takes `tags`/`references` as comma-separated strings;
  `case_update` takes a `fields` dict (keys: `finding`, `step_action`/`step_result`,
  `conclusion`, `hypothesis_statement`/`hypothesis_test`, `hypothesis_result`,
  `tags`, `references`) — validated by the `CaseUpdateFields` DTO.
- `slugify` keeps accents (`très-long`); skills are stored as `skills/<slug>/SKILL.md`, the
  workflow agent lives in `agent/sherlock-second-brain.md` (symlinked to `~/.config/opencode/agent/`).

## Editor LSP

Python LSP in opencode uses `ty` (types) + `ruff` (lint) via `~/.config/opencode/opencode.jsonc`;
the built-in pyright server is disabled. Both binaries are installed globally with `uv tool install`.
