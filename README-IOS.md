# Paycheck Guardian for iOS 17

The native hackathon application is a Swift 6 / SwiftUI project backed by a local Swift Package. It runs offline, uses synthetic fixtures for the one-tap demo, and performs no bank, merchant, analytics, or cancellation network action.

## 60-second promo

The hackathon-ready English product film is at `artifacts/ios/promo/paycheck-guardian-promo.mp4`. Its editable Remotion source, exact reproduction commands, narration source, and audio generators are documented in `promo/README.md`.

## Run in Simulator

Requirements: macOS with Xcode 16 or newer and an iOS 17-or-newer iPhone Simulator runtime. The retained audit used Xcode 26.2 and Swift 6.2.3.

1. Open `ios/PaycheckGuardian.xcodeproj` in Xcode.
2. Select the shared `PaycheckGuardian` scheme.
3. Select an iPhone Simulator running iOS 17 or newer.
4. Press **Run**.
5. Tap **Run the hackathon demo**.

The demo opens a verified plan. Each recommendation exposes its source transactions, calculation, confidence, caveats, and verifier result. Approval records only a local simulation. Dismissal immediately removes the item from the active total. **See how the agent decided** opens the privacy-safe trajectory.

## Exact command-line checks

From the repository root:

```bash
ios/scripts/run-ios-tests.sh
ios/scripts/run-evaluation.sh
ios/scripts/capture-simulator-demo.sh
```

The defaults target `iPhone 17 Pro`. To use a different available device:

```bash
IOS_SIMULATOR_DESTINATION='platform=iOS Simulator,name=iPhone 15 Pro,OS=17.5' ios/scripts/run-ios-tests.sh
```

`run-ios-tests.sh` runs the standalone Swift package tests followed by the application and XCUITest suites. `run-evaluation.sh` regenerates the 12-case offline evaluation. `capture-simulator-demo.sh` executes the real UI flow and writes five Simulator screenshots to `artifacts/ios/screenshots/`.

## Import formats

- CSV with `date`, `description` or `merchant`, and `amount`; optional categories are normalized locally.
- UTF-8 receipt text with one `DATE`, `MERCHANT`, and `TOTAL` field.
- PNG or JPEG receipt images. Apple Vision performs OCR on-device before the bounded receipt parser validates the fields.
- Multiple files may be selected; identical evidence rows are deterministically deduplicated.

Imported data stays in memory for the current process and is cleared by **Reset** or when the app exits.

## Architecture and safety

- `ios/PaycheckGuardianApp/` contains native SwiftUI presentation and session state.
- `ios/Packages/PaycheckGuardianCore/` contains all parsing, normalization, analysis, verification, orchestration, trajectory, and evaluation logic.
- All money uses `Decimal`, and the next-paycheck date must be strictly later than the analysis date.
- Every displayed recommendation passes the independent verifier; evidence cannot be counted across two active recommendations.
- Cancellation language uses a positive allowlist. Essential, telecom, utility, medical, debt, and unknown recurrence is not presented as cancellable.
- Trajectories use opaque identifiers and recursive sensitive-key redaction.
- At most three verified recommendations are shown. A repair is attempted at most once and only from canonical tool facts.

The project has no CocoaPods, third-party runtime package, Python dependency, API key, persistence layer, telemetry SDK, or network requirement.

## Retained Swift evaluation

The bundled 12-case synthetic evaluation retains the following final results:

| Mode | Precision | Recall | F1 | Unsupported |
| --- | ---: | ---: | ---: | ---: |
| Fair baseline | 0.5556 | 0.3846 | 0.4545 | 4 |
| Normalization only | 0.6364 | 0.5385 | 0.5833 | 4 |
| Unverified drafts | 0.8125 | 1.0000 | 0.8966 | 3 |
| Removed unsafe recurrence | 0.0833 | 0.0769 | 0.0800 | 11 |
| Final verified workflow | 1.0000 | 1.0000 | 1.0000 | 0 |

These scores describe only the synthetic fixtures; they are not evidence of real-world financial performance. Paycheck Guardian is an educational prototype, not financial advice.
