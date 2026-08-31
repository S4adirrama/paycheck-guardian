import Foundation

public struct GroundTruthOpportunity: Codable, Hashable, Sendable {
    public let kind: RecommendationKind
    public let target: String
    public let requiredEvidenceIDs: [String]
    public let monthlySavingsUSD: Money
    public let expectedConfidence: Confidence?
    public let caveatRequired: Bool
}

public struct EvaluationCase: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let transactions: [Transaction]
    public let groundTruth: [GroundTruthOpportunity]
    public let isChallenge: Bool
}

public struct PredictedOpportunity: Codable, Hashable, Sendable {
    public let kind: RecommendationKind
    public let target: String
    public let evidenceIDs: [String]
    public let monthlySavingsUSD: Money
    public let confidence: Confidence
    public let caveat: String?
}

public enum EvaluationMode: String, CaseIterable, Codable, Hashable, Sendable {
    case baseline
    case normalizationOnly = "normalization_only"
    case unverifiedAgent = "unverified_agent"
    case removedUnsafeRecurrence = "removed_unsafe_recurrence"
    case final
}

public struct CaseScore: Codable, Hashable, Sendable {
    public let truePositives: Int
    public let falsePositives: Int
    public let falseNegatives: Int
    public let precision: Decimal
    public let recall: Decimal
    public let f1: Decimal
    public let evidenceCoverage: Decimal
    public let meanSavingsErrorUSD: Decimal
    public let unsupportedClaims: Int
}

public struct ModeMetrics: Codable, Hashable, Sendable {
    public let truePositives: Int
    public let falsePositives: Int
    public let falseNegatives: Int
    public let precision: Decimal
    public let recall: Decimal
    public let f1: Decimal
    public let evidenceCoverage: Decimal
    public let meanSavingsErrorUSD: Decimal
    public let unsupportedClaims: Int
}

public struct EvaluationReport: Sendable {
    public let caseCount: Int
    public let predictions: [EvaluationMode: [String: [PredictedOpportunity]]]
    public let perCaseScores: [EvaluationMode: [String: CaseScore]]
    public let metrics: [EvaluationMode: ModeMetrics]
    public let inputFingerprintsByMode: [EvaluationMode: [String: String]]
    public let finalRuns: [String: AgentRun]
}

public enum EvaluationFixtures {
    public static func bundled() throws -> [EvaluationCase] {
        guard let url = Bundle.module.url(forResource: "evaluation-cases", withExtension: "json") else {
            throw DomainError.resourceMissing("evaluation-cases.json")
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let file = try decoder.decode(RawFile.self, from: Data(contentsOf: url))
        let normalizer = try MerchantNormalizer.bundled()
        return try file.cases.map { rawCase in
            let transactions = try rawCase.transactions.map { raw in
                let normalized = try normalizer.normalize(raw.merchantRaw)
                return try Transaction(
                    id: raw.transactionId,
                    date: ISODate.parse(raw.date),
                    merchantRaw: raw.merchantRaw,
                    merchantNormalized: normalized.displayName,
                    amountUSD: Money(raw.amountUsd),
                    category: normalized.category,
                    source: .bankCSV,
                    sourceReference: OpaqueID.digest("evaluation|\(rawCase.caseId)|\(raw.transactionId)"),
                    isSynthetic: true
                )
            }
            let truths = try rawCase.groundTruth.map {
                GroundTruthOpportunity(
                    kind: $0.kind,
                    target: $0.target,
                    requiredEvidenceIDs: $0.requiredEvidenceIds,
                    monthlySavingsUSD: try Money($0.monthlySavingsUsd),
                    expectedConfidence: $0.expectedConfidence,
                    caveatRequired: $0.caveatRequired ?? false
                )
            }
            return EvaluationCase(
                id: rawCase.caseId,
                transactions: transactions,
                groundTruth: truths,
                isChallenge: rawCase.isChallenge ?? false
            )
        }
    }

    private struct RawFile: Decodable { let cases: [RawCase] }
    private struct RawCase: Decodable {
        let caseId: String
        let transactions: [RawTransaction]
        let groundTruth: [RawTruth]
        let isChallenge: Bool?
    }
    private struct RawTransaction: Decodable {
        let transactionId: String
        let date: String
        let merchantRaw: String
        let amountUsd: String
    }
    private struct RawTruth: Decodable {
        let kind: RecommendationKind
        let target: String
        let requiredEvidenceIds: [String]
        let monthlySavingsUsd: String
        let expectedConfidence: Confidence?
        let caveatRequired: Bool?
    }
}

public struct Evaluator: Sendable {
    public init() {}

