from datetime import date
from dataclasses import replace
from decimal import Decimal

import pytest

from paycheck_guardian.agent import run_offline_agent, simulate_cancellation
from paycheck_guardian.models import Confidence, RecommendationStatus, SourceType, Transaction
from paycheck_guardian.trajectory import TrajectoryRecorder


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
def demo_transactions() -> list[Transaction]:
    return [
        make_transaction("n1", date(2026, 5, 1), "Netflix", "15.49", "streaming"),
        make_transaction("n2", date(2026, 5, 31), "Netflix", "16.49", "streaming"),
        make_transaction("n3", date(2026, 6, 30), "Netflix", "16.49", "streaming"),
        make_transaction("d1", date(2026, 7, 1), "Cinema", "18.00", "entertainment"),
        make_transaction("d2", date(2026, 7, 2), "Cinema", "18.00", "entertainment"),
        make_transaction("f1", date(2026, 7, 29), "DoorDash", "20.00", "food_delivery"),
        make_transaction("f2", date(2026, 7, 30), "DoorDash", "21.00", "food_delivery"),
        make_transaction("f3", date(2026, 7, 31), "DoorDash", "22.00", "food_delivery"),
    ]


@pytest.fixture
def run_with_subscription(demo_transactions: list[Transaction]):
    return run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "demo")


def test_agent_uses_tools_and_verifier(demo_transactions: list[Transaction]) -> None:
    """Removing a tool call or verifier invocation would leave the run incomplete."""
    run = run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "demo")

    assert run.recommendations
    assert all(item.status == RecommendationStatus.PROPOSED for item in run.recommendations)
    assert {event.tool_name for event in run.trajectory if event.tool_name} >= {
        "find_recurring",
        "find_duplicates",
        "find_discretionary_patterns",
        "find_anomalies",
        "summarize_categories",
        "verify_recommendation",
    }
    assert any(
        event.human_checkpoint == "recommendations_ready_for_human_review"
        for event in run.trajectory
    )


def test_trajectory_records_a_redacted_call_and_structured_result_for_each_tool(
    demo_transactions: list[Transaction],
) -> None:
    """A replayable trajectory needs an event before and after every deterministic tool call."""
    run = run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "events")

    for tool_name in (
        "find_recurring",
        "find_duplicates",
        "find_discretionary_patterns",
        "find_anomalies",
        "summarize_categories",
        "verify_recommendation",
    ):
        events = [event for event in run.trajectory if event.tool_name == tool_name]
        assert events[0].event_type == "tool_called"
        assert events[1].event_type == "tool_result"
        assert events[0].tool_input
        assert events[1].tool_result

    recurring_result = next(
        event
        for event in run.trajectory
        if event.tool_name == "find_recurring" and event.event_type == "tool_result"
    )
    assert recurring_result.tool_result["candidate_count"] >= 1
    assert recurring_result.tool_result["candidates"][0]["evidence_ids"]
    assert "merchant" not in recurring_result.tool_result["candidates"][0]
    assert "monthly_amount" not in recurring_result.tool_result["candidates"][0]


def test_failed_candidate_retries_once_then_is_omitted(
    monkeypatch: pytest.MonkeyPatch, demo_transactions: list[Transaction]
) -> None:
    """Feedback without a concrete correction omits the candidate after its first rejection."""
    from paycheck_guardian import agent
    from paycheck_guardian.verifier import VerificationResult

    original_verify = agent.verify_recommendation

    def reject_subscription(*args: object, **kwargs: object) -> VerificationResult:
        candidate = args[0]
        if getattr(candidate, "recommendation_id", None) == "subscription-netflix":
            return VerificationResult(False, None, ["candidate is not a Recommendation"])
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(agent, "verify_recommendation", reject_subscription)

    run = run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "retry")

    subscription_events = [
        event
        for event in run.trajectory
        if event.tool_name == "verify_recommendation"
        and event.tool_input.get("recommendation", {}).get("recommendation_id") == "subscription-netflix"
    ]
    assert [event.event_type for event in subscription_events] == ["tool_called", "tool_result"]
    assert "subscription-netflix" not in {item.recommendation_id for item in run.recommendations}
    assert not any(event.event_type == "candidate_retry" for event in run.trajectory)


