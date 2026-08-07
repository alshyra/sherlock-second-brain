"""Cas d'usage : promotion d'un case résolu en fiche ou en skill."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from second_brain.application.ports import CaseRepository, FicheRepository, SkillRepository
from second_brain.domain.models.case import Case
from second_brain.domain.models.promotion import Promotion
from second_brain.domain.text import slugify

VALID_PROMOTION_TARGETS = {"fiche", "skill"}


def _linkify(text: str) -> str:
    """Keep safe chars, strip markdown markup for slugs."""
    return slugify(re.sub(r"[`*_#\[\]()]", "", text))


def _fmt(iso: str) -> str:
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

    def fiche_content(self, case: Case) -> str:
        """Render a validated fiche (MD) from a resolved case."""
        lines: list[str] = []
        lines.append(f"# {case.title}")
        lines.append("")
        lines.append(
            f"> Statut : validé (promu depuis `{case.id}` le {_fmt(case.promotion.date)})"
            if case.promotion
            else ""
        )
        lines.append("")
        lines.append(f"**Objectif :** {case.goal}")
        if case.context:
            lines.append("")
            lines.append(f"**Contexte :** {case.context}")
        lines.append("")
        lines.append("## Constats")
        if case.findings:
            for finding in case.findings:
                lines.append(f"- {finding}")
        else:
            lines.append("- _Aucun constat enregistré._")
        if case.conclusion:
            lines.append("")
            lines.append("## Conclusion")
            lines.append("")
            lines.append(case.conclusion)
        if case.references:
            lines.append("")
            lines.append("## Références")
            lines.append("")
            for ref in case.references:
                lines.append(f"- {ref}")
        if case.tags:
            lines.append("")
            lines.append("## Tags")
            lines.append("")
            lines.append(" ".join(f"`{t}`" for t in case.tags))
        return "\n".join(lines) + "\n"

    def skill_content(self, case: Case) -> str:
        """Render a skill (SKILL.md) from a resolved case (procedure)."""
        lines: list[str] = []
        lines.append("---")
        lines.append(f"name: {_linkify(case.title)}")
        lines.append("description: >")
        lines.append(f"  {case.goal}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {case.title}")
        lines.append("")
        lines.append(f"Promu depuis `{case.id}`. {case.goal}")
        if case.context:
            lines.append("")
            lines.append("## Contexte")
            lines.append("")
            lines.append(case.context)
        lines.append("")
        lines.append("## Procédure")
        lines.append("")
        if case.steps:
            for step in case.steps:
                lines.append(f"{step.order}. {step.action}")
                if step.result:
                    lines.append(f"   - Résultat : {step.result}")
        else:
            lines.append("_Aucune étape enregistrée._")
        if case.findings:
            lines.append("")
            lines.append("## Points d'attention")
            lines.append("")
            for finding in case.findings:
                lines.append(f"- {finding}")
        if case.references:
            lines.append("")
            lines.append("## Références")
            lines.append("")
            for ref in case.references:
                lines.append(f"- {ref}")
        return "\n".join(lines) + "\n"

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