    public func run(cases: [EvaluationCase]) throws -> EvaluationReport {
        let window = try AnalysisWindow(
            analysisDate: ISODate.parse("2026-08-01"),
            nextPaycheck: ISODate.parse("2026-08-15")
        )
        var predictions: [EvaluationMode: [String: [PredictedOpportunity]]] = [:]
        var finalRuns: [String: AgentRun] = [:]
        for mode in EvaluationMode.allCases {
            var byCase: [String: [PredictedOpportunity]] = [:]
            for evaluationCase in cases {
                switch mode {
                case .baseline:
                    byCase[evaluationCase.id] = baseline(evaluationCase)
                case .normalizationOnly:
                    byCase[evaluationCase.id] = normalizationOnly(evaluationCase)
                case .unverifiedAgent:
                    byCase[evaluationCase.id] = RecommendationFactory
                        .drafts(from: AnalysisTools.runAll(evaluationCase.transactions), window: window)
                        .map(PredictedOpportunity.init)
                case .removedUnsafeRecurrence:
                    byCase[evaluationCase.id] = unsafeRecurrence(evaluationCase)
                case .final:
                    let run = try SavingsAgent().run(transactions: evaluationCase.transactions, window: window)
                    finalRuns[evaluationCase.id] = run
                    byCase[evaluationCase.id] = run.plan.recommendations.map(PredictedOpportunity.init)
                }
            }
            predictions[mode] = byCase
        }

        var scores: [EvaluationMode: [String: CaseScore]] = [:]
        var metrics: [EvaluationMode: ModeMetrics] = [:]
        for mode in EvaluationMode.allCases {
            let modeScores = Dictionary(uniqueKeysWithValues: cases.map { evaluationCase in
                let score = Self.score(
                    predictions[mode]?[evaluationCase.id] ?? [],
                    truth: evaluationCase.groundTruth
                )
                return (evaluationCase.id, score)
            })
            scores[mode] = modeScores
            metrics[mode] = Self.aggregate(Array(modeScores.values))
        }

        let fingerprints = Dictionary(uniqueKeysWithValues: cases.map { ($0.id, fingerprint($0.transactions)) })
        return EvaluationReport(
            caseCount: cases.count,
            predictions: predictions,
            perCaseScores: scores,
            metrics: metrics,
            inputFingerprintsByMode: Dictionary(uniqueKeysWithValues: EvaluationMode.allCases.map { ($0, fingerprints) }),
            finalRuns: finalRuns
        )
    }

    public static func matches(_ prediction: PredictedOpportunity, truth: GroundTruthOpportunity) -> Bool {
        prediction.kind == truth.kind
            && normalizedTarget(prediction.target) == normalizedTarget(truth.target)
            && Set(truth.requiredEvidenceIDs).isSubset(of: Set(prediction.evidenceIDs))
            && (truth.expectedConfidence == nil || prediction.confidence == truth.expectedConfidence)
            && (!truth.caveatRequired || !(prediction.caveat?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true))
    }

    private func baseline(_ evaluationCase: EvaluationCase) -> [PredictedOpportunity] {
        recurringPredictions(evaluationCase, merchant: \.merchantRaw, firstPairOnly: false)
    }

    private func normalizationOnly(_ evaluationCase: EvaluationCase) -> [PredictedOpportunity] {
        recurringPredictions(evaluationCase, merchant: \.merchantNormalized, firstPairOnly: false)
    }

    private func unsafeRecurrence(_ evaluationCase: EvaluationCase) -> [PredictedOpportunity] {
        recurringPredictions(evaluationCase, merchant: \.merchantNormalized, firstPairOnly: true)
    }

    private func recurringPredictions(
        _ evaluationCase: EvaluationCase,
        merchant: KeyPath<Transaction, String>,
        firstPairOnly: Bool
    ) -> [PredictedOpportunity] {
        Dictionary(grouping: evaluationCase.transactions, by: { $0[keyPath: merchant] })
            .sorted { $0.key < $1.key }
            .compactMap { name, values in
                let rows = values.sorted { ($0.date, $0.id) < ($1.date, $1.id) }
                guard rows.count >= 2 else { return nil }
                if firstPairOnly {
                    guard let pair = zip(rows, rows.dropFirst()).first(where: {
                        let days = Calendar.utcGregorian.dateComponents([.day], from: $0.date, to: $1.date).day ?? 0
                        return (26...35).contains(days)
                    }) else { return nil }
                    return PredictedOpportunity(
                        kind: .subscription,
                        target: name,
                        evidenceIDs: [pair.0.id, pair.1.id],
                        monthlySavingsUSD: pair.1.amountUSD,
                        confidence: .low,
                        caveat: "Removed unsafe recurrence-only cancellation claim."
                    )
                }
                let gaps = zip(rows, rows.dropFirst()).map {
                    Calendar.utcGregorian.dateComponents([.day], from: $0.date, to: $1.date).day ?? 0
                }
                guard gaps.allSatisfy({ (26...35).contains($0) }) else { return nil }
                return PredictedOpportunity(
                    kind: .subscription,
                    target: name,
                    evidenceIDs: rows.map(\.id),
                    monthlySavingsUSD: rows.last!.amountUSD,
                    confidence: .low,
                    caveat: "Unverified recurrence estimate."
                )
            }
    }

