# Paycheck Guardian final fix report

## Status

**PASS — all Critical and Important findings are resolved.** The adjacent Minor findings are also resolved. The default path remains deterministic and offline, financial calculations remain `Decimal`-based, evaluation inputs remain synthetic, uploaded rows are marked non-synthetic, and the only financial action remains a local simulation gated by explicit human acknowledgement. There are no blocking unresolved findings.

The fix wave started from clean commit `62afb3a1bd4e20f4affcc183b85b6a608e93ceea`. Its tested source commits are:

- `1c0e44d96980c31476cbd049c7cbcdf3b1893680` — `fix: enforce safe verified savings workflow`
- `e09764b34f1d084f7b67890939c4eb3175347a5d` — `fix: initialize date controls without warnings`

All retained evaluation, documentation, report, trajectory, frame, and video artifacts were regenerated against final source commit `e09764b34f1d084f7b67890939c4eb3175347a5d` and committed as:

- `0907e4d7c77e31c1da6e018e4c5b48c2191cd44a` — `chore: regenerate final submission evidence`

## Per-finding resolution

### Critical 1 — cancellation safety and copy contract

**Resolved.** `Recommendation` now requires a structured `verified_target` and `verified_action`. Recurrence detection uses a positive cancellation allowlist; telecom, essential, unknown, and otherwise ambiguous merchants cannot support cancellation advice. The verifier independently matches the structured target/action to deterministic evidence and derives canonical display title/rationale from verified fields, so unsafe draft copy cannot override the action presented to a person.

Files: `paycheck_guardian/models.py`, `paycheck_guardian/tools.py`, `paycheck_guardian/verifier.py`, `paycheck_guardian/agent.py`, `app.py`, `prompts/savings_agent.md`.

Regressions: `test_recommendation_requires_structured_verified_target_and_action`, `test_recurring_cancellation_uses_a_positive_semantic_allowlist`, `test_verifier_blocks_recurring_merchants_outside_cancellation_allowlist`, `test_verifier_canonicalizes_display_copy_from_verified_target_and_action`, `test_verifier_rejects_structured_target_that_does_not_match_evidence`, and `test_agent_omits_non_allowlisted_recurring_cancellation` (Verizon and Mystery Utility cases).

### Important 1 — overlapping savings totals

**Resolved.** Verified recommendations are ranked deterministically and any candidate sharing an evidence transaction with an already retained recommendation is rejected as a conflict. Active display totals additionally sum unique evidence and cap each retained estimate at observed spending, preventing a display total from exceeding the underlying charges even if a malformed run bypasses orchestration.

Files: `paycheck_guardian/agent.py`, `paycheck_guardian/reporting.py`, `app.py`.

Regressions: `test_overlapping_doordash_evidence_is_not_counted_as_multiple_savings_actions` and `test_displayed_aggregate_is_capped_at_unique_observed_spending`.

### Important 2 — evidence-aware opportunity scoring

**Resolved.** A prediction matches a truth item only if it contains every required evidence ID. Aggregate F1 is calculated directly as `2TP / (2TP + FP + FN)`, then rounded once; it is no longer derived from already rounded precision/recall.

Files: `paycheck_guardian/evaluation.py`, regenerated `artifacts/evaluation/*`.

Regressions: `test_matching_requires_every_ground_truth_evidence_id` and `test_f1_is_calculated_directly_from_counts_without_rounded_intermediates`.

### Important 3 — distinct removed unsafe experiment and causal claims

**Resolved.** `removed_unsafe_recurrence` is now a genuinely separate ablation: it uses only normalized 26–35-day adjacent pairs, performs no duplicate, anomaly, category-summary, discretionary, or verification step, and labels each pair as cancellable. The 12-case data includes an irregular City Water sequence that exposes this failure mode. README and video copy now state that candidate tools drive opportunity recall/F1, the verifier reduces unsupported claims, and the human checkpoint is a product-safety control rather than a scored prediction.

Files: `paycheck_guardian/evaluation.py`, `data/evaluation/cases.json`, `scripts/render_submission_docs.py`, `scripts/capture_demo.py`, `README.md`, `REPRODUCTION.md`, regenerated evaluation/video artifacts.

Regressions: `test_removed_unsafe_recurrence_is_distinct_and_recurrence_only` and `test_video_captions_separate_scored_tool_and_safety_contributions`.

### Important 4 — real upload workflow

