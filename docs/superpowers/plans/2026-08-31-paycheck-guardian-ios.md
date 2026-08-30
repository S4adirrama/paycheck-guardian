# Paycheck Guardian iOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete SwiftUI Paycheck Guardian application that runs end-to-end in an iOS 17 Simulator with a reusable Swift core, safe verified recommendations, local approval simulation, tests, evaluation artifacts, and exact reproduction instructions.

**Architecture:** A native iOS app owns presentation and session state while a local Swift Package owns every domain, parsing, analysis, verification, orchestration, trajectory, and evaluation rule. The app bundles synthetic fixtures and never requires Python, third-party packages, network access, persistence, bank access, or merchant access.

**Tech Stack:** Swift 6.2, SwiftUI, Foundation, CryptoKit, Vision, UniformTypeIdentifiers, XCTest, XCUITest, Swift Package Manager, Xcode 26.2, iOS 17 deployment target.

**Spec:** `docs/superpowers/specs/2026-08-30-paycheck-guardian-ios-design.md`

## Global Constraints

- Deployment target is iOS 17.0 or later and the primary deliverable must run in iPhone Simulator.
- All operational app and evaluation code is Swift; Python is not a build or runtime dependency.
- Money uses `Decimal` with explicit cent rounding; never use `Double` for financial values.
- `nextPaycheck` must be strictly later than `analysisDate`.
- The demo is local-only and performs no network, bank, merchant, telemetry, or real cancellation action.
- Every displayed recommendation must pass an independent verifier and active recommendations must have disjoint evidence IDs.
- Retain at most three recommendations; retry a rejected draft at most once and only from canonical facts.
- Cancellation uses a positive category allowlist; essential, telecom, and unknown categories are not cancellable.
- Trajectory identifiers and payloads must expose no merchant slugs, filenames, credentials, or personal identifiers.
- Demo and evaluation data are synthetic and must be visibly labeled as such.
- Use test-driven development: observe the focused test fail before adding production behavior, then observe it pass.

---

## File Structure

```text
ios/
├── PaycheckGuardian.xcodeproj/project.pbxproj
├── PaycheckGuardianApp/
│   ├── PaycheckGuardianApp.swift
│   ├── AppModel.swift
│   ├── RootView.swift
│   ├── WelcomeView.swift
│   ├── SetupView.swift
│   ├── PlanView.swift
│   ├── RecommendationCard.swift
│   ├── EvidenceView.swift
│   ├── TraceView.swift
│   ├── VisionReceiptImporter.swift
│   ├── DesignSystem.swift
│   ├── PrivacyInfo.xcprivacy
│   └── Resources/
│       ├── demo-transactions.csv
│       ├── demo-receipt-01.png
│       ├── demo-receipt-02.png
│       ├── demo-receipt-03.png
│       ├── merchant-aliases.json
│       └── Assets.xcassets/Contents.json
├── PaycheckGuardianAppTests/AppModelTests.swift
├── PaycheckGuardianUITests/PaycheckGuardianUITests.swift
├── Packages/PaycheckGuardianCore/
│   ├── Package.swift
│   ├── Sources/PaycheckGuardianCore/
│   │   ├── Money.swift
│   │   ├── DomainModels.swift
│   │   ├── DomainError.swift
│   │   ├── CSVParser.swift
│   │   ├── ReceiptTextParser.swift
│   │   ├── MerchantNormalizer.swift
│   │   ├── AnalysisTools.swift
│   │   ├── RecommendationFactory.swift
│   │   ├── Verifier.swift
│   │   ├── Trajectory.swift
│   │   ├── SavingsAgent.swift
│   │   ├── Evaluation.swift
│   │   └── Resources/
│   │       ├── evaluation-cases.json
│   │       └── merchant-aliases.json
│   ├── Sources/PaycheckGuardianEvaluation/main.swift
│   └── Tests/PaycheckGuardianCoreTests/
│       ├── MoneyAndModelTests.swift
│       ├── ParserNormalizerTests.swift
│       ├── AnalysisToolsTests.swift
│       ├── VerifierTests.swift
│       ├── SavingsAgentTests.swift
│       ├── TrajectoryTests.swift
│       └── EvaluationTests.swift
├── Config/Debug.xcconfig
├── Config/Release.xcconfig
└── scripts/
    ├── run-ios-tests.sh
    ├── run-evaluation.sh
    └── capture-simulator-demo.sh
artifacts/ios/
├── evaluation/metrics.json
├── evaluation/per-case-results.json
├── trajectories/demo-final.json
└── screenshots/
README-IOS.md
```

---

