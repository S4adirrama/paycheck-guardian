"""Deterministic, evidence-first spending analysis helpers."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from .models import Transaction, money


ESSENTIAL_CATEGORIES = frozenset(
    {"housing", "utilities", "insurance", "healthcare", "debt", "telecom"}
)
CANCELLABLE_CATEGORIES = frozenset(
    {"streaming", "music", "cloud_storage", "subscription", "fitness"}
)
DISCRETIONARY_CATEGORIES = frozenset({"food_delivery", "coffee", "entertainment"})


@dataclass(frozen=True)
class RecurringCandidate:
    merchant: str
    category: str
    interval_days: int
    monthly_amount: Decimal
    evidence_ids: list[str]
    cancellable: bool


@dataclass(frozen=True)
class DuplicateCandidate:
    merchant: str
    amount: Decimal
    evidence_ids: list[str]


@dataclass(frozen=True)
class SpendingPattern:
    merchant: str
    category: str
    charge_count: int
    monthly_amount: Decimal
    evidence_ids: list[str]


@dataclass(frozen=True)
class AnomalyCandidate:
    merchant: str
    category: str
    observed_amount: Decimal
    typical_amount: Decimal
    monthly_amount: Decimal
    evidence_ids: list[str]


@dataclass(frozen=True)
class CategorySummary:
    category: str
    charge_count: int
    total_amount: Decimal
    evidence_ids: list[str]


def _sorted(transactions: list[Transaction]) -> list[Transaction]:
    return sorted(transactions, key=lambda row: (row.date, row.transaction_id))


def _interval_days(median_gap: float) -> int | None:
    if 6 <= median_gap <= 8:
        return 7
    if 13 <= median_gap <= 15:
        return 14
    if 26 <= median_gap <= 35:
        return 30
    if 350 <= median_gap <= 380:
        return 365
    return None


def _monthly_equivalent(amount: Decimal, interval_days: int) -> Decimal:
    if interval_days == 7:
        return money(amount * Decimal(52) / Decimal(12))
    if interval_days == 14:
        return money(amount * Decimal(26) / Decimal(12))
    if interval_days == 365:
        return money(amount / Decimal(12))
    return money(amount)


def find_recurring(transactions: list[Transaction]) -> list[RecurringCandidate]:
    """Return stable merchant charges with a supported cadence and <=15% price drift."""
    by_merchant: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for row in transactions:
        by_merchant[(row.merchant_normalized, row.category)].append(row)

    candidates: list[RecurringCandidate] = []
    for (merchant, category), rows in sorted(by_merchant.items()):
        evidence = _sorted(rows)
        if len(evidence) < 2:
            continue
        gaps = [
            (current.date - previous.date).days
            for previous, current in zip(evidence, evidence[1:])
        ]
        interval = _interval_days(median(gaps))
        if interval is None:
            continue
        amounts = [row.amount_usd for row in evidence]
        if max(amounts) - min(amounts) > min(amounts) * Decimal("0.15"):
            continue
        typical_amount = money(median(amounts))
        candidates.append(
            RecurringCandidate(
                merchant=merchant,
                category=category,
                interval_days=interval,
                monthly_amount=_monthly_equivalent(typical_amount, interval),
                evidence_ids=[row.transaction_id for row in evidence],
                cancellable=category in CANCELLABLE_CATEGORIES,
            )
        )
    return candidates


def find_duplicates(transactions: list[Transaction]) -> list[DuplicateCandidate]:
    """Return each pair sharing merchant, cent amount, and a two-day date window."""
    by_charge: dict[tuple[str, Decimal], list[Transaction]] = defaultdict(list)
    for row in transactions:
        by_charge[(row.merchant_normalized, row.amount_usd)].append(row)

    candidates: list[DuplicateCandidate] = []
    for (merchant, amount), rows in sorted(by_charge.items()):
        evidence = _sorted(rows)
        for first, second in zip(evidence, evidence[1:]):
            if (second.date - first.date).days <= 2:
                candidates.append(
                    DuplicateCandidate(
                        merchant=merchant,
                        amount=amount,
                        evidence_ids=[first.transaction_id, second.transaction_id],
                    )
                )
    return candidates


def find_discretionary_patterns(transactions: list[Transaction]) -> list[SpendingPattern]:
    """Return three-or-more discretionary purchases made within a 30-day window."""
    by_merchant: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for row in transactions:
        if row.category in DISCRETIONARY_CATEGORIES:
            by_merchant[(row.merchant_normalized, row.category)].append(row)

    patterns: list[SpendingPattern] = []
    for (merchant, category), rows in sorted(by_merchant.items()):
        evidence = _sorted(rows)
        for start, first in enumerate(evidence):
            window = [row for row in evidence[start:] if (row.date - first.date).days <= 30]
            if len(window) >= 3:
                patterns.append(
                    SpendingPattern(
                        merchant=merchant,
                        category=category,
                        charge_count=len(window),
                        monthly_amount=money(sum((row.amount_usd for row in window), Decimal("0"))),
                        evidence_ids=[row.transaction_id for row in window],
                    )
                )
                break
    return patterns


def find_anomalies(transactions: list[Transaction]) -> list[AnomalyCandidate]:
    """Find one material high outlier per merchant against at least two stable observations."""
    by_merchant: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for row in transactions:
        by_merchant[(row.merchant_normalized, row.category)].append(row)

    anomalies: list[AnomalyCandidate] = []
    for (merchant, category), rows in sorted(by_merchant.items()):
        evidence = _sorted(rows)
        if len(evidence) < 3:
            continue
        largest = max(evidence, key=lambda row: (row.amount_usd, row.date, row.transaction_id))
        comparison = [row.amount_usd for row in evidence if row is not largest]
        typical = money(median(comparison))
        excess = money(largest.amount_usd - typical)
        if largest.amount_usd < typical * Decimal("2") or excess < Decimal("10.00"):
            continue
        anomalies.append(
            AnomalyCandidate(
                merchant=merchant,
                category=category,
                observed_amount=largest.amount_usd,
                typical_amount=typical,
                monthly_amount=excess,
                evidence_ids=[row.transaction_id for row in evidence],
            )
        )
    return anomalies


def summarize_categories(transactions: list[Transaction]) -> list[CategorySummary]:
    """Return deterministic category totals with complete evidence membership."""
    by_category: dict[str, list[Transaction]] = defaultdict(list)
    for row in transactions:
        by_category[row.category].append(row)
    return [
        CategorySummary(
            category=category,
            charge_count=len(evidence),
            total_amount=money(sum((row.amount_usd for row in evidence), Decimal("0"))),
            evidence_ids=[row.transaction_id for row in evidence],
        )
        for category, rows in sorted(by_category.items())
        if (evidence := _sorted(rows))
    ]


def savings_before_paycheck(
    monthly: Decimal, analysis_date: date, next_paycheck: date
) -> Decimal:
    """Prorate a monthly estimate through the next paycheck using a 365-day year."""
    days_to_paycheck = max((next_paycheck - analysis_date).days, 0)
    return money(money(monthly) * Decimal(days_to_paycheck) * Decimal(12) / Decimal(365))
