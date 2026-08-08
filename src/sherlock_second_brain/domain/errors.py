"""Storage domain exceptions."""

from __future__ import annotations


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


class MemoryNotFoundError(StorageError):
    def __init__(self, memory_id: str) -> None:
        super().__init__(f"memory not found: {memory_id}")
        self.memory_id = memory_id


class MemoryValidationError(StorageError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