### Task 1: Swift Package Scaffold and Validated Domain Types

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Package.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Money.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/DomainModels.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/DomainError.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/MoneyAndModelTests.swift`

**Interfaces:**
- Produces: `Money.init(_:) throws`, `Money.prorated(from:to:) throws -> Money`, `AnalysisWindow.init(analysisDate:nextPaycheck:) throws`, `Transaction`, `CandidateRecommendation`, `VerifiedRecommendation`, `SavingsPlan`, and domain enums used by every later task.

- [ ] **Step 1: Create the Swift package manifest and failing money/date tests**

```swift
func testMoneyRoundsHalfUpToCents() throws {
    XCTAssertEqual(try Money("10.125").amount, Decimal(string: "10.13")!)
}

func testAnalysisWindowRejectsSameDayPaycheck() {
    XCTAssertThrowsError(try AnalysisWindow(
        analysisDate: Date.fixture("2026-07-10"),
        nextPaycheck: Date.fixture("2026-07-10")
    ))
}

func testProrationIsPositiveForTomorrow() throws {
    let value = try Money("15.49").prorated(
        from: Date.fixture("2026-07-10"),
        to: Date.fixture("2026-07-11")
    )
    XCTAssertEqual(value.amount, Decimal(string: "0.51")!)
}

private extension Date {
    static func fixture(_ value: String) -> Date {
        ISO8601DateFormatter.fixtureDate.date(from: value)!
    }
}
```

- [ ] **Step 2: Run the focused tests and confirm the missing-type failure**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter MoneyAndModelTests`

Expected: compilation fails because `Money` and `AnalysisWindow` do not exist.

- [ ] **Step 3: Implement immutable validated value types and Codable models**

```swift
public struct Money: Codable, Hashable, Sendable, Comparable {
    public let amount: Decimal

    public init(_ value: Decimal) throws {
        var source = value
        var rounded = Decimal()
        NSDecimalRound(&rounded, &source, 2, .plain)
        guard rounded > 0 else { throw DomainError.nonPositiveMoney }
        self.amount = rounded
    }

    public init(_ text: String) throws {
        guard let value = Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")) else {
            throw DomainError.invalidMoney(text)
        }
        try self.init(value)
    }
}

public struct AnalysisWindow: Hashable, Sendable {
    public let analysisDate: Date
    public let nextPaycheck: Date

    public init(analysisDate: Date, nextPaycheck: Date) throws {
        guard nextPaycheck > analysisDate else { throw DomainError.invalidPaycheckDate }
        self.analysisDate = analysisDate
        self.nextPaycheck = nextPaycheck
    }
}
```

Define closed enums for source, category/action, recommendation kind, confidence, status, and verification reason. Use explicit initializers that reject empty transaction IDs, merchants, categories, and evidence lists.

- [ ] **Step 4: Run package tests and verify success**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter MoneyAndModelTests`

Expected: all `MoneyAndModelTests` pass.

- [ ] **Step 5: Commit the validated domain foundation**

```bash
git add ios/Packages/PaycheckGuardianCore
git commit -m "feat(ios): add validated Swift domain model"
```

---

### Task 2: CSV Import and Merchant Normalization

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/CSVParser.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/ReceiptTextParser.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/MerchantNormalizer.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Resources/merchant-aliases.json`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/ParserNormalizerTests.swift`
- Copy fixture content from: `data/merchant_aliases.json`

**Interfaces:**
- Consumes: `Transaction`, `Money`, `DomainError`.
- Produces: `CSVTransactionParser.parse(data:sourceName:isSynthetic:) throws -> [Transaction]`, `CSVTransactionParser.merge(_:) -> [Transaction]`, `ReceiptTextParser.parse(_:sourceID:isSynthetic:) throws -> Transaction`, and `MerchantNormalizer.normalize(_:) throws -> NormalizedMerchant`.

- [ ] **Step 1: Write failing tests for quoted CSV, aliases, deduplication, and invalid labels**

```swift
func testAliasNormalizationGroupsNetflixVariants() throws {
    let normalizer = try MerchantNormalizer.bundled()
    XCTAssertEqual(try normalizer.normalize("NETFLIX * 800-585").displayName, "Netflix")
}

func testPunctuationOnlyMerchantIsRejected() throws {
    let csv = "date,merchant,amount,category\n2026-07-01,***,12.00,streaming\n"
    XCTAssertThrowsError(try parser.parse(data: Data(csv.utf8), sourceName: "fixture.csv", isSynthetic: true))
}

func testMultiFileMergeRemovesIdenticalEvidenceRows() throws {
    XCTAssertEqual(parser.merge([rows, rows]).count, rows.count)
}

