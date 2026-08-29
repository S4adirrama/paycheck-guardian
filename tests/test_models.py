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


def test_recommendation_and_ground_truth_normalize_direct_money_inputs() -> None:
    recommendation = Recommendation(
        recommendation_id="rec-1",
        kind="subscription",
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


def test_recommendation_requires_evidence_transaction_ids() -> None:
    with pytest.raises(ValidationError):
        Recommendation(
            recommendation_id="rec-1",
            kind="subscription",
            title="Cancel Example",
            rationale="Recurring charge",
            evidence_transaction_ids=[],
            monthly_savings_usd="12.00",
            next_paycheck_savings_usd="6.00",
            confidence="high",
        )


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
