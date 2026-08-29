"""Offline-only orchestration for verified savings recommendations."""

from collections.abc import Callable
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
    rebuild: Callable[[], Recommendation]


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().split() if part) or "unknown"


def _next_paycheck_savings(monthly: Decimal, analysis_date: date, next_paycheck: date) -> Decimal:
    return savings_before_paycheck(monthly, analysis_date, next_paycheck)


def _subscription_draft(
    candidate: RecurringCandidate, analysis_date: date, next_paycheck: date
) -> _CandidateDraft:
    confidence = Confidence.HIGH if len(candidate.evidence_ids) >= 3 else Confidence.MEDIUM

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
            caveat="Savings are estimates based on the observed recurring charges.",
        )

    return _CandidateDraft(build(), build)


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

    return _CandidateDraft(build(), build)


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

    return _CandidateDraft(build(), build)


def _tool_summary(candidates: list[object]) -> dict[str, object]:
    """Keep trajectory records compact while preserving deterministic tool facts."""
    return {"candidate_count": len(candidates)}


def _should_retry(result: VerificationResult) -> bool:
    feedback = " ".join(result.reasons).lower()
    return any(fragment in feedback for fragment in _REPAIRABLE_FEEDBACK)


def _verify_draft(
    draft: _CandidateDraft,
    transactions: list[Transaction],
    analysis_date: date,
    next_paycheck: date,
    recorder: TrajectoryRecorder,
) -> Recommendation | None:
    candidate = draft.recommendation
    for attempt in (1, 2):
        result = verify_recommendation(
            candidate,
            transactions,
            analysis_date=analysis_date,
            next_paycheck=next_paycheck,
        )
        recorder.record(
            component="verifier",
            event_type="candidate_verified" if result.accepted else "candidate_rejected",
            tool_name="verify_recommendation",
            tool_input={"recommendation": candidate.model_dump(mode="json")},
            tool_result={"accepted": result.accepted},
            verification_feedback=result.reasons,
            attempt=attempt,
        )
        if result.accepted and result.recommendation is not None:
            return result.recommendation.model_copy(
                update={"status": RecommendationStatus.PROPOSED}
            )
        if attempt == 1 and _should_retry(result):
            recorder.record(
                component="agent",
                event_type="candidate_retry",
                verification_feedback=result.reasons,
                attempt=2,
            )
            candidate = draft.rebuild()
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

    recurring = find_recurring(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_completed",
        tool_name="find_recurring",
        tool_input={"transaction_count": len(transactions)},
        tool_result=_tool_summary(recurring),
    )
    duplicates = find_duplicates(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_completed",
        tool_name="find_duplicates",
        tool_input={"transaction_count": len(transactions)},
        tool_result=_tool_summary(duplicates),
    )
    patterns = find_discretionary_patterns(transactions)
    recorder.record(
        component="analysis",
        event_type="tool_completed",
        tool_name="find_discretionary_patterns",
        tool_input={"transaction_count": len(transactions)},
        tool_result=_tool_summary(patterns),
    )

    drafts: list[_CandidateDraft] = []
    for candidate in recurring:
        if not candidate.cancellable:
            recorder.record(
                component="policy",
                event_type="candidate_omitted",
                verification_feedback=["essential recurring payment is not cancellable"],
            )
            continue
        drafts.append(_subscription_draft(candidate, analysis_date, next_paycheck))
    drafts.extend(_duplicate_draft(candidate, analysis_date, next_paycheck) for candidate in duplicates)
    drafts.extend(_pattern_draft(candidate, analysis_date, next_paycheck) for candidate in patterns)

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
        recorder.record(
            component="human",
            event_type="simulation_declined",
            human_checkpoint="cancellation_declined",
        )
    else:
        verification = verify_recommendation(
            recommendation,
            updated.transactions,
            analysis_date=updated.analysis_date,
            next_paycheck=updated.next_paycheck,
        )
        if not verification.accepted:
            recorder.record(
                component="verifier",
                event_type="simulation_blocked",
                tool_name="verify_recommendation",
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
