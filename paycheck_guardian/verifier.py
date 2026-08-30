"""Offline safeguards for evidence-backed savings recommendations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import (
    Confidence,
    Recommendation,
    RecommendationAction,
    RecommendationKind,
    Transaction,
)
from .tools import (
    ESSENTIAL_CATEGORIES,
    find_anomalies,
    find_discretionary_patterns,
    find_duplicates,
    find_recurring,
    savings_before_paycheck,
)


CENT_TOLERANCE = Decimal("0.01")
_MINIMUM_EVIDENCE = {
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
}


@dataclass(frozen=True)
class VerificationResult:
    """The verifier's non-throwing decision and human-readable explanations."""

    accepted: bool
    recommendation: Recommendation | None
    reasons: list[str]


def _deterministic_matches(
    recommendation: Recommendation, transactions: list[Transaction]
) -> list[tuple[str, RecommendationAction, Decimal, bool]]:
    evidence_ids = set(recommendation.evidence_transaction_ids)
    if recommendation.kind == RecommendationKind.SUBSCRIPTION:
        return [
            (
                candidate.merchant,
                RecommendationAction.CANCEL_SUBSCRIPTION,
                candidate.monthly_amount,
                candidate.cancellable,
            )
            for candidate in find_recurring(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    if recommendation.kind == RecommendationKind.DUPLICATE:
        return [
            (
                candidate.merchant,
                RecommendationAction.REVIEW_DUPLICATE,
                candidate.amount,
                True,
            )
            for candidate in find_duplicates(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    if recommendation.kind == RecommendationKind.BEHAVIORAL_PATTERN:
        return [
            (
                candidate.merchant,
                RecommendationAction.REDUCE_DISCRETIONARY_SPENDING,
                candidate.monthly_amount,
                True,
            )
            for candidate in find_discretionary_patterns(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    if recommendation.kind == RecommendationKind.ANOMALY:
        return [
            (
                candidate.merchant,
                RecommendationAction.REVIEW_ANOMALY,
                candidate.monthly_amount,
                True,
            )
            for candidate in find_anomalies(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    return []


def _canonical_copy(recommendation: Recommendation) -> Recommendation:
    target = recommendation.verified_target
    copy = {
        RecommendationAction.CANCEL_SUBSCRIPTION: (
            f"Review cancelling {target}",
            f"Verified recurring evidence supports reviewing whether {target} is still wanted; "
            "confirm before any local cancellation simulation.",
        ),
        RecommendationAction.REVIEW_DUPLICATE: (
            f"Review possible duplicate {target} charge",
            "Two matching charges occurred within two days; confirm one was not duplicated.",
        ),
        RecommendationAction.REDUCE_DISCRETIONARY_SPENDING: (
            f"Set a spending limit for {target}",
            f"Repeated discretionary purchases at {target} form a verified pattern; reduce it "
            "only if that fits your priorities.",
        ),
        RecommendationAction.REVIEW_ANOMALY: (
            f"Review unusual {target} charge",
            f"A {target} charge is materially above the merchant's other observed charges; "
            "confirm whether it was expected.",
        ),
    }
    title, rationale = copy[recommendation.verified_action]
    return recommendation.model_copy(update={"title": title, "rationale": rationale})


def _ambiguous_recurrence(
    evidence: list[Transaction], recommendation: Recommendation) -> bool:
    """Identify repeated subscription charges that deterministic recurrence cannot prove."""
    return (
        recommendation.kind == RecommendationKind.SUBSCRIPTION
        and len(evidence) >= 2
        and len({row.merchant_normalized for row in evidence}) == 1
        and not find_recurring(evidence)
    )


def verify_recommendation(
    candidate: object,
    transactions: list[Transaction],
    *,
    analysis_date: date | None = None,
    next_paycheck: date | None = None,
) -> VerificationResult:
    """Independently recompute evidence and savings without trusting a candidate.

    Invalid or untrusted input is always returned as a rejected result so callers can
    safely surface the reason rather than handling an exception.
    """
    if not isinstance(candidate, Recommendation):
        return VerificationResult(False, None, ["candidate is not a Recommendation"])

    try:
        candidate = Recommendation.model_validate(candidate.model_dump())
    except Exception:
        return VerificationResult(False, None, ["candidate contains invalid recommendation data"])

    try:
        known_transactions = {row.transaction_id: row for row in transactions}
    except (AttributeError, TypeError):
        return VerificationResult(False, None, ["transactions are not valid evidence"])

    reasons: list[str] = []
    unknown_ids = [
        evidence_id
        for evidence_id in candidate.evidence_transaction_ids
        if evidence_id not in known_transactions
    ]
    if unknown_ids:
        reasons.extend(
            f"unknown evidence transaction ID: {evidence_id}" for evidence_id in unknown_ids
        )
        return VerificationResult(False, None, reasons)

    if len(set(candidate.evidence_transaction_ids)) != len(candidate.evidence_transaction_ids):
        reasons.append("duplicate evidence transaction IDs cannot increase confidence")

    evidence = [
        known_transactions[evidence_id] for evidence_id in candidate.evidence_transaction_ids
    ]
    evidence_count = len(evidence)
    required_evidence = _MINIMUM_EVIDENCE[candidate.confidence]
    if evidence_count < required_evidence:
        reasons.append(
            f"confidence {candidate.confidence} requires at least {required_evidence} evidence transactions"
        )

    evidence_categories = {row.category for row in evidence}
    if candidate.kind == RecommendationKind.SUBSCRIPTION and evidence_categories & ESSENTIAL_CATEGORIES:
        reasons.append(
            "essential payment evidence cannot support subscription cancellation advice"
        )

    matches = _deterministic_matches(candidate, transactions)
    if not matches:
        reasons.append("evidence does not match a deterministic recommendation target")
    else:
        targets = {target.casefold() for target, _, _, _ in matches}
        if candidate.verified_target.casefold() not in targets:
            reasons.append("verified target does not match the deterministic evidence target")
        actions = {action for _, action, _, _ in matches}
        if candidate.verified_action not in actions:
            reasons.append("verified action does not match the deterministic recommendation type")
        if (
            candidate.kind == RecommendationKind.SUBSCRIPTION
            and not any(cancellable for _, _, _, cancellable in matches)
        ):
            reasons.append("cancellation target is outside the positive semantic allowlist")

    expected_amounts = [expected for _, _, expected, _ in matches]
    if expected_amounts and not any(
        abs(candidate.monthly_savings_usd - expected) <= CENT_TOLERANCE
        for expected in expected_amounts
    ):
        expected = min(expected_amounts)
        reasons.append(
            "monthly savings estimate "
            f"${candidate.monthly_savings_usd} does not match recomputed ${expected}"
        )

    if (analysis_date is None) != (next_paycheck is None):
        reasons.append("analysis date and next paycheck must be provided together")
    elif analysis_date is not None and next_paycheck is not None and expected_amounts:
        expected_next_paychecks = [
            savings_before_paycheck(expected, analysis_date, next_paycheck)
            for expected in expected_amounts
        ]
        if not any(
            abs(candidate.next_paycheck_savings_usd - expected) <= CENT_TOLERANCE
            for expected in expected_next_paychecks
        ):
            expected_next_paycheck = min(expected_next_paychecks)
            reasons.append(
                "next-paycheck savings estimate "
                f"${candidate.next_paycheck_savings_usd} does not match recomputed "
                f"${expected_next_paycheck}"
            )

    if _ambiguous_recurrence(evidence, candidate) and not candidate.caveat:
        reasons.append("ambiguous recurrence requires a caveat")

    if reasons:
        return VerificationResult(False, None, reasons)
    return VerificationResult(True, _canonical_copy(candidate), [])
