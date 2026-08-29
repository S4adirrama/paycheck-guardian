"""End-to-end checks for the local Streamlit experience."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def _analyzed_demo() -> AppTest:
    """Load the deterministic demo through the same controls a person uses."""
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
    app.button(key="load_demo").click().run(timeout=20)
    app.button(key="analyze").click().run(timeout=20)
    return app


def test_demo_reaches_verified_savings_plan() -> None:
    """Removing the demo-to-analysis flow would leave people without a reviewed plan."""
    app = _analyzed_demo()

    assert not app.exception
    assert any("Verified savings plan" in item.value for item in app.markdown)
    assert len(app.metric) >= 2


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
