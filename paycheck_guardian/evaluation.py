"""Reproducible, offline evaluation for evidence-backed spending recommendations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys
import time

from pydantic import Field

from .agent import draft_offline_recommendations, run_offline_agent
from .models import (
    Confidence,
    DomainModel,
    AgentRun,
    EvaluationCase,
    GroundTruthOpportunity,
    RecommendationKind,
    SourceType,
    Transaction,
    money,
)
from .normalize import load_aliases, normalize_merchant


_FOUR_PLACES = Decimal("0.0001")
_ANALYSIS_DATE = date(2026, 8, 1)
_NEXT_PAYCHECK = date(2026, 8, 15)
_ALIASES = load_aliases(Path(__file__).resolve().parents[1] / "data" / "merchant_aliases.json")


class PredictedOpportunity(DomainModel):
    """A mode-independent projection of a recommendation used for scoring."""

    kind: RecommendationKind
    target: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    monthly_savings_usd: Decimal
    confidence: Confidence
    caveat: str | None = None


@dataclass(frozen=True)
class CaseScore:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: Decimal
    recall: Decimal
    f1: Decimal
    evidence_coverage: Decimal
    mean_savings_error_usd: Decimal
    unsupported_claims: int
    matched_pairs: list[tuple[int, int]]


@dataclass(frozen=True)
class ModeResult:
    mode: str
    predictions: dict[str, list[PredictedOpportunity]]
    case_scores: dict[str, CaseScore]
    elapsed_ms: int


@dataclass(frozen=True)
class EvaluationSummary:
    modes: dict[str, ModeResult]
    metrics: dict[str, dict[str, object]]
    final_runs: dict[str, AgentRun]


def _round(value: Decimal) -> Decimal:
    return value.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def _target(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _case_fingerprint(case: EvaluationCase) -> str:
    payload = [row.model_dump(mode="json") for row in case.transactions]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def input_fingerprint_for_baseline(cases: Iterable[EvaluationCase]) -> dict[str, str]:
    """Fingerprint the exact rows passed into the raw-merchant baseline."""
    return {case.case_id: _case_fingerprint(case) for case in cases}


def input_fingerprint_for_solution(cases: Iterable[EvaluationCase]) -> dict[str, str]:
    """Fingerprint the exact rows passed into all normalized/agent modes."""
    return {case.case_id: _case_fingerprint(case) for case in cases}


def load_cases(path: Path) -> list[EvaluationCase]:
    """Parse original synthetic rows and normalize them through the production normalizer."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvaluationCase] = []
    for case_data in payload["cases"]:
        rows: list[Transaction] = []
        for row in case_data["transactions"]:
            raw = row["merchant_raw"]
            merchant, category = normalize_merchant(raw, _ALIASES)
            rows.append(
                Transaction(
                    transaction_id=row["transaction_id"],
                    date=row["date"],
                    merchant_raw=raw,
                    merchant_normalized=merchant,
                    amount_usd=row["amount_usd"],
                    category=category,
                    source_type=SourceType.BANK_CSV,
                    source_reference=f"evaluation/{case_data['case_id']}.csv:{row['transaction_id']}",
                    is_synthetic=True,
                )
            )
        cases.append(
            EvaluationCase(
                case_id=case_data["case_id"],
                transactions=rows,
                ground_truth=case_data.get("ground_truth", []),
                is_challenge=case_data.get("is_challenge", False),
            )
        )
    return cases


def _prediction(
    kind: RecommendationKind,
    target: str,
    evidence_ids: list[str],
    monthly: Decimal,
    confidence: Confidence,
    caveat: str | None = None,
) -> PredictedOpportunity:
    return PredictedOpportunity(
        kind=kind,
        target=target,
        evidence_ids=evidence_ids,
        monthly_savings_usd=money(monthly),
        confidence=confidence,
        caveat=caveat,
    )


def run_baseline(case: EvaluationCase) -> list[PredictedOpportunity]:
    """A deliberately limited baseline: exact raw labels and monthly gaps only."""
    grouped: dict[str, list[Transaction]] = {}
    for row in case.transactions:
        grouped.setdefault(row.merchant_raw, []).append(row)
    predictions: list[PredictedOpportunity] = []
    for raw, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: (item.date, item.transaction_id))
        if len(ordered) < 2:
            continue
        gaps = [(later.date - earlier.date).days for earlier, later in zip(ordered, ordered[1:])]
        if all(26 <= gap <= 35 for gap in gaps):
            predictions.append(
                _prediction(
                    RecommendationKind.SUBSCRIPTION,
                    raw,
                    [row.transaction_id for row in ordered],
                    ordered[-1].amount_usd,
                    Confidence.LOW,
                    "Unverified recurrence estimate.",
                )
            )
    return predictions


