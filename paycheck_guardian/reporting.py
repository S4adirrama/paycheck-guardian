"""Human-readable, offline reports for verified recommendation runs."""

from decimal import Decimal
from typing import cast

from .models import AgentRun, Recommendation, RecommendationStatus, money
from .verifier import verify_recommendation


DISCLAIMER = "Educational spending analysis only. No bank or subscription action was performed."


def active_recommendations(run: AgentRun) -> list[Recommendation]:
    """Return verifier-accepted recommendations that remain part of the active plan."""
    verified = [
        result.recommendation
        for recommendation in run.recommendations
        if recommendation.status != RecommendationStatus.DISMISSED
        if (
            result := verify_recommendation(
                recommendation,
                run.transactions,
                analysis_date=run.analysis_date,
                next_paycheck=run.next_paycheck,
            )
        ).accepted
    ]
    return sorted(
        cast(list[Recommendation], verified),
        key=lambda recommendation: (
            -recommendation.monthly_savings_usd,
            recommendation.recommendation_id,
        ),
    )[:5]


def active_savings_totals(run: AgentRun) -> tuple[Decimal, Decimal]:
    """Aggregate active estimates once per evidence row and cap them at observed spend."""
    transaction_by_id = {row.transaction_id: row for row in run.transactions}
    claimed: set[str] = set()
    monthly_total = Decimal("0")
    paycheck_total = Decimal("0")
    for recommendation in active_recommendations(run):
        unclaimed_ids = [
            evidence_id
            for evidence_id in recommendation.evidence_transaction_ids
            if evidence_id not in claimed
        ]
        observed = sum(
            (transaction_by_id[evidence_id].amount_usd for evidence_id in unclaimed_ids),
            Decimal("0"),
        )
        monthly_total += min(recommendation.monthly_savings_usd, observed)
        paycheck_total += min(recommendation.next_paycheck_savings_usd, observed)
        claimed.update(recommendation.evidence_transaction_ids)
    return money(monthly_total), money(paycheck_total)


def dispositioned_recommendations(run: AgentRun) -> list[Recommendation]:
    """Return canonical verifier-derived copy for recorded human dispositions."""
    dispositions: list[Recommendation] = []
    for recommendation in run.recommendations:
        if recommendation.status == RecommendationStatus.PROPOSED:
            continue
        result = verify_recommendation(
            recommendation,
            run.transactions,
            analysis_date=run.analysis_date,
            next_paycheck=run.next_paycheck,
        )
        if result.accepted and result.recommendation is not None:
            dispositions.append(result.recommendation)
    return dispositions


def render_markdown(run: AgentRun) -> str:
    """Render up to five independently verified recommendations as Markdown."""
    lines = ["# Paycheck Guardian report", ""]
    recommendations = active_recommendations(run)
    if not recommendations:
        lines.extend(["No verified savings recommendations were found.", ""])
    for recommendation in recommendations:
        lines.extend(
            [
                f"### {recommendation.title}",
                f"Action: {recommendation.rationale}",
                f"Evidence: {', '.join(recommendation.evidence_transaction_ids)}",
                f"Monthly estimate: ${recommendation.monthly_savings_usd:.2f}",
                f"Next-paycheck estimate: ${recommendation.next_paycheck_savings_usd:.2f}",
                f"Confidence: {recommendation.confidence}",
                f"Caveat: {recommendation.caveat or 'None recorded.'}",
                "",
            ]
        )
    dispositions = dispositioned_recommendations(run)
    if dispositions:
        lines.extend(["## Recorded dispositions", ""])
        for recommendation in dispositions:
            lines.append(f"- {recommendation.title} — {recommendation.status.value}")
        lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def serialize_run(run: AgentRun) -> dict[str, object]:
    """Return a JSON-safe run record without performing any external action."""
    serialized = cast(dict[str, object], run.model_dump(mode="json"))
    serialized["recommendations"] = [
        recommendation.model_dump(mode="json")
        for recommendation in active_recommendations(run)
    ]
    serialized["dispositions"] = [
        {
            "recommendation_id": recommendation.recommendation_id,
            "verified_target": recommendation.verified_target,
            "verified_action": recommendation.verified_action.value,
            "status": recommendation.status.value,
        }
        for recommendation in run.recommendations
        if recommendation.status != RecommendationStatus.PROPOSED
    ]
    return serialized
