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
