"""A local-only Streamlit interface for the deterministic Paycheck Guardian workflow."""

from datetime import date
from decimal import Decimal
import json
from io import StringIO
from pathlib import Path

import streamlit as st

from paycheck_guardian.agent import run_offline_agent, simulate_cancellation
from paycheck_guardian.models import RecommendationKind, Transaction
from paycheck_guardian.parsers import InputValidationError, parse_bank_csv, parse_receipt_fixture
from paycheck_guardian.reporting import render_markdown, serialize_run


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
    for key in ("agent_run", "markdown_report", "report_json"):
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


def _parse_upload(upload: object) -> tuple[list[Transaction], str]:
    """Accept only the documented deterministic upload formats."""
    name = getattr(upload, "name", "uploaded file")
    suffix = Path(name).suffix.lower()
    raw = getattr(upload, "getvalue")()
    if suffix in {".png", ".jpg", ".jpeg"}:
        raise InputValidationError(
            f"{name}: receipt images cannot be read here because arbitrary OCR is not available. "
            "Upload the matching deterministic .txt receipt fixture instead."
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputValidationError(f"{name}: upload must be UTF-8 text.") from error
    if suffix == ".csv":
        return parse_bank_csv(StringIO(text), name), "Uploaded bank CSV"
    if suffix == ".txt":
        return parse_receipt_fixture(text, name), "Uploaded receipt text fixture"
    raise InputValidationError(f"{name}: upload a .csv bank export or deterministic .txt receipt fixture.")


def _render_recommendations() -> None:
    run = st.session_state.get("agent_run")
    if run is None:
        return

    st.markdown("## Verified savings plan")
    monthly_total = sum((item.monthly_savings_usd for item in run.recommendations), Decimal("0"))
    paycheck_total = sum((item.next_paycheck_savings_usd for item in run.recommendations), Decimal("0"))
    monthly_metric, paycheck_metric = st.columns(2)
    monthly_metric.metric("Monthly savings estimate", f"${monthly_total:.2f}")
    paycheck_metric.metric("By next paycheck", f"${paycheck_total:.2f}")
    st.caption("Estimates are verified against the displayed evidence. Nothing is cancelled or changed.")

    if not run.recommendations:
        st.info("No verified savings opportunities were found in these transactions.")
        return

    transaction_by_id = {row.transaction_id: row for row in run.transactions}
    for recommendation in run.recommendations:
        with st.container(border=True):
            st.markdown(f"### {recommendation.title}")
            st.write(recommendation.rationale)
            st.caption(
                f"Confidence: {recommendation.confidence.value.title()} · "
                f"Monthly estimate: ${recommendation.monthly_savings_usd:.2f} · "
                f"By next paycheck: ${recommendation.next_paycheck_savings_usd:.2f}"
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
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Local cancellation simulation")
    cancellable = [item for item in run.recommendations if item.kind == RecommendationKind.SUBSCRIPTION]
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
    if st.button(
        "Simulate cancellation locally",
        key="simulate_cancellation",
        disabled=not (selected_id and approved),
    ):
        updated = simulate_cancellation(run, selected_id, approved=True)
        st.session_state["agent_run"] = updated
        st.session_state["markdown_report"] = render_markdown(updated)
        st.session_state["report_json"] = json.dumps(serialize_run(updated), indent=2)
        st.success("Cancellation simulated locally. No merchant or bank was contacted.")


st.set_page_config(page_title="Paycheck Guardian", page_icon="🛡️", layout="wide")
st.title("🛡️ Paycheck Guardian")
st.markdown("Find evidence-backed ways to reduce spending before your next paycheck.")
st.info(
    "Privacy and demo notice: this is a local-only prototype. The Alex demo is synthetic, and "
    "uploads stay in this app session; no bank, merchant, receipt image, or account is contacted."
)

st.markdown("### 1. Review data")
st.caption("Use the synthetic demo or upload a UTF-8 bank CSV / deterministic receipt text fixture.")
if st.button("Load Alex's synthetic demo", key="load_demo"):
    st.session_state["transactions"] = _load_demo()
    st.session_state["data_source"] = "Alex's synthetic demo"
    _reset_analysis()

upload = st.file_uploader(
    "Upload a bank CSV or receipt text fixture",
    type=["csv", "txt", "png", "jpg", "jpeg"],
    help="Images are not OCR'd. Upload the deterministic .txt fixture paired with a receipt image.",
)
if upload is not None:
    try:
        uploaded_transactions, data_source = _parse_upload(upload)
    except InputValidationError as error:
        st.error(str(error))
    else:
        if st.session_state.get("uploaded_file_name") != upload.name:
            st.session_state["transactions"] = uploaded_transactions
            st.session_state["data_source"] = data_source
            st.session_state["uploaded_file_name"] = upload.name
            _reset_analysis()

transactions = st.session_state.get("transactions", [])
if transactions:
    st.success(f"Parsed {len(transactions)} transactions from {st.session_state['data_source']}.")
    st.dataframe(_transaction_rows(transactions), use_container_width=True, hide_index=True)
    _render_retained_baseline_comparison()
    st.markdown("### 2. Analyze")
    if st.button("Analyze verified savings options", key="analyze"):
        run = run_offline_agent(
            transactions,
            analysis_date=DEMO_ANALYSIS_DATE,
            next_paycheck=DEMO_NEXT_PAYCHECK,
            run_id="local-demo-run",
        )
        st.session_state["agent_run"] = run
        st.session_state["markdown_report"] = render_markdown(run)
        st.session_state["report_json"] = json.dumps(serialize_run(run), indent=2)
else:
    st.caption("Load the synthetic demo or a supported local file to preview parsed transactions.")

_render_recommendations()
