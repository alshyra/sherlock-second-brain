"""Filesystem storage adapter for cases, fiches and skills.

Layout::

    <data_dir>/
      cases/<case-id>/case.json
      cases/<case-id>/evidence/<file>
      fiches/<slug>.md
      skills/<slug>/SKILL.md
      vector/            # chromadb persistent dir (gitignored)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

import jsonschema
from pydantic import ValidationError

from second_brain.domain import Case, Evidence, now_iso

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "case.schema.json"

VALID_STATUS = {"open", "in_progress", "resolved", "abandoned"}
_LOCK = threading.RLock()


class StorageError(Exception):
    """Base error for storage operations."""


class CaseNotFoundError(StorageError):
    def __init__(self, case_id: str) -> None:
        super().__init__(f"case not found: {case_id}")
        self.case_id = case_id


class CaseExistsError(StorageError):
    def __init__(self, case_id: str) -> None:
        super().__init__(f"case already exists: {case_id}")
        self.case_id = case_id


class CaseValidationError(StorageError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (tmp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def slugify(text: str) -> str:
    """Turn arbitrary text into a safe lowercase slug (keeps accents)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿœæ'-]+", "-", text)
    text = text.strip("-")
    return text or uuid.uuid4().hex[:8]


class Storage:
    """File-based storage for the second brain."""

    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir).resolve()
        self.cases_dir = self.root / "cases"
        self.fiches_dir = self.root / "fiches"
        self.skills_dir = self.root / "skills"
        self.vector_dir = self.root / "vector"
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Cases ───────────────────────────────────────────────────

    @staticmethod
    def _case_path(case_id: str) -> Path:
        return Path("cases") / case_id / "case.json"

    def case_abs_path(self, case_id: str) -> Path:
        return self.cases_dir / case_id / "case.json"

    def _load_case(self, case_id: str) -> Case:
        path = self.case_abs_path(case_id)
        if not path.exists():
            raise CaseNotFoundError(case_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Case.model_validate(raw)

    def _save_case(self, case: Case) -> None:
        rel = self._case_path(case.id)
        self._validate_case(case)
        _atomic_write(self.root / rel, case.model_dump_json(indent=2))

    def _validate_case(self, case: Case) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(case.model_dump(), schema)
        except jsonschema.ValidationError as exc:
            raise CaseValidationError(exc.message) from exc

    def create_case(
        self,
        title: str,
        goal: str,
        context: str = "",
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> Case:
        if not title.strip():
            raise CaseValidationError("title is required")
        with _LOCK:
            case_id = self.next_case_id()
            now = now_iso()
            case = Case(
                id=case_id,
                title=title.strip(),
                status="open",
                goal=goal.strip(),
                context=context.strip(),
                tags=tags or [],
                references=references or [],
                created_at=now,
                updated_at=now,
            )
            self._save_case(case)
            return case

    def next_case_id(self) -> str:
        """Return the next ``case-YYYY-MM-DD-NNN`` id (per-day counter)."""
        day = now_iso()[:10]
        prefix = f"case-{day}-"
        if not self.cases_dir.exists():
            return f"{prefix}001"
        existing = [
            p.name
            for p in self.cases_dir.iterdir()
            if p.is_dir() and p.name.startswith(prefix)
        ]
        max_n = max((int(n) for n in (name[len(prefix):] for name in existing) if n.isdigit()), default=0)
        return f"{prefix}{max_n + 1:03d}"

    def get_case(self, case_id: str) -> Case:
        with _LOCK:
            return self._load_case(case_id)

    def list_cases(self, status: str | None = None, tag: str | None = None) -> list[Case]:
        with _LOCK:
            if not self.cases_dir.exists():
                return []
            cases: list[Case] = []
            for path in sorted(self.cases_dir.iterdir()):
                if not path.is_dir():
                    continue
                case_path = path / "case.json"
                if not case_path.exists():
                    continue
                try:
                    case = Case.model_validate(json.loads(case_path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, ValidationError):
                    continue
                if status and case.status != status:
                    continue
                if tag and tag not in case.tags:
                    continue
                cases.append(case)
            return cases

    def update_case(self, case: Case) -> Case:
        with _LOCK:
            self._load_case(case.id)  # ensure exists
            case.touch()
            self._save_case(case)
            return case

    def delete_case(self, case_id: str) -> None:
        with _LOCK:
            path = self.cases_dir / case_id
            if not path.exists():
                raise CaseNotFoundError(case_id)
            import shutil

            shutil.rmtree(path)

    def add_evidence(self, case_id: str, content: str, summary: str, filename: str | None = None) -> Case:
        with _LOCK:
            case = self._load_case(case_id)
            ev_dir = self.cases_dir / case_id / "evidence"
            ev_dir.mkdir(parents=True, exist_ok=True)
            fname = filename or f"{slugify(summary)}-{uuid.uuid4().hex[:6]}.txt"
            path = ev_dir / fname
            _atomic_write(path, content)
            rel = f"evidence/{path.name}"
            case.evidence = [
                *case.evidence,
                Evidence(path=rel, type="file", summary=summary),
            ]
            case.touch()
            self._save_case(case)
            return case

    # ── Fiches (KB) ─────────────────────────────────────────────

    def write_fiche(self, slug: str, content: str) -> Path:
        path = self.fiches_dir / f"{slug}.md"
        _atomic_write(path, content)
        return path
    def read_fiche(self, slug: str) -> str:
        path = self.fiches_dir / f"{slug}.md"
        if not path.exists():
            raise StorageError(f"fiche not found: {slug}")
        return path.read_text(encoding="utf-8")

    def list_fiches(self) -> list[Path]:
        if not self.fiches_dir.exists():
            return []
        return sorted(self.fiches_dir.glob("*.md"))

    def delete_fiche(self, slug: str) -> None:
        path = self.fiches_dir / f"{slug}.md"
        if not path.exists():
            raise StorageError(f"fiche not found: {slug}")
        path.unlink()

    # ── Skills (KB) ─────────────────────────────────────────────

    def write_skill(self, slug: str, content: str) -> Path:
        path = self.skills_dir / slug / "SKILL.md"
        _atomic_write(path, content)
        return path

    def read_skill(self, slug: str) -> str:
        path = self.skills_dir / slug / "SKILL.md"
        if not path.exists():
            raise StorageError(f"skill not found: {slug}")
        return path.read_text(encoding="utf-8")

    def list_skills(self) -> list[Path]:
        if not self.skills_dir.exists():
            return []
        return sorted(p / "SKILL.md" for p in self.skills_dir.iterdir() if (p / "SKILL.md").exists())

    def delete_skill(self, slug: str) -> None:
        path = self.skills_dir / slug
        if not (path / "SKILL.md").exists():
            raise StorageError(f"skill not found: {slug}")
        import shutil

        shutil.rmtree(path)
