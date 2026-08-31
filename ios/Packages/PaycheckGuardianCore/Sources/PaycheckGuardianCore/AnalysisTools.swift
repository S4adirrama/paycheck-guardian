import Foundation

public struct RecurringCandidate: Codable, Hashable, Sendable {
    public let merchant: String
    public let category: String
    public let intervalDays: Int
    public let monthlyAmount: Money
    public let evidenceIDs: [String]
    public let cancellable: Bool
}

public struct DuplicateCandidate: Codable, Hashable, Sendable {
    public let merchant: String
    public let category: String
    public let amount: Money
    public let evidenceIDs: [String]
}

public struct SpendingPattern: Codable, Hashable, Sendable {
    public let merchant: String
    public let category: String
    public let chargeCount: Int
    public let monthlyAmount: Money
    public let evidenceIDs: [String]
}

public struct AnomalyCandidate: Codable, Hashable, Sendable {
    public let merchant: String
    public let category: String
    public let observedAmount: Money
    public let typicalAmount: Money
    public let monthlyAmount: Money
    public let evidenceIDs: [String]
}

public struct CategorySummary: Codable, Hashable, Sendable {
    public let category: String
    public let chargeCount: Int
    public let totalAmount: Money
    public let evidenceIDs: [String]
}

public struct AnalysisFacts: Codable, Hashable, Sendable {
    public var recurring: [RecurringCandidate]
    public var duplicates: [DuplicateCandidate]
    public var anomalies: [AnomalyCandidate]
    public var categorySummaries: [CategorySummary]
    public var discretionaryPatterns: [SpendingPattern]

    public static let empty = AnalysisFacts(
        recurring: [], duplicates: [], anomalies: [], categorySummaries: [], discretionaryPatterns: []
    )
}

