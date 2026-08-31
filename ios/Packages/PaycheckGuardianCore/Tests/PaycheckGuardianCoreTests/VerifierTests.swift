import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class VerifierTests: XCTestCase {
    func testFactoryBuildsOpaqueDraftFromRecurringFact() throws {
        let context = try subscriptionContext()

        let draft = try XCTUnwrap(RecommendationFactory.drafts(from: context.facts, window: context.window).first)

        XCTAssertEqual(draft.kind, .subscription)
        XCTAssertEqual(draft.action, .cancelSubscription)
        XCTAssertEqual(draft.target, "Netflix")
        XCTAssertFalse(draft.id.localizedCaseInsensitiveContains("netflix"))
    }

    func testVerifierCanonicalizesSavingsFromEvidence() throws {
        let context = try subscriptionContext(monthlyAmount: "16.49")
        let original = try XCTUnwrap(RecommendationFactory.drafts(from: context.facts, window: context.window).first)
        let badDraft = try CandidateRecommendation(
            id: original.id,
            kind: original.kind,
            target: original.target,
            action: original.action,
            title: "Save everything now",
            rationale: "Trust this draft",
            evidenceIDs: original.evidenceIDs,
            monthlySavingsUSD: Money("1.00"),
            nextPaycheckSavingsUSD: Money("1.00"),
            confidence: original.confidence,
            caveat: original.caveat
        )

        let result = RecommendationVerifier().verify(
            badDraft,
            facts: context.facts,
            transactions: context.rows,
            window: context.window
        )

        XCTAssertEqual(result.status, .correctable)
        XCTAssertEqual(result.correctableCandidate?.monthlySavingsUSD, try Money("16.49"))
        XCTAssertEqual(result.correctableCandidate?.nextPaycheckSavingsUSD, try Money("6.51"))
    }

    func testVerifierRejectsDuplicateEvidenceIDs() throws {
        let context = try subscriptionContext()
        let original = try XCTUnwrap(RecommendationFactory.drafts(from: context.facts, window: context.window).first)
        let duplicateEvidence = try CandidateRecommendation(
            id: original.id,
            kind: original.kind,
            target: original.target,
            action: original.action,
            title: original.title,
            rationale: original.rationale,
            evidenceIDs: [original.evidenceIDs[0], original.evidenceIDs[0]],
            monthlySavingsUSD: original.monthlySavingsUSD,
            nextPaycheckSavingsUSD: original.nextPaycheckSavingsUSD,
            confidence: original.confidence,
            caveat: original.caveat
        )

        let result = RecommendationVerifier().verify(
            duplicateEvidence,
            facts: context.facts,
            transactions: context.rows,
            window: context.window
        )

        XCTAssertEqual(result.status, .rejected)
        XCTAssertTrue(result.reasons.contains(.duplicateEvidence))
    }

    func testVerifierRejectsEssentialCancellation() throws {
        let rows = try [
            row("r1", "2026-06-01", "Rent", "1500.00", "housing"),
            row("r2", "2026-07-01", "Rent", "1500.00", "housing"),
        ]
        let facts = AnalysisTools.runAll(rows)
        let window = try testWindow()
        let draft = try CandidateRecommendation(
            id: "opaque",
            kind: .subscription,
            target: "Rent",
            action: .cancelSubscription,
            title: "Cancel rent",
            rationale: "Unsafe",
            evidenceIDs: ["r1", "r2"],
            monthlySavingsUSD: Money("1500.00"),
            nextPaycheckSavingsUSD: Money("591.78"),
            confidence: .medium,
            caveat: nil
        )

        let result = RecommendationVerifier().verify(draft, facts: facts, transactions: rows, window: window)

        XCTAssertEqual(result.status, .rejected)
        XCTAssertTrue(result.reasons.contains(.unsafeAction))
    }

    func testCanonicalCopyIgnoresUntrustedDraftTitle() throws {
        let context = try subscriptionContext()
        let original = try XCTUnwrap(RecommendationFactory.drafts(from: context.facts, window: context.window).first)
        let draft = try CandidateRecommendation(
            id: original.id,
            kind: original.kind,
            target: original.target,
            action: original.action,
            title: "Guaranteed instant savings",
            rationale: "No review required",
            evidenceIDs: original.evidenceIDs,
            monthlySavingsUSD: original.monthlySavingsUSD,
            nextPaycheckSavingsUSD: original.nextPaycheckSavingsUSD,
            confidence: original.confidence,
            caveat: original.caveat
        )

        let result = RecommendationVerifier().verify(
            draft,
            facts: context.facts,
            transactions: context.rows,
            window: context.window
        )

        XCTAssertEqual(result.status, .accepted)
        XCTAssertEqual(result.recommendation?.title, "Review Netflix subscription")
        XCTAssertEqual(result.recommendation?.status, .proposed)
        XCTAssertFalse(result.recommendation?.rationale.contains("guaranteed") ?? true)
    }

    func testVerifierRejectsUnknownEvidence() throws {
        let context = try subscriptionContext()
        let original = try XCTUnwrap(RecommendationFactory.drafts(from: context.facts, window: context.window).first)
        let draft = try CandidateRecommendation(
            id: original.id,
            kind: original.kind,
            target: original.target,
            action: original.action,
            title: original.title,
            rationale: original.rationale,
            evidenceIDs: ["missing"],
            monthlySavingsUSD: original.monthlySavingsUSD,
            nextPaycheckSavingsUSD: original.nextPaycheckSavingsUSD,
            confidence: .low,
            caveat: "Needs review"
        )

        let result = RecommendationVerifier().verify(draft, facts: context.facts, transactions: context.rows, window: context.window)

        XCTAssertEqual(result.status, .rejected)
        XCTAssertTrue(result.reasons.contains(.unknownEvidence))
    }
}

private typealias SubscriptionContext = (
    rows: [Transaction],
    facts: AnalysisFacts,
    window: AnalysisWindow
)

private func subscriptionContext(monthlyAmount: String = "15.49") throws -> SubscriptionContext {
    let rows = try [
        row("n1", "2026-05-01", "Netflix", monthlyAmount, "streaming"),
        row("n2", "2026-05-31", "Netflix", monthlyAmount, "streaming"),
        row("n3", "2026-06-30", "Netflix", monthlyAmount, "streaming"),
    ]
    return (rows, AnalysisTools.runAll(rows), try testWindow())
}

private func testWindow() throws -> AnalysisWindow {
    try AnalysisWindow(
        analysisDate: ISODate.parse("2026-07-10"),
        nextPaycheck: ISODate.parse("2026-07-22")
    )
}

private func row(
    _ id: String,
    _ date: String,
    _ merchant: String,
    _ amount: String,
    _ category: String
) throws -> Transaction {
    try Transaction(
        id: id,
        date: ISODate.parse(date),
        merchantRaw: merchant,
        merchantNormalized: merchant,
        amountUSD: Money(amount),
        category: category,
        source: .bankCSV,
        sourceReference: "source-\(id)",
        isSynthetic: true
    )
}
