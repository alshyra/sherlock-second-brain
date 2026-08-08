"""Filesystem adapter: persistence of cases, fiches, skills and memories.

Layout::

    <data_dir>/
      cases/<case-id>/case.json
      cases/<case-id>/evidence/<file>
      memories/<id>.md
      fiches/<slug>.md
      skills/<slug>/SKILL.md
      vector/            # chromadb persistent dir (gitignored)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path

import jsonschema
from pydantic import ValidationError

from sherlock_second_brain.adapters.frontmatter import parse_memory, render_memory
from sherlock_second_brain.application.ports import KbDoc
from sherlock_second_brain.domain.errors import (
    CaseNotFoundError,
    CaseValidationError,
    MemoryNotFoundError,
    MemoryValidationError,
    StorageError,
)
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory
from sherlock_second_brain.domain.text import CASE_ID_PATTERN, MEMORY_ID_PATTERN, now_iso

_SCHEMA_NAME = "case.schema.json"
_LOCK = threading.RLock()


def _find_schema() -> Path:
    """Resolves ``schema/case.schema.json`` by walking up to the repo root.

    Robust regardless of how the package is mounted (repo or installed).
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "schema" / _SCHEMA_NAME
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"schema introuvable : {_SCHEMA_NAME}")


SCHEMA_PATH = _find_schema()


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


