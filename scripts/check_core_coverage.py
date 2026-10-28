"""Check statement and branch coverage separately for backend/app/domain only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def evaluate_core(report: object) -> dict[str, object]:
    if not isinstance(report, dict) or not isinstance(report.get("files"), dict):
        raise ValueError("覆盖报告缺少 files 记录")
    statements = covered_lines = branches = covered_branches = 0
    included: list[str] = []
    for name, record in report["files"].items():
        normalized = str(name).replace("\\", "/")
        if not normalized.startswith(("backend/app/domain/", "app/domain/")):
            continue
        if not isinstance(record, dict) or not isinstance(record.get("summary"), dict):
            raise ValueError(f"领域覆盖记录结构无效：{name}")
        summary = record["summary"]
        counts = [
            summary.get(key)
            for key in (
                "num_statements",
                "covered_lines",
                "num_branches",
                "covered_branches",
            )
        ]
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError(f"领域覆盖计数无效：{name}")
        total, lines, branch_total, branch_covered = counts
        if lines > total or branch_covered > branch_total:
            raise ValueError(f"领域覆盖计数超出分母：{name}")
        statements += total
        covered_lines += lines
        branches += branch_total
        covered_branches += branch_covered
        included.append(normalized)
    if not statements or not branches:
        raise ValueError("未找到有效的核心领域语句和分支覆盖，不能判为通过")
    return {
        "scope": "backend/app/domain/**",
        "files": included,
        "statement_percent": covered_lines / statements * 100,
        "branch_percent": covered_branches / branches * 100,
        "covered_statements": covered_lines,
        "statements": statements,
        "covered_branches": covered_branches,
        "branches": branches,
        "passed": covered_lines * 100 >= 80 * statements
        and covered_branches * 100 >= 90 * branches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_core(json.loads(args.report.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"核心覆盖检查失败：{exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
