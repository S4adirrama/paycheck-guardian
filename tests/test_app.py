"""End-to-end checks for the local Streamlit experience."""

from datetime import date
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from paycheck_guardian.models import RecommendationStatus


def _analyzed_demo() -> AppTest:
    """Load the deterministic demo through the same controls a person uses."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
    app.button(key="load_demo").click().run(timeout=20)
    app.button(key="analyze").click().run(timeout=20)
    return app


def _loaded_demo() -> AppTest:
    """Load the synthetic data without running the verified workflow yet."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
    app.button(key="load_demo").click().run(timeout=20)
    return app


def test_loaded_demo_exposes_retained_baseline_comparison() -> None:
    """The video baseline stage needs a real visible in-app comparison state."""
    app = _loaded_demo()
    metrics = json.loads(
        (Path(__file__).resolve().parents[1] / "artifacts/evaluation/metrics.json").read_text()
    )

    assert not app.exception
    assert any("Retained baseline comparison" in item.value for item in app.markdown)
    assert any(
        metric.label == "Baseline F1" and metric.value == metrics["baseline"]["f1"]
        for metric in app.metric
    )


def test_demo_reaches_verified_savings_plan() -> None:
    """Removing the demo-to-analysis flow would leave people without a reviewed plan."""
    app = _analyzed_demo()

    assert not app.exception
    assert any("Verified savings plan" in item.value for item in app.markdown)
    assert len(app.metric) >= 2


def test_analysis_and_next_paycheck_dates_are_user_controlled() -> None:
    """Replacing upload dates with fixed demo constants would make real analysis misleading."""
    app = _loaded_demo()

    assert not app.warning
    assert app.date_input(key="analysis_date").value == date(2026, 8, 1)
    assert app.date_input(key="next_paycheck").value == date(2026, 8, 15)
    app.date_input(key="analysis_date").set_value(date(2026, 8, 2)).run(timeout=20)
    app.date_input(key="next_paycheck").set_value(date(2026, 8, 20)).run(timeout=20)
    app.button(key="analyze").click().run(timeout=20)

    run = app.session_state["agent_run"]
    assert run.analysis_date == date(2026, 8, 2)
    assert run.next_paycheck == date(2026, 8, 20)


def test_cancellation_simulation_requires_explicit_human_approval() -> None:
    """Enabling simulation early would bypass the required human checkpoint."""
    app = _analyzed_demo()

    simulation = app.button(key="simulate_cancellation")
    assert simulation.disabled
    app.checkbox(key="approve_simulation").check().run(timeout=20)
    assert app.button(key="simulate_cancellation").disabled
    target = app.selectbox(key="cancellation_target").options[1]
    app.selectbox(key="cancellation_target").select(target).run(timeout=20)
    assert not app.button(key="simulate_cancellation").disabled
    app.button(key="simulate_cancellation").click().run(timeout=20)
    assert any("Cancellation simulated locally" in item.value for item in app.success)


def test_downloadable_markdown_report_includes_recommendation_evidence() -> None:
    """A report without evidence IDs could not be independently reviewed."""
    app = _analyzed_demo()

    run = app.session_state["agent_run"]
    assert len(app.get("download_button")) == 2
    assert "Evidence: " in app.session_state["markdown_report"]
    assert run.recommendations[0].evidence_transaction_ids[0] in app.session_state["markdown_report"]


def test_recommendation_currency_captions_render_as_text_not_math() -> None:
    """Unescaped currency delimiters must not turn the caption between them into math markup."""
    app = _analyzed_demo()

    recommendation_captions = [
        item.value for item in app.caption if item.value.startswith("Confidence:")
    ]
    assert recommendation_captions
    assert all(caption.count(r"\$") == 2 for caption in recommendation_captions)


def test_recommendation_can_be_dismissed_without_simulation() -> None:
    """A person must be able to decline a selected suggestion without creating an action."""
    app = _analyzed_demo()
    target = app.selectbox(key="cancellation_target").options[1]
    app.selectbox(key="cancellation_target").select(target).run(timeout=20)

    app.button(key="dismiss_recommendation").click().run(timeout=20)

    run = app.session_state["agent_run"]
    dismissed = next(item for item in run.recommendations if item.title == target)
    assert dismissed.status == RecommendationStatus.DISMISSED
    assert run.simulated_actions == []
    assert any(event.human_checkpoint == "cancellation_declined" for event in run.trajectory)
    assert any("dismissed" in item.value.lower() for item in app.success)
    assert target not in app.selectbox(key="cancellation_target").options
    assert target not in app.session_state["markdown_report"].split("## Recorded dispositions")[0]
    assert any("Recorded dispositions" in item.value for item in app.markdown)
    expected_total = sum(
        item.monthly_savings_usd
        for item in run.recommendations
        if item.status != RecommendationStatus.DISMISSED
    )
    monthly_metric = next(item for item in app.metric if item.label == "Monthly savings estimate")
    assert monthly_metric.value == f"${expected_total:.2f}"
