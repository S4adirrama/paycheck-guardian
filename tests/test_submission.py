"""Integrity checks for the evidence-backed hackathon submission."""

import json
import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _renderer_module() -> object:
    specification = importlib.util.spec_from_file_location(
        "render_submission_docs", ROOT / "scripts" / "render_submission_docs.py"
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_readme_contains_required_hackathon_sections() -> None:
    """The submission narrative must disclose both value and known limits."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    for heading in [
        "Problem & User Value",
        "Measured Improvement",
        "Improvement Changelog",
        "Main Failure Mode",
        "Hot Take",
    ]:
        assert heading in text


def test_documented_metrics_equal_machine_readable_metrics() -> None:
    """README figures must be generated from the retained evaluation result."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"{float(metrics['final']['f1']):.4f}" in readme
    assert f"{float(metrics['baseline']['f1']):.4f}" in readme
    assert str(metrics["final"]["unsupported_claims"]) in readme


def test_renderer_derives_case_count_from_retained_fingerprints() -> None:
    """A hard-coded evaluation total would become stale when retained cases change."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    metrics["case_fingerprints"].pop(next(iter(metrics["case_fingerprints"])))
    renderer = _renderer_module()

    readme = renderer._render_readme(metrics)

    assert f"covers {len(metrics['case_fingerprints'])} synthetic cases" in readme


def test_trajectories_have_instructions_tools_feedback_and_checkpoint() -> None:
    """The representative final run must make the verified workflow inspectable."""
    events = json.loads((ROOT / "artifacts/trajectories/final.json").read_text(encoding="utf-8"))
    types = {event["event_type"] for event in events}

    assert {"instruction", "tool_call", "tool_result", "verification", "human_checkpoint"} <= types


def test_renderer_generates_demo_report_and_representative_challenge_artifacts() -> None:
    """Rendering must produce documents from current evidence without external services."""
    result = subprocess.run(
        [sys.executable, "scripts/render_submission_docs.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for relative_path in [
        "README.md",
        "REPRODUCTION.md",
        "artifacts/trajectories/baseline.json",
        "artifacts/trajectories/final.json",
        "artifacts/reports/demo_report.md",
        "artifacts/reports/demo_report.json",
    ]:
        assert (ROOT / relative_path).is_file()

    report = json.loads((ROOT / "artifacts/reports/demo_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == "alex-demo-run"
    assert all(row["is_synthetic"] for row in report["transactions"])


def test_submission_artifacts_do_not_contain_credential_markers() -> None:
    """Public submission material must stay redacted and free of credential-shaped text."""
    public_paths = [
        ROOT / "README.md",
        ROOT / "REPRODUCTION.md",
        ROOT / "artifacts/trajectories/baseline.json",
        ROOT / "artifacts/trajectories/final.json",
        ROOT / "artifacts/reports/demo_report.md",
        ROOT / "artifacts/reports/demo_report.json",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in public_paths).lower()

    assert "sk-" not in text
    assert "authorization" not in text
    assert "tbd" not in text
    assert "todo" not in text
    assert "placeholder" not in text
