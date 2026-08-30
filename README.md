# Paycheck Guardian

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

The retained offline evaluation covers 12 synthetic cases, including merchant aliases, price drift, annual cadence, duplicates, discretionary patterns, ambiguity, and essential payments. All modes receive identical original rows, whose case fingerprints are retained in `artifacts/evaluation/metrics.json`.

| Retained mode | Precision | Recall | F1 | Unsupported claims |
| --- | ---: | ---: | ---: | ---: |
| Fair baseline | 0.6250 | 0.4167 | 0.5000 | 3 |
| Normalization only | 0.7000 | 0.5833 | 0.6363 | 3 |
| Unverified drafts | 0.8000 | 1.0000 | 0.8889 | 3 |
| Removed unsafe recurrence experiment | 0.8000 | 1.0000 | 0.8889 | 3 |
| Final verified workflow | 1.0000 | 1.0000 | 1.0000 | 0 |

In the retained run, matched final recommendations have evidence coverage 1.0000 and mean monthly-savings error USD 0.0000. The final workflow records 12 true positives, 0 false positives, and 0 false negatives. Offline model cost is USD 0.00.

## Improvement Changelog

1. **Baseline.** Exact raw merchant labels and a 26–35-day recurrence rule reached F1 0.5000; it retained 3 unsupported claims.
2. **Normalization.** Canonical merchant grouping alone reached F1 0.6363; it still retained 3 unsupported claims.
3. **Verification.** Deterministic candidate generation before filtering reached F1 0.8889 with 3 unsupported claims, making the verifier's contribution auditable.
4. **Removed experiment.** `removed_unsafe_recurrence` treats every detected 26–35-day charge as cancellable before the final safety gate. Its retained predictions score F1 0.8889 with 3 unsupported claims, including essential-payment false positives. It was removed because recurring evidence alone cannot justify cancellation advice for rent, insurance, healthcare, utilities, or debt.
5. **Final.** The verifier rejects unsupported essential-payment advice and retains only evidence-backed recommendations: F1 1.0000 and 0 unsupported claims in this synthetic evaluation.

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

## Submission verification

Fresh offline audit evidence: Python 3.11.15; 89 tests collected; 12 synthetic cases; final F1 1.0000 with 0 unsupported claims; final-mode runtime 3 ms. The H.264 demo video is 280.000 seconds. Audited source commit: `d7d499047c622878a43f39ede0f6ffcdc31947d0`.