    private static func score(
        _ predictions: [PredictedOpportunity],
        truth: [GroundTruthOpportunity]
    ) -> CaseScore {
        var unmatchedTruth = Set(truth.indices)
        var pairs: [(Int, Int)] = []
        for (predictionIndex, prediction) in predictions.enumerated() {
            if let truthIndex = unmatchedTruth.sorted().first(where: { matches(prediction, truth: truth[$0]) }) {
                unmatchedTruth.remove(truthIndex)
                pairs.append((predictionIndex, truthIndex))
            }
        }
        let tp = pairs.count
        let fp = predictions.count - tp
        let fn = truth.count - tp
        let precision = tp + fp == 0 ? Decimal.zero : rounded(Decimal(tp) / Decimal(tp + fp))
        let recall = tp + fn == 0 ? Decimal(1) : rounded(Decimal(tp) / Decimal(tp + fn))
        let denominator = 2 * tp + fp + fn
        let f1 = denominator == 0 ? Decimal.zero : rounded(Decimal(2 * tp) / Decimal(denominator))
        let coverages = pairs.map { predictionIndex, truthIndex in
            Decimal(Set(predictions[predictionIndex].evidenceIDs).intersection(truth[truthIndex].requiredEvidenceIDs).count)
                / Decimal(truth[truthIndex].requiredEvidenceIDs.count)
        }
        let errors = pairs.map { predictionIndex, truthIndex in
            abs(predictions[predictionIndex].monthlySavingsUSD.amount - truth[truthIndex].monthlySavingsUSD.amount)
        }
        return CaseScore(
            truePositives: tp,
            falsePositives: fp,
            falseNegatives: fn,
            precision: precision,
            recall: recall,
            f1: f1,
            evidenceCoverage: coverages.isEmpty ? 0 : rounded(coverages.reduce(0, +) / Decimal(coverages.count)),
            meanSavingsErrorUSD: errors.isEmpty ? 0 : rounded(errors.reduce(0, +) / Decimal(errors.count)),
            unsupportedClaims: fp
        )
    }

    private static func aggregate(_ scores: [CaseScore]) -> ModeMetrics {
        let tp = scores.reduce(0) { $0 + $1.truePositives }
        let fp = scores.reduce(0) { $0 + $1.falsePositives }
        let fn = scores.reduce(0) { $0 + $1.falseNegatives }
        let precision = tp + fp == 0 ? Decimal.zero : rounded(Decimal(tp) / Decimal(tp + fp))
        let recall = tp + fn == 0 ? Decimal(1) : rounded(Decimal(tp) / Decimal(tp + fn))
        let denominator = 2 * tp + fp + fn
        let matched = scores.filter { $0.truePositives > 0 }
        return ModeMetrics(
            truePositives: tp,
            falsePositives: fp,
            falseNegatives: fn,
            precision: precision,
            recall: recall,
            f1: denominator == 0 ? 0 : rounded(Decimal(2 * tp) / Decimal(denominator)),
            evidenceCoverage: matched.isEmpty ? 0 : rounded(matched.reduce(0) { $0 + $1.evidenceCoverage } / Decimal(matched.count)),
            meanSavingsErrorUSD: matched.isEmpty ? 0 : rounded(matched.reduce(0) { $0 + $1.meanSavingsErrorUSD } / Decimal(matched.count)),
            unsupportedClaims: scores.reduce(0) { $0 + $1.unsupportedClaims }
        )
    }

    private static func rounded(_ value: Decimal) -> Decimal {
        var source = value
        var result = Decimal()
        NSDecimalRound(&result, &source, 4, .plain)
        return result
    }

    private static func normalizedTarget(_ value: String) -> String {
        value.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }

    private func fingerprint(_ transactions: [Transaction]) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return OpaqueID.digest(String(decoding: try! encoder.encode(transactions), as: UTF8.self))
    }
}

private extension PredictedOpportunity {
    init(_ recommendation: CandidateRecommendation) {
        self.init(
            kind: recommendation.kind,
            target: recommendation.target,
            evidenceIDs: recommendation.evidenceIDs,
            monthlySavingsUSD: recommendation.monthlySavingsUSD,
            confidence: recommendation.confidence,
            caveat: recommendation.caveat
        )
    }

    init(_ recommendation: VerifiedRecommendation) {
        self.init(
            kind: recommendation.kind,
            target: recommendation.target,
            evidenceIDs: recommendation.evidenceIDs,
            monthlySavingsUSD: recommendation.monthlySavingsUSD,
            confidence: recommendation.confidence,
            caveat: recommendation.caveat
        )
    }
}
