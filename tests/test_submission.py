"""Integrity checks for the evidence-backed hackathon submission."""

import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VERIFIED_SOURCE_COMMIT = "d78e53fc1c6f1a96c9962431412711ae75e7be1a"
SENSITIVE_ENVIRONMENT_KEY = re.compile(r"API_KEY|TOKEN|SECRET|AUTHORIZATION|PASSWORD", re.IGNORECASE)
AUTHOR_PATH_MARKER = re.compile(r"(?i)/(?:Users|home)/|\.worktrees/|[A-Z]:\\\\Users\\\\")


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
    folded_text = text.casefold()
    return sorted(
        key
        for key, value in environment.items()
        if SENSITIVE_ENVIRONMENT_KEY.search(key)
        and len(value.strip()) >= 8
        and value.strip().casefold() in folded_text
    )


def _renderer_module() -> object:
    specification = importlib.util.spec_from_file_location(
        "render_submission_docs", ROOT / "scripts" / "render_submission_docs.py"
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _capture_module() -> object:
    specification = importlib.util.spec_from_file_location(
        "capture_demo", ROOT / "scripts" / "capture_demo.py"
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


def test_project_builds_an_editable_install_from_the_repository() -> None:
    """Package discovery must include only the application package in a clean install."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--no-deps",
            "-e",
            ".",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_documented_metrics_equal_machine_readable_metrics() -> None:
    """Every comparison row must be generated from the retained evaluation result."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    labels = {
        "baseline": "Fair baseline",
        "normalization_only": "Normalization only",
        "unverified_agent": "Unverified drafts",
        "removed_unsafe_recurrence": "Removed unsafe recurrence experiment",
        "final": "Final verified workflow",
    }
    for mode, label in labels.items():
        values = metrics[mode]
        expected_row = (
            f"| {label} | {values['precision']} | {values['recall']} | "
            f"{values['f1']} | {values['unsupported_claims']} |"
        )
        assert expected_row in readme


def test_renderer_derives_case_count_from_retained_fingerprints() -> None:
    """A hard-coded evaluation total would become stale when retained cases change."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    metrics["case_fingerprints"].pop(next(iter(metrics["case_fingerprints"])))
    renderer = _renderer_module()

    readme = renderer._render_readme(metrics)

    assert f"covers {len(metrics['case_fingerprints'])} synthetic cases" in readme


def test_generated_reproduction_contract_includes_current_toolchain_and_step_results() -> None:
    """A reader must be able to run each submission step and know its expected output."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    renderer = _renderer_module()
    verification = {
        "python_version": sys.version.split()[0],
        "test_count": 1,
        "case_count": metrics["case_count"],
        "final_f1": metrics["final"]["f1"],
        "unsupported_claims": metrics["final"]["unsupported_claims"],
        "final_runtime_ms": metrics["elapsed_ms_by_mode"]["final"],
        "video_duration_seconds": 280.0,
        "source_commit": VERIFIED_SOURCE_COMMIT,
    }
    reproduction = renderer._render_reproduction(metrics, verification)
    readme = renderer._render_readme(metrics, verification)

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
        ".venv/bin/streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501",
        "http://127.0.0.1:8501",
        "git --version",
        "ffmpeg -version",
        "ffprobe -version",
        ".venv/bin/playwright install chromium",
    ]:
        assert expected in reproduction
    assert "artifacts/video/paycheck-guardian-demo.mp4" in readme
    assert "Task 9 supplies" not in reproduction
    assert "intentionally absent" not in reproduction


