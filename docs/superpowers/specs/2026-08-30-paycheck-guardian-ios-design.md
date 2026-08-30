# Paycheck Guardian iOS — Design Specification

**Date:** 2026-08-30  
**Status:** Awaiting final user approval  
**Target:** iOS 17+, iPhone Simulator, hackathon demonstration  
**Language and UI:** Swift 6 / SwiftUI, with no Python runtime dependency

## 1. Objective

Port the complete Paycheck Guardian hackathon prototype to a native iOS application that can be opened in Xcode, launched in an iOS 17 Simulator, and demonstrated without internet access. The iOS app preserves the evidence-first agent workflow: it identifies possible savings before the next paycheck, independently verifies every recommendation, exposes the supporting transactions and calculation, and requires an explicit human decision before a local-only action simulation.

The operational iOS deliverable is implemented entirely in Swift. The existing Python prototype may remain in the repository as historical and evaluation reference material, but it is not required to build, run, test, or demonstrate the iOS application.

## 2. Audience and Product Promise

The target audience is a US consumer reviewing personal spending shortly before payday. The app answers: “Which optional expenses could I safely review now, and how much could that preserve before my next paycheck?”

The product does not connect to banks or merchants and does not actually cancel subscriptions. It produces a short, auditable plan from local transaction evidence and stops at a human approval checkpoint.

## 3. Chosen Architecture

The selected architecture is a native SwiftUI application backed by a reusable Swift Package.

```text
SwiftUI inputs
    ↓
PaycheckGuardianCore
    ↓
Parser / Normalizer
    ↓
Analysis tools
    ↓
Savings agent
    ↓
Independent verifier
    ↓
Verified plan
    ↓
Human approval
    ↓
Local simulation only
```

### 3.1 Targets

- `PaycheckGuardianApp`: iOS 17 SwiftUI application.
- `PaycheckGuardianCore`: platform-independent Swift Package containing models, parsing, analysis, orchestration, verification, trajectory recording, and evaluation logic.
- `PaycheckGuardianCoreTests`: XCTest coverage for calculations, safety rules, parsers, verification, orchestration, and evaluation.
- `PaycheckGuardianUITests`: launch and end-to-end demo-flow tests in Simulator.
- `PaycheckGuardianEvaluation`: Swift command-line executable that runs the retained 12-case synthetic evaluation and emits reproducible JSON/Markdown results.

### 3.2 Repository placement

The native deliverable lives under `ios/` in the existing Paycheck Guardian repository:

```text
ios/
├── PaycheckGuardian.xcodeproj
├── PaycheckGuardianApp/
├── PaycheckGuardianUITests/
└── Packages/PaycheckGuardianCore/
```

The project must build from Xcode without requiring CocoaPods, a Python environment, a network connection, or third-party runtime libraries.

## 4. Core Domain Model

- `Money`: currency plus positive `Decimal` amount, with cent rounding and US dollar formatting.
- `Transaction`: opaque ID, date, raw merchant label, normalized merchant, amount, category, and source evidence reference.
- `AnalysisWindow`: analysis date and next-paycheck date. The next paycheck must be strictly later than the analysis date.
- `CandidateRecommendation`: structured target, action, evidence IDs, monthly estimate, next-paycheck estimate, confidence, and caveats.
- `VerificationResult`: accepted/rejected status, canonical recommendation when accepted, and structured rejection reasons.
- `VerifiedRecommendation`: immutable verified output with disjoint evidence ownership.
- `SavingsPlan`: at most three ranked active recommendations and aggregate totals.
- `TrajectoryEvent`: typed, redacted agent event using opaque identifiers only.

Financial arithmetic uses `Decimal`; binary floating-point values are not used for money. Dates use a deterministic Gregorian calendar and fixed UTC computations inside the core. Locale-sensitive rendering occurs only in the UI.

## 5. Import and Demo Data

The app offers two entry paths:

1. **Run built-in demo** — loads bundled synthetic US transaction data and provides a one-tap hackathon flow.
2. **Import files** — accepts supported CSV transaction exports and bundled-format receipt images through the iOS document picker.

Multiple selected files are merged deterministically. Duplicate source rows are not silently counted twice. Unsupported image layouts, empty files, malformed amounts, punctuation-only merchant labels, and invalid dates produce user-readable validation errors instead of partial unsafe recommendations.

Imported and demo data remain in memory for the session. No SwiftData, Core Data, cloud synchronization, analytics SDK, or external API is required.

## 6. Analysis Tools

The core exposes separate deterministic tools for:

- merchant normalization and alias grouping;
- recurring-subscription detection;
- duplicate-charge detection;
- price and spending anomaly detection;
- category summaries;
- discretionary-spending patterns.

Subscription cancellation candidates require a positive semantic allowlist. Telecom, utilities, rent, insurance, medical, debt, unknown merchants, and ambiguous recurrence are never presented as cancellable subscriptions. Analysis tools produce facts and candidates; they do not directly create user-visible claims.

