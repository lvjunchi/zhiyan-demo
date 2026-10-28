"""Frozen progress comparison rules: same milestone; 20/40 percentage point thresholds."""

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence


@dataclass(frozen=True)
class ProgressRecord:
    participant: str
    milestone: str
    planned_percent: float
    actual_percent: float
    artifact_version: str
    evidence: str
    reported_at: str


def evaluate_progress(
    rows: Sequence[ProgressRecord], participants: tuple[str, ...]
) -> dict[str, object]:
    alerts = []
    gaps = []
    milestones = sorted({row.milestone for row in rows})
    for milestone in milestones:
        group = [row for row in rows if row.milestone == milestone]
        missing = sorted(set(participants) - {row.participant for row in group})
        if missing:
            gaps.append(f"{milestone} 缺少进度记录：{'、'.join(missing)}")
        for row in group:
            lag = row.planned_percent - row.actual_percent
            if lag >= 20:
                alerts.append(
                    {
                        "kind": "schedule_lag",
                        "level": "high" if lag >= 40 else "medium",
                        "milestone": milestone,
                        "participants": [row.participant],
                        "reason": f"{row.participant}计划{row.planned_percent:g}%，实际{row.actual_percent:g}%，落后{lag:g}个百分点",
                        "evidence": [row.evidence],
                        "reported_at": [row.reported_at],
                    }
                )
        for left, right in combinations(group, 2):
            gap = abs(left.actual_percent - right.actual_percent)
            if gap >= 20:
                alerts.append(
                    {
                        "kind": "progress_gap",
                        "level": "high" if gap >= 40 else "medium",
                        "milestone": milestone,
                        "participants": [left.participant, right.participant],
                        "reason": f"{left.participant} {left.actual_percent:g}% / {right.participant} {right.actual_percent:g}%，进度相差{gap:g}个百分点",
                        "evidence": [left.evidence, right.evidence],
                        "reported_at": [left.reported_at, right.reported_at],
                    }
                )
            if left.artifact_version != right.artifact_version:
                alerts.append(
                    {
                        "kind": "delivery_version",
                        "level": "medium",
                        "milestone": milestone,
                        "participants": [left.participant, right.participant],
                        "reason": f"交付版本不一致：{left.participant} {left.artifact_version} / {right.participant} {right.artifact_version}",
                        "evidence": [left.evidence, right.evidence],
                        "reported_at": [left.reported_at, right.reported_at],
                    }
                )
    levels = [item["level"] for item in alerts]
    level = (
        "high"
        if "high" in levels
        else (
            "medium"
            if "medium" in levels
            else "insufficient" if gaps or not rows else "low"
        )
    )
    return {
        "rule_label": "PROGRESS-DEMO-V1",
        "risk_level": level,
        "alerts": alerts,
        "data_gaps": gaps,
        "thresholds": "同里程碑进度差/计划落后≥20个百分点为中、≥40为高；交付版本不同为中；缺记录为数据不足。",
    }
