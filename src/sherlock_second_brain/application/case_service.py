"""Cas d'usage : cycle de vie des investigations (cases)."""

from __future__ import annotations

from typing import Any

from sherlock_second_brain.application.ports import CaseRepository, SearchIndex
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.hypothesis import Hypothesis
from sherlock_second_brain.domain.models.step import Step


class CaseService:
    """Orchestre les opérations sur les cases via leurs ports.

    Ne dépend d'aucun adapter concret : ``CaseRepository`` pour le stockage
    et ``SearchIndex`` pour maintenir l'index à jour sur chaque mutation.
    """

    def __init__(self, repository: CaseRepository, index: SearchIndex) -> None:
        self._repository = repository
        self._index = index

    def create(
        self,
        title: str,
        goal: str,
        context: str = "",
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> Case:
        return self._repository.create_case(
            title=title,
            goal=goal,
            context=context,
            tags=tags,
            references=references,
        )

    def get(self, case_id: str) -> Case:
        return self._repository.get_case(case_id)

    def list_cases(self, status: str = "", tag: str = "") -> list[Case]:
        return self._repository.list_cases(status=status or None, tag=tag or None)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._index.query(query, top_k=top_k)

    def update(
        self,
        case_id: str,
        *,
        finding: str | None = None,
        step_action: str | None = None,
        step_result: str | None = None,
        conclusion: str | None = None,
        hypothesis_statement: str | None = None,
        hypothesis_test: str | None = None,
        hypothesis_result: str | None = None,
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> Case:
        case = self._repository.get_case(case_id)

        if finding:
            case.findings.append(finding)
        if step_action:
            case.steps = [
                *case.steps,
                Step(
                    order=len(case.steps) + 1,
                    action=step_action,
                    result=step_result,
                ),
            ]
        if conclusion:
            case.conclusion = conclusion
        if hypothesis_statement:
            case.hypotheses = [
                *case.hypotheses,
                Hypothesis(
                    id=f"h{len(case.hypotheses) + 1}",
                    statement=hypothesis_statement,
                    test=hypothesis_test or "",
                ),
            ]
        if hypothesis_result:
            if case.hypotheses:
                case.hypotheses[-1].result = hypothesis_result
        if tags is not None:
            case.tags = tags
        if references is not None:
            case.references = references

        updated = self._repository.update_case(case)
        self._index.upsert_single(
            f"case:{updated.id}", str(updated.model_dump()), {"kind": "case", "id": updated.id}
        )
        return updated

    def add_evidence(
        self, case_id: str, content: str, summary: str, filename: str = ""
    ) -> Case:
        case = self._repository.add_evidence(
            case_id, content, summary, filename or None
        )
        self._index.upsert_single(
            f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id}
        )
        return case

    def set_status(self, case_id: str, status: str) -> Case:
        case = self._repository.get_case(case_id)
        case.status = status
        updated = self._repository.update_case(case)
        self._index.upsert_single(
            f"case:{updated.id}", str(updated.model_dump()), {"kind": "case", "id": updated.id}
        )
        return updated

    def delete(self, case_id: str) -> None:
        self._repository.delete_case(case_id)
        self._index.delete_doc(f"case:{case_id}")
