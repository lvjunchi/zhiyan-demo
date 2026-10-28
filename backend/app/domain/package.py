from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

READY = "ready"
BLOCKED = "blocked"
PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class RequirementGateItem:
    requirement_id: str
    display_code: str
    revision: int
    review_status: str
    validity: str


@dataclass(frozen=True)
class ValidationGateItem:
    key: str
    label: str
    requirement_id: str | None
    display_code: str | None
    requirement_revision: int | None
    covered: bool
    execution: str


@dataclass(frozen=True)
class ArtifactGateItem:
    key: str
    label: str
    object_type: str
    object_id: str | None = None
    display_code: str | None = None
    revision: int | None = None
    status: str | None = None
    needs_reconfirmation: bool = False
    exists: bool = True
    failure_messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictGateItem:
    conflict_id: str
    display_code: str
    severity: str
    status: str


@dataclass(frozen=True)
class ConsistencyGateItem:
    check_id: str | None
    display_code: str | None
    status: str | None
    validity: str | None
    blocking_conflicts: tuple[ConflictGateItem, ...]
    open_high_count: int = 0


@dataclass(frozen=True)
class IssueGateItem:
    issue_id: str
    issue_type: str
    severity: str
    status: str
    message: str
    display_code: str = ""


@dataclass(frozen=True)
class CoordinationRiskGateItem:
    topic_id: str
    display_code: str
    metric_run_id: str | None
    risk_level: str | None
    accepted: bool
    validity: str = "current"


@dataclass(frozen=True)
class PackageGateInputs:
    requirements: tuple[RequirementGateItem, ...]
    validation: tuple[ValidationGateItem, ...]
    artifacts: tuple[ArtifactGateItem, ...]
    sample_artifacts: tuple[ArtifactGateItem, ...]
    consistency: ConsistencyGateItem
    issues: tuple[IssueGateItem, ...]
    coordination: tuple[CoordinationRiskGateItem, ...]
    expected_denominator: int = 5


@dataclass
class PackageGateEvaluation:
    checks: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": READY if self.ready else BLOCKED,
            "ready": self.ready,
            "checks": self.checks,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "summary": {
                "check_count": len(self.checks),
                "passed_check_count": sum(
                    1 for check in self.checks if check["status"] == PASS
                ),
                "not_applicable_check_count": sum(
                    1 for check in self.checks if check["status"] == NOT_APPLICABLE
                ),
                "blocker_count": len(self.blockers),
                "warning_count": len(self.warnings),
            },
        }


def _entry(
    code: str,
    message: str,
    *,
    check: str,
    object_type: str | None = None,
    object_id: str | None = None,
    revision: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "code": code,
        "message": message,
        "check": check,
    }
    if object_type is not None:
        value["object_type"] = object_type
    if object_id is not None:
        value["object_id"] = object_id
    if revision is not None:
        value["revision"] = revision
    if details:
        value["details"] = details
    return value


def _check(
    key: str,
    label: str,
    failures: list[dict[str, Any]],
    *,
    status_if_empty: str = PASS,
    summary: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": FAIL if failures else status_if_empty,
        "summary": summary,
        "failures": failures,
    }


_ARTIFACT_LABELS = {
    "test_plan": ("试验方案", "TEST_PLAN_MISSING", "test_plan_confirmed"),
    "design_review": (
        "设计评审清单",
        "DESIGN_REVIEW_MISSING",
        "design_review_confirmed",
    ),
    "dfmea": ("DFMEA", "DFMEA_MISSING", "dfmea_confirmed"),
}


