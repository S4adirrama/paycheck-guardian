from datetime import date

import pytest

from paycheck_guardian.agent import run_offline_agent, simulate_cancellation
from paycheck_guardian.models import RecommendationStatus, SourceType, Transaction
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
        "verify_recommendation",
    }
    assert any(
        event.human_checkpoint == "recommendations_ready_for_human_review"
        for event in run.trajectory
    )


def test_failed_candidate_retries_once_then_is_omitted(
    monkeypatch: pytest.MonkeyPatch, demo_transactions: list[Transaction]
) -> None:
    """An uncorrectable verifier rejection cannot create endless retry attempts."""
    from paycheck_guardian import agent
    from paycheck_guardian.verifier import VerificationResult

    original_verify = agent.verify_recommendation
    calls = 0

    def reject_one_candidate(*args: object, **kwargs: object) -> VerificationResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return VerificationResult(False, None, ["evidence does not match a deterministic recommendation target"])
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(agent, "verify_recommendation", reject_one_candidate)

    run = run_offline_agent(demo_transactions, date(2026, 8, 1), date(2026, 8, 15), "retry")

    assert max(event.attempt for event in run.trajectory) <= 2
    assert any(event.event_type == "candidate_rejected" for event in run.trajectory)


def test_cancellation_requires_approval(run_with_subscription) -> None:
    """Declining the human checkpoint must not create even a simulated action."""
    subscription = next(
        item for item in run_with_subscription.recommendations if item.recommendation_id == "subscription-netflix"
    )

    unchanged = simulate_cancellation(run_with_subscription, subscription.recommendation_id, approved=False)

    assert unchanged.simulated_actions == []
    assert unchanged.recommendations[0].status == RecommendationStatus.PROPOSED
    assert any(event.human_checkpoint == "cancellation_declined" for event in unchanged.trajectory)


def test_approved_cancellation_only_records_a_local_simulation(run_with_subscription) -> None:
    """Approval changes only local run state; it cannot invoke an external cancellation."""
    approved = simulate_cancellation(run_with_subscription, "subscription-netflix", approved=True)

    assert approved.simulated_actions == [
        {"recommendation_id": "subscription-netflix", "action": "simulate_cancellation"}
    ]
    recommendation = next(item for item in approved.recommendations if item.recommendation_id == "subscription-netflix")
    assert recommendation.status == RecommendationStatus.APPROVED_FOR_SIMULATION
    assert any(event.human_checkpoint == "cancellation_approved" for event in approved.trajectory)


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
