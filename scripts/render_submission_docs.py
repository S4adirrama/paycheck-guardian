"""Render public submission material from retained offline evidence.

This script intentionally has no network dependency.  It reads the canonical
evaluation artifacts, derives the representative challenge records, and runs
the deterministic Alex demo to keep the report in sync with production code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from paycheck_guardian.agent import run_offline_agent
from paycheck_guardian.parsers import parse_bank_csv
from paycheck_guardian.reporting import render_markdown, serialize_run


ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "artifacts" / "evaluation"
TRAJECTORY_DIR = ROOT / "artifacts" / "trajectories"
REPORT_DIR = ROOT / "artifacts" / "reports"
CHALLENGE_CASE = "challenge_alias_price_essential"
DEMO_ANALYSIS_DATE = date(2026, 8, 1)
DEMO_NEXT_PAYCHECK = date(2026, 8, 15)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True))


def _offline_command(command: list[str]) -> str:
    """Run a local evidence command without passing an online provider credential."""
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _submission_verification(
    metrics: dict[str, Any], verified_source_commit: str
) -> dict[str, object]:
    """Collect exact submission facts from local commands and retained evidence."""
    source_commit = _offline_command(
        ["git", "rev-parse", "--verify", f"{verified_source_commit}^{{commit}}"]
    )
    collection = _offline_command([sys.executable, "-m", "pytest", "--collect-only", "-q"])
    test_count = sum(int(match) for match in re.findall(r":\s+(\d+)$", collection, re.MULTILINE))
    if test_count == 0:
        raise RuntimeError("pytest collection did not report a test count")
    duration = float(
        _offline_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                "artifacts/video/paycheck-guardian-demo.mp4",
            ]
        )
    )
    return {
        "python_version": sys.version.split()[0],
        "test_count": test_count,
        "case_count": metrics["case_count"],
        "final_f1": metrics["final"]["f1"],
        "unsupported_claims": metrics["final"]["unsupported_claims"],
        "final_runtime_ms": metrics["elapsed_ms_by_mode"]["final"],
        "video_duration_seconds": duration,
        "source_commit": source_commit,
    }


def _render_submission_verification(verification: dict[str, object]) -> str:
    """Render the shared command-backed verification section."""
    return f"""## Submission verification

Fresh offline audit evidence: Python {verification['python_version']}; {verification['test_count']} tests collected; {verification['case_count']} synthetic cases; final F1 {verification['final_f1']} with {verification['unsupported_claims']} unsupported claims; final-mode runtime {verification['final_runtime_ms']} ms. The H.264 demo video is {verification['video_duration_seconds']:.3f} seconds. Audited source commit: `{verification['source_commit']}`.
"""


def _challenge_trajectories(
    baseline: dict[str, Any], final: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project retained challenge artifacts into compact, reviewable event streams."""
    baseline_events = [
        {
            "event_type": "instruction",
            "instruction": "Run the fair baseline on the retained original challenge rows.",
            "source_artifact": "artifacts/evaluation/baseline_predictions.json",
        },
        {
            "event_type": "predictions",
            "predictions": baseline["predictions"][CHALLENGE_CASE],
            "source_artifact": "artifacts/evaluation/baseline_predictions.json",
        },
    ]

    source_events = final["trajectories"][CHALLENGE_CASE]
    final_events: list[dict[str, Any]] = []
    for source_index, source in enumerate(source_events):
        event = {
            "attempt": source["attempt"],
            "component": source["component"],
            "source_event_index": source_index,
            "timestamp": source["timestamp"],
        }
        if source["event_type"] == "run_started":
            final_events.append(
                {
                    **event,
                    "event_type": "instruction",
                    "instruction": source["instruction"],
                    "tool_input": source["tool_input"],
                }
            )
        elif source["event_type"] == "tool_called":
            final_events.append(
                {
                    **event,
                    "event_type": "tool_call",
                    "tool_name": source["tool_name"],
                    "tool_input": source["tool_input"],
                }
            )
        elif source["event_type"] == "tool_result" and source["tool_name"] == "verify_recommendation":
            final_events.append(
                {
                    **event,
                    "event_type": "verification",
                    "tool_name": source["tool_name"],
                    "tool_input": source["tool_input"],
                    "tool_result": source["tool_result"],
                    "feedback": source["verification_feedback"],
                }
            )
        elif source["event_type"] == "tool_result":
            final_events.append(
                {
                    **event,
                    "event_type": "tool_result",
                    "tool_name": source["tool_name"],
                    "tool_result": source["tool_result"],
                }
            )
        elif source["event_type"] == "run_completed":
            final_events.append(
                {
                    **event,
                    "event_type": "human_checkpoint",
                    "checkpoint": source["human_checkpoint"],
                    "tool_result": source["tool_result"],
                }
            )

    final_events.insert(
        -1,
        {
            "event_type": "retry",
            "performed": False,
            "reason": "No correction was attempted: the retained verifier feedback rejects the essential Rent candidate rather than identifying a repairable arithmetic or evidence issue.",
            "source_artifact": "artifacts/evaluation/final_trajectories.json",
        },
    )
    return baseline_events, final_events


