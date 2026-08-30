"""Integrity checks for the evidence-backed hackathon submission."""

import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_ENVIRONMENT_KEY = re.compile(r"API_KEY|TOKEN|SECRET|AUTHORIZATION|PASSWORD", re.IGNORECASE)
AUTHOR_PATH_MARKER = re.compile(r"(?im)(?:^|[\"'])/(?:Users|home)/|\.worktrees/|[A-Z]:\\\\Users\\\\")


def _public_submission_text() -> str:
    """Read every tracked public document and JSON/Markdown submission artifact."""
    public_paths = [
        ROOT / "README.md",
        ROOT / "REPRODUCTION.md",
        ROOT / "artifacts/trajectories/baseline.json",
        ROOT / "artifacts/trajectories/final.json",
        ROOT / "artifacts/reports/demo_report.md",
        ROOT / "artifacts/reports/demo_report.json",
    ]
    video_text_paths = [
        path
        for pattern in ("*.md", "*.txt")
        for path in (ROOT / "artifacts" / "video").rglob(pattern)
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in [*public_paths, *video_text_paths])


def _author_path_markers_in_text(text: str) -> list[str]:
    """Report only a generic finding, never an author's path, in privacy failures."""
    return ["absolute author path"] if AUTHOR_PATH_MARKER.search(text) else []


def _sensitive_environment_keys_in_text(text: str, environment: dict[str, str]) -> list[str]:
    """Return only sensitive environment key names whose specific values leak into text."""
    return sorted(
        key
        for key, value in environment.items()
        if SENSITIVE_ENVIRONMENT_KEY.search(key)
        and len(value.strip()) >= 8
        and value.strip() in text
    )


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


def test_reproduction_contract_includes_future_video_and_step_results() -> None:
    """A reader must be able to run each submission step and know its expected output."""
    reproduction = (ROOT / "REPRODUCTION.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for expected in [
        ".venv/bin/python scripts/capture_demo.py",
        "artifacts/video/paycheck-guardian-demo.mp4",
        "60–300 seconds",
        "H.264",
        "1920×1080",
        "data/demo/receipts/receipt-01.png",
        "data/demo/receipts/receipt-03.txt",
        "artifacts/evaluation/baseline_predictions.json",
        "artifacts/evaluation/normalization_only_predictions.json",
        "artifacts/evaluation/unverified_agent_predictions.json",
        "artifacts/evaluation/removed_unsafe_recurrence_predictions.json",
        "artifacts/evaluation/final_predictions.json",
        "artifacts/evaluation/final_trajectories.json",
        "artifacts/evaluation/metrics.json",
        "artifacts/evaluation/per_case_results.json",
        "artifacts/evaluation/comparison.md",
        "evaluated 12 cases in offline mode",
        ".venv/bin/streamlit run app.py --server.headless true --server.port 8501",
        "http://localhost:8501",
    ]:
        assert expected in reproduction
    assert "artifacts/video/paycheck-guardian-demo.mp4" in readme


def test_specific_environment_values_are_detected_without_exposing_them(
    monkeypatch: object,
) -> None:
    """A public artifact containing a real secret must report only its environment key."""
    secret_value = "submission-only-secret-value"
    monkeypatch.setenv("PAYCHECK_GUARDIAN_SECRET", secret_value)

    leaked_keys = _sensitive_environment_keys_in_text(f"prefix {secret_value} suffix", os.environ)

    assert leaked_keys == ["PAYCHECK_GUARDIAN_SECRET"]


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
    """Public material must exclude fixed markers and values from sensitive environment keys."""
    public_text = _public_submission_text()
    text = public_text.lower()

    assert "sk-" not in text
    assert "authorization" not in text
    assert "tbd" not in text
    assert "todo" not in text
    assert "placeholder" not in text
    assert _sensitive_environment_keys_in_text(public_text, os.environ) == []
    assert _author_path_markers_in_text(public_text) == []


def test_video_exists_and_is_under_five_minutes() -> None:
    """The submitted walkthrough must be a substantial, viewable MP4."""
    video = ROOT / "artifacts/video/paycheck-guardian-demo.mp4"
    assert video.stat().st_size > 100_000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    assert 60 <= duration <= 300


def test_video_text_has_no_author_absolute_path_markers() -> None:
    """Portable video material must not disclose an author's local path."""
    video_text = "\n".join(
        path.read_text(encoding="utf-8")
        for pattern in ("*.md", "*.txt")
        for path in (ROOT / "artifacts" / "video").rglob(pattern)
    )

    assert _author_path_markers_in_text(video_text) == []