func testReceiptTextParsesRequiredFields() throws {
    let text = "Merchant: Coffee Corner\nDate: 2026-07-08\nTotal: $12.40\nCategory: coffee"
    let row = try receiptParser.parse(text, sourceID: "opaque-1", isSynthetic: true)
    XCTAssertEqual(row.amountUSD, try Money("12.40"))
    XCTAssertEqual(row.category, "coffee")
}

func testReceiptWithoutTotalIsRejected() {
    XCTAssertThrowsError(try receiptParser.parse("Merchant: Cafe", sourceID: "opaque-1", isSynthetic: true))
}
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter ParserNormalizerTests`

Expected: compilation fails because parser and normalizer interfaces are missing.

- [ ] **Step 3: Implement RFC-4180-style field parsing and deterministic normalization**

```swift
public func parse(data: Data, sourceName: String, isSynthetic: Bool) throws -> [Transaction] {
    guard let text = String(data: data, encoding: .utf8) else { throw DomainError.invalidUTF8 }
    let records = try CSVRecords.parse(text)
    guard records.headers == requiredHeaders else { throw DomainError.invalidCSVHeaders }
    return try records.rows.enumerated().map { index, row in
        let normalized = try normalizer.normalize(row.merchant)
        return try Transaction(
            id: EvidenceID.digest(sourceOrdinal: index, date: row.date, merchant: row.merchant, amount: row.amount),
            date: dateParser.parse(row.date),
            merchantRaw: row.merchant,
            merchantNormalized: normalized.displayName,
            amountUSD: Money(row.amount),
            category: normalized.categoryOverride ?? row.category,
            source: .bankCSV,
            sourceReference: EvidenceID.opaqueSource(sourceName, index),
            isSynthetic: isSynthetic
        )
    }
}
```

Use CryptoKit SHA-256 for content-based opaque source/evidence IDs. Never include source filenames or merchant text in emitted IDs.

Parse receipt OCR text only when all four labeled lines (`Merchant`, `Date`, `Total`, `Category`) exist exactly once. This intentionally bounded format prevents guessed amounts or dates from entering analysis.

- [ ] **Step 4: Run all parser tests and package tests**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter ParserNormalizerTests && swift test`

Expected: focused and complete package suites pass.

- [ ] **Step 5: Commit import and normalization**

```bash
git add ios/Packages/PaycheckGuardianCore
git commit -m "feat(ios): parse and normalize local transaction data"
```

---

### Task 3: Deterministic Analysis Tools

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/AnalysisTools.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/AnalysisToolsTests.swift`

**Interfaces:**
- Consumes: normalized `[Transaction]`.
- Produces: `RecurringCandidate`, `DuplicateCandidate`, `AnomalyCandidate`, `SpendingPattern`, `CategorySummary`, and `AnalysisTools.runAll(_:) -> AnalysisFacts`.

- [ ] **Step 1: Write failing detector tests for all five tool families**

```swift
func testMonthlyStreamingIsCancellable() throws {
    let candidate = try XCTUnwrap(AnalysisTools.findRecurring(netflixRows).first)
    XCTAssertEqual(candidate.intervalDays, 30)
    XCTAssertEqual(candidate.monthlyAmount, try Money("15.49"))
    XCTAssertTrue(candidate.cancellable)
}

func testTelecomRecurrenceIsNeverCancellable() throws {
    let candidate = try XCTUnwrap(AnalysisTools.findRecurring(telecomRows).first)
    XCTAssertFalse(candidate.cancellable)
}

func testDuplicateRequiresSameMerchantAmountWithinTwoDays() {
    XCTAssertEqual(AnalysisTools.findDuplicates(duplicateRows).count, 1)
}

func testAnomalyNeedsTwoStableComparisonsAndMaterialExcess() {
    XCTAssertEqual(AnalysisTools.findAnomalies(groceryRows).first?.monthlyAmount, try Money("54.50"))
}

func testCategorySummaryOwnsEveryCategoryEvidenceID() {
    XCTAssertEqual(Set(summary.evidenceIDs), Set(expectedIDs))
}
```

- [ ] **Step 2: Run focused tests and observe missing analysis behavior**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter AnalysisToolsTests`

Expected: compilation fails because `AnalysisTools` is undefined.

- [ ] **Step 3: Port cadence, duplicate, discretionary, anomaly, and summary algorithms**