**Resolved.** The UI accepts multiple CSV, receipt-text, and supported receipt-PNG files; parses them in memory; preserves duplicate occurrences within a single source; removes semantic cross-file duplicates by occurrence count; and keys change detection on a content digest rather than filename. Supported PNGs are recognized only by a SHA-256 match to a bundled fixture with a paired text record. Arbitrary PNGs and all JPEGs receive accurate offline-format guidance. Uploaded data defaults its analysis date to the latest charge and exposes editable analysis/next-paycheck controls.

Files: new `paycheck_guardian/uploads.py`, `paycheck_guardian/parsers.py`, `app.py`.

Regressions: `test_bundled_receipt_png_is_verified_by_content_and_arbitrary_image_is_actionable`, `test_multiple_uploads_merge_and_dedupe_csv_receipt_evidence_by_content`, `test_upload_dedupe_preserves_identical_rows_within_one_bank_export`, `test_upload_batch_rejects_inputs_without_transactions`, and `test_analysis_and_next_paycheck_dates_are_user_controlled`.

### Important 5 — anomaly and category-summary tools

**Resolved.** `find_anomalies` identifies one material high outlier only after at least two stable comparison observations; its estimated savings is the outlier's excess above the comparison median. `summarize_categories` returns deterministic `Decimal` totals and complete evidence membership. Both tools are called and sanitized in orchestration trajectories; anomaly recommendations are independently recomputed by the verifier. The existing `trial_conversion` case now contains scored Grocery Mart anomaly behavior without increasing the case count above 12.

Files: `paycheck_guardian/tools.py`, `paycheck_guardian/agent.py`, `paycheck_guardian/verifier.py`, `data/evaluation/cases.json`.

Regressions: `test_anomaly_detects_one_large_charge_against_stable_merchant_history`, `test_category_summary_totals_each_category_with_evidence`, `test_verifier_accepts_anomaly_only_when_tool_evidence_and_excess_match`, and `test_twelve_case_dataset_contains_scored_anomaly_behavior`.

### Important 6 — trajectory and upload privacy

**Resolved.** Parsers accept an explicit `is_synthetic` flag; the bundled demo/evaluation remains synthetic while uploaded rows are marked false. Trajectories retain transaction/candidate fingerprints, IDs, counts, categories, intervals, allowlist decisions, and sanitized summaries, but not raw merchant, date, amount, filename, or source-reference values. Verifier feedback redacts monetary literals. The documented Streamlit command binds only to `127.0.0.1`.

Files: `paycheck_guardian/parsers.py`, `paycheck_guardian/uploads.py`, `paycheck_guardian/agent.py`, `app.py`, `scripts/render_submission_docs.py`, `REPRODUCTION.md`.

Regressions: `test_csv_parser_marks_user_uploads_as_non_synthetic`, `test_real_like_input_values_are_absent_from_trajectory`, strengthened public path/environment scans, and the exact trajectory-field scan recorded below.

### Important 7 — disposition semantics and idempotence

**Resolved.** Dismissed recommendations are removed from the active plan, totals, Markdown/JSON active recommendation arrays, and cancellation selector. Their status remains under a separate recorded-dispositions section. Repeated approval returns the already updated run and cannot append a second action; the UI also removes the approved item from the actionable selector.

Files: `paycheck_guardian/agent.py`, `paycheck_guardian/reporting.py`, `app.py`.

Regressions: `test_repeat_approval_is_idempotent`, `test_markdown_and_serialized_report_exclude_dismissed_items_from_active_plan`, `test_recommendation_can_be_dismissed_without_simulation`, and the live UI approval/dismissal checks below.

### Important 8 — reproducibility and license documentation

**Resolved.** Reproduction instructions now include Git, FFmpeg/ffprobe, pinned pip setup, Playwright Chromium installation, exact loopback launch, current MP4 behavior, tool versions, and expected outputs. README includes runtime, optional-online, build/dev, browser, Chromium, Git, and media license attribution. The stale future-video wording is gone. Text receipt fixtures are documented as the cross-host deterministic contract; PNG rendering is explicitly host/font dependent.

Files: `scripts/render_submission_docs.py`, `README.md`, `REPRODUCTION.md`.

Regressions: `test_generated_reproduction_contract_includes_current_toolchain_and_step_results`, `test_generated_readme_has_third_party_component_license_table`, strengthened docs-to-JSON row assertions, and deterministic temporary-output renderer tests.

