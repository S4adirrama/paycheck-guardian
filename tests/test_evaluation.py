from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

from paycheck_guardian.evaluation import (
    PredictedOpportunity,
    input_fingerprint_for_baseline,
    input_fingerprint_for_solution,
    load_cases,
    match_predictions,
    evaluate_cases,
    write_artifacts,
)
from paycheck_guardian.models import GroundTruthOpportunity, RecommendationKind


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
        caveat="Estimate based on recurring charges.",
    )


def false_positive() -> PredictedOpportunity:
    return PredictedOpportunity(
        kind=RecommendationKind.SUBSCRIPTION,
        target="Gym",
        evidence_ids=["gym-1", "gym-2"],
        monthly_savings_usd="20.00",
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


def test_baseline_and_solution_entry_points_run_directly() -> None:
    """Importing helper scripts as a package would break their documented direct execution."""
    root = Path(__file__).resolve().parents[1]

    for script in ("scripts/run_baseline.py", "scripts/run_solution.py"):
        result = subprocess.run(
            [sys.executable, script, "--mode", "offline"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_retained_artifacts_include_reproducibility_metadata(tmp_path: Path) -> None:
    """Dropping mode timings or input fingerprints would prevent a later audit from being replayed."""
    cases = load_cases(Path("data/evaluation/cases.json"))
    write_artifacts(cases, evaluate_cases(cases), tmp_path)

    required = {
        "baseline_predictions.json",
        "normalization_only_predictions.json",
        "unverified_agent_predictions.json",
        "removed_unsafe_recurrence_predictions.json",
        "final_predictions.json",
        "per_case_results.json",
        "metrics.json",
        "comparison.md",
    }
    assert {path.name for path in tmp_path.iterdir()} == required
    for name in required - {"comparison.md"}:
        artifact = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert artifact["mode"]
        assert artifact["execution_mode"] == "offline"
        assert artifact["package_version"] == "0.1.0"
        assert artifact["python_version"]
        assert artifact["case_fingerprints"]
        assert artifact["model_cost_usd"] == "0.00"
        assert artifact.get("elapsed_ms") is not None or artifact.get("elapsed_ms_by_mode")
