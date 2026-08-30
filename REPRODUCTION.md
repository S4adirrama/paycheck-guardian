# Reproducing Paycheck Guardian

These instructions reproduce the local, deterministic submission on Python 3.11. The normal commands write the canonical artifacts in this repository; the evaluation `--output-dir` option exists for isolated automated tests and is intentionally not used below.

## Requirements

- Python 3.11 (tested: Python 3.11.15)
- Git (tested: `git version 2.50.1 (Apple Git-155)`)
- FFmpeg and ffprobe (tested: 8.0.1, GPL-enabled Homebrew build)
- Playwright 1.60.0 with Chrome for Testing 148.0.7778.96 / Chromium revision 1223
- macOS, Linux, or Windows shell with a local browser for Streamlit
- No database, bank credentials, API request, or external service for the offline path

Install the external tools on macOS with Homebrew:

```sh
brew install python@3.11 git ffmpeg
python3.11 --version
git --version
ffmpeg -version
ffprobe -version
```

On Debian/Ubuntu, install the distribution packages, then confirm that the commands above resolve to Python 3.11, Git, FFmpeg, and ffprobe:

```sh
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv git ffmpeg
```

## Create an environment

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip==26.0.1
python -m pip install -e '.[dev]'
.venv/bin/playwright install chromium
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Generate deterministic receipt fixtures

```sh
.venv/bin/python scripts/generate_receipts.py
```

Expected result: the deterministic fixture generator creates `data/demo/receipts/receipt-01.png`, `data/demo/receipts/receipt-01.txt`, `data/demo/receipts/receipt-02.png`, `data/demo/receipts/receipt-02.txt`, `data/demo/receipts/receipt-03.png`, and `data/demo/receipts/receipt-03.txt`.

The paired `.txt` fixtures are the cross-host deterministic parsing contract. PNG rendering is byte-stable on one host but can vary with the available system font; image uploads are accepted only when their content hash matches a locally bundled PNG and its paired text fixture.

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
.venv/bin/python scripts/render_submission_docs.py --verified-source-commit e09764b34f1d084f7b67890939c4eb3175347a5d
```

Expected result: evaluation prints `evaluated 12 cases in offline mode` and writes `artifacts/evaluation/baseline_predictions.json`, `artifacts/evaluation/normalization_only_predictions.json`, `artifacts/evaluation/unverified_agent_predictions.json`, `artifacts/evaluation/removed_unsafe_recurrence_predictions.json`, `artifacts/evaluation/final_predictions.json`, `artifacts/evaluation/final_trajectories.json`, `artifacts/evaluation/metrics.json`, `artifacts/evaluation/per_case_results.json`, and `artifacts/evaluation/comparison.md`. Rendering prints `rendered evidence-backed submission documents and representative artifacts` and writes `README.md`, `REPRODUCTION.md`, `artifacts/trajectories/baseline.json`, `artifacts/trajectories/final.json`, `artifacts/reports/demo_report.md`, and `artifacts/reports/demo_report.json`.

## Run tests

```sh
.venv/bin/pytest
```

Expected result: the complete collected suite passes with exit status 0.

## Run the local app

```sh
.venv/bin/streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
```

Expected result: Streamlit serves the local app only on loopback at `http://127.0.0.1:8501`. Open that URL, choose **Load Alex's synthetic demo**, then choose **Analyze verified savings options**. For uploads, select one or more CSV, paired receipt-text, or supported bundled PNG inputs and set the analysis/next-paycheck dates. Inputs are merged and semantic duplicates are kept once. The download buttons emit the same Markdown/JSON report format retained under `artifacts/reports/`. The cancellation control is only a local simulation and requires acknowledgement.

## Capture a local demo video

The current capture script and submitted MP4 are included. Rebuild them with:

```sh
.venv/bin/python scripts/capture_demo.py
```

Expected result: the existing `artifacts/video/paycheck-guardian-demo.mp4` is replaced by a freshly captured H.264 1920×1080 MP4 lasting 60–300 seconds. Do not show real transaction data, credentials, terminal environment variables, or API configuration in a recording.

## Expected retained measurements

The current machine's retained final evaluation time is 4 ms for the final mode; timings are machine-specific and can vary. The retained offline model cost is USD 0.00. The final score is precision 1.0000, recall 1.0000, F1 1.0000, and 0 unsupported claims across the 12 synthetic cases.

## Optional online setup

The judged workflow does not require an online model. If you add or experiment with an online adapter, install its optional dependency and supply your provider credential through your shell's secret-management mechanism:

```sh
python -m pip install -e '.[online]'
export OPENAI_API_KEY='set-this-in-your-shell-or-secret-manager'
```

Do not print, commit, paste into reports, or record the credential. No current evaluation command uses it, and all reported submission metrics are from the offline workflow.

## Troubleshooting and integrity checks

```sh
.venv/bin/python scripts/render_submission_docs.py --verified-source-commit e09764b34f1d084f7b67890939c4eb3175347a5d
.venv/bin/pytest tests/test_submission.py -v
if rg -n '[T]BD|[T]ODO|[P]LACEHOLDER|s[k]-[A-Za-z0-9]' README.md REPRODUCTION.md artifacts; then exit 1; fi
.venv/bin/pytest
```

The final scan should emit no matches. All input fixtures and retained evaluation data are synthetic; this prototype does not provide financial advice or execute financial actions.

## Submission verification

Fresh offline audit evidence: Python 3.11.15; 122 tests collected; 12 synthetic cases; final F1 1.0000 with 0 unsupported claims; final-mode runtime 4 ms. The H.264 demo video is 280.000 seconds. Audited source commit: `e09764b34f1d084f7b67890939c4eb3175347a5d`.
