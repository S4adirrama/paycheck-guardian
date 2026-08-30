# Paycheck Guardian

Paycheck Guardian is a local-first prototype for people who want a safer way to find potential savings before their next paycheck. It turns transaction evidence into a short, reviewable set of recommendations; it never contacts a bank, merchant, or subscription service.

## Problem & User Value

The bottleneck is not spotting a recurring charge; it is deciding whether that pattern is safe to act on. A plausible-looking monthly charge can be rent, insurance, a duplicate, a price change, or a merchant alias. Paycheck Guardian normalizes merchant labels, detects recurring, duplicate, and discretionary patterns, verifies every recommendation against its underlying transactions, and leaves the person at a human checkpoint before any local cancellation simulation.

The intended user is a person reviewing their own spending shortly before payday. The value is an evidence-bearing suggestion with a monthly and next-paycheck estimate, not autonomous financial action. The Alex demo and all evaluation cases are synthetic; no personal banking data is included in this repository.

## Architecture & Safety Boundaries

- Deterministic CSV/fixture parsers and merchant normalization keep the offline path reproducible.
- Evidence-first recurrence, duplicate, anomaly, category-summary, and discretionary tools produce candidate transactions and cent-rounded estimates.
- Cancellation requires a positive semantic allowlist; telecom, utilities, unknown merchants, and other ambiguous recurrence remain non-cancellable.
- A verifier checks structured target/action fields, evidence, arithmetic, confidence, caveats, and cancellation semantics before canonical display copy is shown.
- Cross-recommendation evidence ownership prevents one charge from being counted in more than one active savings action.
- Streamlit runs locally. The only cancellation capability is a clearly labelled local simulation after an acknowledgement; no bank or merchant integration exists.

## Measured Improvement

The retained offline evaluation covers 12 synthetic cases, including merchant aliases, price drift, annual cadence, duplicates, discretionary patterns, ambiguity, and essential payments. All modes receive identical original rows, whose case fingerprints are retained in `artifacts/evaluation/metrics.json`.

| Retained mode | Precision | Recall | F1 | Unsupported claims |
| --- | ---: | ---: | ---: | ---: |
| Fair baseline | 0.5556 | 0.3846 | 0.4545 | 4 |
| Normalization only | 0.6364 | 0.5385 | 0.5833 | 4 |
| Unverified drafts | 0.8125 | 1.0000 | 0.8966 | 3 |
| Removed unsafe recurrence experiment | 0.0833 | 0.0769 | 0.0800 | 11 |
| Final verified workflow | 1.0000 | 1.0000 | 1.0000 | 0 |

In the retained run, matched final recommendations have evidence coverage 1.0000 and mean monthly-savings error USD 0.0000. The final workflow records 13 true positives, 0 false positives, and 0 false negatives. Offline model cost is USD 0.00.

## Improvement Changelog

1. **Baseline.** Exact raw merchant labels and a 26–35-day recurrence rule reached F1 0.4545; it retained 4 unsupported claims.
2. **Normalization.** Canonical merchant grouping alone reached F1 0.5833; it still retained 4 unsupported claims.
3. **Candidate tools and verification.** The unverified recurrence, duplicate, anomaly, and discretionary candidates reached F1 0.8966 with 3 unsupported claims. The candidate tools drive opportunity recall and F1; the verifier's measured role is reducing unsupported claims before display.
4. **Removed experiment.** `removed_unsafe_recurrence` labels any normalized 26–35-day pair as cancellable and uses no duplicate, anomaly, category-summary, discretionary, or verification tool. Its retained predictions score F1 0.0800 with 11 unsupported claims, including essential and irregular-payment false positives. It was removed because recurrence alone cannot justify cancellation advice.
5. **Final.** The verifier rejects unsupported essential-payment advice and retains only evidence-backed recommendations: F1 1.0000 and 0 unsupported claims in this synthetic evaluation.

The explicit human checkpoint is a local product-safety control. It is not a prediction and is not included in precision, recall, F1, or unsupported-claim scoring.

## Main Failure Mode

The main remaining risk is semantic ambiguity in real transaction exports: merchant labels and categories can be incomplete or misleading. The retained score demonstrates correctness only on the 12 synthetic cases, not on live bank data or a representative population. Treat every output as a review prompt, keep the evidence visible, and do not use this prototype for autonomous financial decisions.

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

### Third-party components and licenses

| Layer | Component | Pinned/tested version | License |
| --- | --- | --- | --- |
| Runtime | Python | 3.11.15 tested | PSF-2.0 |
| Runtime | Pydantic | 2.13.5 | MIT |
| Runtime | Streamlit | 1.50.0 | Apache-2.0 |
| Runtime | Pillow | 11.3.0 | MIT-CMU |
| Optional online | OpenAI Python SDK | 2.48.0 | Apache-2.0 |
| Build/dev | setuptools | 82.0.1 build pin | MIT |
| Dev/test | pytest | 8.4.2 | MIT |
| Browser automation | Playwright | 1.60.0 | Apache-2.0 |
| Browser runtime | Chromium / Chrome for Testing | 148.0.7778.96, Playwright revision 1223 tested | BSD-3-Clause core plus bundled third-party notices |
| Reproduction | Git | 2.50.1 Apple Git-155 tested | GPL-2.0-only |
| Media | FFmpeg / ffprobe | 8.0.1 tested Homebrew GPL build | GPL-3.0-or-later for the tested build; license varies with build flags |

## Submission verification

Fresh offline audit evidence: Python 3.11.15; 122 tests collected; 12 synthetic cases; final F1 1.0000 with 0 unsupported claims; final-mode runtime 4 ms. The H.264 demo video is 280.000 seconds. Audited source commit: `e09764b34f1d084f7b67890939c4eb3175347a5d`.
