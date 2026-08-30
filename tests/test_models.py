from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from paycheck_guardian.models import (
    EvaluationCase,
    GroundTruthOpportunity,
    Recommendation,
    TrajectoryEvent,
    Transaction,
    money,
)


def transaction(amount_usd: Decimal | str = "12.00") -> Transaction:
    return Transaction(
        transaction_id="t1",
        date=date(2026, 7, 1),
        merchant_raw="Example",
        merchant_normalized="Example",
        amount_usd=amount_usd,
        category="other",
        source_type="bank_csv",
        source_reference="x.csv:2",
        is_synthetic=True,
    )


def test_money_quantizes_to_cents() -> None:
    assert money("12.345") == Decimal("12.35")


def test_transaction_rejects_non_usd_and_non_expense() -> None:
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="t1",
            date=date(2026, 7, 1),
            merchant_raw="Example",
            merchant_normalized="Example",
            amount_usd="-1.00",
            category="other",
            source_type="bank_csv",
            source_reference="x.csv:2",
            is_synthetic=True,
        )


def test_transaction_normalizes_direct_money_inputs_to_two_fractional_digits() -> None:
    result = transaction(Decimal("12.3"))
    assert result.amount_usd == Decimal("12.30")
    assert result.amount_usd.as_tuple().exponent == -2


@pytest.mark.parametrize("invalid_amount", [None, "not-a-number"])
def test_transaction_invalid_money_is_a_validation_error(invalid_amount: object) -> None:
    with pytest.raises(ValidationError):
        transaction(invalid_amount)  # type: ignore[arg-type]


def test_recommendation_and_ground_truth_normalize_direct_money_inputs() -> None:
    recommendation = Recommendation(
        recommendation_id="rec-1",
        kind="subscription",
        verified_target="Example",
        verified_action="cancel_subscription",
        title="Cancel Example",
        rationale="Recurring charge",
        evidence_transaction_ids=["t1"],
        monthly_savings_usd=Decimal("12.3"),
        next_paycheck_savings_usd=Decimal("6.7"),
        confidence="high",
    )
    ground_truth = GroundTruthOpportunity(
        kind="subscription",
        target="Example",
        required_evidence_ids=["t1"],
        monthly_savings_usd=Decimal("12.3"),
    )

    assert [
        value.as_tuple().exponent
        for value in (
            recommendation.monthly_savings_usd,
            recommendation.next_paycheck_savings_usd,
            ground_truth.monthly_savings_usd,
        )
    ] == [-2, -2, -2]


@pytest.mark.parametrize("field_name", ["monthly_savings_usd", "next_paycheck_savings_usd"])
def test_recommendation_invalid_money_is_a_validation_error(field_name: str) -> None:
    values: dict[str, object] = {
        "recommendation_id": "rec-1",
        "kind": "subscription",
        "verified_target": "Example",
        "verified_action": "cancel_subscription",
        "title": "Cancel Example",
        "rationale": "Recurring charge",
        "evidence_transaction_ids": ["t1"],
        "monthly_savings_usd": "12.00",
        "next_paycheck_savings_usd": "6.00",
        "confidence": "high",
    }
    values[field_name] = "not-a-number"

    with pytest.raises(ValidationError):
        Recommendation(**values)


def test_ground_truth_invalid_money_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        GroundTruthOpportunity(
            kind="subscription",
            target="Example",
            required_evidence_ids=["t1"],
            monthly_savings_usd=None,
        )


def test_recommendation_requires_evidence_transaction_ids() -> None:
    with pytest.raises(ValidationError):
        Recommendation(
            recommendation_id="rec-1",
            kind="subscription",
            verified_target="Example",
            verified_action="cancel_subscription",
            title="Cancel Example",
            rationale="Recurring charge",
            evidence_transaction_ids=[],
            monthly_savings_usd="12.00",
            next_paycheck_savings_usd="6.00",
            confidence="high",
        )


def test_recommendation_requires_structured_verified_target_and_action() -> None:
    """Removing either structured field would let free-form copy define a financial action."""
    base = {
        "recommendation_id": "rec-1",
        "kind": "subscription",
        "verified_target": "Netflix",
        "verified_action": "cancel_subscription",
        "title": "Untrusted draft copy",
        "rationale": "Untrusted draft rationale",
        "evidence_transaction_ids": ["t1"],
        "monthly_savings_usd": "12.00",
        "next_paycheck_savings_usd": "6.00",
        "confidence": "high",
    }

    recommendation = Recommendation(**base)

    assert recommendation.verified_target == "Netflix"
    assert recommendation.verified_action.value == "cancel_subscription"
    for missing in ("verified_target", "verified_action"):
        values = {key: value for key, value in base.items() if key != missing}
        with pytest.raises(ValidationError):
            Recommendation(**values)


def test_evaluation_case_requires_transactions() -> None:
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="case-1", transactions=[])


def test_trajectory_event_requires_dictionary_tool_data() -> None:
    event = dict(
        timestamp=datetime(2026, 7, 1),
        run_id="run-1",
        component="agent",
        event_type="tool_call",
    )

    with pytest.raises(ValidationError):
        TrajectoryEvent(**event, tool_input=["not", "a", "dictionary"])

    with pytest.raises(ValidationError):
        TrajectoryEvent(**event, tool_result=["not", "a", "dictionary"])
