from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pytest

from paycheck_guardian.evaluation import (
    PredictedOpportunity,
    input_fingerprint_for_baseline,
    input_fingerprint_for_solution,
    load_cases,
    match_predictions,
    evaluate_cases,
    write_artifacts,
)
from paycheck_guardian.models import Confidence, GroundTruthOpportunity, RecommendationKind


REQUIRED_ARTIFACTS = {
    "baseline_predictions.json",
    "normalization_only_predictions.json",
    "unverified_agent_predictions.json",
    "removed_unsafe_recurrence_predictions.json",
    "final_predictions.json",
    "final_trajectories.json",
    "per_case_results.json",
    "metrics.json",
    "comparison.md",
}


def truth() -> GroundTruthOpportunity:
    return GroundTruthOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Netflix",
        required_evidence_ids=["netflix-1", "netflix-2"],
        monthly_savings_usd="15.49",
    )


def correct_prediction() -> PredictedOpportunity:
    return PredictedOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Netflix",
        evidence_ids=["netflix-1", "netflix-2"],
        monthly_savings_usd="15.49",
        confidence=Confidence.HIGH,
        caveat="Estimate based on recurring charges.",
    )


def false_positive() -> PredictedOpportunity:
    return PredictedOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Gym",
        evidence_ids=["gym-1", "gym-2"],
        monthly_savings_usd="20.00",
        confidence=Confidence.LOW,
    )


def test_f1_penalizes_false_positive() -> None:
    """Counting an unmatched prediction as correct would hide unsafe recommendations."""
    score = match_predictions([correct_prediction(), false_positive()], [truth()])

    assert score.precision == Decimal("0.5000")
    assert score.recall == Decimal("1.0000")
    assert score.f1 == Decimal("0.6667")


def test_dataset_has_twelve_cases_and_challenge() -> None:
    """A missing scenario would invalidate the documented evaluation coverage."""
    cases = load_cases(Path("data/evaluation/cases.json"))

    assert len(cases) == 12
    assert sum(case.is_challenge for case in cases) == 1


def test_baseline_and_solution_receive_identical_original_rows() -> None:
    """Changing inputs per mode would make a measured comparison meaningless."""
    cases = load_cases(Path("data/evaluation/cases.json"))

    assert input_fingerprint_for_baseline(cases) == input_fingerprint_for_solution(cases)


def test_matching_scores_evidence_and_savings_separately() -> None:
    """A correct target must not receive full evidence or savings credit by coincidence."""
    prediction = correct_prediction().model_copy(
        update={"evidence_ids": ["netflix-1"], "monthly_savings_usd": Decimal("14.00")}
    )

    score = match_predictions([prediction], [truth()])

    assert score.true_positives == 1
    assert score.evidence_coverage == Decimal("0.5000")
    assert score.mean_savings_error_usd == Decimal("1.4900")


def test_baseline_and_solution_entry_points_write_only_to_requested_directory(
    tmp_path: Path,
) -> None:
    """Ignoring the output option would dirty retained artifacts during routine tests."""
    root = Path(__file__).resolve().parents[1]

    for script in ("scripts/run_baseline.py", "scripts/run_solution.py"):
        output_dir = tmp_path / Path(script).stem
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--mode",
                "offline",
                "--output-dir",
                str(output_dir),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert {path.name for path in output_dir.iterdir()} == REQUIRED_ARTIFACTS


@pytest.mark.parametrize(
    ("script", "expected_mode", "rent_expected"),
    [
        ("scripts/run_baseline.py", "baseline", True),
        ("scripts/run_solution.py", "final", False),
    ],
)
def test_case_entry_points_emit_only_the_requested_case_without_rewriting_artifacts(
    script: str,
    expected_mode: str,
    rent_expected: bool,
) -> None:
    """A case smoke run must expose its mode-specific result without replacing retained evidence."""
    root = Path(__file__).resolve().parents[1]
    metrics_path = root / "artifacts" / "evaluation" / "metrics.json"
    retained_metrics = metrics_path.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            script,
            "--case",
            "challenge_alias_price_essential",
            "--mode",
            "offline",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["case_id"] == "challenge_alias_price_essential"
    assert payload["mode"] == expected_mode
    targets = {item["target"].casefold() for item in payload["predictions"]}
    assert ("rent" in targets) is rent_expected
    assert metrics_path.read_bytes() == retained_metrics


