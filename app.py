"""A local-only Streamlit interface for the deterministic Paycheck Guardian workflow."""

from datetime import date, timedelta
import json
from pathlib import Path

import streamlit as st

from paycheck_guardian.agent import run_offline_agent, simulate_cancellation
from paycheck_guardian.models import (
    RecommendationAction,
    RecommendationKind,
    RecommendationStatus,
    Transaction,
)
from paycheck_guardian.parsers import InputValidationError, parse_bank_csv
from paycheck_guardian.reporting import (
    active_recommendations,
    active_savings_totals,
    dispositioned_recommendations,
    render_markdown,
    serialize_run,
)
from paycheck_guardian.uploads import parse_upload_batch


APP_ROOT = Path(__file__).resolve().parent
DEMO_CSV = APP_ROOT / "data" / "demo" / "transactions.csv"
METRICS_JSON = APP_ROOT / "artifacts" / "evaluation" / "metrics.json"
DEMO_ANALYSIS_DATE = date(2026, 8, 1)
DEMO_NEXT_PAYCHECK = date(2026, 8, 15)


def _transaction_rows(transactions: list[Transaction]) -> list[dict[str, str]]:
    """Format parsed records for review without changing their underlying values."""
    return [
        {
            "Date": transaction.date.isoformat(),
            "Merchant": transaction.merchant_normalized,
            "Amount": f"${transaction.amount_usd:.2f}",
            "Category": transaction.category.replace("_", " ").title(),
            "Evidence ID": transaction.transaction_id,
            "Source": transaction.source_reference,
        }
        for transaction in transactions
    ]


def _reset_analysis() -> None:
    for key in (
        "agent_run",
        "markdown_report",
        "report_json",
        "cancellation_target",
        "approve_simulation",
        "decision_notice",
    ):
        st.session_state.pop(key, None)


def _load_demo() -> list[Transaction]:
    with DEMO_CSV.open(encoding="utf-8", newline="") as source:
        return parse_bank_csv(source, DEMO_CSV.name)


def _retained_metrics() -> dict[str, object]:
    """Read the offline evaluation record used for the in-app comparison."""
    return json.loads(METRICS_JSON.read_text(encoding="utf-8"))


def _render_retained_baseline_comparison() -> None:
    """Show the measured baseline before a person runs the local workflow."""
    metrics = _retained_metrics()
    baseline = metrics["baseline"]
    final = metrics["final"]
    with st.expander("Retained baseline comparison"):
        st.markdown("### Retained baseline comparison")
        baseline_column, final_column, claims_column = st.columns(3)
        baseline_column.metric("Baseline F1", str(baseline["f1"]))
        final_column.metric("Verified workflow F1", str(final["f1"]))
        claims_column.metric("Final unsupported claims", str(final["unsupported_claims"]))
        st.caption(
            f"Offline evaluation on {len(metrics['case_fingerprints'])} synthetic cases. "
            "The baseline is a retained measurement, not a live financial recommendation."
        )


def _render_recommendations() -> None:
    run = st.session_state.get("agent_run")
    if run is None:
        return

    st.markdown("## Verified savings plan")
    active = active_recommendations(run)
    monthly_total, paycheck_total = active_savings_totals(run)
    monthly_metric, paycheck_metric = st.columns(2)
    monthly_metric.metric("Monthly savings estimate", f"${monthly_total:.2f}")
    paycheck_metric.metric("By next paycheck", f"${paycheck_total:.2f}")
    st.caption("Estimates are verified against the displayed evidence. Nothing is cancelled or changed.")

    notice = st.session_state.pop("decision_notice", None)
    if notice:
        st.success(notice)

    if not active:
        st.info("No verified savings opportunities were found in these transactions.")

    transaction_by_id = {row.transaction_id: row for row in run.transactions}
    for recommendation in active:
        with st.container(border=True):
            st.markdown(f"### {recommendation.title}")
            st.write(recommendation.rationale)
            st.caption(
                f"Confidence: {recommendation.confidence.value.title()} · "
                f"Monthly estimate: \\${recommendation.monthly_savings_usd:.2f} · "
                f"By next paycheck: \\${recommendation.next_paycheck_savings_usd:.2f}"
            )
            if recommendation.caveat:
                st.warning(recommendation.caveat, icon="⚠️")
            with st.expander(f"Evidence ({len(recommendation.evidence_transaction_ids)} transactions)"):
                for evidence_id in recommendation.evidence_transaction_ids:
                    transaction = transaction_by_id[evidence_id]
                    st.markdown(
                        f"`{evidence_id}` — {transaction.date.isoformat()} · "
                        f"{transaction.merchant_normalized} · ${transaction.amount_usd:.2f}"
                    )

    downloads = st.columns(2)
    downloads[0].download_button(
        "Download Markdown report",
        data=st.session_state["markdown_report"],
        file_name="paycheck-guardian-report.md",
        mime="text/markdown",
        key="download_markdown",
    )
    downloads[1].download_button(
        "Download JSON evidence record",
        data=st.session_state["report_json"],
        file_name="paycheck-guardian-run.json",
        mime="application/json",
        key="download_json",
    )

    with st.expander("How the agent reached this result"):
        st.caption("Offline trajectory: deterministic tools, verification, and any recorded human checkpoint.")
        st.dataframe(
            [
                {
                    "Step": event.event_type.replace("_", " "),
                    "Component": event.component,
                    "Tool": event.tool_name or "—",
                    "Attempt": event.attempt,
                    "Checkpoint": event.human_checkpoint or "—",
                }
                for event in run.trajectory
            ],
            width="stretch",
            hide_index=True,
        )

    dispositions = dispositioned_recommendations(run)
    if dispositions:
        st.markdown("### Recorded dispositions")
        for recommendation in dispositions:
            st.caption(
                f"{recommendation.title} · {recommendation.status.value.replace('_', ' ').title()}"
            )

    st.markdown("### Local cancellation simulation")
    cancellable = [
        item
        for item in active
        if item.kind == RecommendationKind.SUBSCRIPTION
        and item.verified_action == RecommendationAction.CANCEL_SUBSCRIPTION
        and item.status == RecommendationStatus.PROPOSED
    ]
    selection_options = [""] + [item.title for item in cancellable]
    recommendation_by_title = {item.title: item for item in cancellable}
    selected_title = st.selectbox(
        "Choose a verified subscription to simulate cancelling",
        options=selection_options,
        format_func=lambda item: "Select a verified recommendation" if not item else item,
        key="cancellation_target",
        disabled=not cancellable,
    )
    selected_id = recommendation_by_title[selected_title].recommendation_id if selected_title else ""
    approved = st.checkbox(
        "I understand this is only a simulation",
        key="approve_simulation",
        disabled=not cancellable,
    )
    dismiss_column, simulate_column = st.columns(2)
    if dismiss_column.button(
        "Dismiss recommendation",
        key="dismiss_recommendation",
        disabled=not selected_id,
    ):
        updated = simulate_cancellation(run, selected_id, approved=False)
        st.session_state["agent_run"] = updated
        st.session_state["markdown_report"] = render_markdown(updated)
        st.session_state["report_json"] = json.dumps(serialize_run(updated), indent=2)
        st.session_state["decision_notice"] = (
            "Recommendation dismissed for this local review. No action was taken."
        )
        st.rerun()
    if simulate_column.button(
        "Simulate cancellation locally",
        key="simulate_cancellation",
        disabled=not (selected_id and approved),
    ):
        updated = simulate_cancellation(run, selected_id, approved=True)
        st.session_state["agent_run"] = updated
        st.session_state["markdown_report"] = render_markdown(updated)
        st.session_state["report_json"] = json.dumps(serialize_run(updated), indent=2)
        st.session_state["decision_notice"] = (
            "Cancellation simulated locally. No merchant or bank was contacted."
        )
        st.rerun()