public enum AnalysisTools {
    public static let essentialCategories: Set<String> = [
        "housing", "utilities", "insurance", "healthcare", "debt", "telecom",
    ]
    public static let cancellableCategories: Set<String> = [
        "streaming", "music", "cloud_storage", "subscription", "fitness",
    ]
    public static let discretionaryCategories: Set<String> = [
        "food_delivery", "coffee", "entertainment",
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

    public static func findRecurring(_ transactions: [Transaction]) -> [RecurringCandidate] {
        groups(transactions).compactMap { key, rows in
            let evidence = sorted(rows)
            guard evidence.count >= 2 else { return nil }
            let gaps = zip(evidence, evidence.dropFirst()).map {
                Calendar.utcGregorian.dateComponents([.day], from: $0.date, to: $1.date).day ?? 0
            }
            guard let interval = supportedInterval(median(gaps.map { Decimal($0) })) else { return nil }
            let amounts = evidence.map(\.amountUSD.amount)
            guard let lowest = amounts.min(), let highest = amounts.max(),
                  highest - lowest <= lowest * Decimal(string: "0.15")!
            else { return nil }
            let typical = median(amounts)
            return RecurringCandidate(
                merchant: key.merchant,
                category: key.category,
                intervalDays: interval,
                monthlyAmount: monthlyEquivalent(typical, interval: interval),
                evidenceIDs: evidence.map(\.id),
                cancellable: cancellableCategories.contains(key.category)
            )
        }
        .sorted { ($0.merchant, $0.category) < ($1.merchant, $1.category) }
    }

    public static func findDuplicates(_ transactions: [Transaction]) -> [DuplicateCandidate] {
        var grouped: [DuplicateKey: [Transaction]] = [:]
        for row in transactions {
            grouped[DuplicateKey(merchant: row.merchantNormalized, amount: row.amountUSD), default: []].append(row)
        }
        var candidates: [DuplicateCandidate] = []
        for (key, rows) in grouped {
            let evidence = sorted(rows)
            for pair in zip(evidence, evidence.dropFirst()) {
                let days = Calendar.utcGregorian.dateComponents([.day], from: pair.0.date, to: pair.1.date).day ?? 0
                if days <= 2 {
                    candidates.append(
                        DuplicateCandidate(
                            merchant: key.merchant,
                            category: pair.0.category,
                            amount: key.amount,
                            evidenceIDs: [pair.0.id, pair.1.id]
                        )
                    )
                }
            }
        }
        return candidates.sorted {
            ($0.merchant, $0.evidenceIDs.joined(separator: "|"))
                < ($1.merchant, $1.evidenceIDs.joined(separator: "|"))
        }
    }

    public static func findDiscretionaryPatterns(_ transactions: [Transaction]) -> [SpendingPattern] {
        groups(transactions.filter { discretionaryCategories.contains($0.category) }).compactMap { key, rows in
            let evidence = sorted(rows)
            for start in evidence.indices {
                let window = evidence[start...].filter {
                    (Calendar.utcGregorian.dateComponents([.day], from: evidence[start].date, to: $0.date).day ?? 31) <= 30
                }
                if window.count >= 3 {
                    return SpendingPattern(
                        merchant: key.merchant,
                        category: key.category,
                        chargeCount: window.count,
                        monthlyAmount: positiveMoney(window.reduce(Decimal.zero) { $0 + $1.amountUSD.amount }),
                        evidenceIDs: window.map(\.id)
                    )
                }
            }
            return nil
        }
        .sorted { ($0.merchant, $0.category) < ($1.merchant, $1.category) }
    }

    public static func findAnomalies(_ transactions: [Transaction]) -> [AnomalyCandidate] {
        groups(transactions).compactMap { key, rows in
            let evidence = sorted(rows)
            guard evidence.count >= 3,
                  let largest = evidence.max(by: {
                      ($0.amountUSD, $0.date, $0.id) < ($1.amountUSD, $1.date, $1.id)
                  })
            else { return nil }
            let comparisons = evidence.filter { $0.id != largest.id }.map(\.amountUSD.amount)
            let typicalDecimal = median(comparisons)
            let excess = largest.amountUSD.amount - typicalDecimal
            guard largest.amountUSD.amount >= typicalDecimal * 2, excess >= 10 else { return nil }
            return AnomalyCandidate(
                merchant: key.merchant,
                category: key.category,
                observedAmount: largest.amountUSD,
                typicalAmount: positiveMoney(typicalDecimal),
                monthlyAmount: positiveMoney(excess),
                evidenceIDs: evidence.map(\.id)
            )
        }
        .sorted { ($0.merchant, $0.category) < ($1.merchant, $1.category) }
    }

    public static func summarizeCategories(_ transactions: [Transaction]) -> [CategorySummary] {
        Dictionary(grouping: transactions, by: \.category).map { category, rows in
            let evidence = sorted(rows)
            return CategorySummary(
                category: category,
                chargeCount: evidence.count,
                totalAmount: positiveMoney(evidence.reduce(Decimal.zero) { $0 + $1.amountUSD.amount }),
                evidenceIDs: evidence.map(\.id)
            )
        }
        .sorted { $0.category < $1.category }
    }

    private struct MerchantKey: Hashable {
        let merchant: String
        let category: String
    }

    private struct DuplicateKey: Hashable {
        let merchant: String
        let amount: Money
    }

    private static func groups(_ transactions: [Transaction]) -> [MerchantKey: [Transaction]] {
        Dictionary(grouping: transactions) {
            MerchantKey(merchant: $0.merchantNormalized, category: $0.category)
        }
    }

    private static func sorted(_ transactions: [Transaction]) -> [Transaction] {
        transactions.sorted { ($0.date, $0.id) < ($1.date, $1.id) }
    }

    private static func median(_ values: [Decimal]) -> Decimal {
        let sortedValues = values.sorted()
        let middle = sortedValues.count / 2
        return sortedValues.count.isMultiple(of: 2)
            ? (sortedValues[middle - 1] + sortedValues[middle]) / 2
            : sortedValues[middle]
    }

    private static func supportedInterval(_ gap: Decimal) -> Int? {
        if gap >= 6, gap <= 8 { return 7 }
        if gap >= 13, gap <= 15 { return 14 }
        if gap >= 26, gap <= 35 { return 30 }
        if gap >= 350, gap <= 380 { return 365 }
        return nil
    }

    private static func monthlyEquivalent(_ amount: Decimal, interval: Int) -> Money {
        switch interval {
        case 7: positiveMoney(amount * 52 / 12)
        case 14: positiveMoney(amount * 26 / 12)
        case 365: positiveMoney(amount / 12)
        default: positiveMoney(amount)
        }
    }

    private static func positiveMoney(_ value: Decimal) -> Money {
        // Call sites establish positive input before constructing a validated Money value.
        try! Money(value)
    }
}