def test_retained_artifacts_include_reproducibility_metadata(tmp_path: Path) -> None:
    """Dropping mode timings or input fingerprints would prevent a later audit from being replayed."""
    cases = load_cases(Path("data/evaluation/cases.json"))
    write_artifacts(cases, evaluate_cases(cases), tmp_path)

    assert {path.name for path in tmp_path.iterdir()} == REQUIRED_ARTIFACTS
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["case_count"] == 12
    for name in REQUIRED_ARTIFACTS - {"comparison.md"}:
        artifact = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert artifact["mode"]
        assert artifact["execution_mode"] == "offline"
        assert artifact["package_version"] == "0.1.0"
        assert artifact["python_version"]
        assert artifact["case_fingerprints"]
        assert artifact["model_cost_usd"] == "0.00"
        assert artifact.get("elapsed_ms") is not None or artifact.get("elapsed_ms_by_mode")

    trajectories = json.loads((tmp_path / "final_trajectories.json").read_text(encoding="utf-8"))
    challenge_events = trajectories["trajectories"]["challenge_alias_price_essential"]
    rent_rejection = next(
        event
        for event in challenge_events
        if event["tool_name"] == "verify_recommendation"
        and event["event_type"] == "tool_result"
        and event["tool_input"]["recommendation"]["recommendation_id"] == "subscription-rent"
    )
    assert rent_rejection["tool_result"]["accepted"] is False
    assert any("essential" in reason for reason in rent_rejection["tool_result"]["reasons"])
    serialized_trajectories = json.dumps(trajectories).lower()
    assert not any(secret_key in serialized_trajectories for secret_key in ("api_key", "token", "authorization", "secret"))


def test_normalization_only_changes_only_the_merchant_grouping() -> None:
    """Adding cadence conversion or drift rules would make this ablation more than normalization."""
    cases = load_cases(Path("data/evaluation/cases.json"))
    summary = evaluate_cases(cases)

    aliases = summary.modes["normalization_only"].predictions["merchant_aliases"]
    annual = summary.modes["normalization_only"].predictions["annual_subscription"]

    assert [(item.target, item.monthly_savings_usd) for item in aliases] == [
        ("Netflix", Decimal("15.49"))
    ]
    assert annual == []


def test_unverified_predictions_retain_the_essential_draft_rejected_by_final() -> None:
    """Filtering essential candidates before verification would hide the verifier's safety effect."""
    cases = load_cases(Path("data/evaluation/cases.json"))
    summary = evaluate_cases(cases)

    unverified = summary.modes["unverified_agent"].predictions["essential_rent"]
    final = summary.modes["final"].predictions["essential_rent"]

    assert [(item.kind, item.target) for item in unverified] == [
        (RecommendationKind.SUBSCRIPTION, "Rent")
    ]
    assert final == []


def test_matching_rejects_required_confidence_or_caveat_mismatch() -> None:
    """A target match cannot mask an unsupported high-confidence, caveat-free claim."""
    ambiguous_truth = GroundTruthOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Hulu",
        required_evidence_ids=["h1", "h2"],
        monthly_savings_usd="7.99",
        expected_confidence=Confidence.LOW,
        caveat_required=True,
    )
    prediction = PredictedOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Hulu",
        evidence_ids=["h1", "h2"],
        monthly_savings_usd="7.99",
        confidence=Confidence.MEDIUM,
    )

    score = match_predictions([prediction], [ambiguous_truth])

    assert score.true_positives == 0
    assert score.false_positives == 1
    assert score.false_negatives == 1
