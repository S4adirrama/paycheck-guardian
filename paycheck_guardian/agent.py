"""Offline-only orchestration for verified savings recommendations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import (
    AgentRun,
    Confidence,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
    Transaction,
)
from .tools import (
    DuplicateCandidate,
    RecurringCandidate,
    SpendingPattern,
    find_discretionary_patterns,
    find_duplicates,
    find_recurring,
    savings_before_paycheck,
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


def _serialized_transactions(transactions: list[Transaction]) -> dict[str, object]:
    return {"transactions": [row.model_dump(mode="json") for row in transactions]}


def _tool_result(candidates: list[object]) -> dict[str, object]:
    """Serialize all deterministic findings so a trajectory can be replayed and audited."""
    serialized: list[dict[str, object]] = []
    for candidate in candidates:
        if isinstance(candidate, RecurringCandidate):
            serialized.append(
                {
                    "merchant": candidate.merchant,
                    "category": candidate.category,
                    "interval_days": candidate.interval_days,
                    "monthly_amount": candidate.monthly_amount,
                    "evidence_ids": candidate.evidence_ids,
                    "cancellable": candidate.cancellable,
                }
            )
        elif isinstance(candidate, DuplicateCandidate):
            serialized.append(
                {
                    "merchant": candidate.merchant,
                    "amount": candidate.amount,
                    "evidence_ids": candidate.evidence_ids,
                }
            )
        elif isinstance(candidate, SpendingPattern):
            serialized.append(
                {
                    "merchant": candidate.merchant,
                    "category": candidate.category,
                    "charge_count": candidate.charge_count,
                    "monthly_amount": candidate.monthly_amount,
                    "evidence_ids": candidate.evidence_ids,
                }
            )
    return {"candidates": serialized}


def _drafts_from_candidates(
    recurring: list[RecurringCandidate],
    duplicates: list[DuplicateCandidate],
    patterns: list[SpendingPattern],
    analysis_date: date,
    next_paycheck: date,
) -> list[_CandidateDraft]:
    """Create every deterministic candidate draft; verifier policy decides what is retained."""
    drafts = [_subscription_draft(candidate, analysis_date, next_paycheck) for candidate in recurring]
    drafts.extend(_duplicate_draft(candidate, analysis_date, next_paycheck) for candidate in duplicates)
    drafts.extend(_pattern_draft(candidate, analysis_date, next_paycheck) for candidate in patterns)
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
            tool_input={"recommendation": candidate.model_dump(mode="json")},
            attempt=attempt,
        )
        result = verify_recommendation(
            candidate,
            transactions,
            analysis_date=analysis_date,
            next_paycheck=next_paycheck,
        )
        recorder.record(
            component="verifier",
            event_type="tool_result",
            tool_name="verify_recommendation",
            tool_input={"recommendation": candidate.model_dump(mode="json")},
            tool_result={
                "accepted": result.accepted,
                "recommendation": (
                    result.recommendation.model_dump(mode="json")
                    if result.recommendation is not None
                    else None
                ),
                "reasons": result.reasons,
            },
            verification_feedback=result.reasons,
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
                verification_feedback=result.reasons,
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

    drafts = _drafts_from_candidates(recurring, duplicates, patterns, analysis_date, next_paycheck)

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
    ranked = sorted(
        verified,
        key=lambda recommendation: (-recommendation.monthly_savings_usd, recommendation.recommendation_id),
    )[:3]
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
    if recommendation is None or recommendation.kind != RecommendationKind.SUBSCRIPTION:
        recorder.record(
            component="human",
            event_type="simulation_not_available",
            human_checkpoint="cancellation_not_available",
        )
    elif not approved:
        recommendation.status = RecommendationStatus.DISMISSED
        recorder.record(
            component="human",
            event_type="simulation_declined",
            human_checkpoint="cancellation_declined",
        )
    else:
        recorder.record(
            component="verifier",
            event_type="tool_called",
            tool_name="verify_recommendation",
            tool_input={"recommendation": recommendation.model_dump(mode="json")},
        )
        verification = verify_recommendation(
            recommendation,
            updated.transactions,
            analysis_date=updated.analysis_date,
            next_paycheck=updated.next_paycheck,
        )
        recorder.record(
            component="verifier",
            event_type="tool_result",
            tool_name="verify_recommendation",
            tool_result={
                "accepted": verification.accepted,
                "recommendation": (
                    verification.recommendation.model_dump(mode="json")
                    if verification.recommendation is not None
                    else None
                ),
                "reasons": verification.reasons,
            },
            verification_feedback=verification.reasons,
        )
        if not verification.accepted:
            recorder.record(
                component="verifier",
                event_type="simulation_blocked",
                verification_feedback=verification.reasons,
                human_checkpoint="cancellation_blocked",
            )
        else:
            recommendation.status = RecommendationStatus.APPROVED_FOR_SIMULATION
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
