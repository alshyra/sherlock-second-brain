"""FastMCP server exposing Sherlock's second brain as local MCP tools (stdio).

Every ``case`` is an investigation file (debug / troubleshooting); once resolved
it is promoted into a validated fiche or skill. Composition root: instantiates
the concrete adapters, the application services and exposes the MCP tools that
delegate to those services.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from sherlock_second_brain.adapters.chroma import VectorIndex
from sherlock_second_brain.adapters.dto.case_update import CaseUpdateFields
from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.adapters.hybrid import HybridIndex
from sherlock_second_brain.adapters.lexical import LexicalIndex
from sherlock_second_brain.application.case_service import CaseService
from sherlock_second_brain.application.ports import SearchIndex
from sherlock_second_brain.application.promotion_service import PromotionService
from sherlock_second_brain.domain.models.case import Case

DEFAULT_DATA_DIR = os.environ.get("SHERLOCK_BRAIN_DATA_DIR", str(Path.home() / "sherlock-second-brain-data"))

mcp = FastMCP("sherlock-second-brain")

_storage = Storage(DEFAULT_DATA_DIR)
_vector = VectorIndex(_storage, _storage.vector_dir)
_index: SearchIndex = HybridIndex(_vector, LexicalIndex(_storage))
_cases = CaseService(_storage, _index)
_promotions = PromotionService(_storage, _storage, _storage)


# ── Cases ────────────────────────────────────────────────────────


@mcp.tool()
def case_create(title: str, goal: str, context: str = "", tags: str = "", references: str = "") -> Case:
    """Create a new investigation case for a topic that is not yet validated.

    Mutating: writes the case to disk (``cases/<case-id>/case.json``) and adds it
    to the search index. Returns the created case. Use ``case_promote`` once the
    investigation is resolved.

    Args:
        title: Short human-readable summary of the investigation.
        goal: What the investigation aims to establish or decide.
        context: Optional background, symptoms or clues (default "").
        tags: Comma-separated tags, e.g. ``networking,debugging``.
        references: Comma-separated source references or URLs.
    """
    return _cases.create(
        title=title,
        goal=goal,
        context=context,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        references=[r.strip() for r in references.split(",") if r.strip()],
    )


@mcp.tool()
def case_get(case_id: str) -> Case:
    """Read a case by its id. Read-only, no side effects.

    Raises an error if the id does not exist. Use ``case_list`` or ``case_search``
    to find ids first.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
    """
    return _cases.get(case_id)


@mcp.tool()
def case_list(status: str = "", tag: str = "") -> list[Case]:
    """List cases, optionally filtered by ``status`` and ``tag``. Read-only.

    Use ``case_search`` for semantic ranking instead of structured enumeration.

    Args:
        status: Filter by status: open, in_progress, resolved or abandoned (empty = all).
        tag: Only return cases carrying this tag (empty = all).
    """
    return _cases.list_cases(status=status, tag=tag)


@mcp.tool()
def case_search(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """Semantic hybrid search across cases and KB. Read-only.

    Results are ranked by vector + lexical fusion (multilingual). Use this FIRST
    when debugging or planning; use ``case_list`` for filtered enumeration.

    Args:
        query: Free-text search query (any language, multilingual embeddings).
        top_k: Number of results to return (default 5).
    """
    return _cases.search(query, top_k=top_k)


@mcp.tool()
def case_update(case_id: str, fields: CaseUpdateFields) -> Case:
    """Append structured fields to an existing case. Mutating.

    Persists the case and refreshes the search index. Prefer ``case_add_evidence``
    for attaching raw logs or outputs as files; use ``case_set_status`` to change
    the case status.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
        fields: Dict of fields to update; see each field description below.
    """
    return _cases.update(
        case_id,
        finding=fields.finding,
        step_action=fields.step_action,
        step_result=fields.step_result,
        conclusion=fields.conclusion,
        hypothesis_statement=fields.hypothesis_statement,
        hypothesis_test=fields.hypothesis_test,
        hypothesis_result=fields.hypothesis_result,
        tags=fields.tags,
        references=fields.references,
    )


@mcp.tool()
def case_add_evidence(case_id: str, content: str, summary: str, filename: str = "") -> Case:
    """Attach a piece of evidence (log excerpt, output, note) to a case. Mutating.

    Writes the content under ``cases/<case-id>/evidence/`` and reindexes the case.
    Use ``case_update`` instead for structured findings or steps.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
        content: Full text of the evidence to store.
        summary: One-line label describing the evidence.
        filename: Optional file name for the evidence (auto-generated if empty).
    """
    return _cases.add_evidence(case_id, content, summary, filename)


@mcp.tool()
def case_set_status(case_id: str, status: str) -> Case:
    """Change a case status: open / in_progress / resolved / abandoned. Mutating.

    Persists the change and reindexes the case. Only ``resolved`` cases can be
    promoted with ``case_promote``.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
        status: One of open, in_progress, resolved or abandoned.
    """
    return _cases.set_status(case_id, status)


@mcp.tool()
def case_delete(case_id: str) -> dict[str, str]:
    """Delete a case and its evidence directory. Destructive and irreversible.

    Removes ``cases/<case-id>/`` and the case from the search index.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
    """
    _cases.delete(case_id)
    return {"deleted": case_id}


@mcp.tool()
def case_promote(case_id: str, target: str) -> dict[str, str]:
    """Promote a resolved case into validated knowledge. Mutating.

    Renders the case into a fiche (``fiches/<slug>.md``) or a skill
    (``skills/<slug>/SKILL.md``) depending on ``target``, writes it to the KB,
    reindexes it and marks the case. The case status must be ``resolved``.

    Args:
        case_id: Case identifier, e.g. ``case-2026-08-07-001``.
        target: Destination kind: ``fiche`` or ``skill``.
    """
    case = _cases.get(case_id)
    result = _promotions.promote(case, target)
    _index.upsert_single(
        result["target"] + ":" + result["slug"],
        result["content"],
        {"kind": result["target"], "slug": result["slug"]},
    )
    _index.upsert_single(
        f"case:{case_id}",
        str(_cases.get(case_id).model_dump()),
        {"kind": "case", "id": case_id},
    )
    return result


# ── KB (fiches) ──────────────────────────────────────────────────


@mcp.tool()
def fiche_list() -> list[str]:
    """List validated fiche slugs. Read-only.

    Use ``fiche_read`` to fetch the content of a specific fiche.

    Args:
        None.
    """
    return [p.stem for p in _storage.list_fiches()]


@mcp.tool()
def fiche_read(slug: str) -> str:
    """Read a validated fiche by slug. Read-only.

    Raises an error if the slug does not exist. Use ``fiche_list`` to discover
    available slugs.

    Args:
        slug: Fiche identifier, lowercase, accents preserved (e.g. ``très-long``).
    """
    return _storage.read_fiche(slug)


@mcp.tool()
def fiche_write(slug: str, content: str) -> str:
    """Create or overwrite a fiche. Mutating, overwrites existing content.

    Writes ``fiches/<slug>.md`` and upserts it into the search index. Prefer
    ``case_promote`` for validated knowledge — this tool bypasses validation.

    Args:
        slug: Fiche identifier used as the file name.
        content: Full Markdown content of the fiche.
    """
    path = _storage.write_fiche(slug, content)
    _index.upsert_single(f"fiche:{slug}", content, {"kind": "fiche", "slug": slug})
    return str(path)


@mcp.tool()
def fiche_delete(slug: str) -> dict[str, str]:
    """Delete a fiche by slug. Destructive and irreversible.

    Removes ``fiches/<slug>.md`` and its search-index entry.

    Args:
        slug: Fiche identifier to remove.
    """
    _storage.delete_fiche(slug)
    _index.delete_doc(f"fiche:{slug}")
    return {"deleted": slug}


# ── Skills (KB) ──────────────────────────────────────────────────


@mcp.tool()
def skill_list() -> list[str]:
    """List validated skill slugs. Read-only.

    Use ``skill_read`` to fetch the content of a specific skill.

    Args:
        None.
    """
    return [p.parent.name for p in _storage.list_skills()]


@mcp.tool()
def skill_read(slug: str) -> str:
    """Read a validated skill by slug. Read-only.

    Raises an error if the slug does not exist. Use ``skill_list`` to discover
    available slugs.

    Args:
        slug: Skill identifier, lowercase, accents preserved (e.g. ``très-long``).
    """
    return _storage.read_skill(slug)


@mcp.tool()
def skill_write(slug: str, content: str) -> str:
    """Create or overwrite a skill. Mutating, overwrites existing content.

    Writes ``skills/<slug>/SKILL.md`` and upserts it into the search index. Prefer
    ``case_promote`` for validated knowledge — this tool bypasses validation.

    Args:
        slug: Skill identifier used as the directory/file name.
        content: Full Markdown content of the SKILL.md file.
    """
    path = _storage.write_skill(slug, content)
    _index.upsert_single(f"skill:{slug}", content, {"kind": "skill", "slug": slug})
    return str(path)


@mcp.tool()
def skill_delete(slug: str) -> dict[str, str]:
    """Delete a skill by slug. Destructive and irreversible.

    Removes ``skills/<slug>/`` and its search-index entry.

    Args:
        slug: Skill identifier to remove.
    """
    _storage.delete_skill(slug)
    _index.delete_doc(f"skill:{slug}")
    return {"deleted": slug}


# ── Index ────────────────────────────────────────────────────────


@mcp.tool()
def index_rebuild() -> dict[str, int | bool]:
    """Rebuild the vector index from all source files. Mutating.

    Replaces the derived ``vector/`` index; the first run downloads the
    multilingual embedding model (~0.22GB). Returns the number of indexed docs
    and whether the vector engine is available.

    Args:
        None.
    """
    count = _index.rebuild()
    return {"indexed_docs": count, "vector_enabled": _index.available}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
