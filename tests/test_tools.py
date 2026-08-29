from datetime import date, timedelta
from decimal import Decimal

import pytest

from paycheck_guardian.models import SourceType, Transaction
from paycheck_guardian.tools import (
    find_discretionary_patterns,
    find_duplicates,
    find_recurring,
    savings_before_paycheck,
)


def make_transaction(
    transaction_id: str,
    occurred_on: date,
    merchant: str,
    amount: str,
    category: str,
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
def rent_transactions() -> list[Transaction]:
    return [
        make_transaction("r1", date(2026, 5, 1), "Home Rental", "1200.00", "housing"),
        make_transaction("r2", date(2026, 6, 1), "Home Rental", "1200.00", "housing"),
    ]


@pytest.fixture
def duplicate_transactions() -> list[Transaction]:
    return [
        make_transaction("d1", date(2026, 7, 1), "Cinema", "18.00", "entertainment"),
        make_transaction("d2", date(2026, 7, 3), "Cinema", "18.00", "entertainment"),
        make_transaction("d3", date(2026, 7, 4), "Cinema", "18.01", "entertainment"),
        make_transaction("d4", date(2026, 7, 6), "Cinema", "18.00", "entertainment"),
    ]


def test_monthly_recurrence_accepts_aliases_and_price_drift(transactions: list[Transaction]) -> None:
    """A normalized merchant with up to 15% price drift remains a monthly candidate."""
    result = find_recurring(transactions)
    netflix = next(item for item in result if item.merchant == "Netflix")

    assert netflix.interval_days == 30
    assert netflix.monthly_amount == Decimal("16.49")
    assert len(netflix.evidence_ids) == 3


def test_essential_recurring_charge_is_marked_non_cancellable(
    rent_transactions: list[Transaction],
) -> None:
    """A recurring housing charge must never be surfaced as cancellable."""
    result = find_recurring(rent_transactions)[0]

    assert result.category == "housing"
    assert result.cancellable is False


def test_duplicate_requires_same_merchant_amount_and_close_date(
    duplicate_transactions: list[Transaction],
) -> None:
    """A price mismatch or a gap longer than two days cannot be a duplicate."""
    assert len(find_duplicates(duplicate_transactions)) == 1


def test_prorates_monthly_savings_to_next_paycheck() -> None:
    """Paycheck savings uses the 365-day monthly equivalence, rounded to cents."""
    assert savings_before_paycheck(
        Decimal("30.00"), date(2026, 8, 1), date(2026, 8, 15)
    ) == Decimal("13.81")


@pytest.mark.parametrize(
    ("gap", "expected_interval"),
    [(6, 7), (8, 7), (13, 14), (15, 14), (26, 30), (35, 30), (350, 365), (380, 365)],
)
def test_recurrence_accepts_each_interval_window_boundary(
    gap: int, expected_interval: int
) -> None:
    """Each inclusive recurrence window maps to its documented cadence."""
    first = date(2025, 1, 1)
    rows = [
        make_transaction("a", first, "Service", "10.00", "other"),
        make_transaction("b", first + timedelta(days=gap), "Service", "10.00", "other"),
    ]

    assert find_recurring(rows)[0].interval_days == expected_interval


def test_recurrence_rejects_amount_drift_over_fifteen_percent() -> None:
    """A larger price change must not be mistaken for a stable recurring charge."""
    rows = [
        make_transaction("a", date(2026, 1, 1), "Service", "10.00", "other"),
        make_transaction("b", date(2026, 2, 1), "Service", "11.51", "other"),
    ]

    assert find_recurring(rows) == []


def test_discretionary_pattern_requires_three_charges_in_thirty_days() -> None:
    """Three food-delivery charges in a 30-day window form an actionable pattern."""
    rows = [
        make_transaction("f1", date(2026, 7, 1), "DoorDash", "20.00", "food_delivery"),
        make_transaction("f2", date(2026, 7, 15), "DoorDash", "21.00", "food_delivery"),
        make_transaction("f3", date(2026, 7, 31), "DoorDash", "22.00", "food_delivery"),
        make_transaction("c1", date(2026, 7, 1), "Coffee Co", "4.00", "coffee"),
        make_transaction("c2", date(2026, 8, 2), "Coffee Co", "4.00", "coffee"),
        make_transaction("c3", date(2026, 8, 3), "Coffee Co", "4.00", "coffee"),
    ]

    patterns = find_discretionary_patterns(rows)

    assert [(item.merchant, item.category, item.charge_count) for item in patterns] == [
        ("DoorDash", "food_delivery", 3)
    ]
