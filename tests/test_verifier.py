from datetime import date
from decimal import Decimal

import pytest

from paycheck_guardian.models import (
    AgentRun,
    Confidence,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
    SourceType,
    Transaction,
)
from paycheck_guardian.reporting import active_savings_totals, render_markdown, serialize_run
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
        verified_target="Netflix",
        verified_action="cancel_subscription",
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
        verified_target="Home Rental",
        verified_action="cancel_subscription",
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


def test_verifier_rejects_inflated_next_paycheck_savings(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.next_paycheck_savings_usd = Decimal("999.00")

    result = verify_recommendation(
        candidate,
        transactions,
        analysis_date=date(2026, 7, 1),
        next_paycheck=date(2026, 7, 13),
    )

    assert result.accepted is False
    assert any("next-paycheck" in reason for reason in result.reasons)


def test_verifier_prorates_from_recomputed_monthly_savings(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.monthly_savings_usd = Decimal("16.50")
    candidate.next_paycheck_savings_usd = Decimal("198.00")

    result = verify_recommendation(
        candidate,
        transactions,
        analysis_date=date(2026, 1, 1),
        next_paycheck=date(2027, 1, 1),
    )

    assert result.accepted is False
    assert any("next-paycheck" in reason for reason in result.reasons)


def test_verifier_rejects_duplicate_evidence_ids_for_high_confidence(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    candidate.evidence_transaction_ids = ["n1", "n2", "n2"]

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert any("duplicate evidence" in reason for reason in result.reasons)


def test_verifier_blocks_cancellation_of_essential_payment(
    rent_candidate: Recommendation, rent_transactions: list[Transaction]
) -> None:
    result = verify_recommendation(rent_candidate, rent_transactions)

    assert result.accepted is False
    assert any("essential" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    ("merchant", "category"),
    [("Verizon", "telecom"), ("Mystery Utility", "other")],
)
def test_verifier_blocks_recurring_merchants_outside_cancellation_allowlist(
    candidate: Recommendation, merchant: str, category: str
) -> None:
    """A monthly cadence cannot prove that an unknown or telecom target is cancellable."""
    rows = [
        make_transaction("x1", date(2026, 6, 1), merchant, "40.00", category),
        make_transaction("x2", date(2026, 7, 1), merchant, "40.00", category),
    ]
    unsafe = candidate.model_copy(
        update={
            "recommendation_id": "unsafe-recurring",
            "verified_target": merchant,
            "evidence_transaction_ids": ["x1", "x2"],
            "monthly_savings_usd": Decimal("40.00"),
            "next_paycheck_savings_usd": Decimal("18.41"),
            "confidence": Confidence.LOW,
        }
    )

    result = verify_recommendation(
        unsafe,
        rows,
        analysis_date=date(2026, 8, 1),
        next_paycheck=date(2026, 8, 15),
    )

    assert result.accepted is False
    assert any("allowlist" in reason for reason in result.reasons)


def test_verifier_canonicalizes_display_copy_from_verified_target_and_action(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    """Free-form copy naming a different merchant must never reach a displayed result."""
    candidate.title = "Cancel Verizon immediately"
    candidate.rationale = "The draft claims Verizon is the target."

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is True
    assert result.recommendation is not None
    assert result.recommendation.title == "Review cancelling Netflix"
    assert "Verizon" not in result.recommendation.title
    assert "Verizon" not in result.recommendation.rationale


def test_verifier_rejects_structured_target_that_does_not_match_evidence(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    """Changing the structured target must invalidate otherwise matching evidence."""
    candidate.verified_target = "Verizon"

    result = verify_recommendation(candidate, transactions)

    assert result.accepted is False
    assert any("target" in reason for reason in result.reasons)


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


def test_markdown_and_serialized_report_exclude_dismissed_items_from_active_plan(
    candidate: Recommendation, transactions: list[Transaction]
) -> None:
    """A dismissed suggestion belongs in dispositions, not active savings or selectors."""
    dismissed = candidate.model_copy(update={"status": RecommendationStatus.DISMISSED})
    run = AgentRun(
        run_id="run-dismissed",
        analysis_date=date(2026, 7, 1),
        next_paycheck=date(2026, 7, 13),
        transactions=transactions,
        recommendations=[dismissed],
    )

    markdown = render_markdown(run)
    serialized = serialize_run(run)

    assert "No verified savings recommendations were found" in markdown
    assert "Recorded dispositions" in markdown
    assert "Review cancelling Netflix" in markdown
    assert serialized["recommendations"] == []
    assert serialized["dispositions"] == [
        {
            "recommendation_id": "cancel-netflix",
            "verified_target": "Netflix",
            "verified_action": "cancel_subscription",
            "status": "dismissed",
        }
    ]


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


def test_verifier_accepts_anomaly_only_when_tool_evidence_and_excess_match() -> None:
    """An anomaly recommendation must be independently reconstructed from the raw rows."""
    rows = [
        make_transaction("g1", date(2026, 5, 1), "Grocery Mart", "20.00", "groceries"),
        make_transaction("g2", date(2026, 6, 1), "Grocery Mart", "21.00", "groceries"),
        make_transaction("g3", date(2026, 7, 1), "Grocery Mart", "75.00", "groceries"),
    ]
    candidate = Recommendation(
        recommendation_id="anomaly-grocery-mart",
        kind=RecommendationKind.ANOMALY,
        verified_target="Grocery Mart",
        verified_action="review_anomaly",
        title="Untrusted anomaly title",
        rationale="Untrusted anomaly rationale",
        evidence_transaction_ids=["g1", "g2", "g3"],
        monthly_savings_usd="54.50",
        next_paycheck_savings_usd="25.08",
        confidence="medium",
        caveat="Confirm whether the unusual charge was expected.",
    )

    result = verify_recommendation(
        candidate,
        rows,
        analysis_date=date(2026, 8, 1),
        next_paycheck=date(2026, 8, 15),
    )

    assert result.accepted is True
    assert result.recommendation is not None
    assert result.recommendation.title == "Review unusual Grocery Mart charge"


def test_displayed_aggregate_is_capped_at_unique_observed_spending() -> None:
    """A monthly projection may exceed two observed weeks, but the displayed sum may not."""
    rows = [
        make_transaction("w1", date(2026, 7, 1), "Netflix", "10.00", "streaming"),
        make_transaction("w2", date(2026, 7, 8), "Netflix", "10.00", "streaming"),
    ]
    recommendation = Recommendation(
        recommendation_id="weekly-netflix",
        kind=RecommendationKind.SUBSCRIPTION,
        verified_target="Netflix",
        verified_action="cancel_subscription",
        title="Untrusted",
        rationale="Untrusted",
        evidence_transaction_ids=["w1", "w2"],
        monthly_savings_usd="43.33",
        next_paycheck_savings_usd="19.94",
        confidence="medium",
        caveat="Confirm the weekly recurrence before cancelling.",
    )
    run = AgentRun(
        run_id="weekly",
        analysis_date=date(2026, 8, 1),
        next_paycheck=date(2026, 8, 15),
        transactions=rows,
        recommendations=[recommendation],
    )

    monthly_total, paycheck_total = active_savings_totals(run)

    assert monthly_total == Decimal("20.00")
    assert paycheck_total == Decimal("19.94")
