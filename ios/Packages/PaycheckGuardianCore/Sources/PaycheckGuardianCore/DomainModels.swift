import Foundation

public enum SourceType: String, Codable, Hashable, Sendable {
    case bankCSV = "bank_csv"
    case receipt
}

public enum RecommendationKind: String, Codable, Hashable, Sendable {
    case subscription
    case duplicate
    case anomaly
    case behavioralPattern = "behavioral_pattern"
}

public enum Confidence: String, Codable, Hashable, Sendable {
    case high
    case medium
    case low
}

public enum RecommendationStatus: String, Codable, Hashable, Sendable {
    case proposed
    case approvedForSimulation = "approved_for_simulation"
    case dismissed
}

public enum RecommendationAction: String, Codable, Hashable, Sendable {
    case cancelSubscription = "cancel_subscription"
    case reviewDuplicate = "review_duplicate"
    case reduceDiscretionarySpending = "reduce_discretionary_spending"
    case reviewAnomaly = "review_anomaly"
}

public struct AnalysisWindow: Codable, Hashable, Sendable {
    public let analysisDate: Date
    public let nextPaycheck: Date

    public init(analysisDate: Date, nextPaycheck: Date) throws {
        guard nextPaycheck > analysisDate else {
            throw DomainError.invalidPaycheckDate
        }
        self.analysisDate = analysisDate
        self.nextPaycheck = nextPaycheck
    }
}

public struct Transaction: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let date: Date
    public let merchantRaw: String
    public let merchantNormalized: String
    public let amountUSD: Money
    public let category: String
    public let source: SourceType
    public let sourceReference: String
    public let isSynthetic: Bool

    public init(
        id: String,
        date: Date,
        merchantRaw: String,
        merchantNormalized: String,
        amountUSD: Money,
        category: String,
        source: SourceType,
        sourceReference: String,
        isSynthetic: Bool
    ) throws {
        try Self.requireText(id, named: "Transaction ID")
        try Self.requireText(merchantRaw, named: "Raw merchant")
        try Self.requireText(merchantNormalized, named: "Normalized merchant")
        try Self.requireText(category, named: "Category")
        try Self.requireText(sourceReference, named: "Source reference")
        self.id = id
        self.date = date
        self.merchantRaw = merchantRaw
        self.merchantNormalized = merchantNormalized
        self.amountUSD = amountUSD
        self.category = category
        self.source = source
        self.sourceReference = sourceReference
        self.isSynthetic = isSynthetic
    }

    private static func requireText(_ value: String, named name: String) throws {
        guard !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw DomainError.blankField(name)
        }
    }
}

public struct CandidateRecommendation: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let kind: RecommendationKind
    public let target: String
    public let action: RecommendationAction
    public let title: String
    public let rationale: String
    public let evidenceIDs: [String]
    public let monthlySavingsUSD: Money
    public let nextPaycheckSavingsUSD: Money
    public let confidence: Confidence
    public let caveat: String?

    public init(
        id: String,
        kind: RecommendationKind,
        target: String,
        action: RecommendationAction,
        title: String,
        rationale: String,
        evidenceIDs: [String],
        monthlySavingsUSD: Money,
        nextPaycheckSavingsUSD: Money,
        confidence: Confidence,
        caveat: String?
    ) throws {
        for (name, value) in [("Recommendation ID", id), ("Target", target), ("Title", title), ("Rationale", rationale)] {
            guard !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                throw DomainError.blankField(name)
            }
        }
        guard !evidenceIDs.isEmpty else { throw DomainError.emptyEvidence }
        guard evidenceIDs.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else {
            throw DomainError.blankField("Evidence ID")
        }
        self.id = id
        self.kind = kind
        self.target = target
        self.action = action
        self.title = title
        self.rationale = rationale
        self.evidenceIDs = evidenceIDs
        self.monthlySavingsUSD = monthlySavingsUSD
        self.nextPaycheckSavingsUSD = nextPaycheckSavingsUSD
        self.confidence = confidence
        self.caveat = caveat
    }
}

public struct VerifiedRecommendation: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let kind: RecommendationKind
    public let target: String
    public let action: RecommendationAction
    public let title: String
    public let rationale: String
    public let evidenceIDs: [String]
    public let monthlySavingsUSD: Money
    public let nextPaycheckSavingsUSD: Money
    public let confidence: Confidence
    public let caveat: String?
    public let status: RecommendationStatus

    init(canonical candidate: CandidateRecommendation, status: RecommendationStatus = .proposed) {
        id = candidate.id
        kind = candidate.kind
        target = candidate.target
        action = candidate.action
        title = candidate.title
        rationale = candidate.rationale
        evidenceIDs = candidate.evidenceIDs
        monthlySavingsUSD = candidate.monthlySavingsUSD
        nextPaycheckSavingsUSD = candidate.nextPaycheckSavingsUSD
        confidence = candidate.confidence
        caveat = candidate.caveat
        self.status = status
    }

    public func withStatus(_ status: RecommendationStatus) -> VerifiedRecommendation {
        VerifiedRecommendation(copying: self, status: status)
    }

    private init(copying value: VerifiedRecommendation, status: RecommendationStatus) {
        id = value.id
        kind = value.kind
        target = value.target
        action = value.action
        title = value.title
        rationale = value.rationale
        evidenceIDs = value.evidenceIDs
        monthlySavingsUSD = value.monthlySavingsUSD
        nextPaycheckSavingsUSD = value.nextPaycheckSavingsUSD
        confidence = value.confidence
        caveat = value.caveat
        self.status = status
    }
}