def _render_readme(metrics: dict[str, Any], verification: dict[str, object] | None = None) -> str:
    baseline = metrics["baseline"]
    normalization = metrics["normalization_only"]
    unverified = metrics["unverified_agent"]
    unsafe = metrics["removed_unsafe_recurrence"]
    final = metrics["final"]
    case_count = len(metrics["case_fingerprints"])
    verification_section = (
        _render_submission_verification(verification) if verification is not None else ""
    )
    return f"""# Paycheck Guardian

Paycheck Guardian is a local-first prototype for people who want a safer way to find potential savings before their next paycheck. It turns transaction evidence into a short, reviewable set of recommendations; it never contacts a bank, merchant, or subscription service.

## Problem & User Value

The bottleneck is not spotting a recurring charge; it is deciding whether that pattern is safe to act on. A plausible-looking monthly charge can be rent, insurance, a duplicate, a price change, or a merchant alias. Paycheck Guardian normalizes merchant labels, detects recurring, duplicate, and discretionary patterns, verifies every recommendation against its underlying transactions, and leaves the person at a human checkpoint before any local cancellation simulation.

The intended user is a person reviewing their own spending shortly before payday. The value is an evidence-bearing suggestion with a monthly and next-paycheck estimate, not autonomous financial action. The Alex demo and all evaluation cases are synthetic; no personal banking data is included in this repository.

## Architecture & Safety Boundaries

- Deterministic CSV/fixture parsers and merchant normalization keep the offline path reproducible.
- Evidence-first tools produce candidate transactions and cent-rounded estimates.
- A verifier checks evidence, arithmetic, confidence, caveats, and essential-payment exclusions before a recommendation is shown.
- Streamlit runs locally. The only cancellation capability is a clearly labelled local simulation after an acknowledgement; no bank or merchant integration exists.

## Measured Improvement

The retained offline evaluation covers {case_count} synthetic cases, including merchant aliases, price drift, annual cadence, duplicates, discretionary patterns, ambiguity, and essential payments. All modes receive identical original rows, whose case fingerprints are retained in `artifacts/evaluation/metrics.json`.

| Retained mode | Precision | Recall | F1 | Unsupported claims |
| --- | ---: | ---: | ---: | ---: |
| Fair baseline | {baseline['precision']} | {baseline['recall']} | {baseline['f1']} | {baseline['unsupported_claims']} |
| Normalization only | {normalization['precision']} | {normalization['recall']} | {normalization['f1']} | {normalization['unsupported_claims']} |
| Unverified drafts | {unverified['precision']} | {unverified['recall']} | {unverified['f1']} | {unverified['unsupported_claims']} |
| Removed unsafe recurrence experiment | {unsafe['precision']} | {unsafe['recall']} | {unsafe['f1']} | {unsafe['unsupported_claims']} |
| Final verified workflow | {final['precision']} | {final['recall']} | {final['f1']} | {final['unsupported_claims']} |

In the retained run, matched final recommendations have evidence coverage {final['evidence_coverage']} and mean monthly-savings error USD {final['mean_savings_error_usd']}. The final workflow records {final['true_positives']} true positives, {final['false_positives']} false positives, and {final['false_negatives']} false negatives. Offline model cost is USD {metrics['model_cost_usd']}.

## Improvement Changelog

1. **Baseline.** Exact raw merchant labels and a 26–35-day recurrence rule reached F1 {baseline['f1']}; it retained {baseline['unsupported_claims']} unsupported claims.
2. **Normalization.** Canonical merchant grouping alone reached F1 {normalization['f1']}; it still retained {normalization['unsupported_claims']} unsupported claims.
3. **Verification.** Deterministic candidate generation before filtering reached F1 {unverified['f1']} with {unverified['unsupported_claims']} unsupported claims, making the verifier's contribution auditable.
4. **Removed experiment.** `removed_unsafe_recurrence` treats every detected 26–35-day charge as cancellable before the final safety gate. Its retained predictions score F1 {unsafe['f1']} with {unsafe['unsupported_claims']} unsupported claims, including essential-payment false positives. It was removed because recurring evidence alone cannot justify cancellation advice for rent, insurance, healthcare, utilities, or debt.
5. **Final.** The verifier rejects unsupported essential-payment advice and retains only evidence-backed recommendations: F1 {final['f1']} and {final['unsupported_claims']} unsupported claims in this synthetic evaluation.

## Main Failure Mode

The main remaining risk is semantic ambiguity in real transaction exports: merchant labels and categories can be incomplete or misleading. The retained score demonstrates correctness only on the {case_count} synthetic cases, not on live bank data or a representative population. Treat every output as a review prompt, keep the evidence visible, and do not use this prototype for autonomous financial decisions.

## Hot Take

For personal finance, an agent that can say “I cannot safely recommend this” is more valuable than one that confidently maximizes the number of suggested cancellations. Evidence and a human checkpoint are product features, not compliance decoration.

## Reproduce, Inspect, and Demo

- [Reproduction guide](REPRODUCTION.md)
- [Machine-readable metrics](artifacts/evaluation/metrics.json) and [per-case scores](artifacts/evaluation/per_case_results.json)
- [Representative baseline trajectory](artifacts/trajectories/baseline.json) and [final verified trajectory](artifacts/trajectories/final.json)
- [Alex synthetic demo report](artifacts/reports/demo_report.md) and [JSON evidence record](artifacts/reports/demo_report.json)
- [Video-capture instructions](REPRODUCTION.md#capture-a-local-demo-video) for the submitted [H.264 MP4 artifact](artifacts/video/paycheck-guardian-demo.mp4).

## Scope, Data, and License

This project was created during the hackathon as a prototype. The demo and evaluation datasets are intentionally synthetic. The repository source, documentation, and synthetic fixtures are available under the [MIT License](LICENSE). See [REPRODUCTION.md](REPRODUCTION.md) for the Python 3.11 setup, offline execution, optional online configuration, and expected artifacts.

{verification_section}
"""


