# Native iOS Verification

Audit environment: macOS 15.7.9, Xcode 26.2, Swift 6.2.3, iPhone 17 Pro Simulator running iOS 26.2, deployment target iOS 17.0.

## Results

- `ios/scripts/run-ios-tests.sh`: 41 Swift Core tests, 5 application-model tests, and 4 Simulator UI tests passed with zero failures.
- `ios/scripts/run-evaluation.sh`: 12 synthetic cases; final precision, recall, and F1 1.0000; 13 TP, 0 FP, 0 FN; 0 unsupported claims; evidence coverage 1.0000; USD 0.0000 mean savings error; USD 0.00 model cost.
- `ios/scripts/capture-simulator-demo.sh`: five 1206×2622 PNGs produced from the real XCUITest flow.
- Visual inspection: welcome, verified plan, evidence detail, local simulated approval, and privacy-safe trace render full-screen without clipping or compatibility-mode letterboxing.
- Static review: no network API, persistence API, third-party runtime dependency, `Double`/`Float` money arithmetic, repository TODO, or source-path disclosure in the native deliverable.

System-owned Xcode warnings about not stripping signed XCTest frameworks can appear during command-line UI-test builds; they originate from the installed Apple simulator toolchain and do not affect the application binary or test result.