class Storage:
    """File-based storage for Sherlock's second brain.

    Implements ``CaseRepository``, ``FicheRepository``, ``SkillRepository``
    and ``DocumentSource`` (ports defined in ``application.ports``).
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir).resolve()
        self.cases_dir = self.root / "cases"
        self.memories_dir = self.root / "memories"
        self.fiches_dir = self.root / "fiches"
        self.skills_dir = self.root / "skills"
        self.vector_dir = self.root / "vector"
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Safety helpers ───────────────────────────────────────────

    @staticmethod
    def _require_valid_case_id(case_id: str) -> None:
        if not re.fullmatch(CASE_ID_PATTERN, case_id):
            raise CaseNotFoundError(case_id)

    @staticmethod
    def _require_valid_memory_id(memory_id: str) -> None:
        if not re.fullmatch(MEMORY_ID_PATTERN, memory_id):
            raise MemoryNotFoundError(memory_id)

    # ── Cases ───────────────────────────────────────────────────

    @staticmethod
    def _case_path(case_id: str) -> Path:
        return Path("cases") / case_id / "case.json"

    def case_abs_path(self, case_id: str) -> Path:
        self._require_valid_case_id(case_id)
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

    def save_case(self, case: Case) -> None:
        """Persist a case (create or update) as ``cases/<id>/case.json``."""
        with _LOCK:
            self._save_case(case)

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

    def list_cases(self) -> list[Case]:
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
                    cases.append(Case.model_validate(json.loads(case_path.read_text(encoding="utf-8"))))
                except (json.JSONDecodeError, ValidationError):
                    continue
            return cases

    def delete_case(self, case_id: str) -> None:
        with _LOCK:
            self._require_valid_case_id(case_id)
            path = self.cases_dir / case_id
            if not path.exists():
                raise CaseNotFoundError(case_id)
            shutil.rmtree(path)

    def write_evidence(self, case_id: str, filename: str, content: str) -> str:
        """Write an evidence file and return its relative path (``evidence/<name>``)."""
        with _LOCK:
            self._require_valid_case_id(case_id)
            ev_dir = self.cases_dir / case_id / "evidence"
            ev_dir.mkdir(parents=True, exist_ok=True)
            path = ev_dir / Path(filename).name  # strip any parent directory
            _atomic_write(path, content)
            return f"evidence/{path.name}"

    # ── Memories ────────────────────────────────────────────────

    @staticmethod
    def _memory_path(memory_id: str) -> Path:
        return Path("memories") / f"{memory_id}.md"

    def memory_abs_path(self, memory_id: str) -> Path:
        self._require_valid_memory_id(memory_id)
        return self.memories_dir / f"{memory_id}.md"

    def _load_memory(self, memory_id: str) -> Memory:
        path = self.memory_abs_path(memory_id)
        if not path.exists():
            raise MemoryNotFoundError(memory_id)
        return parse_memory(path.read_text(encoding="utf-8"), id_from_filename=memory_id)

    def save_memory(self, memory: Memory) -> None:
        """Persist a memory (create or update) as ``memories/<id>.md``."""
        with _LOCK:
            _atomic_write(self.memory_abs_path(memory.id), render_memory(memory))

    def next_memory_id(self) -> str:
        """Return the next ``mem-YYYY-MM-DD-NNN`` id (per-day counter)."""
        day = now_iso()[:10]
        prefix = f"mem-{day}-"
        if not self.memories_dir.exists():
            return f"{prefix}001"
        existing = [
            p.stem
            for p in self.memories_dir.glob("*.md")
            if p.stem.startswith(prefix)
        ]
        max_n = max((int(n) for n in (name[len(prefix):] for name in existing) if n.isdigit()), default=0)
        return f"{prefix}{max_n + 1:03d}"

    def get_memory(self, memory_id: str) -> Memory:
        with _LOCK:
            return self._load_memory(memory_id)

    def list_memories(self) -> list[Memory]:
        with _LOCK:
            if not self.memories_dir.exists():
                return []
            memories: list[Memory] = []
            for path in sorted(self.memories_dir.glob("*.md")):
                try:
                    memories.append(parse_memory(path.read_text(encoding="utf-8"), id_from_filename=path.stem))
                except MemoryValidationError:
                    continue
            return memories

    def delete_memory(self, memory_id: str) -> None:
        with _LOCK:
            self._require_valid_memory_id(memory_id)
            path = self.memory_abs_path(memory_id)
            if not path.exists():
                raise MemoryNotFoundError(memory_id)
            path.unlink()

    # ── Fiches (KB) ─────────────────────────────────────────────

    def write_fiche(self, slug: str, content: str) -> str:
        path = self.fiches_dir / f"{slug}.md"
        _atomic_write(path, content)
        return str(path)

    def read_fiche(self, slug: str) -> str:
        path = self.fiches_dir / f"{slug}.md"
        if not path.exists():
            raise StorageError(f"fiche not found: {slug}")
        return path.read_text(encoding="utf-8")

    def list_fiches(self) -> list[KbDoc]:
        if not self.fiches_dir.exists():
            return []
        return [
            KbDoc(slug=p.stem, content=p.read_text(encoding="utf-8"))
            for p in sorted(self.fiches_dir.glob("*.md"))
        ]

    def delete_fiche(self, slug: str) -> None:
        path = self.fiches_dir / f"{slug}.md"
        if not path.exists():
            raise StorageError(f"fiche not found: {slug}")
        path.unlink()

    # ── Skills (KB) ─────────────────────────────────────────────

    def write_skill(self, slug: str, content: str) -> str:
        path = self.skills_dir / slug / "SKILL.md"
        _atomic_write(path, content)
        return str(path)

    def read_skill(self, slug: str) -> str:
        path = self.skills_dir / slug / "SKILL.md"
        if not path.exists():
            raise StorageError(f"skill not found: {slug}")
        return path.read_text(encoding="utf-8")

    def list_skills(self) -> list[KbDoc]:
        if not self.skills_dir.exists():
            return []
        return [
            KbDoc(slug=p.parent.name, content=p.read_text(encoding="utf-8"))
            for p in sorted(self.skills_dir.glob("*/SKILL.md"))
        ]

    def delete_skill(self, slug: str) -> None:
        path = self.skills_dir / slug
        if not (path / "SKILL.md").exists():
            raise StorageError(f"skill not found: {slug}")
        shutil.rmtree(path)
