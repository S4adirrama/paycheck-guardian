from datetime import date
from decimal import Decimal

import pytest

from paycheck_guardian.models import (
    AgentRun,
    Confidence,
    Recommendation,
    RecommendationKind,
    SourceType,
    Transaction,
)
from paycheck_guardian.reporting import render_markdown, serialize_run
from paycheck_guardian.verifier import verify_recommendation


def make_transaction(
    transaction_id: str, occurred_on: date, merchant: str, amount: str, category: str
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        date=occurred_on,
        merchant_raw=merchant,
        merchant_normalized=merchant,
        amount_usd=amount,
        category=category,
        source_type=SourceType.BANK_CSV,
        source_reference=f"test.csv:{transaction_id}",
        is_synthetic=True,
    )


@pytest.fixture
def transactions() -> list[Transaction]:
    return [
        make_transaction("n1", date(2026, 5, 1), "Netflix", "15.49", "streaming"),
        make_transaction("n2", date(2026, 5, 31), "Netflix", "16.49", "streaming"),
        make_transaction("n3", date(2026, 6, 30), "Netflix", "16.49", "streaming"),
    ]


@pytest.fixture
def candidate() -> Recommendation:
    return Recommendation(
        recommendation_id="cancel-netflix",
        kind=RecommendationKind.SUBSCRIPTION,
        title="Cancel Netflix",
        rationale="Netflix recurs every month.",
        evidence_transaction_ids=["n1", "n2", "n3"],
        monthly_savings_usd="16.49",
        next_paycheck_savings_usd="6.51",
        confidence=Confidence.HIGH,
    )


@pytest.fixture
def rent_transactions() -> list[Transaction]:
    return [
        make_transaction("r1", date(2026, 5, 1), "Home Rental", "1200.00", "housing"),
        make_transaction("r2", date(2026, 6, 1), "Home Rental", "1200.00", "housing"),
    ]


@pytest.fixture
def rent_candidate() -> Recommendation:
    return Recommendation(
        recommendation_id="cancel-rent",
        kind=RecommendationKind.SUBSCRIPTION,
        title="Cancel Home Rental",
        rationale="Home Rental recurs monthly.",
        evidence_transaction_ids=["r1", "r2"],
        monthly_savings_usd="1200.00",
        next_paycheck_savings_usd="100.00",
        confidence=Confidence.MEDIUM,
    )


def test_verifier_rejects_missing_evidence(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.evidence_transaction_ids = ["does-not-exist"]

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert "unknown evidence" in result.reasons[0]


def test_verifier_rejects_inflated_savings(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.monthly_savings_usd = Decimal("999.00")

    assert verify_recommendation(candidate, transactions).accepted is False


def test_verifier_blocks_cancellation_of_essential_payment(
    rent_candidate: Recommendation, rent_transactions: list[Transaction]
) -> None:
    result = verify_recommendation(rent_candidate, rent_transactions)

    assert result.accepted is False
    assert any("essential" in reason for reason in result.reasons)


def test_verifier_rejects_confidence_unsupported_by_evidence(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.evidence_transaction_ids = ["n1", "n2"]

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert any("confidence" in reason for reason in result.reasons)


def test_verifier_requires_caveat_for_ambiguous_recurrence(
    transactions: list[Transaction], candidate: Recommendation
) -> None:
    transactions[1].amount_usd = Decimal("18.00")

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert any("caveat" in reason for reason in result.reasons)


def test_verifier_never_throws_for_an_unrecognised_candidate(
    transactions: list[Transaction]
) -> None:
    result = verify_recommendation(object(), transactions)

    assert result.accepted is False
    assert result.recommendation is None
    assert result.reasons


def test_verifier_never_throws_for_a_mutated_invalid_candidate(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.monthly_savings_usd = None  # type: ignore[assignment]

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert result.recommendation is None
    assert result.reasons


def test_markdown_labels_estimates_lists_evidence_and_disclaimer(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    run = AgentRun(
        run_id="run-1",
        analysis_date=date(2026, 7, 1),
        next_paycheck=date(2026, 7, 13),
        transactions=transactions,
        recommendations=[candidate],
    )

    report = render_markdown(run)

    assert "Monthly estimate: $16.49" in report
    assert "Next-paycheck estimate:" in report
    assert "Evidence: n1, n2, n3" in report
    assert "Educational spending analysis only. No bank or subscription action was performed." in report


def test_markdown_renders_only_five_verified_recommendations_in_savings_order(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    recommendations = [candidate.model_copy(update={"recommendation_id": f"rec-{index}"}) for index in range(6)]
    for index, recommendation in enumerate(recommendations):
        recommendation.monthly_savings_usd = Decimal("16.49")
        recommendation.title = f"Cancel Netflix {index}"
        recommendation.rationale = "Netflix recurs every month."
    run = AgentRun(
        run_id="run-1",
        analysis_date=date(2026, 7, 1),
        next_paycheck=date(2026, 7, 13),
        transactions=transactions,
        recommendations=recommendations,
    )

    report = render_markdown(run)

    assert report.count("### ") == 5


def test_serialize_run_returns_json_safe_values(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    run = AgentRun(
        run_id="run-1",
        analysis_date=date(2026, 7, 1),
        next_paycheck=date(2026, 7, 13),
        transactions=transactions,
        recommendations=[candidate],
    )

    serialized = serialize_run(run)

    assert serialized["analysis_date"] == "2026-07-01"
    assert serialized["recommendations"][0]["monthly_savings_usd"] == "16.49"
