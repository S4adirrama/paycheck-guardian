# Task 10 report — clean-environment reproduction and final submission audit

## Outcome

Completed the audit in a fresh `.verify-venv` with `OPENAI_API_KEY` removed from every audit subprocess. The final submission implementation and refreshed evidence are committed as `d78e53fc1c6f1a96c9962431412711ae75e7be1a` (`chore: verify final hackathon submission`).

## Defects found and fixed

1. Clean editable installation failed because setuptools auto-discovered `data`, `prompts`, and `artifacts` as top-level namespace packages. Added explicit `paycheck_guardian` package selection and a real editable-install regression.
2. The Task 10 `run_baseline.py --case ...` and `run_solution.py --case ...` commands rejected `--case`. Added mode-specific, non-mutating single-case JSON output and subprocess coverage proving the final challenge output excludes Rent.
3. `metrics.json` omitted the required explicit `case_count`. Added it to all generated evaluation artifacts and refreshed canonical evidence.
4. Streamlit had no dismissal action even though dismissal state existed in the model. Added local dismissal UI/state/trajectory coverage; dismissal creates no simulated action.
5. Currency in recommendation captions rendered as math markup. Escaped currency delimiters, verified the DOM, and refreshed affected video frames plus the MP4.
6. Generated docs omitted the required `Submission verification` section and still described the MP4 as uncommitted. The renderer now gathers Python, collected tests, evaluation facts/runtime, video duration, and audited source commit from local commands, and generates the corrected submission wording.

All production fixes followed failing regression tests before implementation. The only transient failure was the first clean full-suite run: one Streamlit AppTest cold-start timed out at 20 seconds (85 passed, 1 timed out). The isolated test then passed three consecutive times in 0.56 seconds each; after the fixes, the fresh complete suite passed 89/89 in 3.27 seconds.

## Exact final evidence

- Python: 3.11.15; `pip check`: no broken requirements.
- Receipt generation: exit 0; no retained receipt changes.
- Challenge baseline: emitted Rent as the expected unsafe baseline finding.
- Challenge final: emitted Netflix only; no Rent prediction.
- Offline evaluation: 12 synthetic cases; wall time 0.12 seconds; final-mode retained runtime 3 ms; model cost USD 0.00.
- Baseline: precision 0.6250, recall 0.4167, F1 0.5000, 3 unsupported claims.
- Final: precision 1.0000, recall 1.0000, F1 1.0000, 0 unsupported claims; no final Rent prediction.
- Tests: 89 passed in 3.27 seconds.
- Streamlit: loaded 8 synthetic transactions; analyzed the verified plan; downloaded Markdown and JSON; expanded the trajectory; confirmed the approval gate; approved a local simulation; dismissed a recommendation with no action.
- Video: H.264, 1920×1080, yuv420p; AAC stereo at 48 kHz; 280.000 seconds; 4,507,162 bytes; SHA-256 `69e680167975d33b0e47e54995e8df154a46465bdfb40374fcf670eb22282793`; full audio/video decode exited 0. Representative frames were visually inspected.
- Privacy/secret/forbidden-marker scan: zero matches across the exact repository-wide audit and the narrower public-artifact audit.
- License: repository MIT license present; built wheel contains `dist-info/licenses/LICENSE` and declares `License-File: LICENSE`. Direct pinned dependencies reported MIT/MIT-CMU or Apache-2.0-compatible metadata.
- Required deliverables: README, REPRODUCTION, MP4, baseline trajectory, and final trajectory all present.

## Concerns

No blocking concerns. Evaluation runtime is intentionally machine-specific. Generated verification now records the explicit tested implementation commit `d78e53fc1c6f1a96c9962431412711ae75e7be1a`, independently of later documentation commits.

## Fix Round 1

Addressed both Important review findings:

1. Rebuilt the three forbidden self-check terms from noncontiguous fragments at runtime. The test behavior is unchanged, while the repository source no longer triggers its own audit.
2. Replaced implicit `HEAD` capture with required `--verified-source-commit` input. The renderer validates the supplied object with `git rev-parse --verify <value>^{commit}`, canonicalizes it to the full commit hash, rejects an invalid value, and writes the same explicit hash into both generated documents and their documented reproduction commands.

TDD evidence:

- Red: `test_renderer_generates_command_backed_submission_verification` failed because `--verified-source-commit not-a-commit` incorrectly exited 0 under the old renderer.
- Green: the focused deterministic renderer test passed after validation/input implementation; two renders with the same explicit commit produced byte-identical README and REPRODUCTION outputs.

Final commands and outputs:

- `.verify-venv/bin/python scripts/render_submission_docs.py --verified-source-commit d78e53fc1c6f1a96c9962431412711ae75e7be1a` → `rendered evidence-backed submission documents and representative artifacts`.
- `git cat-file -e d78e53fc1c6f1a96c9962431412711ae75e7be1a^{commit}` → exit 0.
- Exact repository scan from the Task 10 brief, with failure on any match → zero matches.
- Public privacy/secret/path scan over README, REPRODUCTION, and artifacts → zero matches.
- `.verify-venv/bin/pytest tests/test_submission.py -q` → 12/12 passed.
- `.verify-venv/bin/pytest` → 89 passed in 3.68 seconds.
- `git diff --check` → exit 0.
