from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]
DataType = Literal["numeric", "range", "boolean", "text"]
DocumentType = Literal[
    "protocol", "change_notice", "drawing", "test_report", "communication", "other"
]
Mode = Literal["rule", "mock", "manual"]

_DISPLAY_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def _clean_display_code(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not _DISPLAY_CODE_PATTERN.fullmatch(value):
        raise ValueError("显示编号只能包含字母、数字、下划线和连字符")
    return value


class ProjectCreate(BaseModel):
    display_code: str | None = None
    name: str = Field(min_length=1, max_length=200)
    customer: str = Field(min_length=1, max_length=200)
    product: str = Field(min_length=1, max_length=200)

    @field_validator("display_code")
    @classmethod
    def validate_display_code(cls, value: str | None) -> str | None:
        return _clean_display_code(value)

    @field_validator("name", "customer", "product")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class SourceOriginal(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    data_base64: str = Field(max_length=11184816)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if (
            value != value.strip()
            or any(c in value for c in "/\\:\x00\r\n")
            or value in {".", ".."}
        ):
            raise ValueError("文件名不可包含路径或控制字符")
        return value


class SourceDocumentCreate(BaseModel):
    import_id: str | None = Field(default=None, min_length=1, max_length=100)
    display_code: str
    doc_type: DocumentType
    version: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)
    mode: Mode = "manual"
    original_file: SourceOriginal | None = None

    @field_validator("display_code")
    @classmethod
    def validate_display_code(cls, value: str) -> str:
        cleaned = _clean_display_code(value)
        if cleaned is None:
            raise ValueError("显示编号不能为空")
        return cleaned

    @field_validator("version")
    @classmethod
    def strip_version(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("文件版本不能为空")
        return value


class RequirementCreate(BaseModel):
    display_code: str | None = None
    category: Category
    parameter_name: str = Field(min_length=1, max_length=200)
    data_type: DataType
    operator: str = Field(min_length=1, max_length=10)
    value_text: str = Field(min_length=1, max_length=500)
    unit: str = Field(default="", max_length=50)
    raw_expression: str = Field(default="", max_length=2000)
    source_document_id: str | None = None
    source_location: str = Field(default="", max_length=200)
    source_excerpt: str = Field(default="", max_length=2000)

    @field_validator("display_code")
    @classmethod
    def validate_display_code(cls, value: str | None) -> str | None:
        return _clean_display_code(value)

    @field_validator("parameter_name", "operator", "value_text")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_document_id")
    @classmethod
    def clean_source_document_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RequirementUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    category: Category | None = None
    parameter_name: str | None = Field(default=None, min_length=1, max_length=200)
    data_type: DataType | None = None
    operator: str | None = Field(default=None, min_length=1, max_length=10)
    value_text: str | None = Field(default=None, min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=50)
    raw_expression: str | None = Field(default=None, max_length=2000)
    source_document_id: str | None = None
    source_location: str | None = Field(default=None, max_length=200)
    source_excerpt: str | None = Field(default=None, max_length=2000)

    @field_validator("parameter_name", "operator", "value_text")
    @classmethod
    def strip_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("unit", "raw_expression", "source_location", "source_excerpt")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("source_document_id")
    @classmethod
    def clean_source_document_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ConfirmationCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    decision: Literal["confirmed", "rejected"]
    comment: str = Field(default="", max_length=2000)

    @field_validator("actor", "role")
    @classmethod
    def strip_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class RecommendRequest(BaseModel):
    top_n: int = Field(default=3, ge=1, le=10)


class VariantAnalysisRequest(BaseModel):
    base_display_code: str = Field(min_length=1, max_length=80)

    @field_validator("base_display_code")
    @classmethod
    def validate_display_code(cls, value: str) -> str:
        cleaned = _clean_display_code(value)
        if cleaned is None:
            raise ValueError("基型显示编号不能为空")
        return cleaned


class CloseIssueRequest(BaseModel):
    expected_status: Literal["open"] = "open"
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    resolution_type: Literal[
        "evidence_added",
        "requirement_clarified",
        "accepted_risk",
        "manual_supplement",
    ]
    resolution_note: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    linked_requirement_id: str | None = None

    @field_validator("actor", "role", "resolution_note", "evidence")
    @classmethod
    def strip_required_identity_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("linked_requirement_id")
    @classmethod
    def clean_linked_requirement_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReopenIssueRequest(BaseModel):
    expected_status: Literal["closed"] = "closed"
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("actor", "role", "reason")
    @classmethod
    def strip_required_identity_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class SimilarProjectsRequest(BaseModel):
    top_n: int = Field(default=3, ge=1, le=10)


class DesignArtifactRequest(BaseModel):
    base_display_code: str = Field(min_length=1, max_length=80)

    @field_validator("base_display_code")
    @classmethod
    def validate_display_code(cls, value: str) -> str:
        cleaned = _clean_display_code(value)
        if cleaned is None:
            raise ValueError("基型显示编号不能为空")
        return cleaned


class ArtifactConfirmationCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    decision: Literal["confirmed", "rejected"]
    comment: str = Field(default="", max_length=2000)

    @field_validator("actor", "role")
    @classmethod
    def strip_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须包含时区")
    return value.astimezone(timezone.utc)


class CoordinationTopicCreate(BaseModel):
    display_code: str | None = None
    name: str = Field(min_length=1, max_length=200)
    expected_participants: list[str] = Field(min_length=1, max_length=50)
    window_start: datetime
    window_end: datetime

    @field_validator("display_code")
    @classmethod
    def validate_display_code(cls, value: str | None) -> str | None:
        return _clean_display_code(value)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("expected_participants")
    @classmethod
    def clean_participants(cls, value: list[str]) -> list[str]:
        cleaned = []
        for participant in value:
            participant = participant.strip()
            if not participant:
                raise ValueError("应参与方不能为空")
            if participant in cleaned:
                raise ValueError("应参与方不能重复")
            cleaned.append(participant)
        return cleaned

    @field_validator("window_start", "window_end")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_window(self):
        if self.window_end <= self.window_start:
            raise ValueError("统计窗口结束时间必须晚于开始时间")
        return self


class CoordinationRecordCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=100)
    record_type: Literal["message", "reopened"]
    sender: str = Field(min_length=1, max_length=200)
    content_summary: str = Field(default="", max_length=2000)
    sent_at: datetime
    reply_to_external_id: str | None = Field(default=None, max_length=100)

    @field_validator("external_id", "sender")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("content_summary")
    @classmethod
    def strip_summary(cls, value: str) -> str:
        return value.strip()

    @field_validator("reply_to_external_id")
    @classmethod
    def clean_reply_to(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("sent_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class CoordinationMetricRequest(BaseModel):
    labor_hours: float | None = Field(default=None, ge=0, le=100000)
    hourly_rate: float | None = Field(default=None, ge=0, le=10000000)


class ConflictCloseRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    resolution_type: Literal["fixed", "evidence_added", "accepted_risk"]
    note: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)

    @field_validator("actor", "role", "note", "evidence")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class FmeaItemUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    function_text: str | None = Field(default=None, min_length=1, max_length=2000)
    failure_mode: str | None = Field(default=None, min_length=1, max_length=2000)
    cause: str | None = Field(default=None, min_length=1, max_length=2000)
    effect: str | None = Field(default=None, min_length=1, max_length=2000)
    control: str | None = Field(default=None, min_length=1, max_length=2000)
    action_text: str | None = Field(default=None, min_length=1, max_length=2000)
    severity: int | None = Field(default=None, ge=1, le=10)
    occurrence: int | None = Field(default=None, ge=1, le=10)
    detection: int | None = Field(default=None, ge=1, le=10)

    @field_validator("actor", "role")
    @classmethod
    def strip_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator(
        "function_text",
        "failure_mode",
        "cause",
        "effect",
        "control",
        "action_text",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class FmeaScoreConfirmation(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=2000)

    @field_validator("actor", "role")
    @classmethod
    def strip_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class TestCaseUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, min_length=1, max_length=2000)
    conditions_text: str | None = Field(default=None, min_length=1, max_length=2000)
    load_conditions_text: str | None = Field(
        default=None, min_length=1, max_length=2000
    )
    acceptance_criteria: str | None = Field(default=None, max_length=2000)
    rebase_requirements: bool = False
    comment: str = Field(default="", max_length=2000)

    @field_validator(
        "actor", "role", "title", "purpose", "conditions_text", "load_conditions_text"
    )
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("acceptance_criteria", "comment")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class TestRunCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    conditions: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    load_basis_numeric: float | None = None
    backup_coefficient: float | None = None
    manual_result: Literal["pass", "fail", "incomplete", "invalid"] | None = None

    @field_validator("actor", "role", "conditions", "evidence")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class DrawingParameterCreate(BaseModel):
    parameter_key: str = Field(min_length=1, max_length=80)
    parameter_name: str = Field(min_length=1, max_length=200)
    expected_value: float
    tolerance: float = Field(ge=0)
    unit: str = Field(default="", max_length=50)
    source_note: str = Field(default="", max_length=500)

    @field_validator("parameter_key", "parameter_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("unit", "source_note")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()


class SampleDeliveryCreate(BaseModel):
    display_code: str | None = None
    supplier: str = Field(min_length=1, max_length=200)
    part_display_code: str = Field(min_length=1, max_length=80)
    drawing_display_code: str = Field(min_length=1, max_length=80)
    drawing_revision: str = Field(min_length=1, max_length=50)
    delivered_at: str = Field(min_length=1, max_length=50)
    quantity: int = Field(default=1, ge=1, le=100000)
    notes: str = Field(default="", max_length=2000)
    drawing_parameters: list[DrawingParameterCreate] = Field(
        min_length=1, max_length=100
    )

    @field_validator("display_code")
    @classmethod
    def validate_display_code(cls, value: str | None) -> str | None:
        return _clean_display_code(value)

    @field_validator(
        "supplier",
        "part_display_code",
        "drawing_display_code",
        "drawing_revision",
        "delivered_at",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str) -> str:
        return value.strip()

    @field_validator("drawing_parameters")
    @classmethod
    def unique_parameter_keys(
        cls, value: list[DrawingParameterCreate]
    ) -> list[DrawingParameterCreate]:
        keys = [item.parameter_key for item in value]
        if len(set(keys)) != len(keys):
            raise ValueError("图纸参数键不能重复")
        return value


class SampleMeasurementCreate(BaseModel):
    parameter_key: str = Field(min_length=1, max_length=80)
    measured_value: float | None = None
    unit: str = Field(default="", max_length=50)

    @field_validator("parameter_key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("unit")
    @classmethod
    def strip_unit(cls, value: str) -> str:
        return value.strip()


class VisualCheckCreate(BaseModel):
    mode: Literal["mock", "manual"]
    result: Literal["pass", "fail", "incomplete", "invalid"]
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class SampleComparisonCreate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    parameters: list[SampleMeasurementCreate] = Field(min_length=1, max_length=100)
    visual_check: VisualCheckCreate
    evidence: str = Field(min_length=1, max_length=2000)

    @field_validator("actor", "role", "evidence")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("parameters")
    @classmethod
    def unique_measurement_keys(
        cls, value: list[SampleMeasurementCreate]
    ) -> list[SampleMeasurementCreate]:
        keys = [item.parameter_key for item in value]
        if len(set(keys)) != len(keys):
            raise ValueError("实测参数键不能重复")
        return value


class ParseRequest(BaseModel):
    display_code_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("display_code_map")
    @classmethod
    def validate_display_code_map(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned_map: dict[str, str] = {}
        for key, code in value.items():
            key = key.strip()
            if not key or len(key) > 100:
                raise ValueError("映射键不能为空且长度不能超过 100")
            cleaned = _clean_display_code(code)
            if cleaned is None:
                raise ValueError("显示编号不能为空")
            cleaned_map[key] = cleaned
        if len(set(cleaned_map.values())) != len(cleaned_map):
            raise ValueError("display_code_map 中不能有重复显示编号")
        return cleaned_map


class CoordinationRiskAcceptanceCreate(BaseModel):
    metric_run_id: str = Field(min_length=1, max_length=100)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("metric_run_id", "actor", "role", "note")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class MaterialPackageCreate(BaseModel):
    include_originals: bool = False
    actor: str = Field(default="演示用户（未认证）", min_length=1, max_length=100)

    @field_validator("actor")
    @classmethod
    def strip_actor(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class MaterialPackageApprovalCreate(BaseModel):
    expected_snapshot_hash: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("actor", "role", "comment")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value