### Adjacent Minor findings

All four were addressed:

- Upload change detection uses an ordered content digest (`paycheck_guardian/uploads.py`).
- Punctuation-only merchants produce a source-qualified `InputValidationError` (`paycheck_guardian/parsers.py`; `test_punctuation_only_merchant_is_a_source_qualified_input_error`).
- Receipt PNG/text stem parity and regeneration repeatability were strengthened, while text fixtures are the stated cross-host contract (`tests/test_parsers.py`, `REPRODUCTION.md`).
- Docs-to-JSON checks now validate every comparison row; environment-value matching is case-insensitive; author-path detection catches unquoted home/worktree paths (`tests/test_submission.py`).

## TDD RED/GREEN evidence

The pre-change baseline command was:

```sh
.venv/bin/pytest -q
```

Observed before new regressions: **89 tests passed**.

Every production change followed a failing regression. The RED groups and observed failure signals were:

| RED command | Selected observed pre-fix failure |
| --- | --- |
| `.venv/bin/pytest -q tests/test_models.py tests/test_tools.py tests/test_verifier.py` | Structured target/action fields did not exist; Verizon and an unknown recurring utility were cancellable; unsafe title/target mismatches were accepted; anomaly/category tools were absent. |
| `.venv/bin/pytest -q tests/test_agent.py` | Real-like merchant/date/amount/source values appeared in trajectories; non-allowlisted recurring drafts survived; overlapping DoorDash recommendations double-counted evidence; repeat approval appended another simulated action. |
| `.venv/bin/pytest -q tests/test_evaluation.py` | A prediction missing required evidence still counted as a true positive; the rounded-intermediate example produced F1 `0.2858` rather than direct-count `0.2857`; unverified and removed-unsafe predictions were identical; no truth case exercised anomaly behavior. |
| `.venv/bin/pytest -q tests/test_parsers.py tests/test_app.py` | Parsers rejected the new `is_synthetic` argument; punctuation-only input escaped as a Pydantic error; bundled image/multiple-upload behavior was absent; upload analysis dates were fixed demo dates. |
| `.venv/bin/pytest -q tests/test_submission.py` | Toolchain/install/license/loopback/current-video documentation and stronger metric/scan assertions were absent; captions attributed prediction results to the unscored checkpoint. |
| `.venv/bin/pytest -q tests/test_parsers.py::test_upload_dedupe_preserves_identical_rows_within_one_bank_export tests/test_parsers.py::test_upload_batch_rejects_inputs_without_transactions` | The first merge implementation collapsed legitimate repeated rows within one export and accepted an empty CSV batch. |
| `.venv/bin/pytest -q tests/test_app.py::test_analysis_and_next_paycheck_dates_are_user_controlled` | Final UI inspection exposed `AssertionError: assert not ElementList(_list=[Warning()])` because date widgets supplied both session state and an explicit default. |

After implementation, the focused groups and complete suite were GREEN. The final source-bound command was:

```text
.venv/bin/pytest -q
........................................................................ [ 59%]
..................................................                       [100%]
```

Collection verification returned `122 tests collected in 0.13s`. The final fresh-environment suite also completed all **122/122** tests.

## Actual regenerated evaluation

All modes used the same 12 retained synthetic cases. Offline model cost was `$0.00`.

| Mode | TP | FP | FN | Precision | Recall | F1 | Unsupported | Evidence coverage | Mean savings error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fair baseline | 5 | 4 | 8 | 0.5556 | 0.3846 | 0.4545 | 4 | 1.0000 | $0.0000 |
| Normalization only | 7 | 4 | 6 | 0.6364 | 0.5385 | 0.5833 | 4 | 1.0000 | $0.0000 |
| Unverified drafts | 13 | 3 | 0 | 0.8125 | 1.0000 | 0.8966 | 3 | 1.0000 | $0.0000 |
| Removed unsafe recurrence | 1 | 11 | 12 | 0.0833 | 0.0769 | 0.0800 | 11 | 1.0000 | $0.0000 |
| Final verified workflow | 13 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | $0.0000 |

Retained elapsed times were baseline 0 ms, normalization-only 0 ms, unverified 1 ms, removed unsafe 0 ms, and final 4 ms. These are machine-local observations, not performance guarantees.

## Required verification evidence

### Fresh Python 3.11 environment

