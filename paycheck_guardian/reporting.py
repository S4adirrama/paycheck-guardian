"""Human-readable, offline reports for verified recommendation runs."""

from typing import cast

from .models import AgentRun, Recommendation
from .verifier import verify_recommendation


DISCLAIMER = "Educational spending analysis only. No bank or subscription action was performed."


def _verified_recommendations(run: AgentRun) -> list[Recommendation]:
    verified = [
        result.recommendation
        for recommendation in run.recommendations
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


def render_markdown(run: AgentRun) -> str:
    """Render up to five independently verified recommendations as Markdown."""
    lines = ["# Paycheck Guardian report", ""]
    recommendations = _verified_recommendations(run)
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
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def serialize_run(run: AgentRun) -> dict[str, object]:
    """Return a JSON-safe run record without performing any external action."""
    return cast(dict[str, object], run.model_dump(mode="json"))