```swift
public enum AnalysisTools {
    public static let cancellableCategories: Set<String> = [
        "streaming", "music", "cloud_storage", "subscription", "fitness"
    ]

    public static func runAll(_ transactions: [Transaction]) -> AnalysisFacts {
        AnalysisFacts(
            recurring: findRecurring(transactions),
            duplicates: findDuplicates(transactions),
            anomalies: findAnomalies(transactions),
            categorySummaries: summarizeCategories(transactions),
            discretionaryPatterns: findDiscretionaryPatterns(transactions)
        )
    }
}
```

Implement median cadence ranges `6...8`, `13...15`, `26...35`, and `350...380`; maximum recurring price drift `15%`; duplicates within two days; discretionary groups of at least three charges within 30 days; anomalies at least `2×` typical and at least `$10` excess.

- [ ] **Step 4: Run focused and complete package tests**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter AnalysisToolsTests && swift test`

Expected: every test passes and repeated runs return the same sorted facts.

- [ ] **Step 5: Commit analysis tools**

```bash
git add ios/Packages/PaycheckGuardianCore
git commit -m "feat(ios): add evidence-first spending analysis"
```

---

### Task 4: Recommendation Factory and Independent Verifier

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/RecommendationFactory.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Verifier.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/VerifierTests.swift`

**Interfaces:**
- Consumes: `AnalysisFacts`, `[Transaction]`, `AnalysisWindow`.
- Produces: `RecommendationFactory.drafts(from:) -> [CandidateRecommendation]` and `RecommendationVerifier.verify(_:facts:transactions:window:) -> VerificationResult`.

- [ ] **Step 1: Write failing safety and arithmetic verification tests**

```swift
func testVerifierCanonicalizesSavingsFromEvidence() throws {
    let badDraft = fixtureDraft(monthly: "1.00")
    let result = verifier.verify(badDraft, facts: facts, transactions: rows, window: window)
    XCTAssertEqual(result.correctableCandidate?.monthlySavingsUSD, try Money("16.49"))
}

func testVerifierRejectsDuplicateEvidenceIDs() {
    XCTAssertEqual(verifier.verify(duplicateEvidenceDraft, facts: facts, transactions: rows, window: window).status, .rejected)
}

func testVerifierRejectsEssentialCancellation() {
    XCTAssertTrue(verifier.verify(rentCancellation, facts: rentFacts, transactions: rentRows, window: window).reasons.contains(.unsafeAction))
}

func testCanonicalCopyIgnoresUntrustedDraftTitle() {
    XCTAssertEqual(accepted.recommendation?.title, "Review Netflix subscription")
}
```

- [ ] **Step 2: Run verifier tests and confirm failure**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter VerifierTests`

Expected: compilation fails because factory/verifier types are missing.

- [ ] **Step 3: Implement structured drafts, canonical truth lookup, and verifier**

```swift
public func verify(
    _ candidate: CandidateRecommendation,
    facts: AnalysisFacts,
    transactions: [Transaction],
    window: AnalysisWindow
) -> VerificationResult {
    guard Set(candidate.evidenceIDs).count == candidate.evidenceIDs.count else {
        return .rejected([.duplicateEvidence])
    }
    guard let canonical = facts.canonicalCandidate(matching: candidate) else {
        return .rejected([.unsupportedEvidence])
    }
    guard canonical.action.isAllowed(for: canonical.category) else {
        return .rejected([.unsafeAction])
    }
    let verified = try VerifiedRecommendation.canonical(canonical, window: window)
    return candidate.matchesFinancials(of: verified)
        ? .accepted(verified)
        : .correctable(verified, reasons: [.incorrectArithmetic])
}
```

Derive all display text from verified kind/action/target and never reuse a draft-provided title or rationale.

- [ ] **Step 4: Run verifier tests and full package suite**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter VerifierTests && swift test`

Expected: every verifier and package test passes.

- [ ] **Step 5: Commit verified recommendation contracts**

```bash
git add ios/Packages/PaycheckGuardianCore
git commit -m "feat(ios): independently verify savings recommendations"
```

---

### Task 5: Safe Trajectory and Agent Orchestration

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Trajectory.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/SavingsAgent.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/TrajectoryTests.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/SavingsAgentTests.swift`

**Interfaces:**
- Consumes: parser output, `AnalysisTools`, `RecommendationFactory`, `RecommendationVerifier`.
- Produces: `SavingsAgent.run(transactions:window:) throws -> AgentRun`, `SavingsAgent.approve(id:in:) throws -> AgentRun`, `SavingsAgent.dismiss(id:in:) -> AgentRun`, and privacy-safe `[TrajectoryEvent]`.

- [ ] **Step 1: Write failing orchestration, retry, ownership, action, and redaction tests**

```swift
func testEveryToolHasCallBeforeResult() throws {
    let events = try agent.run(transactions: rows, window: window).trajectory
    XCTAssertEqual(events.map(\.type), expectedCallResultSequence)
}