def _render_reproduction(
    metrics: dict[str, Any], verification: dict[str, object] | None = None
) -> str:
    final_ms = metrics["elapsed_ms_by_mode"]["final"]
    case_count = len(metrics["case_fingerprints"])
    verification_section = (
        _render_submission_verification(verification) if verification is not None else ""
    )
    return f"""# Reproducing Paycheck Guardian

These instructions reproduce the local, deterministic submission on Python 3.11. The normal commands write the canonical artifacts in this repository; the evaluation `--output-dir` option exists for isolated automated tests and is intentionally not used below.

## Requirements

- Python 3.11 (the retained run used Python {metrics['python_version']})
- macOS, Linux, or Windows shell with a local browser for Streamlit
- No database, bank credentials, API request, or external service for the offline path

## Create an environment

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1`.

## Generate deterministic receipt fixtures

```sh
.venv/bin/python scripts/generate_receipts.py
```

Expected result: the deterministic fixture generator creates `data/demo/receipts/receipt-01.png`, `data/demo/receipts/receipt-01.txt`, `data/demo/receipts/receipt-02.png`, `data/demo/receipts/receipt-02.txt`, `data/demo/receipts/receipt-03.png`, and `data/demo/receipts/receipt-03.txt`.

## Run the fair baseline

```sh
.venv/bin/python scripts/run_baseline.py --mode offline
```

Expected result: the command prints `evaluated {case_count} cases in offline mode` and writes the canonical offline evaluation set under `artifacts/evaluation/`, including `artifacts/evaluation/baseline_predictions.json`.

## Run the final solution

```sh
.venv/bin/python scripts/run_solution.py --mode offline
```

Expected result: the command prints `evaluated {case_count} cases in offline mode` and refreshes the same canonical evaluation set, including `artifacts/evaluation/final_predictions.json` and `artifacts/evaluation/final_trajectories.json`.

## Run the retained evaluation and render submission documents

```sh
.venv/bin/python scripts/evaluate.py --mode offline
.venv/bin/python scripts/render_submission_docs.py --verified-source-commit {verification['source_commit']}
```

Expected result: evaluation prints `evaluated {case_count} cases in offline mode` and writes `artifacts/evaluation/baseline_predictions.json`, `artifacts/evaluation/normalization_only_predictions.json`, `artifacts/evaluation/unverified_agent_predictions.json`, `artifacts/evaluation/removed_unsafe_recurrence_predictions.json`, `artifacts/evaluation/final_predictions.json`, `artifacts/evaluation/final_trajectories.json`, `artifacts/evaluation/metrics.json`, `artifacts/evaluation/per_case_results.json`, and `artifacts/evaluation/comparison.md`. Rendering prints `rendered evidence-backed submission documents and representative artifacts` and writes `README.md`, `REPRODUCTION.md`, `artifacts/trajectories/baseline.json`, `artifacts/trajectories/final.json`, `artifacts/reports/demo_report.md`, and `artifacts/reports/demo_report.json`.

## Run tests

```sh
.venv/bin/pytest
```

Expected result: the complete collected suite passes with exit status 0.

## Run the local app

```sh
.venv/bin/streamlit run app.py --server.headless true --server.port 8501
```

Expected result: Streamlit serves the local app at `http://localhost:8501`. Open that URL, choose **Load Alex's synthetic demo**, then choose **Analyze verified savings options**. The download buttons emit the same Markdown/JSON report format retained under `artifacts/reports/`. The cancellation control is only a local simulation and requires acknowledgement.

## Capture a local demo video

Task 9 supplies the capture script. After that task is complete, run:

```sh
.venv/bin/python scripts/capture_demo.py
```

Expected result: `artifacts/video/paycheck-guardian-demo.mp4`, an H.264 1920×1080 MP4 lasting 60–300 seconds. The file is intentionally absent before Task 9; do not substitute a manual recording or fabricate a fake file. Do not show real transaction data, credentials, terminal environment variables, or API configuration in a recording.

## Expected retained measurements

The current machine's retained final evaluation time is {final_ms} ms for the final mode; timings are machine-specific and can vary. The retained offline model cost is USD {metrics['model_cost_usd']}. The final score is precision {metrics['final']['precision']}, recall {metrics['final']['recall']}, F1 {metrics['final']['f1']}, and {metrics['final']['unsupported_claims']} unsupported claims across the {case_count} synthetic cases.

## Optional online setup

The judged workflow does not require an online model. If you add or experiment with an online adapter, install its optional dependency and supply your provider credential through your shell's secret-management mechanism:

```sh
python -m pip install -e '.[online]'
export OPENAI_API_KEY='set-this-in-your-shell-or-secret-manager'
```

Do not print, commit, paste into reports, or record the credential. No current evaluation command uses it, and all reported submission metrics are from the offline workflow.

## Troubleshooting and integrity checks

```sh
.venv/bin/python scripts/render_submission_docs.py --verified-source-commit {verification['source_commit']}
.venv/bin/pytest tests/test_submission.py -v
if rg -n '[T]BD|[T]ODO|[P]LACEHOLDER|s[k]-[A-Za-z0-9]' README.md REPRODUCTION.md artifacts; then exit 1; fi
.venv/bin/pytest
```

The final scan should emit no matches. All input fixtures and retained evaluation data are synthetic; this prototype does not provide financial advice or execute financial actions.

{verification_section}
"""


