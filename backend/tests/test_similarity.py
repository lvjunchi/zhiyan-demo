from app.domain.similarity import (
    HistoryProject,
    ProjectProfile,
    find_similar_projects,
)


def _history(
    display_code: str,
    *,
    transmission_type: str = "AMT",
    gear_count: int = 12,
    rated_input_torque: float = 2700,
    has_pto: bool = True,
    assembly_weight_kg: float = 285,
    top_gear_type: str = "direct",
) -> HistoryProject:
    return HistoryProject(
        id=f"id-{display_code}",
        display_code=display_code,
        name=f"项目 {display_code}",
        customer="陕汽集团",
        transmission_type=transmission_type,
        gear_count=gear_count,
        rated_input_torque=rated_input_torque,
        has_pto=has_pto,
        assembly_weight_kg=assembly_weight_kg,
        top_gear_type=top_gear_type,
        notes="合成历史项目",
        source="合成历史项目库 V1（示意数据）",
    )


def _profile(**overrides) -> ProjectProfile:
    values = {
        "transmission_type": "AMT",
        "gear_count": 12,
        "rated_input_torque": 2600.0,
        "has_pto": True,
        "weight_limit_kg": 300.0,
        "requirement_versions": (),
    }
    values.update(overrides)
    return ProjectProfile(**values)


def test_exact_history_profile_scores_highest():
    history = [
        _history("HX-03", transmission_type="MT"),
        _history("HX-01"),
        _history("HX-02", rated_input_torque=2500),
    ]

    result = find_similar_projects(history, _profile(), top_n=3)

    assert [item.display_code for item in result.matches] == [
        "HX-01",
        "HX-02",
        "HX-03",
    ]
    assert result.matches[0].score == 100.0
    assert not result.matches[0].differences
    assert len(result.matches[0].criteria) == 5


def test_missing_project_criterion_is_excluded_not_scored_zero():
    profile = _profile(
        rated_input_torque=None,
        has_pto=None,
        weight_limit_kg=None,
    )

    result = find_similar_projects(
        [_history("HX-01"), _history("HX-02", gear_count=10)],
        profile,
        top_n=2,
    )

    assert list(result.missing_criteria) == [
        "ratedInputTorque",
        "pto",
        "weightLimit",
    ]
    assert result.matches[0].score == 100.0
    assert result.matches[0].missing_criteria == result.missing_criteria
    applicable = [
        criterion
        for criterion in result.matches[0].criteria
        if criterion.score is not None
    ]
    assert len(applicable) == 2
    assert all(criterion.score == 1.0 for criterion in applicable)


def test_transmission_mismatch_reduces_score_and_is_explained():
    result = find_similar_projects(
        [_history("HX-MT", transmission_type="MT")],
        _profile(),
    )

    match = result.matches[0]
    transmission = next(
        criterion
        for criterion in match.criteria
        if criterion.criterion == "transmissionType"
    )
    assert transmission.score == 0.0
    assert transmission.matched is False
    assert match.score == 75.0
    assert any("换挡方式" in difference for difference in match.differences)


def test_weight_slightly_above_limit_gets_partial_credit():
    result = find_similar_projects(
        [_history("HX-HEAVY", assembly_weight_kg=310)],
        _profile(),
    )

    weight = next(
        criterion
        for criterion in result.matches[0].criteria
        if criterion.criterion == "weightLimit"
    )
    assert weight.score == 0.5
    assert weight.matched is False
    assert "5%" in weight.reason


def test_candidate_shortage_is_reported():
    result = find_similar_projects(
        [_history("HX-01"), _history("HX-02")],
        _profile(),
        top_n=3,
    )

    assert result.candidate_count == 2
    assert result.candidate_shortage is True
    assert len(result.matches) == 2


def test_no_available_criteria_returns_zero_without_inventing_match():
    profile = _profile(
        transmission_type=None,
        gear_count=None,
        rated_input_torque=None,
        has_pto=None,
        weight_limit_kg=None,
    )

    result = find_similar_projects([_history("HX-01")], profile)

    assert result.applicable_criteria_count == 0
    assert result.matches[0].score == 0.0
    assert not result.matches[0].matched_points
    assert len(result.matches[0].missing_criteria) == 5
