"""Offline safeguards for evidence-backed savings recommendations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import Confidence, Recommendation, RecommendationKind, Transaction
from .tools import (
    ESSENTIAL_CATEGORIES,
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


def _expected_monthly_amounts(
    recommendation: Recommendation, transactions: list[Transaction]
) -> list[Decimal]:
    evidence_ids = set(recommendation.evidence_transaction_ids)
    if recommendation.kind == RecommendationKind.SUBSCRIPTION:
        return [
            candidate.monthly_amount
            for candidate in find_recurring(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    if recommendation.kind == RecommendationKind.DUPLICATE:
        return [
            candidate.amount
            for candidate in find_duplicates(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    if recommendation.kind == RecommendationKind.BEHAVIORAL_PATTERN:
        return [
            candidate.monthly_amount
            for candidate in find_discretionary_patterns(transactions)
            if set(candidate.evidence_ids) == evidence_ids
        ]
    return []


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

    expected_amounts = _expected_monthly_amounts(candidate, transactions)
    if not expected_amounts:
        reasons.append("evidence does not match a deterministic recommendation target")
    elif not any(
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
    return VerificationResult(True, candidate, [])