func testCorrectableCandidateRetriesOnceWithChangedCanonicalValue() throws {
    XCTAssertEqual(verifier.seenMonthlyAmounts, [try Money("1.00"), try Money("16.49")])
}

func testEvidenceCannotAppearInTwoRetainedRecommendations() throws {
    let plan = try agent.run(transactions: overlappingRows, window: window).plan
    XCTAssertEqual(plan.recommendations.flatMap(\.evidenceIDs).count, Set(plan.recommendations.flatMap(\.evidenceIDs)).count)
}

func testTrajectoryContainsNoMerchantSlugOrFilename() throws {
    let json = try trajectoryJSON(agent.run(transactions: secretNamedRows, window: window))
    XCTAssertFalse(json.localizedCaseInsensitiveContains("netflix"))
    XCTAssertFalse(json.localizedCaseInsensitiveContains("statement.csv"))
}

func testApprovalIsFreshVerifiedAndIdempotent() throws {
    let once = try agent.approve(id: id, in: run)
    let twice = try agent.approve(id: id, in: once)
    XCTAssertEqual(once.simulatedActions, twice.simulatedActions)
}
```

- [ ] **Step 2: Run focused tests and observe failure**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter 'TrajectoryTests|SavingsAgentTests'`

Expected: compilation fails because trajectory and agent interfaces are missing.

- [ ] **Step 3: Implement ordered orchestration and recursive redaction**

```swift
public func run(transactions: [Transaction], window: AnalysisWindow) throws -> AgentRun {
    var recorder = TrajectoryRecorder(runID: UUID().uuidString)
    let facts = analysisToolNames.reduce(into: AnalysisFacts.empty) { aggregate, tool in
        recorder.recordCall(tool: tool, input: ["transactionCount": .int(transactions.count)])
        let result = invoke(tool, transactions: transactions)
        recorder.recordResult(tool: tool, result: result.safeSummary)
        aggregate.merge(result)
    }
    let accepted = verifyDraftsWithAtMostOneConcreteRetry(facts, transactions, window, &recorder)
    let plan = SavingsPlan.selectingAtMostThreeWithoutEvidenceOverlap(accepted)
    recorder.recordCompletion(recommendationCount: plan.recommendations.count)
    return AgentRun(window: window, transactions: transactions, plan: plan, trajectory: recorder.events)
}
```

Use `UUID`/SHA-256 opaque identifiers and recursively replace values under keys matching `token`, `secret`, `password`, `authorization`, `account`, `merchant`, `filename`, and `sourceReference` before an event is stored.

- [ ] **Step 4: Run focused tests and the entire package suite**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter 'TrajectoryTests|SavingsAgentTests' && swift test`

Expected: all tests pass; no candidate is verified more than twice.

- [ ] **Step 5: Commit the safe agent workflow**

```bash
git add ios/Packages/PaycheckGuardianCore
git commit -m "feat(ios): orchestrate safe verified savings plans"
```

---

### Task 6: Swift Evaluation CLI and Retained Fixtures

**Files:**
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Evaluation.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianEvaluation/main.swift`
- Create: `ios/Packages/PaycheckGuardianCore/Sources/PaycheckGuardianCore/Resources/evaluation-cases.json`
- Create: `ios/Packages/PaycheckGuardianCore/Tests/PaycheckGuardianCoreTests/EvaluationTests.swift`
- Create: `ios/scripts/run-evaluation.sh`
- Generate: `artifacts/ios/evaluation/metrics.json`
- Generate: `artifacts/ios/evaluation/per-case-results.json`
- Copy and adapt fixture content from: `data/evaluation/cases.json`

**Interfaces:**
- Consumes: the same original rows for every mode and the complete agent workflow.
- Produces: `Evaluator.run(cases:) throws -> EvaluationReport`, JSON encoders, CLI `--output-directory`, and retained artifacts.

- [ ] **Step 1: Write failing metric and fairness tests**

```swift
func testMatchRequiresEveryTruthEvidenceID() {
    XCTAssertFalse(Evaluator.matches(predictionMissingOneID, truth: completeTruth))
}

func testFinalWorkflowReachesRetainedTargets() throws {
    let report = try evaluator.run(cases: fixtures)
    XCTAssertEqual(report.final.precision, Decimal(1))
    XCTAssertEqual(report.final.recall, Decimal(1))
    XCTAssertEqual(report.final.f1, Decimal(1))
    XCTAssertEqual(report.final.unsupportedClaims, 0)
    XCTAssertEqual(report.final.truePositives, 13)
    XCTAssertEqual(report.final.falsePositives, 0)
    XCTAssertEqual(report.final.falseNegatives, 0)
}

func testUnsafeAblationIsDistinctAndPoorerThanFinal() throws {
    XCTAssertEqual(report.removedUnsafeRecurrence.f1, Decimal(string: "0.0800"))
    XCTAssertGreaterThan(report.removedUnsafeRecurrence.unsupportedClaims, report.final.unsupportedClaims)
}
```