def evaluate_package_gate(
    inputs: PackageGateInputs,
) -> PackageGateEvaluation:
    evaluation = PackageGateEvaluation()

    requirement_failures: list[dict[str, Any]] = []
    if not inputs.requirements:
        requirement_failures.append(
            _entry(
                "REQUIRED_REQUIREMENT_MISSING",
                "未找到验证范围内的必需需求",
                check="requirements_confirmed",
            )
        )
    for requirement in inputs.requirements:
        if requirement.validity != "current":
            requirement_failures.append(
                _entry(
                    "REQUIREMENT_STALE",
                    f"需求 {requirement.display_code} 不是当前有效版本",
                    check="requirements_confirmed",
                    object_type="requirement",
                    object_id=requirement.requirement_id,
                    revision=requirement.revision,
                    details={"validity": requirement.validity},
                )
            )
        if requirement.review_status != "confirmed":
            requirement_failures.append(
                _entry(
                    "REQUIREMENT_NOT_CONFIRMED",
                    f"需求 {requirement.display_code} 尚未确认",
                    check="requirements_confirmed",
                    object_type="requirement",
                    object_id=requirement.requirement_id,
                    revision=requirement.revision,
                    details={"review_status": requirement.review_status},
                )
            )
    evaluation.checks.append(
        _check(
            "requirements_confirmed",
            "验证范围需求已确认且有效",
            requirement_failures,
            summary=f"检查 {len(inputs.requirements)} 条需求",
        )
    )
    evaluation.blockers.extend(requirement_failures)

    artifact_by_key = {item.key: item for item in inputs.artifacts}
    for artifact_key in ("test_plan", "design_review", "dfmea"):
        label, missing_code, check_key = _ARTIFACT_LABELS[artifact_key]
        artifact = artifact_by_key.get(artifact_key)
        failures: list[dict[str, Any]] = []
        if artifact is None or not artifact.exists:
            failures.append(
                _entry(
                    missing_code,
                    f"{label}尚未生成",
                    check=check_key,
                    object_type=(
                        artifact.object_type if artifact is not None else artifact_key
                    ),
                    object_id=artifact.object_id if artifact is not None else None,
                )
            )
        else:
            if artifact.status != "confirmed":
                failures.append(
                    _entry(
                        "ARTIFACT_NOT_CONFIRMED",
                        f"{label} {artifact.display_code or ''} 尚未确认",
                        check=check_key,
                        object_type=artifact.object_type,
                        object_id=artifact.object_id,
                        revision=artifact.revision,
                        details={"status": artifact.status},
                    )
                )
            if artifact.needs_reconfirmation:
                failures.append(
                    _entry(
                        "ARTIFACT_NEEDS_RECONFIRMATION",
                        f"{label}已产生新版本，需重新确认",
                        check=check_key,
                        object_type=artifact.object_type,
                        object_id=artifact.object_id,
                        revision=artifact.revision,
                    )
                )
        evaluation.checks.append(_check(check_key, f"{label}已确认", failures))
        evaluation.blockers.extend(failures)

    engineering = tuple(
        item for item in inputs.artifacts if item.key not in _ARTIFACT_LABELS
    )
    if engineering:
        failures = []
        for item in engineering:
            if (
                not item.exists
                or item.status != "confirmed"
                or item.needs_reconfirmation
            ):
                failures.append(
                    _entry(
                        "ENGINEERING_DECISION_NOT_READY",
                        f"{item.label} 缺失、待审核或需要重新复核",
                        check="engineering_decisions_confirmed",
                        object_type=item.object_type,
                        object_id=item.object_id,
                        revision=item.revision,
                        details={
                            "exists": item.exists,
                            "review_status": item.status,
                            "needs_reconfirmation": item.needs_reconfirmation,
                        },
                    )
                )
        evaluation.checks.append(
            _check(
                "engineering_decisions_confirmed",
                "变型与复用决策已确认且有效",
                failures,
            )
        )
        evaluation.blockers.extend(failures)

    coverage_failures: list[dict[str, Any]] = []
    if len(inputs.validation) != inputs.expected_denominator:
        coverage_failures.append(
            _entry(
                "COVERAGE_DENOMINATOR_INVALID",
                (
                    "验证范围数量与受控分母不一致："
                    f"{len(inputs.validation)} / {inputs.expected_denominator}"
                ),
                check="coverage_complete",
                details={
                    "actual": len(inputs.validation),
                    "expected": inputs.expected_denominator,
                },
            )
        )
    for item in inputs.validation:
        if item.requirement_id is None:
            coverage_failures.append(
                _entry(
                    "VALIDATION_REQUIREMENT_MISSING",
                    f"验证范围 {item.key} 缺少对应需求",
                    check="coverage_complete",
                    details={"key": item.key, "label": item.label},
                )
            )
        if not item.covered:
            coverage_failures.append(
                _entry(
                    "COVERAGE_INCOMPLETE",
                    f"验证范围 {item.display_code or item.key} 尚无有效用例",
                    check="coverage_complete",
                    object_type=(
                        "requirement" if item.requirement_id else "validation_scope"
                    ),
                    object_id=item.requirement_id,
                    revision=item.requirement_revision,
                    details={
                        "key": item.key,
                        "label": item.label,
                        "execution": item.execution,
                    },
                )
            )
    covered_count = sum(1 for item in inputs.validation if item.covered)
    evaluation.checks.append(
        _check(
            "coverage_complete",
            "固定验证范围 5/5 覆盖",
            coverage_failures,
            summary=(f"有效覆盖 {covered_count} / {inputs.expected_denominator}"),
        )
    )
    evaluation.blockers.extend(coverage_failures)

    verification_failures: list[dict[str, Any]] = []
    for item in inputs.validation:
        if item.execution != "pass":
            verification_failures.append(
                _entry(
                    "VERIFICATION_NOT_PASSED",
                    (
                        f"验证范围 {item.display_code or item.key} "
                        f"最新执行结论不是通过：{item.execution}"
                    ),
                    check="verification_passed",
                    object_type=(
                        "requirement" if item.requirement_id else "validation_scope"
                    ),
                    object_id=item.requirement_id,
                    revision=item.requirement_revision,
                    details={
                        "key": item.key,
                        "execution": item.execution,
                    },
                )
            )
    evaluation.checks.append(
        _check(
            "verification_passed",
            "全部必需验证已通过",
            verification_failures,
        )
    )
    evaluation.blockers.extend(verification_failures)

    sample_failures: list[dict[str, Any]] = []
    for artifact in inputs.sample_artifacts:
        if not artifact.exists:
            sample_failures.append(
                _entry(
                    "SAMPLE_COMPARISON_MISSING",
                    f"样件交付 {artifact.display_code or ''} 尚无比对记录",
                    check="sample_comparison_confirmed",
                    object_type=artifact.object_type,
                    object_id=artifact.object_id,
                )
            )
            continue
        if artifact.status != "confirmed":
            sample_failures.append(
                _entry(
                    "SAMPLE_COMPARISON_NOT_CONFIRMED",
                    f"样件比对 {artifact.display_code or ''} 尚未确认",
                    check="sample_comparison_confirmed",
                    object_type=artifact.object_type,
                    object_id=artifact.object_id,
                    revision=artifact.revision,
                    details={"status": artifact.status},
                )
            )
        if artifact.needs_reconfirmation:
            sample_failures.append(
                _entry(
                    "SAMPLE_COMPARISON_NOT_CONFIRMED",
                    f"样件比对 {artifact.display_code or ''} 需要重新确认",
                    check="sample_comparison_confirmed",
                    object_type=artifact.object_type,
                    object_id=artifact.object_id,
                    revision=artifact.revision,
                )
            )
        for message in artifact.failure_messages:
            sample_failures.append(
                _entry(
                    "SAMPLE_COMPARISON_INVALID",
                    message,
                    check="sample_comparison_confirmed",
                    object_type=artifact.object_type,
                    object_id=artifact.object_id,
                    revision=artifact.revision,
                )
            )
    evaluation.checks.append(
        _check(
            "sample_comparison_confirmed",
            "适用样件比对已确认",
            sample_failures,
            status_if_empty=(NOT_APPLICABLE if not inputs.sample_artifacts else PASS),
            summary=(
                "未登记样件交付，按不适用处理"
                if not inputs.sample_artifacts
                else f"检查 {len(inputs.sample_artifacts)} 条样件比对"
            ),
        )
    )
    evaluation.blockers.extend(sample_failures)
    if not inputs.sample_artifacts:
        evaluation.warnings.append(
            _entry(
                "SAMPLE_NOT_PROVIDED",
                "项目未登记样件交付，材料包不含 O12 样件比对记录",
                check="sample_comparison_confirmed",
            )
        )

    consistency = inputs.consistency
    consistency_failures: list[dict[str, Any]] = []
    if consistency.check_id is None:
        consistency_failures.append(
            _entry(
                "CONSISTENCY_CHECK_MISSING",
                "项目尚无一致性检查报告",
                check="consistency_cleared",
            )
        )
    else:
        if consistency.validity != "current":
            consistency_failures.append(
                _entry(
                    "CONSISTENCY_CHECK_STALE",
                    "最新一致性检查已被新检查取代",
                    check="consistency_cleared",
                    object_type="consistency_check",
                    object_id=consistency.check_id,
                    details={"validity": consistency.validity},
                )
            )
        if consistency.status != "confirmed":
            consistency_failures.append(
                _entry(
                    "CONSISTENCY_CHECK_NOT_CONFIRMED",
                    "最新一致性检查尚未确认",
                    check="consistency_cleared",
                    object_type="consistency_check",
                    object_id=consistency.check_id,
                    details={"status": consistency.status},
                )
            )
    for conflict in consistency.blocking_conflicts:
        if conflict.status != "open":
            continue
        consistency_failures.append(
            _entry(
                "BLOCKING_CONFLICT_OPEN",
                f"阻断冲突 {conflict.display_code} 尚未关闭",
                check="consistency_cleared",
                object_type="conflict",
                object_id=conflict.conflict_id,
                details={"severity": conflict.severity},
            )
        )
    evaluation.checks.append(
        _check(
            "consistency_cleared",
            "一致性检查已确认且无未关闭阻断冲突",
            consistency_failures,
        )
    )
    evaluation.blockers.extend(consistency_failures)
    if consistency.open_high_count:
        evaluation.warnings.append(
            _entry(
                "OPEN_HIGH_CONFLICT",
                f"仍有 {consistency.open_high_count} 条高严重度非阻断冲突开放",
                check="consistency_cleared",
            )
        )

    issue_failures: list[dict[str, Any]] = []
    for issue in inputs.issues:
        if issue.status != "open":
            continue
        if issue.severity in ("high", "blocking"):
            issue_failures.append(
                _entry(
                    "HIGH_ISSUE_OPEN",
                    issue.message,
                    check="issues_cleared",
                    object_type="issue",
                    object_id=issue.issue_id,
                    details={
                        "issue_type": issue.issue_type,
                        "severity": issue.severity,
                    },
                )
            )
        else:
            evaluation.warnings.append(
                _entry(
                    "OPEN_ISSUE",
                    issue.message,
                    check="issues_cleared",
                    object_type="issue",
                    object_id=issue.issue_id,
                    details={"severity": issue.severity},
                )
            )
    evaluation.checks.append(
        _check(
            "issues_cleared",
            "无未关闭高严重度或阻断问题",
            issue_failures,
        )
    )
    evaluation.blockers.extend(issue_failures)

    coordination_failures: list[dict[str, Any]] = []
    for topic in inputs.coordination:
        if topic.validity != "current":
            coordination_failures.append(
                _entry(
                    "COORDINATION_METRICS_STALE",
                    f"协同议题 {topic.display_code} 记录已变化，请重算指标",
                    check="coordination_risk_accepted",
                    object_type="coordination_topic",
                    object_id=topic.topic_id,
                )
            )
            continue
        if topic.metric_run_id is None:
            coordination_failures.append(
                _entry(
                    "COORDINATION_METRICS_MISSING",
                    f"协同议题 {topic.display_code} 尚无指标计算结果",
                    check="coordination_risk_accepted",
                    object_type="coordination_topic",
                    object_id=topic.topic_id,
                )
            )
            continue
        if topic.risk_level in ("high", "insufficient") and not topic.accepted:
            coordination_failures.append(
                _entry(
                    "COORDINATION_RISK_UNACCEPTED",
                    (
                        f"协同议题 {topic.display_code} 风险为 "
                        f"{topic.risk_level}，未记录明确接受理由"
                    ),
                    check="coordination_risk_accepted",
                    object_type="coordination_metric_run",
                    object_id=topic.metric_run_id,
                    details={"risk_level": topic.risk_level},
                )
            )
    evaluation.checks.append(
        _check(
            "coordination_risk_accepted",
            "协同高风险或数据不足已明确接受",
            coordination_failures,
            status_if_empty=(NOT_APPLICABLE if not inputs.coordination else PASS),
            summary=(
                "未登记协同议题，按不适用处理"
                if not inputs.coordination
                else f"检查 {len(inputs.coordination)} 个协同议题"
            ),
        )
    )
    evaluation.blockers.extend(coordination_failures)
    if not inputs.coordination:
        evaluation.warnings.append(
            _entry(
                "COORDINATION_NOT_PROVIDED",
                "项目未登记协同议题，材料包不含协同记录",
                check="coordination_risk_accepted",
            )
        )

    evaluation.ready = not evaluation.blockers
    return evaluation