st.set_page_config(page_title="Paycheck Guardian", page_icon="🛡️", layout="wide")
st.title("🛡️ Paycheck Guardian")
st.markdown("Find evidence-backed ways to reduce spending before your next paycheck.")
st.info(
    "Privacy and demo notice: this is a local-only prototype. The Alex demo is synthetic, and "
    "uploads stay in this app session; no bank, merchant, receipt image, or account is contacted."
)

st.markdown("### 1. Review data")
st.caption(
    "Use the synthetic demo or combine local bank CSVs, receipt text fixtures, and supported "
    "bundled receipt PNGs. Files are merged in memory and duplicate charges are kept once."
)
if st.button("Load Alex's synthetic demo", key="load_demo"):
    st.session_state["transactions"] = _load_demo()
    st.session_state["data_source"] = "Alex's synthetic demo"
    st.session_state["analysis_date"] = DEMO_ANALYSIS_DATE
    st.session_state["next_paycheck"] = DEMO_NEXT_PAYCHECK
    st.session_state.pop("uploaded_content_digest", None)
    _reset_analysis()

uploads = st.file_uploader(
    "Upload one or more bank CSVs or supported receipts",
    type=["csv", "txt", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
    help=(
        "Bundled PNG receipt fixtures are verified by content and resolved through paired local "
        "text. Arbitrary images and JPEGs receive an offline-format error; no OCR service is used."
    ),
)
if uploads:
    try:
        batch = parse_upload_batch(uploads)
    except InputValidationError as error:
        st.error(str(error))
    else:
        if st.session_state.get("uploaded_content_digest") != batch.content_digest:
            st.session_state["transactions"] = batch.transactions
            st.session_state["data_source"] = batch.source_label
            st.session_state["uploaded_content_digest"] = batch.content_digest
            analysis_default = max(row.date for row in batch.transactions)
            st.session_state["analysis_date"] = analysis_default
            st.session_state["next_paycheck"] = analysis_default + timedelta(days=14)
            _reset_analysis()

transactions = st.session_state.get("transactions", [])
if transactions:
    st.success(f"Parsed {len(transactions)} transactions from {st.session_state['data_source']}.")
    st.dataframe(_transaction_rows(transactions), width="stretch", hide_index=True)
    _render_retained_baseline_comparison()
    st.markdown("### 2. Analyze")
    analysis_date = st.date_input(
        "Analysis date",
        value=st.session_state.get("analysis_date", DEMO_ANALYSIS_DATE),
        key="analysis_date",
        help="The date from which next-paycheck estimates are calculated.",
    )
    next_paycheck = st.date_input(
        "Next paycheck date",
        value=st.session_state.get("next_paycheck", DEMO_NEXT_PAYCHECK),
        key="next_paycheck",
    )
    invalid_window = next_paycheck < analysis_date
    if invalid_window:
        st.error("Next paycheck date must be on or after the analysis date.")
    if st.button("Analyze verified savings options", key="analyze", disabled=invalid_window):
        run = run_offline_agent(
            transactions,
            analysis_date=analysis_date,
            next_paycheck=next_paycheck,
            run_id="local-demo-run",
        )
        st.session_state["agent_run"] = run
        st.session_state["markdown_report"] = render_markdown(run)
        st.session_state["report_json"] = json.dumps(serialize_run(run), indent=2)
else:
    st.caption("Load the synthetic demo or a supported local file to preview parsed transactions.")

_render_recommendations()