def _normalization_only_predictions(case: EvaluationCase) -> list[PredictedOpportunity]:
    """Apply only production merchant normalization to the baseline's recurrence rule."""
    grouped: dict[str, list[Transaction]] = {}
    for row in case.transactions:
        grouped.setdefault(row.merchant_normalized, []).append(row)
    predictions: list[PredictedOpportunity] = []
    for merchant, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: (item.date, item.transaction_id))
        if len(ordered) < 2:
            continue
        gaps = [(later.date - earlier.date).days for earlier, later in zip(ordered, ordered[1:])]
        if all(26 <= gap <= 35 for gap in gaps):
            predictions.append(
                _prediction(
                    RecommendationKind.SUBSCRIPTION,
                    merchant,
                    [row.transaction_id for row in ordered],
                    ordered[-1].amount_usd,
                    Confidence.LOW,
                    "Unverified recurrence estimate.",
                )
            )
    return predictions


def _draft_predictions(case: EvaluationCase) -> list[PredictedOpportunity]:
    """Expose the same drafts final mode submits to verification, before acceptance filtering."""
    transactions = {row.transaction_id: row for row in case.transactions}
    return [
        _prediction(
            recommendation.kind,
            transactions[recommendation.evidence_transaction_ids[0]].merchant_normalized,
            recommendation.evidence_transaction_ids,
            recommendation.monthly_savings_usd,
            recommendation.confidence,
            recommendation.caveat,
        )
        for recommendation in draft_offline_recommendations(
            case.transactions, _ANALYSIS_DATE, _NEXT_PAYCHECK
        )
    ]


def _predictions_from_final_run(run: AgentRun) -> list[PredictedOpportunity]:
    transactions = {row.transaction_id: row for row in run.transactions}
    return [
        _prediction(
            recommendation.kind,
            transactions[recommendation.evidence_transaction_ids[0]].merchant_normalized,
            recommendation.evidence_transaction_ids,
            recommendation.monthly_savings_usd,
            recommendation.confidence,
            recommendation.caveat,
        )
        for recommendation in run.recommendations
    ]


def _is_match(prediction: PredictedOpportunity, truth: GroundTruthOpportunity) -> bool:
    return (
        prediction.kind == truth.kind
        and _target(prediction.target) == _target(truth.target)
        and (truth.expected_confidence is None or prediction.confidence == truth.expected_confidence)
        and (not truth.caveat_required or bool(prediction.caveat and prediction.caveat.strip()))
    )


def match_predictions(
    predictions: list[PredictedOpportunity], truth: list[GroundTruthOpportunity]
) -> CaseScore:
    """Score target matching first, retaining evidence and savings fidelity independently."""
    unmatched_truth = set(range(len(truth)))
    pairs: list[tuple[int, int]] = []
    for prediction_index, prediction in enumerate(predictions):
        match = next(
            (truth_index for truth_index in sorted(unmatched_truth) if _is_match(prediction, truth[truth_index])),
            None,
        )
        if match is not None:
            unmatched_truth.remove(match)
            pairs.append((prediction_index, match))
    true_positives = len(pairs)
    false_positives = len(predictions) - true_positives
    false_negatives = len(truth) - true_positives
    precision = _round(Decimal(true_positives) / Decimal(len(predictions))) if predictions else Decimal("0.0000")
    recall = _round(Decimal(true_positives) / Decimal(len(truth))) if truth else Decimal("1.0000")
    f1 = _round(Decimal(2) * precision * recall / (precision + recall)) if precision + recall else Decimal("0.0000")
    if pairs:
        coverage = [
            Decimal(len(set(predictions[prediction_index].evidence_ids) & set(truth[truth_index].required_evidence_ids)))
            / Decimal(len(truth[truth_index].required_evidence_ids))
            for prediction_index, truth_index in pairs
        ]
        savings_error = [
            abs(predictions[prediction_index].monthly_savings_usd - truth[truth_index].monthly_savings_usd)
            for prediction_index, truth_index in pairs
        ]
        evidence_coverage = _round(sum(coverage) / Decimal(len(coverage)))
        mean_savings_error = _round(sum(savings_error) / Decimal(len(savings_error)))
    else:
        evidence_coverage = Decimal("0.0000")
        mean_savings_error = Decimal("0.0000")
    return CaseScore(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
        evidence_coverage=evidence_coverage,
        mean_savings_error_usd=mean_savings_error,
        unsupported_claims=false_positives,
        matched_pairs=pairs,
    )


