"""Offline-only orchestration for verified savings recommendations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import re

from .models import (
    AgentRun,
    Confidence,
    Recommendation,
    RecommendationAction,
    RecommendationKind,
    RecommendationStatus,
    Transaction,
)
from .tools import (
    AnomalyCandidate,
    CategorySummary,
    DuplicateCandidate,
    RecurringCandidate,
    SpendingPattern,
    find_anomalies,
    find_discretionary_patterns,
    find_duplicates,
    find_recurring,
    savings_before_paycheck,
    summarize_categories,
)
from .trajectory import TrajectoryRecorder
from .verifier import VerificationResult, verify_recommendation


_REPAIRABLE_FEEDBACK = ("monthly savings estimate", "next-paycheck savings estimate", "evidence")


@dataclass(frozen=True)
class _CandidateDraft:
    recommendation: Recommendation
    tool_truth: Recommendation


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().split() if part) or "unknown"


def _next_paycheck_savings(monthly: Decimal, analysis_date: date, next_paycheck: date) -> Decimal:
    return savings_before_paycheck(monthly, analysis_date, next_paycheck)


def _subscription_draft(
    candidate: RecurringCandidate, analysis_date: date, next_paycheck: date
) -> _CandidateDraft:
    ambiguous_two_observation_monthly = len(candidate.evidence_ids) == 2 and candidate.interval_days == 30
    confidence = (
        Confidence.LOW
        if ambiguous_two_observation_monthly
        else Confidence.HIGH if len(candidate.evidence_ids) >= 3 else Confidence.MEDIUM
    )
    caveat = (
        "Only two monthly charges were observed; confirm this possible subscription before cancelling."
        if ambiguous_two_observation_monthly
        else "Savings are estimates based on the observed recurring charges."
    )

    def build() -> Recommendation:
        return Recommendation(
            recommendation_id=f"subscription-{_slug(candidate.merchant)}",
            kind=RecommendationKind.SUBSCRIPTION,
            verified_target=candidate.merchant,
            verified_action=RecommendationAction.CANCEL_SUBSCRIPTION,
            title=f"Review {candidate.merchant} subscription",
            rationale=(
                f"{candidate.merchant} appears to recur every {candidate.interval_days} days; "
                "confirm it is still wanted before cancelling."
            ),
            evidence_transaction_ids=candidate.evidence_ids,
            monthly_savings_usd=candidate.monthly_amount,
            next_paycheck_savings_usd=_next_paycheck_savings(
                candidate.monthly_amount, analysis_date, next_paycheck
            ),
            confidence=confidence,
            caveat=caveat,
        )

    recommendation = build()
    return _CandidateDraft(recommendation, recommendation.model_copy(deep=True))


def _duplicate_draft(
    candidate: DuplicateCandidate, analysis_date: date, next_paycheck: date
) -> _CandidateDraft:
    def build() -> Recommendation:
        return Recommendation(
            recommendation_id=f"duplicate-{_slug(candidate.merchant)}-{'-'.join(candidate.evidence_ids)}",
            kind=RecommendationKind.DUPLICATE,
            verified_target=candidate.merchant,
            verified_action=RecommendationAction.REVIEW_DUPLICATE,
            title=f"Review possible duplicate {candidate.merchant} charge",
            rationale="Two matching charges occurred within two days; confirm one was not duplicated.",
            evidence_transaction_ids=candidate.evidence_ids,
            monthly_savings_usd=candidate.amount,
            next_paycheck_savings_usd=_next_paycheck_savings(
                candidate.amount, analysis_date, next_paycheck
            ),
            confidence=Confidence.MEDIUM,
            caveat="Savings are an estimate pending merchant confirmation.",
        )

    recommendation = build()
    return _CandidateDraft(recommendation, recommendation.model_copy(deep=True))


def _pattern_draft(
    candidate: SpendingPattern, analysis_date: date, next_paycheck: date
) -> _CandidateDraft:
    def build() -> Recommendation:
        return Recommendation(
            recommendation_id=f"pattern-{_slug(candidate.merchant)}-{'-'.join(candidate.evidence_ids)}",
            kind=RecommendationKind.BEHAVIORAL_PATTERN,
            verified_target=candidate.merchant,
            verified_action=RecommendationAction.REDUCE_DISCRETIONARY_SPENDING,
            title=f"Set a limit for {candidate.merchant}",
            rationale=(
                f"{candidate.charge_count} discretionary {candidate.category} purchases occurred "
                "within 30 days; reduce this pattern only if it fits your priorities."
            ),
            evidence_transaction_ids=candidate.evidence_ids,
            monthly_savings_usd=candidate.monthly_amount,
            next_paycheck_savings_usd=_next_paycheck_savings(
                candidate.monthly_amount, analysis_date, next_paycheck
            ),
            confidence=Confidence.HIGH,
            caveat="Savings are an estimate based on the observed 30-day pattern.",
        )

    recommendation = build()
    return _CandidateDraft(recommendation, recommendation.model_copy(deep=True))


def _anomaly_draft(
    candidate: AnomalyCandidate, analysis_date: date, next_paycheck: date
) -> _CandidateDraft:
    def build() -> Recommendation:
        return Recommendation(
            recommendation_id=f"anomaly-{_slug(candidate.merchant)}-{'-'.join(candidate.evidence_ids)}",
            kind=RecommendationKind.ANOMALY,
            verified_target=candidate.merchant,
            verified_action=RecommendationAction.REVIEW_ANOMALY,
            title=f"Review unusual {candidate.merchant} charge",
            rationale="One charge is materially above the merchant's other observed charges.",
            evidence_transaction_ids=candidate.evidence_ids,
            monthly_savings_usd=candidate.monthly_amount,
            next_paycheck_savings_usd=_next_paycheck_savings(
                candidate.monthly_amount, analysis_date, next_paycheck
            ),
            confidence=Confidence.MEDIUM,
            caveat="Confirm whether the unusual charge was expected before treating it as savings.",
        )

    recommendation = build()
    return _CandidateDraft(recommendation, recommendation.model_copy(deep=True))


def _serialized_transactions(transactions: list[Transaction]) -> dict[str, object]:
    private_payload = [row.model_dump(mode="json") for row in transactions]
    fingerprint = sha256(
        json.dumps(private_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    category_counts: dict[str, int] = {}
    for row in transactions:
        category_counts[row.category] = category_counts.get(row.category, 0) + 1
    return {
        "transaction_fingerprint": fingerprint,
        "transaction_count": len(transactions),
        "transaction_ids": [row.transaction_id for row in transactions],
        "category_counts": dict(sorted(category_counts.items())),
        "synthetic_count": sum(row.is_synthetic for row in transactions),
    }


def _fingerprint(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _tool_result(candidates: list[object]) -> dict[str, object]:
    """Summarize deterministic findings without retaining raw merchant or amount fields."""
    serialized: list[dict[str, object]] = []
    for candidate in candidates:
        if isinstance(candidate, RecurringCandidate):
            serialized.append(
                {
                    "candidate_fingerprint": _fingerprint(candidate.__dict__),
                    "category": candidate.category,
                    "interval_days": candidate.interval_days,
                    "evidence_ids": candidate.evidence_ids,
                    "evidence_count": len(candidate.evidence_ids),
                    "cancellable": candidate.cancellable,
                    "summary": "recurring cadence candidate",
                }
            )
        elif isinstance(candidate, DuplicateCandidate):
            serialized.append(
                {
                    "candidate_fingerprint": _fingerprint(candidate.__dict__),
                    "evidence_ids": candidate.evidence_ids,
                    "evidence_count": len(candidate.evidence_ids),
                    "summary": "near-date matching charge candidate",
                }
            )
        elif isinstance(candidate, SpendingPattern):
            serialized.append(
                {
                    "candidate_fingerprint": _fingerprint(candidate.__dict__),
                    "category": candidate.category,
                    "charge_count": candidate.charge_count,
                    "evidence_ids": candidate.evidence_ids,
                    "evidence_count": len(candidate.evidence_ids),
                    "summary": "discretionary frequency candidate",
                }
            )
        elif isinstance(candidate, AnomalyCandidate):
            serialized.append(
                {
                    "candidate_fingerprint": _fingerprint(candidate.__dict__),
                    "category": candidate.category,
                    "evidence_ids": candidate.evidence_ids,
                    "evidence_count": len(candidate.evidence_ids),
                    "summary": "material high-outlier candidate",
                }
            )
        elif isinstance(candidate, CategorySummary):
            serialized.append(
                {
                    "candidate_fingerprint": _fingerprint(candidate.__dict__),
                    "category": candidate.category,
                    "charge_count": candidate.charge_count,
                    "evidence_ids": candidate.evidence_ids,
                    "evidence_count": len(candidate.evidence_ids),
                    "summary": "category spending summary",
                }
            )
    return {"candidate_count": len(serialized), "candidates": serialized}


def _trace_recommendation(recommendation: Recommendation) -> dict[str, object]:
    private_payload = recommendation.model_dump(mode="json")
    return {
        "recommendation_id": recommendation.recommendation_id,
        "kind": recommendation.kind.value,
        "verified_action": recommendation.verified_action.value,
        "target_fingerprint": _fingerprint(recommendation.verified_target),
        "recommendation_fingerprint": _fingerprint(private_payload),
        "evidence_ids": recommendation.evidence_transaction_ids,
        "evidence_count": len(recommendation.evidence_transaction_ids),
        "status": recommendation.status.value,
    }


def _sanitized_feedback(reasons: list[str]) -> list[str]:
    return [re.sub(r"\$\d+(?:\.\d+)?", "[amount redacted]", reason) for reason in reasons]


def _drafts_from_candidates(
    recurring: list[RecurringCandidate],
    duplicates: list[DuplicateCandidate],
    patterns: list[SpendingPattern],
    anomalies: list[AnomalyCandidate],
    analysis_date: date,
    next_paycheck: date,
) -> list[_CandidateDraft]:
    """Create every deterministic candidate draft; verifier policy decides what is retained."""
    drafts = [_subscription_draft(candidate, analysis_date, next_paycheck) for candidate in recurring]
    drafts.extend(_duplicate_draft(candidate, analysis_date, next_paycheck) for candidate in duplicates)
    drafts.extend(_pattern_draft(candidate, analysis_date, next_paycheck) for candidate in patterns)
    drafts.extend(_anomaly_draft(candidate, analysis_date, next_paycheck) for candidate in anomalies)
    return drafts


def draft_offline_recommendations(
    transactions: list[Transaction], analysis_date: date, next_paycheck: date
) -> list[Recommendation]:
    """Return the exact pre-verification drafts submitted by the offline agent."""
    return [
        draft.recommendation.model_copy(deep=True)
        for draft in _drafts_from_candidates(
            find_recurring(transactions),
            find_duplicates(transactions),
            find_discretionary_patterns(transactions),
            find_anomalies(transactions),
            analysis_date,
            next_paycheck,
        )
    ]


def _should_retry(result: VerificationResult) -> bool:
    feedback = " ".join(result.reasons).lower()
    return any(fragment in feedback for fragment in _REPAIRABLE_FEEDBACK)


def _correct_candidate(
    draft: _CandidateDraft, candidate: Recommendation, result: VerificationResult
) -> Recommendation | None:
    """Return a changed canonical recommendation only when feedback identifies its bad field."""
    if not _should_retry(result):
        return None
    feedback = " ".join(result.reasons).lower()
    corrected = draft.tool_truth
    arithmetic_mismatch = (
        ("monthly savings estimate" in feedback
         and candidate.monthly_savings_usd != corrected.monthly_savings_usd)
        or ("next-paycheck savings estimate" in feedback
            and candidate.next_paycheck_savings_usd != corrected.next_paycheck_savings_usd)
    )
    evidence_mismatch = "evidence" in feedback and (
        candidate.evidence_transaction_ids != corrected.evidence_transaction_ids
    )
    if not arithmetic_mismatch and not evidence_mismatch:
        return None
    return corrected.model_copy(deep=True)


def _verify_draft(
    draft: _CandidateDraft,
    transactions: list[Transaction],
    analysis_date: date,
    next_paycheck: date,
    recorder: TrajectoryRecorder,
) -> Recommendation | None:
    candidate = draft.recommendation
    for attempt in (1, 2):
        recorder.record(
            component="verifier",
            event_type="tool_called",
            tool_name="verify_recommendation",
            tool_input={"recommendation": _trace_recommendation(candidate)},
            attempt=attempt,
        )
        result = verify_recommendation(
            candidate,
            transactions,
            analysis_date=analysis_date,
            next_paycheck=next_paycheck,
        )
        safe_feedback = _sanitized_feedback(result.reasons)
        recorder.record(
            component="verifier",
            event_type="tool_result",
            tool_name="verify_recommendation",
            tool_input={"recommendation": _trace_recommendation(candidate)},
            tool_result={
                "accepted": result.accepted,
                "reason_count": len(safe_feedback),
                "reasons": safe_feedback,
                "summary": "accepted verified candidate" if result.accepted else "rejected candidate",
            },
            verification_feedback=safe_feedback,
            attempt=attempt,
        )
        if result.accepted and result.recommendation is not None:
            return result.recommendation.model_copy(
                update={"status": RecommendationStatus.PROPOSED}
            )
        corrected = _correct_candidate(draft, candidate, result) if attempt == 1 else None
        if corrected is not None:
            recorder.record(
                component="agent",
                event_type="candidate_retry",
                verification_feedback=safe_feedback,
                attempt=2,
            )
            candidate = corrected
        else:
            return None
    return None


def run_offline_agent(
    transactions: list[Transaction], analysis_date: date, next_paycheck: date, run_id: str
) -> AgentRun:
    """Generate up to three independently verified recommendations without network access."""
    recorder = TrajectoryRecorder(run_id)
    recorder.record(
        component="agent",
        event_type="run_started",
        instruction="Use deterministic tools and verification; do not perform external actions.",
        tool_input={"transaction_count": len(transactions)},
    )

    recorder.record(
        component="analysis",
        event_type="tool_called",
        tool_name="find_recurring",
        tool_input=_serialized_transactions(transactions),
    )
    recurring = find_recurring(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_result",
        tool_name="find_recurring",
        tool_result=_tool_result(recurring),
    )
    recorder.record(
        component="analysis",
        event_type="tool_called",
        tool_name="find_duplicates",
        tool_input=_serialized_transactions(transactions),
    )
    duplicates = find_duplicates(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_result",
        tool_name="find_duplicates",
        tool_result=_tool_result(duplicates),
    )
    recorder.record(
        component="analysis",
        event_type="tool_called",
        tool_name="find_discretionary_patterns",
        tool_input=_serialized_transactions(transactions),
    )
    patterns = find_discretionary_patterns(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_result",
        tool_name="find_discretionary_patterns",
        tool_result=_tool_result(patterns),
    )

    recorder.record(
        component="analysis",
        event_type="tool_called",
        tool_name="find_anomalies",
        tool_input=_serialized_transactions(transactions),
    )
    anomalies = find_anomalies(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_result",
        tool_name="find_anomalies",
        tool_result=_tool_result(anomalies),
    )
    recorder.record(
        component="analysis",
        event_type="tool_called",
        tool_name="summarize_categories",
        tool_input=_serialized_transactions(transactions),
    )
    category_summaries = summarize_categories(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_result",
        tool_name="summarize_categories",
        tool_result=_tool_result(category_summaries),
    )

    drafts = _drafts_from_candidates(
        recurring, duplicates, patterns, anomalies, analysis_date, next_paycheck
    )

    verified = [
        recommendation
        for draft in drafts
        if (
            recommendation := _verify_draft(
                draft, transactions, analysis_date, next_paycheck, recorder
            )
        )
        is not None
    ]
    ranked_candidates = sorted(
        verified,
        key=lambda recommendation: (-recommendation.monthly_savings_usd, recommendation.recommendation_id),
    )
    ranked: list[Recommendation] = []
    claimed_evidence: set[str] = set()
    for recommendation in ranked_candidates:
        evidence = set(recommendation.evidence_transaction_ids)
        if evidence & claimed_evidence:
            continue
        ranked.append(recommendation)
        claimed_evidence.update(evidence)
        if len(ranked) == 3:
            break
    recorder.record(
        component="agent",
        event_type="run_completed",
        tool_result={"verified_recommendation_count": len(ranked)},
        human_checkpoint="recommendations_ready_for_human_review",
    )
    return AgentRun(
        run_id=run_id,
        analysis_date=analysis_date,
        next_paycheck=next_paycheck,
        transactions=transactions,
        recommendations=ranked,
        trajectory=recorder.events,
    )


def simulate_cancellation(run: AgentRun, recommendation_id: str, approved: bool) -> AgentRun:
    """Record a human decision locally; this function never contacts a merchant or bank."""
    updated = run.model_copy(deep=True)
    recorder = TrajectoryRecorder(updated.run_id, updated.trajectory)
    recommendation = next(
        (
            item
            for item in updated.recommendations
            if item.recommendation_id == recommendation_id
        ),
        None,
    )
    action_exists = any(
        action.get("recommendation_id") == recommendation_id
        and action.get("action") == "simulate_cancellation"
        for action in updated.simulated_actions
    )
    if (
        recommendation is None
        or recommendation.kind != RecommendationKind.SUBSCRIPTION
        or recommendation.verified_action != RecommendationAction.CANCEL_SUBSCRIPTION
        or recommendation.status == RecommendationStatus.DISMISSED
    ):
        recorder.record(
            component="human",
            event_type="simulation_not_available",
            human_checkpoint="cancellation_not_available",
        )
    elif not approved:
        if recommendation.status == RecommendationStatus.DISMISSED:
            updated.trajectory = recorder.events
            return updated
        recommendation.status = RecommendationStatus.DISMISSED
        recorder.record(
            component="human",
            event_type="simulation_declined",
            human_checkpoint="cancellation_declined",
        )
    elif action_exists or recommendation.status == RecommendationStatus.APPROVED_FOR_SIMULATION:
        recorder.record(
            component="human",
            event_type="simulation_already_approved",
            human_checkpoint="cancellation_already_approved",
        )
    else:
        recorder.record(
            component="verifier",
            event_type="tool_called",
            tool_name="verify_recommendation",
            tool_input={"recommendation": _trace_recommendation(recommendation)},
        )
        verification = verify_recommendation(
            recommendation,
            updated.transactions,
            analysis_date=updated.analysis_date,
            next_paycheck=updated.next_paycheck,
        )
        safe_feedback = _sanitized_feedback(verification.reasons)
        recorder.record(
            component="verifier",
            event_type="tool_result",
            tool_name="verify_recommendation",
            tool_result={
                "accepted": verification.accepted,
                "reason_count": len(safe_feedback),
                "reasons": safe_feedback,
                "summary": "accepted verified candidate" if verification.accepted else "rejected candidate",
            },
            verification_feedback=safe_feedback,
        )
        if not verification.accepted:
            recorder.record(
                component="verifier",
                event_type="simulation_blocked",
                verification_feedback=safe_feedback,
                human_checkpoint="cancellation_blocked",
            )
        else:
            recommendation.status = RecommendationStatus.APPROVED_FOR_SIMULATION
            if not action_exists:
                updated.simulated_actions.append(
                    {"recommendation_id": recommendation_id, "action": "simulate_cancellation"}
                )
            recorder.record(
                component="human",
                event_type="simulation_approved",
                human_checkpoint="cancellation_approved",
            )
    updated.trajectory = recorder.events
    return updated
