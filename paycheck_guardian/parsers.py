"""Offline parsers for bank CSVs and synthetic receipt text fixtures."""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import TextIO

from .models import SourceType, Transaction, money
from .normalize import MerchantRule, load_aliases, normalize_merchant


class InputValidationError(ValueError):
    """Input that cannot safely become a deterministic transaction."""


_REQUIRED_COLUMNS = {"date", "description", "amount"}
_ALIASES = load_aliases(Path(__file__).resolve().parents[1] / "data" / "merchant_aliases.json")


def _error(source_name: str, row: int, message: str) -> InputValidationError:
    return InputValidationError(f"{source_name}:{row}: {message}")


def _parse_date(value: str, source_name: str, row: int) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise _error(source_name, row, "date must be ISO-8601 (YYYY-MM-DD)") from error


def _parse_amount(value: str, source_name: str, row: int) -> Decimal:
    try:
        amount = money(value)
    except (InvalidOperation, ValueError) as error:
        raise _error(source_name, row, "amount must be a positive USD amount") from error
    if not amount.is_finite() or amount <= 0:
        raise _error(source_name, row, "amount must be positive")
    return amount


def _transaction(
    *, source_name: str, row: int, transaction_date: date, description: str,
    amount: Decimal, source_type: SourceType,
) -> Transaction:
    merchant_raw = description.strip()
    if not merchant_raw:
        raise _error(source_name, row, "description must not be blank")
    merchant_normalized, category = normalize_merchant(merchant_raw, _ALIASES)
    hash_input = f"{source_name}|{row}|{transaction_date.isoformat()}|{merchant_raw}|{amount:.2f}"
    return Transaction(
        transaction_id=sha256(hash_input.encode("utf-8")).hexdigest()[:12],
        date=transaction_date,
        merchant_raw=merchant_raw,
        merchant_normalized=merchant_normalized,
        amount_usd=amount,
        category=category,
        source_type=source_type,
        source_reference=f"{source_name}:{row}",
        is_synthetic=True,
    )


def parse_bank_csv(stream: TextIO, source_name: str) -> list[Transaction]:
    """Parse a UTF-8 bank export that records positive USD spending amounts."""
    reader = csv.DictReader(stream)
    fields = set(reader.fieldnames or [])
    missing = sorted(_REQUIRED_COLUMNS - fields)
    if missing:
        raise _error(source_name, 1, f"missing required columns: {', '.join(missing)}")

    transactions: list[Transaction] = []
    for row_number, row in enumerate(reader, start=2):
        currency = (row.get("currency") or "USD").strip().upper()
        if currency != "USD":
            raise _error(source_name, row_number, "currency must be USD")
        transaction_date = _parse_date((row.get("date") or "").strip(), source_name, row_number)
        amount = _parse_amount((row.get("amount") or "").strip(), source_name, row_number)
        transactions.append(
            _transaction(
                source_name=source_name,
                row=row_number,
                transaction_date=transaction_date,
                description=row.get("description") or "",
                amount=amount,
                source_type=SourceType.BANK_CSV,
            )
        )
    return transactions


def parse_receipt_fixture(text: str, source_name: str) -> list[Transaction]:
    """Parse a deliberately small, deterministic synthetic receipt text format."""
    values: dict[str, str] = {}
    for line in StringIO(text):
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip().upper()] = value.strip()
    missing = [key for key in ("DATE", "MERCHANT", "TOTAL") if not values.get(key)]
    if missing:
        raise _error(source_name, 1, f"missing receipt fields: {', '.join(missing)}")
    currency = values.get("CURRENCY", "USD").upper()
    if currency != "USD":
        raise _error(source_name, 1, "currency must be USD")
    amount_value = values["TOTAL"].removeprefix("$").strip()
    return [
        _transaction(
            source_name=source_name,
            row=1,
            transaction_date=_parse_date(values["DATE"], source_name, 1),
            description=values["MERCHANT"],
            amount=_parse_amount(amount_value, source_name, 1),
            source_type=SourceType.RECEIPT,
        )
    ]
