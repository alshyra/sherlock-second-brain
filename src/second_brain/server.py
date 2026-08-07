"""FastMCP server exposing the second brain as local MCP tools (stdio)."""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from second_brain import promote
from second_brain.domain import Hypothesis, Step
from second_brain.storage import Storage
from second_brain.vector import VectorIndex

DEFAULT_DATA_DIR = os.environ.get("SECOND_BRAIN_DATA_DIR", str(Path.home() / "second-brain-data"))

mcp = FastMCP("second-brain")

_storage: Storage | None = None
_index: VectorIndex | None = None


def _svc() -> tuple[Storage, VectorIndex]:
    global _storage, _index
    if _storage is None:
        _storage = Storage(DEFAULT_DATA_DIR)
    if _index is None:
        _index = VectorIndex(_storage)
    return _storage, _index


# ── Cases ────────────────────────────────────────────────────────


@mcp.tool()
def case_create(title: str, goal: str, context: str = "", tags: str = "", references: str = "") -> dict:
    """Create an investigation case. Use this when a topic is not yet validated.

    ``tags`` and ``references`` are comma-separated strings.
    """
    storage, _ = _svc()
    case = storage.create_case(
        title=title,
        goal=goal,
        context=context,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        references=[r.strip() for r in references.split(",") if r.strip()],
    )
    return case.model_dump()


@mcp.tool()
def case_get(case_id: str) -> dict:
    """Read a case by its id (e.g. ``case-2026-08-07-001``)."""
    storage, _ = _svc()
    return storage.get_case(case_id).model_dump()


@mcp.tool()
def case_list(status: str = "", tag: str = "") -> list[dict]:
    """List cases, optionally filtered by ``status`` (open/in_progress/resolved/abandoned) and ``tag``."""
    storage, _ = _svc()
    return [c.model_dump() for c in storage.list_cases(status=status or None, tag=tag or None)]


@mcp.tool()
def case_search(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search across cases and KB. Use this FIRST when debugging or planning."""
    _, index = _svc()
    return index.query(query, top_k=top_k)


@mcp.tool()
def case_update(case_id: str, fields: dict) -> dict:
    """Append to a case.

    ``fields`` supports:
    - ``finding`` (str): append to findings
    - ``step_action`` (str): append a step (with optional ``step_result``)
    - ``step_result`` (str): result for the step being appended
    - ``conclusion`` (str): set conclusion
    - ``hypothesis_statement`` / ``hypothesis_test``: append a hypothesis
    - ``tags`` (list[str]) / ``references`` (list[str]): replace lists
    """
    storage, index = _svc()
    case = storage.get_case(case_id)

    if fields.get("finding"):
        case.findings.append(str(fields["finding"]))
    if fields.get("step_action"):
        case.steps = [
            *case.steps,
            Step(
                order=len(case.steps) + 1,
                action=str(fields["step_action"]),
                result=fields.get("step_result"),
            ),
        ]
    if fields.get("conclusion"):
        case.conclusion = str(fields["conclusion"])
    if fields.get("hypothesis_statement"):
        h_id = f"h{len(case.hypotheses) + 1}"
        case.hypotheses = [
            *case.hypotheses,
            Hypothesis(
                id=h_id,
                statement=str(fields["hypothesis_statement"]),
                test=str(fields.get("hypothesis_test", "")),
            ),
        ]
    if fields.get("tags") is not None:
        case.tags = [str(t) for t in fields["tags"]]
    if fields.get("references") is not None:
        case.references = [str(r) for r in fields["references"]]

    storage.update_case(case)
    index.upsert_single(f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id})
    return case.model_dump()


@mcp.tool()
def case_add_evidence(case_id: str, content: str, summary: str, filename: str = "") -> dict:
    """Attach a piece of evidence (log excerpt, output, note) to a case."""
    storage, index = _svc()
    case = storage.add_evidence(case_id, content, summary, filename or None)
    index.upsert_single(f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id})
    return case.model_dump()


@mcp.tool()
def case_set_status(case_id: str, status: str) -> dict:
    """Change a case status: open / in_progress / resolved / abandoned."""
    storage, index = _svc()
    case = storage.get_case(case_id)
    case.status = status
    storage.update_case(case)
    index.upsert_single(f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id})
    return case.model_dump()


@mcp.tool()
def case_promote(case_id: str, target: str) -> dict:
    """Promote a resolved case into validated KB: ``target`` = ``fiche`` or ``skill``.

    Generates the MD/SKILL.md from the case, writes it to kb/ and marks the case.
    """
    storage, index = _svc()
    case = storage.get_case(case_id)
    result = promote.promote(storage, case, target)
    index.upsert_single(result["target"] + ":" + result["slug"], result["content"], {"kind": result["target"], "slug": result["slug"]})
    index.upsert_single(f"case:{case.id}", str(storage.get_case(case_id).model_dump()), {"kind": "case", "id": case_id})
    return result


# ── KB (fiches) ──────────────────────────────────────────────────


@mcp.tool()
def fiche_list() -> list[str]:
    """List validated fiches (slugs)."""
    storage, _ = _svc()
    return [p.stem for p in storage.list_fiches()]


@mcp.tool()
def fiche_read(slug: str) -> str:
    """Read a validated fiche by slug."""
    storage, _ = _svc()
    return storage.read_fiche(slug)


@mcp.tool()
def fiche_write(slug: str, content: str) -> str:
    """Create or overwrite a fiche. Prefer ``case_promote`` for validated knowledge."""
    storage, index = _svc()
    path = storage.write_fiche(slug, content)
    index.upsert_single(f"fiche:{slug}", content, {"kind": "fiche", "slug": slug})
    return str(path)


# ── Skills (KB) ─────────────────────────────────────────────────


@mcp.tool()
def skill_list() -> list[str]:
    """List validated skills (slugs)."""
    storage, _ = _svc()
    return [p.parent.name for p in storage.list_skills()]


@mcp.tool()
def skill_read(slug: str) -> str:
    """Read a validated skill by slug."""
    storage, _ = _svc()
    return storage.read_skill(slug)


# ── Index ───────────────────────────────────────────────────────


@mcp.tool()
def index_rebuild() -> dict:
    """Rebuild the vector index from all source files. Returns doc count."""
    _, index = _svc()
    count = index.rebuild()
    return {"indexed_docs": count, "vector_enabled": index.available}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