def test_generated_readme_has_third_party_component_license_table() -> None:
    """Every shipped runtime, optional, dev, browser, and media component needs attribution."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    readme = _renderer_module()._render_readme(metrics)

    for expected in (
        "Third-party components and licenses",
        "Pydantic",
        "Streamlit",
        "Pillow",
        "OpenAI Python SDK",
        "pytest",
        "Playwright",
        "Chromium",
        "FFmpeg / ffprobe",
    ):
        assert expected in readme


def test_video_captions_separate_scored_tool_and_safety_contributions() -> None:
    """The video must not attribute prediction metrics to the unscored human checkpoint."""
    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))

    captions = " ".join(
        str(item["caption"]) for item in _capture_module()._captions(metrics)
    )

    assert "Candidate tools drive" in captions
    assert "verifier reduces unsupported claims" in captions
    assert "human checkpoint is not prediction-scored" in captions


def test_specific_environment_values_are_detected_without_exposing_them(
    monkeypatch: object,
) -> None:
    """A public artifact containing a real secret must report only its environment key."""
    secret_value = "submission-only-secret-value"
    monkeypatch.setenv("PAYCHECK_GUARDIAN_SECRET", secret_value)

    leaked_keys = _sensitive_environment_keys_in_text(f"prefix {secret_value} suffix", os.environ)

    assert leaked_keys == ["PAYCHECK_GUARDIAN_SECRET"]


def test_sensitive_environment_value_detection_is_case_insensitive(
    monkeypatch: object,
) -> None:
    """Case changes in an emitted value must not bypass the public-artifact scan."""
    secret_value = "MixedCaseSubmissionValue"
    monkeypatch.setenv("PAYCHECK_GUARDIAN_SECRET", secret_value)

    leaked_keys = _sensitive_environment_keys_in_text(
        f"prefix {secret_value.lower()} suffix", os.environ
    )

    assert leaked_keys == ["PAYCHECK_GUARDIAN_SECRET"]


def test_author_path_scan_detects_unquoted_home_and_worktree_paths() -> None:
    """Markdown punctuation must not hide an author-specific filesystem path."""
    assert _author_path_markers_in_text("See (`/Users/example/project`) for details")
    assert _author_path_markers_in_text("build/.worktrees/implementation/result")


def test_trajectories_have_instructions_tools_feedback_and_checkpoint() -> None:
    """The representative final run must make the verified workflow inspectable."""
    events = json.loads((ROOT / "artifacts/trajectories/final.json").read_text(encoding="utf-8"))
    types = {event["event_type"] for event in events}

    assert {"instruction", "tool_call", "tool_result", "verification", "human_checkpoint"} <= types


def test_renderer_generates_demo_report_and_representative_challenge_artifacts(
    tmp_path: Path,
) -> None:
    """Rendering must produce documents from current evidence without external services."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_submission_docs.py",
            "--verified-source-commit",
            VERIFIED_SOURCE_COMMIT,
            "--output-root",
            str(tmp_path),
        ],
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
        assert (tmp_path / relative_path).is_file()

    report = json.loads((tmp_path / "artifacts/reports/demo_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == "alex-demo-run"
    assert all(row["is_synthetic"] for row in report["transactions"])


def test_renderer_generates_command_backed_submission_verification(tmp_path: Path) -> None:
    """Final submission facts must be refreshed from the environment and retained evidence."""
    commit_check = subprocess.run(
        ["git", "cat-file", "-e", f"{VERIFIED_SOURCE_COMMIT}^{{commit}}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert commit_check.returncode == 0, commit_check.stderr

    invalid_result = subprocess.run(
        [
            sys.executable,
            "scripts/render_submission_docs.py",
            "--verified-source-commit",
            "not-a-commit",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert invalid_result.returncode != 0

    rendered_documents: list[tuple[bytes, bytes]] = []
    for _ in range(2):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/render_submission_docs.py",
                "--verified-source-commit",
                VERIFIED_SOURCE_COMMIT,
                "--output-root",
                str(tmp_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        rendered_documents.append(
            (
                (tmp_path / "README.md").read_bytes(),
                (tmp_path / "REPRODUCTION.md").read_bytes(),
            )
        )
    assert rendered_documents[0] == rendered_documents[1]

    metrics = json.loads((ROOT / "artifacts/evaluation/metrics.json").read_text(encoding="utf-8"))
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            "artifacts/video/paycheck-guardian-demo.mp4",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    duration = float(probe.stdout.strip())

    for document in ("README.md", "REPRODUCTION.md"):
        text = (tmp_path / document).read_text(encoding="utf-8")
        assert "## Submission verification" in text
        assert f"Python {sys.version.split()[0]}" in text
        assert f"{metrics['case_count']} synthetic cases" in text
        assert f"final F1 {metrics['final']['f1']}" in text
        assert f"{metrics['final']['unsupported_claims']} unsupported claims" in text
        assert f"final-mode runtime {metrics['elapsed_ms_by_mode']['final']} ms" in text
        assert f"{duration:.3f} seconds" in text
        assert VERIFIED_SOURCE_COMMIT in text
        assert re.search(r"\b\d+ tests collected\b", text)


def test_submission_artifacts_do_not_contain_credential_markers() -> None:
    """Public material must exclude fixed markers and values from sensitive environment keys."""
    public_text = _public_submission_text()
    text = public_text.lower()

    assert "sk-" not in text
    assert "authorization" not in text
    for forbidden in ("t" + "bd", "to" + "do", "place" + "holder"):
        assert forbidden not in text
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
