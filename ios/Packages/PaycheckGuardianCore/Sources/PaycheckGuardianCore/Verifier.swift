import Foundation

public enum VerificationStatus: String, Codable, Hashable, Sendable {
    case accepted
    case correctable
    case rejected
}

public enum VerificationReason: String, Codable, Hashable, Sendable {
    case unknownEvidence = "unknown_evidence"
    case duplicateEvidence = "duplicate_evidence"
    case insufficientEvidence = "insufficient_evidence"
    case unsupportedEvidence = "unsupported_evidence"
    case mismatchedTarget = "mismatched_target"
    case mismatchedAction = "mismatched_action"
    case unsafeAction = "unsafe_action"
    case incorrectArithmetic = "incorrect_arithmetic"
    case missingCaveat = "missing_caveat"
}

public struct VerificationResult: Codable, Hashable, Sendable {
    public let status: VerificationStatus
    public let recommendation: VerifiedRecommendation?
    public let correctableCandidate: CandidateRecommendation?
    public let reasons: [VerificationReason]
}

public struct RecommendationVerifier: Sendable {
    public init() {}

    public func verify(
        _ candidate: CandidateRecommendation,
        facts: AnalysisFacts,
        transactions: [Transaction],
        window: AnalysisWindow
    ) -> VerificationResult {
        let knownIDs = Set(transactions.map(\.id))
        guard candidate.evidenceIDs.allSatisfy(knownIDs.contains) else {
            return rejected(.unknownEvidence)
        }
        guard Set(candidate.evidenceIDs).count == candidate.evidenceIDs.count else {
            return rejected(.duplicateEvidence)
        }

        let evidence = transactions.filter { candidate.evidenceIDs.contains($0.id) }
        if candidate.action == .cancelSubscription,
           evidence.contains(where: { AnalysisTools.essentialCategories.contains($0.category) }) {
            return rejected(.unsafeAction)
        }
        if candidate.action == .cancelSubscription,
           facts.recurring.contains(where: {
               Set($0.evidenceIDs) == Set(candidate.evidenceIDs) && !$0.cancellable
           }) {
            return rejected(.unsafeAction)
        }

        let minimumEvidence: [Confidence: Int] = [.low: 1, .medium: 2, .high: 3]
        guard candidate.evidenceIDs.count >= minimumEvidence[candidate.confidence, default: 1] else {
            return rejected(.insufficientEvidence)
        }

        let canonicalDrafts = RecommendationFactory.drafts(from: facts, window: window)
        guard let canonical = canonicalDrafts.first(where: {
            $0.kind == candidate.kind && Set($0.evidenceIDs) == Set(candidate.evidenceIDs)
        }) else {
            return rejected(.unsupportedEvidence)
        }
        guard canonical.target.caseInsensitiveCompare(candidate.target) == .orderedSame else {
            return rejected(.mismatchedTarget)
        }
        guard canonical.action == candidate.action else {
            return rejected(.mismatchedAction)
        }
        if candidate.confidence == .low,
           candidate.kind == .subscription,
           candidate.caveat?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty != false {
            return rejected(.missingCaveat)
        }

        if candidate.monthlySavingsUSD != canonical.monthlySavingsUSD
            || candidate.nextPaycheckSavingsUSD != canonical.nextPaycheckSavingsUSD {
            return VerificationResult(
                status: .correctable,
                recommendation: nil,
                correctableCandidate: canonical,
                reasons: [.incorrectArithmetic]
            )
        }
        return VerificationResult(
            status: .accepted,
            recommendation: VerifiedRecommendation(canonical: canonical),
            correctableCandidate: nil,
            reasons: []
        )
    }

    private func rejected(_ reason: VerificationReason) -> VerificationResult {
        VerificationResult(
            status: .rejected,
            recommendation: nil,
            correctableCandidate: nil,
            reasons: [reason]
        )
    }
}
