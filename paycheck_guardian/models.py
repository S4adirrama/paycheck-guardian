"""Strict, serializable contracts shared across the application."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


CENT = Decimal("0.01")
Money = Annotated[Decimal, Field(gt=0, decimal_places=2)]


def money(value: Decimal | str | int) -> Decimal:
    """Round a USD value to cents using financial half-up rounding."""
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("value must be a valid USD amount") from error


class SourceType(StrEnum):
    BANK_CSV = "bank_csv"
    RECEIPT = "receipt"


class RecommendationKind(StrEnum):
    SUBSCRIPTION = "subscription"
    DUPLICATE = "duplicate"
    ANOMALY = "anomaly"
    BEHAVIORAL_PATTERN = "behavioral_pattern"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(StrEnum):
    PROPOSED = "proposed"
    REJECTED_BY_VERIFIER = "rejected_by_verifier"
    APPROVED_FOR_SIMULATION = "approved_for_simulation"
    DISMISSED = "dismissed"


class DomainModel(BaseModel):
    """Base model that rejects misspelled or undocumented fields."""

    model_config = ConfigDict(extra="forbid")


class Transaction(DomainModel):
    transaction_id: str = Field(min_length=1)
    date: date
    merchant_raw: str = Field(min_length=1)
    merchant_normalized: str = Field(min_length=1)
    amount_usd: Money
    category: str = Field(min_length=1)
    source_type: SourceType
    source_reference: str = Field(min_length=1)
    is_synthetic: bool

    @field_validator("amount_usd", mode="before")
    @classmethod
    def normalize_amount_usd(cls, value: Decimal | str | int) -> Decimal:
        return money(value)


class Evidence(DomainModel):
    transaction_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class Recommendation(DomainModel):
    recommendation_id: str = Field(min_length=1)
    kind: RecommendationKind
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_transaction_ids: list[str] = Field(min_length=1)
    monthly_savings_usd: Money
    next_paycheck_savings_usd: Money
    confidence: Confidence
    caveat: str | None = None
    status: RecommendationStatus = RecommendationStatus.PROPOSED

    @field_validator("monthly_savings_usd", "next_paycheck_savings_usd", mode="before")
    @classmethod
    def normalize_savings_usd(cls, value: Decimal | str | int) -> Decimal:
        return money(value)

    @field_validator("evidence_transaction_ids")
    @classmethod
    def evidence_ids_are_not_blank(cls, value: list[str]) -> list[str]:
        if any(not transaction_id.strip() for transaction_id in value):
            raise ValueError("evidence transaction IDs cannot be blank")
        return value


class TrajectoryEvent(DomainModel):
    timestamp: datetime
    run_id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    instruction: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, JsonValue] = Field(default_factory=dict)
    tool_result: dict[str, JsonValue] = Field(default_factory=dict)
    verification_feedback: list[str] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)
    human_checkpoint: str | None = None


class AgentRun(DomainModel):
    run_id: str = Field(min_length=1)
    analysis_date: date
    next_paycheck: date
    transactions: list[Transaction]
    recommendations: list[Recommendation] = Field(default_factory=list)
    trajectory: list[TrajectoryEvent] = Field(default_factory=list)
    simulated_actions: list[dict[str, JsonValue]] = Field(default_factory=list)


class GroundTruthOpportunity(DomainModel):
    kind: RecommendationKind
    target: str = Field(min_length=1)
    required_evidence_ids: list[str] = Field(min_length=1)
    monthly_savings_usd: Money
    expected_confidence: Confidence | None = None
    caveat_required: bool = False

    @field_validator("monthly_savings_usd", mode="before")
    @classmethod
    def normalize_monthly_savings_usd(cls, value: Decimal | str | int) -> Decimal:
        return money(value)


class EvaluationCase(DomainModel):
    case_id: str = Field(min_length=1)
    transactions: list[Transaction] = Field(min_length=1)
    ground_truth: list[GroundTruthOpportunity] = Field(default_factory=list)
    is_challenge: bool = False
