"""Cas d'usage : promotion d'un case résolu en fiche ou en skill.

Le rendu markdown (fiche MD / SKILL.md) est délégué à des templates Jinja2
dans ``adapters/templates/``, chargés une seule fois.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from jinja2 import Environment, PackageLoader

from second_brain.application.ports import CaseRepository, FicheRepository, SkillRepository
from second_brain.domain.models.case import Case
from second_brain.domain.models.promotion import Promotion
from second_brain.domain.text import slugify

VALID_PROMOTION_TARGETS = {"fiche", "skill"}


def _linkify(text: str) -> str:
    """Keep safe chars, strip markdown markup for slugs."""
    return slugify(re.sub(r"[`*_#\[\]()]", "", text))


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d")
    except ValueError:
        return iso


class PromotionService:
    """Transforme un case ``resolved`` en artefact validé (fiche MD ou SKILL.md).

    La promotion est l'acte de validation : elle écrit l'artefact dans la KB
    et marque le case comme promu.
    """

    def __init__(
        self,
        cases: CaseRepository,
        fiches: FicheRepository,
        skills: SkillRepository,
    ) -> None:
        self._cases = cases
        self._fiches = fiches
        self._skills = skills
        self._env = Environment(
            loader=PackageLoader("second_brain.adapters", "templates"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["fmt_date"] = _fmt_date
        self._env.filters["linkify"] = _linkify
        self._env.filters["backtick"] = lambda tag: f"`{tag}`"
        self._fiche_template = self._env.get_template("fiche.md.j2")
        self._skill_template = self._env.get_template("skill.md.j2")

    def fiche_content(self, case: Case) -> str:
        """Render a validated fiche (MD) from a resolved case."""
        return self._fiche_template.render(case=case)

    def skill_content(self, case: Case) -> str:
        """Render a skill (SKILL.md) from a resolved case (procedure)."""
        return self._skill_template.render(case=case)

    def promote(self, case: Case, target: str) -> dict[str, str]:
        """Promote a resolved case into a fiche or a skill. Returns metadata."""
        if target not in VALID_PROMOTION_TARGETS:
            raise ValueError(f"invalid promotion target: {target!r} (expected fiche|skill)")
        if case.status != "resolved":
            raise ValueError(f"cannot promote a case in status {case.status!r} — mark it resolved first")

        slug = _linkify(case.title)
        rel = f"fiches/{slug}.md" if target == "fiche" else f"skills/{slug}/SKILL.md"
        case.promotion = Promotion(
            target=target,
            path=rel,
            date=datetime.now(UTC).isoformat(timespec="seconds"),
        )

        if target == "fiche":
            content = self.fiche_content(case)
            self._fiches.write_fiche(slug, content)
        else:
            content = self.skill_content(case)
            self._skills.write_skill(slug, content)

        case.touch()
        self._cases.update_case(case)
        return {"target": target, "path": rel, "slug": slug, "content": content}
