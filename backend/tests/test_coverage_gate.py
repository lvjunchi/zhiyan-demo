import pytest
from scripts.check_core_coverage import evaluate_core


def report(branches=90, covered=80):
    return {
        "files": {
            "backend/app/domain/example.py": {
                "summary": {
                    "num_statements": 100,
                    "covered_lines": covered,
                    "num_branches": 100,
                    "covered_branches": branches,
                }
            },
            "backend/app/services.py": {
                "summary": {
                    "num_statements": 10000,
                    "covered_lines": 10000,
                    "num_branches": 10000,
                    "covered_branches": 10000,
                }
            },
        }
    }


def test_a_high_orchestration_score_cannot_hide_a_core_branch_failure():
    assert evaluate_core(report(branches=89))["passed"] is False


def test_core_statement_and_branch_boundaries_are_both_required():
    assert evaluate_core(report(branches=90, covered=80))["passed"] is True
    assert evaluate_core(report(branches=90, covered=79))["passed"] is False


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"files": {}},
        report(branches=-1),
        report(branches=101),
        report(branches=True),
    ],
)
def test_missing_or_invalid_counts_cannot_pass(value):
    with pytest.raises(ValueError):
        evaluate_core(value)
