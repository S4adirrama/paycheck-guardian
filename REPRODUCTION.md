# Reproducing Paycheck Guardian

These instructions reproduce the local, deterministic submission on Python 3.11. The normal commands write the canonical artifacts in this repository; the evaluation `--output-dir` option exists for isolated automated tests and is intentionally not used below.

## Requirements

- Python 3.11 (the retained run used Python 3.11.15)
- macOS, Linux, or Windows shell with a local browser for Streamlit
- No database, bank credentials, API request, or external service for the offline path

## Create an environment

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Generate deterministic receipt fixtures

```sh
.venv/bin/python scripts/generate_receipts.py
```

Expected result: the deterministic fixture generator creates `data/demo/receipts/receipt-01.png`, `data/demo/receipts/receipt-01.txt`, `data/demo/receipts/receipt-02.png`, `data/demo/receipts/receipt-02.txt`, `data/demo/receipts/receipt-03.png`, and `data/demo/receipts/receipt-03.txt`.

## Run the fair baseline

```sh
.venv/bin/python scripts/run_baseline.py --mode offline
```

Expected result: the command prints `evaluated 12 cases in offline mode` and writes the canonical offline evaluation set under `artifacts/evaluation/`, including `artifacts/evaluation/baseline_predictions.json`.

## Run the final solution

```sh
.venv/bin/python scripts/run_solution.py --mode offline
```

Expected result: the command prints `evaluated 12 cases in offline mode` and refreshes the same canonical evaluation set, including `artifacts/evaluation/final_predictions.json` and `artifacts/evaluation/final_trajectories.json`.

## Run the retained evaluation and render submission documents

```sh
.venv/bin/python scripts/evaluate.py --mode offline
.venv/bin/python scripts/render_submission_docs.py
```

Expected result: evaluation prints `evaluated 12 cases in offline mode` and writes `artifacts/evaluation/baseline_predictions.json`, `artifacts/evaluation/normalization_only_predictions.json`, `artifacts/evaluation/unverified_agent_predictions.json`, `artifacts/evaluation/removed_unsafe_recurrence_predictions.json`, `artifacts/evaluation/final_predictions.json`, `artifacts/evaluation/final_trajectories.json`, `artifacts/evaluation/metrics.json`, `artifacts/evaluation/per_case_results.json`, and `artifacts/evaluation/comparison.md`. Rendering prints `rendered evidence-backed submission documents and representative artifacts` and writes `README.md`, `REPRODUCTION.md`, `artifacts/trajectories/baseline.json`, `artifacts/trajectories/final.json`, `artifacts/reports/demo_report.md`, and `artifacts/reports/demo_report.json`.

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

The current machine's retained final evaluation time is 3 ms for the final mode; timings are machine-specific and can vary. The retained offline model cost is USD 0.00. The final score is precision 1.0000, recall 1.0000, F1 1.0000, and 0 unsupported claims across the 12 synthetic cases.

## Optional online setup

The judged workflow does not require an online model. If you add or experiment with an online adapter, install its optional dependency and supply your provider credential through your shell's secret-management mechanism:

```sh
python -m pip install -e '.[online]'
export OPENAI_API_KEY='set-this-in-your-shell-or-secret-manager'
```

Do not print, commit, paste into reports, or record the credential. No current evaluation command uses it, and all reported submission metrics are from the offline workflow.

## Troubleshooting and integrity checks

```sh
.venv/bin/python scripts/render_submission_docs.py
.venv/bin/pytest tests/test_submission.py -v
if rg -n '[T]BD|[T]ODO|[P]LACEHOLDER|s[k]-[A-Za-z0-9]' README.md REPRODUCTION.md artifacts; then exit 1; fi
.venv/bin/pytest
```

The final scan should emit no matches. All input fixtures and retained evaluation data are synthetic; this prototype does not provide financial advice or execute financial actions.