- [ ] **Step 2: Run evaluation tests and confirm failure**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter EvaluationTests`

Expected: compilation fails because `Evaluator` is missing.

- [ ] **Step 3: Implement modes, direct confusion counts, coverage, error, and CLI output**

```swift
let precision = tp + fp == 0 ? Decimal.zero : Decimal(tp) / Decimal(tp + fp)
let recall = tp + fn == 0 ? Decimal.one : Decimal(tp) / Decimal(tp + fn)
let f1 = precision + recall == 0 ? Decimal.zero : 2 * precision * recall / (precision + recall)
```

Fingerprint each case's original decoded rows before running any mode, assert all modes consume the same fingerprint, require full truth evidence containment to match, and encode sorted JSON with a stable `en_US_POSIX` date format.

- [ ] **Step 4: Run evaluation tests, CLI, and inspect retained metrics**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test && swift run PaycheckGuardianEvaluation --output-directory ../../../../artifacts/ios/evaluation`

Expected: 12 cases, final `P/R/F1 = 1.0000/1.0000/1.0000`, `13/0/0`, zero unsupported claims, and unsafe ablation F1 `0.0800`.

- [ ] **Step 5: Commit evaluation implementation and generated evidence**

```bash
git add ios/Packages/PaycheckGuardianCore ios/scripts/run-evaluation.sh artifacts/ios/evaluation
git commit -m "feat(ios): add reproducible Swift evaluation"
```

---

### Task 7: iOS 17 Xcode Project and SwiftUI End-to-End UX

**Files:**
- Create: `ios/PaycheckGuardian.xcodeproj/project.pbxproj`
- Create: `ios/Config/Debug.xcconfig`
- Create: `ios/Config/Release.xcconfig`
- Create: `ios/PaycheckGuardianApp/PaycheckGuardianApp.swift`
- Create: `ios/PaycheckGuardianApp/AppModel.swift`
- Create: `ios/PaycheckGuardianApp/RootView.swift`
- Create: `ios/PaycheckGuardianApp/WelcomeView.swift`
- Create: `ios/PaycheckGuardianApp/SetupView.swift`
- Create: `ios/PaycheckGuardianApp/PlanView.swift`
- Create: `ios/PaycheckGuardianApp/RecommendationCard.swift`
- Create: `ios/PaycheckGuardianApp/EvidenceView.swift`
- Create: `ios/PaycheckGuardianApp/TraceView.swift`
- Create: `ios/PaycheckGuardianApp/VisionReceiptImporter.swift`
- Create: `ios/PaycheckGuardianApp/DesignSystem.swift`
- Create: `ios/PaycheckGuardianApp/PrivacyInfo.xcprivacy`
- Create: `ios/PaycheckGuardianApp/Resources/demo-transactions.csv`
- Create: `ios/PaycheckGuardianApp/Resources/demo-receipt-01.png`
- Create: `ios/PaycheckGuardianApp/Resources/demo-receipt-02.png`
- Create: `ios/PaycheckGuardianApp/Resources/demo-receipt-03.png`
- Create: `ios/PaycheckGuardianApp/Resources/merchant-aliases.json`
- Create: `ios/PaycheckGuardianApp/Resources/Assets.xcassets/Contents.json`
- Create: `ios/PaycheckGuardianAppTests/AppModelTests.swift`

**Interfaces:**
- Consumes: public `PaycheckGuardianCore` APIs.
- Produces: `@MainActor final class AppModel`, navigable SwiftUI app, document import, demo analysis, plan decisions, reset, and trace views.

- [ ] **Step 1: Create the project skeleton and failing app-model tests**

```swift
@MainActor
func testDemoRunsToVerifiedPlan() async throws {
    let model = AppModel(loader: .fixture)
    await model.runDemo()
    XCTAssertEqual(model.route, .plan)
    XCTAssertFalse(model.activeRecommendations.isEmpty)
    XCTAssertTrue(model.activeRecommendations.allSatisfy { $0.status == .proposed })
}

@MainActor
func testDismissalRecalculatesHeadlineTotal() async throws {
    await model.runDemo()
    let before = model.nextPaycheckTotal
    model.dismiss(model.activeRecommendations[0].id)
    XCTAssertLessThan(model.nextPaycheckTotal, before)
}
```