def _render_demo_report() -> tuple[dict[str, Any], str]:
    demo_path = ROOT / "data" / "demo" / "transactions.csv"
    with demo_path.open(encoding="utf-8", newline="") as source:
        transactions = parse_bank_csv(source, demo_path.name)
    run = run_offline_agent(
        transactions,
        analysis_date=DEMO_ANALYSIS_DATE,
        next_paycheck=DEMO_NEXT_PAYCHECK,
        run_id="alex-demo-run",
    )
    return serialize_run(run), render_markdown(run)


def main() -> None:
    """Render all tracked submission documents and representative artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verified-source-commit",
        required=True,
        help="tested implementation commit to record in generated verification evidence",
    )
    args = parser.parse_args()
    metrics = _read_json(EVALUATION_DIR / "metrics.json")
    baseline = _read_json(EVALUATION_DIR / "baseline_predictions.json")
    final = _read_json(EVALUATION_DIR / "final_trajectories.json")
    verification = _submission_verification(metrics, args.verified_source_commit)
    baseline_events, final_events = _challenge_trajectories(baseline, final)
    demo_json, demo_markdown = _render_demo_report()

    _write(ROOT / "README.md", _render_readme(metrics, verification))
    _write(ROOT / "REPRODUCTION.md", _render_reproduction(metrics, verification))
    _json(TRAJECTORY_DIR / "baseline.json", baseline_events)
    _json(TRAJECTORY_DIR / "final.json", final_events)
    _json(REPORT_DIR / "demo_report.json", demo_json)
    _write(REPORT_DIR / "demo_report.md", demo_markdown)
    print("rendered evidence-backed submission documents and representative artifacts")


if __name__ == "__main__":
    main()
