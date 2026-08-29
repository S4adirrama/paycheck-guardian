from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from paycheck_guardian.models import Transaction, money


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
