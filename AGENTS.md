# AGENTS.md

Sherlock's second brain MCP server: validated knowledge lives in `fiches/` and `skills/`;
everything unvalidated lives in `cases/` (JSON investigations — dossiers d'enquête pour le
debug et l'analyse). A `resolved` case is promoted into a fiche or skill via the MCP.
Repo language is **French** (docstrings, generated output) — the `README.md` is in English
because it is parsed by Glama (https://glama.ai).

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
  - `domain/` — pure pydantic, one file per class (`models/{case,hypothesis,step,evidence,promotion}.py`),
    plus `errors.py` (StorageError hierarchy) and `text.py` (`slugify`, `now_iso`, `CASE_ID_PATTERN`)
  - `application/` — use cases depending on `ports.py` Protocols only:
    `case_service.py` (`CaseService`), `promotion_service.py` (`PromotionService`)
  - `adapters/` — concrete implementations: `filesystem.py` (`Storage`), `chroma.py`
    (`VectorIndex` + `FastembedEmbeddingFunction` multilingue), `lexical.py`
    (`LexicalIndex`), `hybrid.py` (`HybridIndex` RRF), `dto/case_update.py`
    (`CaseUpdateFields` for the `case_update` fields), `templates/` (Jinja2:
    `fiche.md.j2`, `skill.md.j2` rendered by `PromotionService`)
- Data layout under `SHERLOCK_BRAIN_DATA_DIR` (default `~/sherlock-second-brain-data`):
  - `cases/<case-id>/case.json` + `cases/<case-id>/evidence/*` — `case-id` = `case-YYYY-MM-DD-NNN` (per-day counter)
  - `fiches/<slug>.md`, `skills/<slug>/SKILL.md`
  - `vector/` — derived ChromaDB index, always rebuildable via the `index_rebuild` tool
- `schema/case.schema.json` is the source of truth: `Storage._save_case` validates every case
  against it (`SCHEMA_PATH` resolved by walking up to the repo root). If you touch the schema,
  keep writes compatible or `test_written_case_matches_json_schema` fails.
- Search is hybrid: `server.py` composes `HybridIndex(VectorIndex, LexicalIndex)` and
  fuses rankings by RRF. ChromaDB is a mandatory dependency (no fallback). The embedding
  model is multilingual (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
  downloaded at first `index_rebuild`). Doc IDs are `fiche:<slug>`, `case:<id>`,
  `skill:<slug>`. Document enumeration is shared in `adapters/documents.py`.
- `CaseService` maintains the index on every mutation (update/evidence/status/delete).

## Conventions de code

- **Pas de lazy import** : les imports se font en haut de module, jamais dans le corps des
  fonctions. Les dépendances optionnelles (aucune aujourd'hui : chromadb+fastembed sont
  obligatoires) se géreraient à la composition root par `try/except` d'import.

## Domain workflow (matches `agent/sherlock-second-brain.md`)

- Never direct-write validated knowledge. Unvalidated topics → `case_create`; promotion
  (`case_promote`, target `fiche`|`skill`, status must be `resolved`) is the validation act.
- Tool API quirks: `case_create` takes `tags`/`references` as comma-separated strings;
  `case_update` takes a `fields` dict (keys: `finding`, `step_action`/`step_result`,
  `conclusion`, `hypothesis_statement`/`hypothesis_test`, `hypothesis_result`,
  `tags`, `references`) — validated by the `CaseUpdateFields` DTO.
- `slugify` keeps accents (`très-long`); skills are stored as `skills/<slug>/SKILL.md`, the
  workflow agent lives in `agent/sherlock-second-brain.md` (symlinked to `~/.config/opencode/agent/`).

## Editor LSP

Python LSP in opencode uses `ty` (types) + `ruff` (lint) via `~/.config/opencode/opencode.jsonc`;
the built-in pyright server is disabled. Both binaries are installed globally with `uv tool install`.
