import Foundation

public enum RecommendationFactory {
    public static func drafts(from facts: AnalysisFacts, window: AnalysisWindow) -> [CandidateRecommendation] {
        let subscriptions = facts.recurring.filter(\.cancellable).map { candidate in
            let lowConfidence = candidate.evidenceIDs.count == 2 && candidate.intervalDays == 30
            return draft(
                kind: .subscription,
                target: candidate.merchant,
                action: .cancelSubscription,
                title: "Review \(candidate.merchant) subscription",
                rationale: "Recurring evidence suggests reviewing whether this subscription is still wanted.",
                evidenceIDs: candidate.evidenceIDs,
                monthly: candidate.monthlyAmount,
                confidence: lowConfidence ? .low : (candidate.evidenceIDs.count >= 3 ? .high : .medium),
                caveat: lowConfidence
                    ? "Only two monthly charges were observed; confirm this possible subscription before any simulation."
                    : "Savings are estimates based on observed recurring charges.",
                window: window
            )
        }
        let duplicates = facts.duplicates.map { candidate in
            draft(
                kind: .duplicate,
                target: candidate.merchant,
                action: .reviewDuplicate,
                title: "Review possible duplicate \(candidate.merchant) charge",
                rationale: "Two matching charges occurred within two days.",
                evidenceIDs: candidate.evidenceIDs,
                monthly: candidate.amount,
                confidence: .medium,
                caveat: "Confirm the duplicate with the merchant before treating it as savings.",
                window: window
            )
        }
        let patterns = facts.discretionaryPatterns.map { candidate in
            draft(
                kind: .behavioralPattern,
                target: candidate.merchant,
                action: .reduceDiscretionarySpending,
                title: "Set a spending limit for \(candidate.merchant)",
                rationale: "Repeated discretionary purchases form a verified 30-day pattern.",
                evidenceIDs: candidate.evidenceIDs,
                monthly: candidate.monthlyAmount,
                confidence: .high,
                caveat: "Reduce this pattern only if it fits your priorities.",
                window: window
            )
        }
        let anomalies = facts.anomalies.map { candidate in
            draft(
                kind: .anomaly,
                target: candidate.merchant,
                action: .reviewAnomaly,
                title: "Review unusual \(candidate.merchant) charge",
                rationale: "One charge is materially above the merchant’s other observed charges.",
                evidenceIDs: candidate.evidenceIDs,
                monthly: candidate.monthlyAmount,
                confidence: .medium,
                caveat: "Confirm whether the unusual charge was expected.",
                window: window
            )
        }
        return (subscriptions + duplicates + patterns + anomalies).sorted {
            ($0.kind.rawValue, $0.id) < ($1.kind.rawValue, $1.id)
        }
    }

    private static func draft(
        kind: RecommendationKind,
        target: String,
        action: RecommendationAction,
        title: String,
        rationale: String,
        evidenceIDs: [String],
        monthly: Money,
        confidence: Confidence,
        caveat: String,
        window: AnalysisWindow
    ) -> CandidateRecommendation {
        try! CandidateRecommendation(
            id: OpaqueID.digest("recommendation|\(kind.rawValue)|\(evidenceIDs.sorted().joined(separator: "|"))"),
            kind: kind,
            target: target,
            action: action,
            title: title,
            rationale: rationale,
            evidenceIDs: evidenceIDs,
            monthlySavingsUSD: monthly,
            nextPaycheckSavingsUSD: try! monthly.prorated(from: window.analysisDate, to: window.nextPaycheck),
            confidence: confidence,
            caveat: caveat
        )
    }
}