Commands:

```sh
fresh_root=$(mktemp -d /tmp/paycheck-guardian-final-verify.XXXXXX)
python3.11 -m venv "$fresh_root/venv"
"$fresh_root/venv/bin/python" -m pip install --upgrade pip==26.0.1
"$fresh_root/venv/bin/python" -m pip install -e '.[dev]'
"$fresh_root/venv/bin/python" -m pytest -q
```

Observed: Python `3.11.15`, pip `26.0.1`, editable install succeeded, and the fresh suite completed all 122 tests with exit 0. The documented `.venv/bin/pytest -q` command independently completed the same 122 tests with exit 0.

### Exact documented CLI workflow

Commands were executed from the final source:

```sh
.venv/bin/playwright install chromium
.venv/bin/python scripts/generate_receipts.py
.venv/bin/python scripts/run_baseline.py --mode offline
.venv/bin/python scripts/run_solution.py --mode offline
.venv/bin/python scripts/evaluate.py --mode offline
.venv/bin/python scripts/capture_demo.py
.venv/bin/python scripts/render_submission_docs.py --verified-source-commit e09764b34f1d084f7b67890939c4eb3175347a5d
```

Observed: Chromium installation exited 0; fixture generation exited 0; each of the three evaluation entry points printed `evaluated 12 cases in offline mode`; capture printed `Wrote artifacts/video/paycheck-guardian-demo.mp4`; document rendering printed `rendered evidence-backed submission documents and representative artifacts`.

Toolchain observations:

- Python `3.11.15`
- Git `2.50.1 (Apple Git-155)`
- FFmpeg/ffprobe `8.0.1` (tested Homebrew GPL-enabled build)
- Pydantic `2.13.5`, Streamlit `1.50.0`, Pillow `11.3.0`, pytest `8.4.2`, Playwright `1.60.0`, OpenAI SDK `2.48.0`
- build-system setuptools pin `82.0.1`
- Chrome for Testing `148.0.7778.96`, Playwright Chromium revision `1223`, Playwright FFmpeg revision `1011`

### Safety assertions

An explicit offline assertion script checked: 12 cases; final F1 `1.0000`; zero unsupported final claims; unverified and removed-unsafe prediction payloads differ; the unsafe ablation emits Rent and City Water claims; final does not; every final case has disjoint recommendation evidence; anomaly truth is exercised; a non-synthetic `real-like-bank.csv` containing recurring Verizon and Mystery Utility rows yields no recommendation.

Observed output:

```text
safety assertions passed: 12 cases; distinct unsafe mode; essential/telecom/unknown rejected; disjoint evidence; anomaly exercised
trajectory field privacy scan passed: no raw merchant/date/amount/source fields
```

### UI, approval, dismissal, uploads, and downloads

Streamlit was launched with the exact loopback command:

```sh
.venv/bin/streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
```

The clean interactive audit verified:

- Initial page visibly identifies an offline synthetic demo and local-only processing.
- Demo load parses 8 transactions with analysis date `2026-08-01` and next paycheck `2026-08-15`; there are no Streamlit widget warnings after `e09764b`.
- Analysis displays active totals `$97.49` monthly and `$44.87` by next paycheck, with DoorDash pattern, Cinema duplicate, and canonical Netflix cancellation-review copy plus evidence expanders.
- Both `Download Markdown report` and `Download JSON evidence record` emitted browser download events (`markdownDownload: true`, `jsonDownload: true`). Unit/AppTest coverage separately verifies that the emitted state contains evidence IDs and valid JSON-safe content.
- Selecting Netflix alone does not enable simulation; explicit acknowledgement enables it. Simulation displays `Cancellation simulated locally. No merchant or bank was contacted.`, records `Approved For Simulation`, disables further action for that item, and the idempotence regression proves one action after a repeated approval call.
- In an independent session, dismissal changes active totals to `$81.00` / `$37.28`, removes Netflix from active recommendations and the selector, creates no simulated action, and records `Review cancelling Netflix · Dismissed` separately.
- The multi-file chooser reports `multiple: true`. Uploading `data/demo/transactions.csv` plus bundled `receipt-01.png` parses 9 merged transactions from 2 local files, defaults dates to `2026-07-31` / `2026-08-14`, and completes analysis successfully.

### Privacy, secret, path, and integrity scans

The exact repository scan from the prior audit contract was rerun:

