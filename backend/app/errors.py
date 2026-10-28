from __future__ import annotations

from typing import Any


class ApiError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ApiError):
    status_code = 404
    code = "NOT_FOUND"


class VersionConflictError(ApiError):
    status_code = 409
    code = "VERSION_CONFLICT"


class DuplicateDisplayCodeError(ApiError):
    status_code = 409
    code = "DUPLICATE_DISPLAY_CODE"


class DuplicateRecordError(ApiError):
    status_code = 409
    code = "DUPLICATE_RECORD"


class InvalidReferenceError(ApiError):
    status_code = 400
    code = "INVALID_REFERENCE"


class IssueStateConflictError(ApiError):
    status_code = 409
    code = "ISSUE_STATE_CONFLICT"


class ConflictStateError(ApiError):
    status_code = 409
    code = "CONFLICT_STATE_CONFLICT"


class MaterialPackageStateError(ApiError):
    status_code = 409
    code = "PACKAGE_STATE_CONFLICT"


class DomainValidationError(ApiError):
    status_code = 422
    code = "VALIDATION_ERROR"
