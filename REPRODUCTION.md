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

## Generate deterministic fixtures and evaluate

```sh
python scripts/generate_receipts.py
python scripts/run_baseline.py --mode offline
python scripts/run_solution.py --mode offline
python scripts/evaluate.py --mode offline
python scripts/render_submission_docs.py
python -m pytest
```

The normal evaluation commands write `artifacts/evaluation/`. They produce the retained prediction files, `metrics.json`, `per_case_results.json`, `comparison.md`, and `final_trajectories.json`. The document renderer writes `README.md`, `artifacts/trajectories/baseline.json`, `artifacts/trajectories/final.json`, and the Alex synthetic demo report files.

## Run the local app

```sh
streamlit run app.py
```

Open the local URL printed by Streamlit, choose **Load Alex's synthetic demo**, then choose **Analyze verified savings options**. The download buttons emit the same Markdown/JSON report format retained under `artifacts/reports/`. The cancellation control is only a local simulation and requires acknowledgement.

## Capture a local demo video

Start the app with `streamlit run app.py`, record the browser while loading the synthetic Alex demo and opening the evidence expanders, then save the recording outside the repository or in an ignored path. Do not show real transaction data, credentials, terminal environment variables, or API configuration in a recording.

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
python scripts/render_submission_docs.py
python -m pytest tests/test_submission.py -v
if rg -n '[T]BD|[T]ODO|[P]LACEHOLDER|s[k]-[A-Za-z0-9]' README.md REPRODUCTION.md artifacts; then exit 1; fi
python -m pytest
```

The final scan should emit no matches. All input fixtures and retained evaluation data are synthetic; this prototype does not provide financial advice or execute financial actions.
