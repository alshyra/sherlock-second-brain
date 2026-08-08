"""Use case: lifecycle of investigation cases (thin orchestration).

Business rules live on the ``Case`` aggregate (domain). This service only
orders the calls: allocate the id, mutate the domain object, persist, re-index.
"""

from __future__ import annotations

import uuid
from typing import Any

from sherlock_second_brain.application.ports import CaseRepository, SearchIndex
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.text import slugify


class CaseService:
    """Coordinates case operations through their ports."""

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
        case = Case.create_case(
            self._repository.next_case_id(),
            title=title,
            goal=goal,
            context=context,
            tags=tags,
            references=references,
        )
        self._repository.save_case(case)
        return case

    def get(self, case_id: str) -> Case:
        return self._repository.get_case(case_id)

    def list_cases(self, status: str = "", tag: str = "") -> list[Case]:
        cases = self._repository.list_cases()
        if status:
            cases = [c for c in cases if c.status == status]
        if tag:
            cases = [c for c in cases if tag in c.tags]
        return cases

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
            case.add_finding(finding)
        if step_action:
            case.add_step(step_action, step_result)
        if conclusion:
            case.set_conclusion(conclusion)
        if hypothesis_statement:
            case.add_hypothesis(hypothesis_statement, hypothesis_test or "")
        if hypothesis_result:
            case.set_hypothesis_result(hypothesis_result)
        if tags is not None:
            case.set_tags(tags)
        if references is not None:
            case.set_references(references)
        self._repository.save_case(case)
        self._index.upsert_single(
            f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id}
        )
        return case

    def add_evidence(
        self, case_id: str, content: str, summary: str, filename: str = ""
    ) -> Case:
        case = self._repository.get_case(case_id)
        fname = filename or f"{slugify(summary)}-{uuid.uuid4().hex[:6]}.txt"
        rel = self._repository.write_evidence(case_id, fname, content)
        case.add_evidence(summary, rel)
        self._repository.save_case(case)
        self._index.upsert_single(
            f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id}
        )
        return case

    def set_status(self, case_id: str, status: str) -> Case:
        case = self._repository.get_case(case_id)
        case.set_status(status)
        self._repository.save_case(case)
        self._index.upsert_single(
            f"case:{case.id}", str(case.model_dump()), {"kind": "case", "id": case.id}
        )
        return case

    def delete(self, case_id: str) -> None:
        self._repository.delete_case(case_id)
        self._index.delete_doc(f"case:{case_id}")