def test_fixable_arithmetic_feedback_retries_with_a_corrected_tool_derived_candidate(
    monkeypatch: pytest.MonkeyPatch, demo_transactions: list[Transaction]
) -> None:
    """The sole retry must submit corrected savings, not the original candidate again."""
    from paycheck_guardian import agent

    original_draft = agent._subscription_draft

    def initially_incorrect_subscription(*args: object, **kwargs: object):
        draft = original_draft(*args, **kwargs)
        incorrect = draft.recommendation.model_copy(update={"monthly_savings_usd": Decimal("1.00")})
        return replace(draft, recommendation=incorrect)

    monkeypatch.setattr(agent, "_subscription_draft", initially_incorrect_subscription)

    run = run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "fixed")

    attempts = [
        event.tool_input["recommendation"]["recommendation_fingerprint"]
        for event in run.trajectory
        if event.tool_name == "verify_recommendation"
        and event.event_type == "tool_called"
        and event.tool_input["recommendation"]["recommendation_id"] == "subscription-netflix"
    ]
    results = [
        event.tool_result["accepted"]
        for event in run.trajectory
        if event.tool_name == "verify_recommendation"
        and event.event_type == "tool_result"
        and event.tool_input["recommendation"]["recommendation_id"] == "subscription-netflix"
    ]
    assert len(attempts) == 2
    assert attempts[0] != attempts[1]
    assert results == [False, True]
    assert "subscription-netflix" in {item.recommendation_id for item in run.recommendations}


def test_cancellation_requires_approval(run_with_subscription) -> None:
    """Declining the human checkpoint must not create even a simulated action."""
    subscription = next(
        item for item in run_with_subscription.recommendations if item.recommendation_id == "subscription-netflix"
    )

    unchanged = simulate_cancellation(run_with_subscription, subscription.recommendation_id, approved=False)

    assert unchanged.simulated_actions == []
    assert subscription.recommendation_id in {
        item.recommendation_id
        for item in unchanged.recommendations
        if item.status == RecommendationStatus.DISMISSED
    }
    assert any(event.human_checkpoint == "cancellation_declined" for event in unchanged.trajectory)


def test_approved_cancellation_only_records_a_local_simulation(run_with_subscription) -> None:
    """Approval changes only local run state; it cannot invoke an external cancellation."""
    verifier_events_before = len(
        [event for event in run_with_subscription.trajectory if event.tool_name == "verify_recommendation"]
    )
    approved = simulate_cancellation(run_with_subscription, "subscription-netflix", approved=True)

    assert approved.simulated_actions == [
        {"recommendation_id": "subscription-netflix", "action": "simulate_cancellation"}
    ]
    recommendation = next(item for item in approved.recommendations if item.recommendation_id == "subscription-netflix")
    assert recommendation.status == RecommendationStatus.APPROVED_FOR_SIMULATION
    assert any(event.human_checkpoint == "cancellation_approved" for event in approved.trajectory)
    verifier_events = [
        event for event in approved.trajectory if event.tool_name == "verify_recommendation"
    ]
    assert len(verifier_events) == verifier_events_before + 2
    assert [event.event_type for event in verifier_events[-2:]] == ["tool_called", "tool_result"]


def test_repeat_approval_is_idempotent(run_with_subscription) -> None:
    """Retrying a local approval must retain exactly one simulated action."""
    once = simulate_cancellation(run_with_subscription, "subscription-netflix", approved=True)

    twice = simulate_cancellation(once, "subscription-netflix", approved=True)

    assert twice.simulated_actions == [
        {"recommendation_id": "subscription-netflix", "action": "simulate_cancellation"}
    ]


def test_trajectory_recorder_redacts_sensitive_values_recursively() -> None:
    """Leaking a nested credential into a trajectory would make its JSON unsafe to retain."""
    recorder = TrajectoryRecorder("safe-run")

    event = recorder.record(
        component="agent",
        event_type="tool_called",
        tool_name="find_recurring",
        tool_input={"token": "top-secret", "nested": {"api_key": "another-secret"}},
        tool_result={"items": [{"authorization": "Bearer secret"}]},
    )

    assert event.tool_input == {"token": "***REDACTED***", "nested": {"api_key": "***REDACTED***"}}
    assert event.tool_result == {"items": [{"authorization": "***REDACTED***"}]}


def test_two_observation_monthly_recurrence_is_low_confidence_with_an_ambiguity_caveat() -> None:
    """Treating two monthly observations as high confidence would overstate thin evidence."""
    rows = [
        make_transaction("h1", date(2026, 6, 1), "Hulu", "7.99", "streaming"),
        make_transaction("h2", date(2026, 7, 1), "Hulu", "7.99", "streaming"),
    ]

    run = run_offline_agent(rows, date(2026, 8, 1), date(2026, 8, 15), "ambiguous")
    recommendation = next(item for item in run.recommendations if item.recommendation_id == "subscription-hulu")

    assert recommendation.confidence == Confidence.LOW
    assert recommendation.caveat and "Only two" in recommendation.caveat


