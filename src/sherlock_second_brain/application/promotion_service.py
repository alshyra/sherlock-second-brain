"""Use case: promotion of a resolved case into a fiche or a skill.

The markdown rendering (MD fiche / SKILL.md) is delegated to Jinja2 templates
in ``adapters/templates/``, loaded once.
"""

from __future__ import annotations

import re
from datetime import datetime

from jinja2 import Environment, PackageLoader

from sherlock_second_brain.application.ports import (
    CaseRepository,
    FicheRepository,
    MemoryRepository,
    SkillRepository,
)
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory
from sherlock_second_brain.domain.text import slugify


def _linkify(text: str) -> str:
    """Keep safe chars, strip markdown markup for slugs."""
    return slugify(re.sub(r"[`*_#\[\]()]", "", text))


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d")
    except ValueError:
        return iso


class PromotionService:
    """Transforms a ``resolved`` case into a validated artifact (MD fiche or SKILL.md).

    Promotion is the validation act: it writes the artifact into the KB and
    marks the case as promoted.
    """

    def __init__(
        self,
        cases: CaseRepository,
        fiches: FicheRepository,
        skills: SkillRepository,
        memories: MemoryRepository,
    ) -> None:
        self._cases = cases
        self._fiches = fiches
        self._skills = skills
        self._memories = memories
        self._env = Environment(
            loader=PackageLoader("sherlock_second_brain.adapters", "templates"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["fmt_date"] = _fmt_date
        self._env.filters["linkify"] = _linkify
        self._env.filters["backtick"] = lambda tag: f"`{tag}`"
        self._fiche_template = self._env.get_template("fiche.md.j2")
        self._skill_template = self._env.get_template("skill.md.j2")
        self._memory_fiche_template = self._env.get_template("memory_fiche.md.j2")

    def fiche_content(self, case: Case) -> str:
        """Render a validated fiche (MD) from a resolved case."""
        return self._fiche_template.render(case=case)

    def skill_content(self, case: Case) -> str:
        """Render a skill (SKILL.md) from a resolved case (procedure)."""
        return self._skill_template.render(case=case)

    def promote(self, case: Case, target: str) -> dict[str, str]:
        """Promote a resolved case into a fiche or a skill. Returns metadata.

        The promotion rule (valid target, resolved status, one-shot) is
        enforced by ``Case.promote``; this service only renders and persists.
        """
        slug = _linkify(case.title)
        rel = f"fiches/{slug}.md" if target == "fiche" else f"skills/{slug}/SKILL.md"
        case.promote(target, rel)

        if target == "fiche":
            content = self.fiche_content(case)
            self._fiches.write_fiche(slug, content)
        else:
            content = self.skill_content(case)
            self._skills.write_skill(slug, content)

        self._cases.save_case(case)
        return {"target": target, "path": rel, "slug": slug, "content": content}

    def promote_memory(self, memory: Memory) -> dict[str, str]:
        """Promote a memory into a validated fiche. Returns metadata.

        The one-shot rule is enforced by ``Memory.promote``.
        """
        slug = _linkify(memory.summary)
        rel = f"fiches/{slug}.md"
        memory.promote(rel)
        content = self._memory_fiche_template.render(memory=memory)
        self._fiches.write_fiche(slug, content)
        self._memories.save_memory(memory)
        return {"target": "fiche", "path": rel, "slug": slug, "content": content}