- [ ] **Step 2: Run app tests through xcodebuild and observe failure**

Run: `xcodebuild test -project ios/PaycheckGuardian.xcodeproj -scheme PaycheckGuardian -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:PaycheckGuardianAppTests`

Expected: build/test fails because the app model and screens are not implemented.

- [ ] **Step 3: Implement the main actor state machine and native screens**

```swift
@MainActor
final class AppModel: ObservableObject {
    enum Route: Equatable { case welcome, setup, analyzing, plan, trace }
    @Published private(set) var route: Route = .welcome
    @Published private(set) var run: AgentRun?
    @Published var presentedError: UserFacingError?

    func runDemo() async {
        do {
            route = .analyzing
            let transactions = try loader.loadDemo()
            let window = try AnalysisWindow(analysisDate: demoAnalysisDate, nextPaycheck: demoPaycheckDate)
            run = try agent.run(transactions: transactions, window: window)
            route = .plan
        } catch {
            presentedError = UserFacingError(error)
            route = .setup
        }
    }
}
```

Use `NavigationStack`, `fileImporter(allowsMultipleSelection: true)`, `ContentUnavailableView`, `ProgressView`, `DisclosureGroup`, confirmation dialogs, Dynamic Type text styles, accessibility identifiers, and a visible “Simulation only — no merchant contacted” statement.

For imported PNG/JPEG receipts, `VisionReceiptImporter` uses an on-device `VNRecognizeTextRequest` with accurate recognition and passes only recognized text into `ReceiptTextParser`. It rejects unavailable security-scoped URLs and recognition results missing the bounded receipt labels. Copy the three existing synthetic PNG fixtures into the app bundle and mark every rendered demo row as synthetic.

- [ ] **Step 4: Run app-model tests, build, and launch smoke check**

Run: `xcodebuild test -project ios/PaycheckGuardian.xcodeproj -scheme PaycheckGuardian -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:PaycheckGuardianAppTests`

Run: `xcodebuild build -project ios/PaycheckGuardian.xcodeproj -scheme PaycheckGuardian -destination 'platform=iOS Simulator,name=iPhone 17 Pro'`

Expected: app tests pass and the application build succeeds with no warnings from owned Swift sources.

- [ ] **Step 5: Commit the runnable native application**

```bash
git add ios/PaycheckGuardian.xcodeproj ios/Config ios/PaycheckGuardianApp ios/PaycheckGuardianAppTests
git commit -m "feat(ios): build native SwiftUI hackathon app"
```

---

### Task 8: Simulator UI Tests and Demonstration Capture

**Files:**
- Create: `ios/PaycheckGuardianUITests/PaycheckGuardianUITests.swift`
- Create: `ios/scripts/run-ios-tests.sh`
- Create: `ios/scripts/capture-simulator-demo.sh`
- Generate: `artifacts/ios/trajectories/demo-final.json`
- Generate: `artifacts/ios/screenshots/01-welcome.png`
- Generate: `artifacts/ios/screenshots/02-verified-plan.png`
- Generate: `artifacts/ios/screenshots/03-evidence.png`
- Generate: `artifacts/ios/screenshots/04-simulation.png`
- Generate: `artifacts/ios/screenshots/05-agent-trace.png`

**Interfaces:**
- Consumes: accessibility identifiers and launch arguments from the app.
- Produces: repeatable full-flow XCUITest and shell scripts for testing/capture.

- [ ] **Step 1: Write the failing end-to-end UI test**

```swift
func testHackathonDemoEndToEnd() throws {
    app.launchArguments = ["--ui-testing", "--reset-demo"]
    app.launch()
    app.buttons["run-demo"].tap()
    XCTAssertTrue(app.staticTexts["verified-plan-title"].waitForExistence(timeout: 10))
    app.buttons["recommendation-evidence-0"].tap()
    XCTAssertTrue(app.staticTexts["calculation-detail"].exists)
    app.buttons["close-evidence"].tap()
    app.buttons["approve-recommendation-0"].tap()
    app.buttons["confirm-simulation"].tap()
    XCTAssertTrue(app.staticTexts["simulation-confirmed"].exists)
    app.buttons["show-agent-trace"].tap()
    XCTAssertTrue(app.staticTexts["agent-trace-title"].exists)
}
```

Add a second test that dismisses one card and asserts both card count and accessible total change, plus a third test for invalid same-day dates.

- [ ] **Step 2: Run UI tests and confirm the missing-identifier failure**