def test_verifier_receives_and_rejects_essential_recurring_draft() -> None:
    """Omitting an essential draft before verification would leave the safeguard unmeasured."""
    rows = [
        make_transaction("r1", date(2026, 6, 1), "Rent", "1500.00", "housing"),
        make_transaction("r2", date(2026, 7, 1), "Rent", "1500.00", "housing"),
    ]

    run = run_offline_agent(rows, date(2026, 8, 1), date(2026, 8, 15), "rent")
    rent_results = [
        event.tool_result
        for event in run.trajectory
        if event.tool_name == "verify_recommendation"
        and event.event_type == "tool_result"
        and event.tool_input["recommendation"]["recommendation_id"] == "subscription-rent"
    ]

    assert run.recommendations == []
    assert rent_results and rent_results[0]["accepted"] is False
    assert any("essential" in reason for reason in rent_results[0]["reasons"])


@pytest.mark.parametrize(
    ("merchant", "category"),
    [("Verizon", "telecom"), ("Mystery Utility", "other")],
)
def test_agent_omits_non_allowlisted_recurring_cancellation(
    merchant: str, category: str
) -> None:
    """The final plan must not expose telecom or unknown recurrence as cancellable."""
    rows = [
        make_transaction("r1", date(2026, 6, 1), merchant, "40.00", category),
        make_transaction("r2", date(2026, 7, 1), merchant, "40.00", category),
    ]

    run = run_offline_agent(rows, date(2026, 8, 1), date(2026, 8, 15), "unsafe")

    assert run.recommendations == []
    rejection = next(
        event
        for event in run.trajectory
        if event.tool_name == "verify_recommendation" and event.event_type == "tool_result"
    )
    assert rejection.tool_result["accepted"] is False


def test_overlapping_doordash_evidence_is_not_counted_as_multiple_savings_actions() -> None:
    """One set of DoorDash charges cannot fund both duplicate and pattern totals."""
    rows = [
        make_transaction("d1", date(2026, 7, 1), "DoorDash", "20.00", "food_delivery"),
        make_transaction("d2", date(2026, 7, 2), "DoorDash", "20.00", "food_delivery"),
        make_transaction("d3", date(2026, 7, 3), "DoorDash", "20.00", "food_delivery"),
    ]

    run = run_offline_agent(rows, date(2026, 8, 1), date(2026, 8, 15), "overlap")

    assert [(item.kind.value, item.monthly_savings_usd) for item in run.recommendations] == [
        ("behavioral_pattern", Decimal("60.00"))
    ]
    claimed_ids = [
        evidence_id
        for recommendation in run.recommendations
        for evidence_id in recommendation.evidence_transaction_ids
    ]
    assert len(claimed_ids) == len(set(claimed_ids))
    assert sum((item.monthly_savings_usd for item in run.recommendations), Decimal("0")) <= sum(
        (row.amount_usd for row in rows), Decimal("0")
    )


def test_real_like_input_values_are_absent_from_trajectory() -> None:
    """Tool auditing may retain fingerprints and IDs, never raw uploaded financial fields."""
    rows = [
        Transaction(
            transaction_id="private-1",
            date=date(2026, 6, 1),
            merchant_raw="Dr Personal Merchant 9911",
            merchant_normalized="Dr Personal Merchant",
            amount_usd="43.21",
            category="streaming",
            source_type=SourceType.BANK_CSV,
            source_reference="real-payroll-export.csv:2",
            is_synthetic=False,
        ),
        Transaction(
            transaction_id="private-2",
            date=date(2026, 7, 1),
            merchant_raw="Dr Personal Merchant 9911",
            merchant_normalized="Dr Personal Merchant",
            amount_usd="43.21",
            category="streaming",
            source_type=SourceType.BANK_CSV,
            source_reference="real-payroll-export.csv:3",
            is_synthetic=False,
        ),
    ]

    run = run_offline_agent(rows, date(2026, 8, 1), date(2026, 8, 15), "private")
    serialized = " ".join(str(event.model_dump(mode="json")) for event in run.trajectory)

    for private_value in (
        "Dr Personal Merchant",
        "Dr Personal Merchant 9911",
        "real-payroll-export.csv",
        "2026-06-01",
        "2026-07-01",
        "43.21",
    ):
        assert private_value not in serialized
    assert "transaction_fingerprint" in serialized
    assert "private-1" in serialized