def _aggregate(case_scores: Iterable[CaseScore]) -> dict[str, object]:
    scores = list(case_scores)
    tp = sum(score.true_positives for score in scores)
    fp = sum(score.false_positives for score in scores)
    fn = sum(score.false_negatives for score in scores)
    precision = _round(Decimal(tp) / Decimal(tp + fp)) if tp + fp else Decimal("0.0000")
    recall = _round(Decimal(tp) / Decimal(tp + fn)) if tp + fn else Decimal("1.0000")
    f1 = _round(Decimal(2) * precision * recall / (precision + recall)) if precision + recall else Decimal("0.0000")
    matched = [score for score in scores if score.true_positives]
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "evidence_coverage": _round(sum((score.evidence_coverage for score in matched), Decimal("0")) / Decimal(len(matched))) if matched else Decimal("0.0000"),
        "mean_savings_error_usd": _round(sum((score.mean_savings_error_usd for score in matched), Decimal("0")) / Decimal(len(matched))) if matched else Decimal("0.0000"),
        "unsupported_claims": sum(score.unsupported_claims for score in scores),
    }


def evaluate_cases(cases: list[EvaluationCase]) -> EvaluationSummary:
    """Evaluate baseline, ablations, and final verified agent on identical rows."""
    modes = {
        "baseline": lambda case: run_baseline(case),
        "normalization_only": _normalization_only_predictions,
        "unverified_agent": _draft_predictions,
        "removed_unsafe_recurrence": _draft_predictions,
    }
    results: dict[str, ModeResult] = {}
    for mode, runner in modes.items():
        started = time.perf_counter()
        predictions = {case.case_id: runner(case) for case in cases}
        scores = {
            case.case_id: match_predictions(predictions[case.case_id], case.ground_truth)
            for case in cases
        }
        results[mode] = ModeResult(
            mode=mode,
            predictions=predictions,
            case_scores=scores,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
    final_started = time.perf_counter()
    final_runs = {
        case.case_id: run_offline_agent(
            case.transactions, _ANALYSIS_DATE, _NEXT_PAYCHECK, f"evaluation-{case.case_id}"
        )
        for case in cases
    }
    final_predictions = {
        case.case_id: _predictions_from_final_run(final_runs[case.case_id])
        for case in cases
    }
    final_scores = {
        case.case_id: match_predictions(final_predictions[case.case_id], case.ground_truth)
        for case in cases
    }
    results["final"] = ModeResult(
        mode="final",
        predictions=final_predictions,
        case_scores=final_scores,
        elapsed_ms=round((time.perf_counter() - final_started) * 1000),
    )
    return EvaluationSummary(
        modes=results,
        metrics={mode: _aggregate(result.case_scores.values()) for mode, result in results.items()},
        final_runs=final_runs,
    )


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return f"{value:.4f}"
    if isinstance(value, CaseScore):
        return {key: _jsonable(item) for key, item in value.__dict__.items()}
    if isinstance(value, PredictedOpportunity):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def write_artifacts(cases: list[EvaluationCase], summary: EvaluationSummary, output_dir: Path) -> None:
    """Persist complete predictions and score evidence for a reproducible offline run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprints = input_fingerprint_for_baseline(cases)
    metadata = {
        "package_version": "0.1.0",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "mode": "offline",
        "execution_mode": "offline",
        "model_cost_usd": "0.00",
        "case_count": len(cases),
        "case_fingerprints": fingerprints,
        "elapsed_ms_by_mode": {mode: result.elapsed_ms for mode, result in summary.modes.items()},
    }
    for mode, result in summary.modes.items():
        (output_dir / f"{mode}_predictions.json").write_text(
            json.dumps(
                _jsonable({**metadata, "mode": mode, "elapsed_ms": result.elapsed_ms, "predictions": result.predictions}),
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    final_result = summary.modes["final"]
    (output_dir / "final_trajectories.json").write_text(
        json.dumps(
            _jsonable(
                {
                    **metadata,
                    "mode": "final",
                    "elapsed_ms": final_result.elapsed_ms,
                    "trajectories": {
                        case_id: [event.model_dump(mode="json") for event in run.trajectory]
                        for case_id, run in summary.final_runs.items()
                    },
                }
            ),
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    per_case = {
        case.case_id: {
            mode: summary.modes[mode].case_scores[case.case_id]
            for mode in summary.modes
        }
        for case in cases
    }
    (output_dir / "per_case_results.json").write_text(
        json.dumps(_jsonable({**metadata, "per_case": per_case}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(_jsonable({**metadata, **summary.metrics}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows = ["# Offline evaluation comparison", "", "| Mode | Precision | Recall | F1 | Evidence coverage | Unsupported claims |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for mode, metrics in summary.metrics.items():
        rows.append(
            f"| {mode} | {metrics['precision']} | {metrics['recall']} | {metrics['f1']} | {metrics['evidence_coverage']} | {metrics['unsupported_claims']} |"
        )
    rows.extend(["", "All modes received the identical retained original transaction rows; no online model was called."])
    (output_dir / "comparison.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
