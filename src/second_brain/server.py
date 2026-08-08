"""FastMCP server exposing the second brain as local MCP tools (stdio).

Composition root : instancie les adapters concrets, les services applicatifs
et expose les outils MCP qui délèguent aux services.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from second_brain.adapters.dto.case_update import CaseUpdateFields
from second_brain.adapters.filesystem import Storage
from second_brain.application.case_service import CaseService
from second_brain.application.ports import SearchIndex
from second_brain.application.promotion_service import PromotionService
from second_brain.domain.models.case import Case

DEFAULT_DATA_DIR = os.environ.get("SECOND_BRAIN_DATA_DIR", str(Path.home() / "second-brain-data"))

mcp = FastMCP("second-brain")

_storage = Storage(DEFAULT_DATA_DIR)
try:  # extra [vector] présent
    from second_brain.adapters.chroma import VectorIndex

    _index: SearchIndex = VectorIndex(_storage, _storage.vector_dir)
except ImportError:
    from second_brain.adapters.lexical import LexicalIndex

    _index = LexicalIndex(_storage)
_cases = CaseService(_storage, _index)
_promotions = PromotionService(_storage, _storage, _storage)


# ── Cases ────────────────────────────────────────────────────────


@mcp.tool()
def case_create(title: str, goal: str, context: str = "", tags: str = "", references: str = "") -> Case:
    """Create an investigation case. Use this when a topic is not yet validated.

    ``tags`` and ``references`` are comma-separated strings.
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
    """Read a case by its id (e.g. ``case-2026-08-07-001``)."""
    return _cases.get(case_id)


@mcp.tool()
def case_list(status: str = "", tag: str = "") -> list[Case]:
    """List cases, optionally filtered by ``status`` (open/in_progress/resolved/abandoned) and ``tag``."""
    return _cases.list_cases(status=status, tag=tag)


@mcp.tool()
def case_search(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """Semantic search across cases and KB. Use this FIRST when debugging or planning."""
    return _cases.search(query, top_k=top_k)


@mcp.tool()
def case_update(case_id: str, fields: CaseUpdateFields) -> Case:
    """Append to a case.

    ``fields`` supports:
    - ``finding`` (str): append to findings
    - ``step_action`` (str): append a step (with optional ``step_result``)
    - ``step_result`` (str): result for the step being appended
    - ``conclusion`` (str): set conclusion
    - ``hypothesis_statement`` / ``hypothesis_test``: append a hypothesis
    - ``hypothesis_result`` (str): result of the last hypothesis (confirmed|refuted|inconclusive)
    - ``tags`` (list[str]) / ``references`` (list[str]): replace lists
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
    """Attach a piece of evidence (log excerpt, output, note) to a case."""
    return _cases.add_evidence(case_id, content, summary, filename)


@mcp.tool()
def case_set_status(case_id: str, status: str) -> Case:
    """Change a case status: open / in_progress / resolved / abandoned."""
    return _cases.set_status(case_id, status)


@mcp.tool()
def case_delete(case_id: str) -> dict[str, str]:
    """Delete a case and its evidence directory."""
    _cases.delete(case_id)
    return {"deleted": case_id}


@mcp.tool()
def case_promote(case_id: str, target: str) -> dict[str, str]:
    """Promote a resolved case into validated KB: ``target`` = ``fiche`` or ``skill``.

    Generates the MD/SKILL.md from the case, writes it to the KB and marks the case.
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
    """List validated fiches (slugs)."""
    return [p.stem for p in _storage.list_fiches()]


@mcp.tool()
def fiche_read(slug: str) -> str:
    """Read a validated fiche by slug."""
    return _storage.read_fiche(slug)


@mcp.tool()
def fiche_write(slug: str, content: str) -> str:
    """Create or overwrite a fiche. Prefer ``case_promote`` for validated knowledge."""
    path = _storage.write_fiche(slug, content)
    _index.upsert_single(f"fiche:{slug}", content, {"kind": "fiche", "slug": slug})
    return str(path)


@mcp.tool()
def fiche_delete(slug: str) -> dict[str, str]:
    """Delete a fiche by slug."""
    _storage.delete_fiche(slug)
    _index.delete_doc(f"fiche:{slug}")
    return {"deleted": slug}


# ── Skills (KB) ──────────────────────────────────────────────────


@mcp.tool()
def skill_list() -> list[str]:
    """List validated skills (slugs)."""
    return [p.parent.name for p in _storage.list_skills()]


@mcp.tool()
def skill_read(slug: str) -> str:
    """Read a validated skill by slug."""
    return _storage.read_skill(slug)


@mcp.tool()
def skill_write(slug: str, content: str) -> str:
    """Create or overwrite a skill. Prefer ``case_promote`` for validated knowledge."""
    path = _storage.write_skill(slug, content)
    _index.upsert_single(f"skill:{slug}", content, {"kind": "skill", "slug": slug})
    return str(path)


@mcp.tool()
def skill_delete(slug: str) -> dict[str, str]:
    """Delete a skill by slug."""
    _storage.delete_skill(slug)
    _index.delete_doc(f"skill:{slug}")
    return {"deleted": slug}


# ── Index ────────────────────────────────────────────────────────


@mcp.tool()
def index_rebuild() -> dict[str, int | bool]:
    """Rebuild the vector index from all source files. Returns doc count."""
    count = _index.rebuild()
    return {"indexed_docs": count, "vector_enabled": _index.available}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