Run: `xcodebuild test -project ios/PaycheckGuardian.xcodeproj -scheme PaycheckGuardian -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:PaycheckGuardianUITests`

Expected: UI tests fail at the first missing accessibility identifier or interaction.

- [ ] **Step 3: Complete identifiers, launch-state reset, scripts, and artifact export**

```bash
#!/usr/bin/env bash
set -euo pipefail
xcodebuild test \
  -project ios/PaycheckGuardian.xcodeproj \
  -scheme PaycheckGuardian \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro'
```

The capture script must boot the selected Simulator, install the built `.app`, launch with deterministic demo arguments, and use `xcrun simctl io booted screenshot` at named checkpoints. Export the sanitized trajectory through a test-only launch argument to `artifacts/ios/trajectories/demo-final.json`.

- [ ] **Step 4: Run every package/app/UI test and inspect screenshots**

Run: `bash ios/scripts/run-ios-tests.sh`

Run: `bash ios/scripts/capture-simulator-demo.sh`

Expected: all tests pass; five PNGs exist, are non-empty, show the intended distinct states, and contain no clipped primary controls or personal data.

- [ ] **Step 5: Commit end-to-end evidence**

```bash
git add ios/PaycheckGuardianUITests ios/scripts artifacts/ios
git commit -m "test(ios): verify simulator demo end to end"
```

---

### Task 9: Documentation, Privacy Audit, and Final Reproduction

**Files:**
- Create: `README-IOS.md`
- Modify: `README.md`
- Modify: `.gitignore`
- Verify: every file under `ios/` and `artifacts/ios/`

**Interfaces:**
- Consumes: final project commands, evaluation output, screenshots, and app behavior.
- Produces: exact reviewer instructions and completion evidence.

- [ ] **Step 1: Add documentation assertions to the core test suite**

```swift
func testIOSReadmeContainsExactReproductionCommands() throws {
    let readme = try String(contentsOfFile: repositoryRoot + "/README-IOS.md")
    XCTAssertTrue(readme.contains("open ios/PaycheckGuardian.xcodeproj"))
    XCTAssertTrue(readme.contains("bash ios/scripts/run-ios-tests.sh"))
    XCTAssertTrue(readme.contains("bash ios/scripts/run-evaluation.sh"))
    XCTAssertTrue(readme.contains("iOS 17.0"))
    XCTAssertTrue(readme.contains("Simulation only"))
}
```

- [ ] **Step 2: Run the documentation test and observe failure**

Run: `cd ios/Packages/PaycheckGuardianCore && swift test --filter testIOSReadmeContainsExactReproductionCommands`

Expected: test fails because `README-IOS.md` does not exist.

- [ ] **Step 3: Write exact setup, demo, architecture, safety, evaluation, and limitation documentation**

Document Xcode `26.2`, Swift `6.2.3`, iOS minimum `17.0`, the tested simulator runtime/device, exact GUI steps, exact CLI commands, expected metric values, generated artifact paths, all-local behavior, synthetic-data limitation, and the fact that approval only creates an in-app simulation.

- [ ] **Step 4: Perform fresh final verification and privacy/media audit**

Run: `bash ios/scripts/run-ios-tests.sh`

Run: `bash ios/scripts/run-evaluation.sh`

Run: `xcodebuild -project ios/PaycheckGuardian.xcodeproj -scheme PaycheckGuardian -showBuildSettings | rg 'IPHONEOS_DEPLOYMENT_TARGET|SWIFT_VERSION|PRODUCT_BUNDLE_IDENTIFIER'`

Run: `rg -n -i '(authorization|bearer|api[_-]?key|password|secret|token|/Users/|ramazan|netflix)' artifacts/ios/trajectories ios/PaycheckGuardianApp/Resources || true`

Expected: all tests pass; evaluation retains the specified metrics; deployment target is `17.0`; trajectory/privacy scan has no matches; source resource matches are limited to intentionally synthetic fixture merchant names and are absent from trajectory output.

Open every generated PNG and verify legibility, safe-area layout, state correctness, synthetic label, and absence of personal data. Launch the app once outside XCUITest and manually complete demo → evidence → approve → confirmation → trace → reset.

- [ ] **Step 5: Commit the final documented deliverable**

```bash
git add README.md README-IOS.md .gitignore ios artifacts/ios docs/superpowers
git commit -m "docs(ios): finalize reproducible hackathon application"
```

- [ ] **Step 6: Confirm a clean tree and record immutable completion evidence**

Run: `git diff --check && git status --short && git log -1 --oneline`

Expected: `git diff --check` emits nothing, `git status --short` emits nothing, and the final commit is displayed.