```sh
rg -n -i 'TBD|TODO|PLACEHOLDER|sk-[a-z0-9_-]+|authorization:|real customer|real account' . --glob '!*.mp4' --glob '!.git/**'
```

Observed: zero matches; the fail-on-match wrapper printed `exact repository forbidden-marker scan passed: zero matches`.

A public README/reproduction/artifact scan for credential markers, unfinished markers, Unix home paths, worktree paths, and Windows user paths also returned zero matches. Focused tests for case-insensitive environment-value containment, video path text, and real-like trajectory input returned `... [100%]`. `git diff --check` returned exit 0.

### Documentation and retained artifact integrity

Both generated documents contain source commit `e09764b34f1d084f7b67890939c4eb3175347a5d`, contain no prior audited-source hash, and exactly match all five rows in `artifacts/evaluation/metrics.json`. An explicit assertion printed:

```text
docs-to-evidence assertions passed: source commit, 5 metric rows, 12 cases, 122 tests, 280.000-second video
required artifact existence checks passed
```

Required evaluation JSON, baseline/final trajectories, Markdown/JSON demo reports, receipt fixtures, video script, frames, and MP4 all exist. Renderer tests write to temporary roots and demonstrated byte-identical repeated README/reproduction output for the same inputs.

### Media probe, full decode, and visual inspection

Probe command:

```sh
ffprobe -v error -show_entries stream=index,codec_name,codec_type,width,height,pix_fmt,sample_rate,channels -show_entries format=duration,size,format_name -of json artifacts/video/paycheck-guardian-demo.mp4
```

Observed:

- container: MP4-compatible `mov,mp4,m4a,3gp,3g2,mj2`
- video: H.264, 1920×1080, `yuv420p`
- audio: AAC, 48 kHz, stereo
- duration: `280.000000` seconds
- size: `4,625,429` bytes

Full decode command:

```sh
ffmpeg -v error -i artifacts/video/paycheck-guardian-demo.mp4 -f null -
```

Observed: exit 0 and `full ffmpeg decode passed`.

Representative original-resolution inspection covered captioned problem, baseline, verified-plan, evidence, approval, comparison, contribution/changelog, unsafe-ablation, and closing frames plus accurate first/mid/last decode samples. Text is legible and within frame bounds; the privacy/local-only notice is visible; evidence is clearly synthetic; approval says no merchant/bank contact; metrics match retained JSON; candidate/verifier/checkpoint contributions are correctly separated; no browser error, credential, author path, stale metric, or unfinished content is visible.

### Final repository state at artifact boundary

After artifact commit `0907e4d7c77e31c1da6e018e4c5b48c2191cd44a`, `git status --short` produced no output. Only this audit report is added afterward; the report commit is followed by another clean-status check.

## Self-review

- Reviewed all source and test diffs for scope: no unrelated user files were changed.
- Confirmed all retained documentation/artifacts were generated only after the final source commit, not staged with source/tests.
- Confirmed production code uses `Decimal`/`money()` for financial arithmetic; no float-based savings path was introduced.
- Confirmed the default and evaluated paths make no network request and report model cost `$0.00`.
- Confirmed structured verification, conflict handling, disposition filtering, and local simulation compose consistently in UI, Markdown, JSON, evaluation, and trajectories.
- Confirmed the evaluation still contains exactly 12 synthetic cases and did not obtain a higher score by dropping hard cases; the unsafe ablation worsened as expected because it is now genuinely unsafe and distinct.
- Confirmed public artifacts do not contain author filesystem paths or sensitive environment values.

## Unresolved concerns

No unresolved Critical, Important, or adjacent Minor finding remains.

Intentional prototype constraints remain and are disclosed rather than hidden:

- The perfect final score applies only to 12 designed synthetic cases, not a representative live financial population.
- Arbitrary receipt OCR is not implemented; only byte-identical bundled PNG fixtures with paired text are accepted offline.
- Receipt text fixtures, rather than host-rendered PNG bytes, are the cross-host deterministic parsing contract.
- Merchant labels/categories in real exports can be ambiguous; unknown and telecom recurrence is therefore non-cancellable by policy.
- Downloads may contain the user's own uploaded transactions because they are explicit local evidence exports; trajectories remain sanitized and nothing is transmitted externally.
- All cancellation behavior is simulation-only and human-approved; no bank, merchant, subscription, or account integration exists.