## 7. Agent and Verification Contract

The savings agent performs a deterministic offline orchestration run:

1. Record a redacted `toolCalled` event before each tool invocation.
2. Invoke all required analysis tools.
3. Record a structured, redacted `toolResult` event after each invocation.
4. Build candidate recommendations from tool facts.
5. Submit every candidate to an independent verifier.
6. Retry at most once only when verifier feedback identifies a concrete arithmetic or evidence correction derived from canonical tool facts.
7. Omit candidates that cannot be safely corrected.
8. Prevent evidence overlap across retained recommendations.
9. Rank deterministically and retain at most three accepted recommendations.

The verifier recomputes monthly and next-paycheck savings, confirms evidence ownership, validates structured target/action semantics, canonicalizes displayed copy, and rejects non-positive or unsupported amounts. The strict date rule prevents a same-day paycheck from producing zero-dollar recommendations.

Trajectory identifiers are generated from opaque stable hashes or random UUIDs and must never contain merchant slugs, filenames, account values, authorization values, or environment secrets.

## 8. User Experience

### 8.1 Main flow

1. **Welcome / Data source** — prominent “Run Demo” action and secondary file import.
2. **Review setup** — analysis date and next-paycheck date controls with immediate validation.
3. **Analysis progress** — clear local-processing states without pretending that an online bank connection exists.
4. **Verified plan** — a headline next-paycheck savings estimate and up to three recommendation cards.
5. **Evidence detail** — each card exposes transactions, calculation, confidence, caveats, and verification status.
6. **Human checkpoint** — approve or dismiss each recommendation.
7. **Local simulation result** — approved cancellation actions show a clearly labeled simulated confirmation; no external action is performed.
8. **Agent trace** — a separate screen presents safe tool-call, tool-result, verification, retry, and checkpoint events.

### 8.2 Interaction rules

- Dismissing a recommendation immediately removes it from active totals and selectors.
- Approval is idempotent: repeating it cannot add savings twice or create duplicate events.
- Approval requires the recommendation to still pass a fresh verification.
- The plan never claims guaranteed savings.
- Empty, loading, validation, failure, and completed states are visually distinct.

### 8.3 Visual direction

The interface uses native SwiftUI components, Dynamic Type, VoiceOver labels, sufficient contrast, light/dark appearances, and US currency/date formatting. A large savings card anchors the plan screen, while verification badges and evidence disclosure make safety legible during a live demonstration.

## 9. Error Handling and Privacy

- All parsing and domain failures use typed errors with concise recovery guidance.
- A failed file does not crash the app or silently contaminate merged data.
- No credentials, bank account identifiers, merchant integrations, telemetry, or network requests exist in the demo path.
- Trajectory payloads are recursively redacted by sensitive-key policy before storage or display.
- Imported content is session-only and cleared when the app process ends or the user resets the demo.
- The app states that it is an educational hackathon prototype, not financial advice.

## 10. Evaluation and Testing

The Swift evaluation executable ports the same 12 synthetic cases and measures baseline, normalization-only, unverified, removed unsafe recurrence, and final verified workflows. It reports precision, recall, F1, TP/FP/FN, evidence coverage, monthly-estimate error, unsupported claims, runtime, and zero model cost.

Acceptance targets for the retained fixture set:

- final precision, recall, and F1: `1.0000`;
- final unsupported claims: `0`;
- all expected truth evidence IDs must be present for a match;
- final recommendations must have non-overlapping evidence;
- the removed unsafe recurrence experiment must remain genuinely distinct from the final workflow.

Test layers:

- unit tests for parsing, normalization, dates, `Decimal` rounding, detectors, verifier, retry bounds, ranking, evidence ownership, redaction, approval, and dismissal;
- fixture-integrity and evaluation regression tests;
- UI tests for launch, demo, validation, plan display, evidence disclosure, approval, dismissal, trace, reset, import, and multiple-file handling;
- command-line build/test checks using `xcodebuild` with an iOS 17-compatible Simulator destination;
- privacy scans over source, generated trajectories, reports, and screenshots.

## 11. Hackathon Deliverables

- runnable Xcode project targeting iOS 17+;
- all operational application and evaluation logic in Swift;
- shared Swift Package and XCTest suites;
- bundled synthetic demo fixtures;
- reproducible Swift evaluation artifacts;
- README and exact Xcode/CLI reproduction instructions;
- screenshots and, if refreshed for the native version, a Simulator demonstration video;
- explicit safety disclosure and MIT license information.

## 12. Definition of Done

The work is complete when a reviewer can clone/open the repository, select an available iPhone Simulator, build and run the application without Python or network setup, execute the one-tap demo, inspect verified evidence, approve and dismiss simulated actions, view a privacy-safe agent trace, and reproduce the full Swift test and evaluation suite from documented commands.
