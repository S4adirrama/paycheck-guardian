import Foundation

public struct SavingsPlan: Codable, Hashable, Sendable {
    public let recommendations: [VerifiedRecommendation]

    public init(recommendations: [VerifiedRecommendation]) {
        self.recommendations = recommendations
    }

    public var activeRecommendations: [VerifiedRecommendation] {
        recommendations.filter { $0.status != .dismissed }
    }

    public var monthlyTotalUSD: Decimal {
        activeRecommendations.reduce(Decimal.zero) { $0 + $1.monthlySavingsUSD.amount }
    }

    public var nextPaycheckTotalUSD: Decimal {
        activeRecommendations.reduce(Decimal.zero) { $0 + $1.nextPaycheckSavingsUSD.amount }
    }

    static func selecting(_ candidates: [VerifiedRecommendation]) -> SavingsPlan {
        let ranked = candidates.sorted {
            if $0.nextPaycheckSavingsUSD != $1.nextPaycheckSavingsUSD {
                return $0.nextPaycheckSavingsUSD > $1.nextPaycheckSavingsUSD
            }
            return $0.id < $1.id
        }
        var evidenceOwner = Set<String>()
        var selected: [VerifiedRecommendation] = []
        for candidate in ranked where selected.count < 3 {
            let evidence = Set(candidate.evidenceIDs)
            guard evidenceOwner.isDisjoint(with: evidence) else { continue }
            selected.append(candidate)
            evidenceOwner.formUnion(evidence)
        }
        return SavingsPlan(recommendations: selected)
    }
}

public struct SimulatedAction: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let recommendationID: String
    public let action: RecommendationAction
    public let disclosure: String
}

public struct AgentRun: Codable, Hashable, Sendable {
    public let runID: String
    public let window: AnalysisWindow
    public let transactions: [Transaction]
    public let plan: SavingsPlan
    public let trajectory: [TrajectoryEvent]
    public let simulatedActions: [SimulatedAction]
}

public struct SavingsAgent: Sendable {
    private let verifier: RecommendationVerifier
    private let draftTransform: @Sendable (CandidateRecommendation) -> CandidateRecommendation

    public init() {
        verifier = RecommendationVerifier()
        draftTransform = { $0 }
    }

    init(draftTransform: @escaping @Sendable (CandidateRecommendation) -> CandidateRecommendation) {
        verifier = RecommendationVerifier()
        self.draftTransform = draftTransform
    }

    public func run(transactions: [Transaction], window: AnalysisWindow) throws -> AgentRun {
        let seed = transactions.map(\.id).sorted().joined(separator: "|")
            + "|\(window.analysisDate.timeIntervalSince1970)|\(window.nextPaycheck.timeIntervalSince1970)"
        var recorder = TrajectoryRecorder(seed: seed)
        recorder.record(
            component: "agent",
            type: .runStarted,
            payload: .object([
                "instruction": .string("Find evidence-backed savings before the next paycheck; never act externally."),
                "transaction_count": .int(transactions.count),
                "synthetic_count": .int(transactions.filter(\.isSynthetic).count),
            ])
        )

        let recurring: [RecurringCandidate] = invoke(
            "find_recurring", transactions: transactions, recorder: &recorder
        ) { AnalysisTools.findRecurring(transactions) }
        let duplicates: [DuplicateCandidate] = invoke(
            "find_duplicates", transactions: transactions, recorder: &recorder
        ) { AnalysisTools.findDuplicates(transactions) }
        let anomalies: [AnomalyCandidate] = invoke(
            "find_anomalies", transactions: transactions, recorder: &recorder
        ) { AnalysisTools.findAnomalies(transactions) }
        let summaries: [CategorySummary] = invoke(
            "summarize_categories", transactions: transactions, recorder: &recorder
        ) { AnalysisTools.summarizeCategories(transactions) }
        let patterns: [SpendingPattern] = invoke(
            "find_discretionary_patterns", transactions: transactions, recorder: &recorder
        ) { AnalysisTools.findDiscretionaryPatterns(transactions) }

        let facts = AnalysisFacts(
            recurring: recurring,
            duplicates: duplicates,
            anomalies: anomalies,
            categorySummaries: summaries,
            discretionaryPatterns: patterns
        )
        var accepted: [VerifiedRecommendation] = []
        for draft in RecommendationFactory.drafts(from: facts, window: window) {
            let submitted = draftTransform(draft)
            let first = verify(
                submitted,
                facts: facts,
                transactions: transactions,
                window: window,
                attempt: 1,
                recorder: &recorder
            )
            if let recommendation = first.recommendation {
                accepted.append(recommendation)
            } else if first.status == .correctable, let correction = first.correctableCandidate,
                      correction != submitted {
                recorder.record(
                    component: "agent",
                    type: .retry,
                    toolName: "recommendation_verifier",
                    payload: .object(["attempt": .int(2), "reason": .string("canonical arithmetic correction")])
                )
                let second = verify(
                    correction,
                    facts: facts,
                    transactions: transactions,
                    window: window,
                    attempt: 2,
                    recorder: &recorder
                )
                if let recommendation = second.recommendation {
                    accepted.append(recommendation)
                }
            }
        }

        let plan = SavingsPlan.selecting(accepted)
        recorder.record(
            component: "agent",
            type: .runCompleted,
            payload: .object(["recommendation_count": .int(plan.recommendations.count)])
        )
        return AgentRun(
            runID: recorder.runID,
            window: window,
            transactions: transactions,
            plan: plan,
            trajectory: recorder.events,
            simulatedActions: []
        )
    }

    public func approve(id: String, in run: AgentRun) throws -> AgentRun {
        guard let selected = run.plan.recommendations.first(where: { $0.id == id }) else {
            throw DomainError.blankField("Unknown recommendation")
        }
        if selected.status == .approvedForSimulation { return run }
        guard selected.status != .dismissed else { return run }

        let facts = AnalysisTools.runAll(run.transactions)
        let candidate = try CandidateRecommendation(
            id: selected.id,
            kind: selected.kind,
            target: selected.target,
            action: selected.action,
            title: selected.title,
            rationale: selected.rationale,
            evidenceIDs: selected.evidenceIDs,
            monthlySavingsUSD: selected.monthlySavingsUSD,
            nextPaycheckSavingsUSD: selected.nextPaycheckSavingsUSD,
            confidence: selected.confidence,
            caveat: selected.caveat
        )
        var recorder = TrajectoryRecorder(runID: run.runID, events: run.trajectory)
        let result = verify(
            candidate,
            facts: facts,
            transactions: run.transactions,
            window: run.window,
            attempt: 1,
            recorder: &recorder
        )
        guard result.status == .accepted else { return run }
        let recommendations = run.plan.recommendations.map {
            $0.id == id ? $0.withStatus(.approvedForSimulation) : $0
        }
        recorder.record(
            component: "human",
            type: .humanCheckpoint,
            payload: .object(["decision": .string("approved_local_simulation"), "recommendation_id": .string(id)])
        )
        let action = SimulatedAction(
            id: TrajectoryRecorder.opaqueID(seed: "simulation|\(run.runID)|\(id)"),
            recommendationID: id,
            action: selected.action,
            disclosure: "Simulation only — no bank or merchant was contacted."
        )
        return AgentRun(
            runID: run.runID,
            window: run.window,
            transactions: run.transactions,
            plan: SavingsPlan(recommendations: recommendations),
            trajectory: recorder.events,
            simulatedActions: run.simulatedActions.contains(where: { $0.recommendationID == id })
                ? run.simulatedActions
                : run.simulatedActions + [action]
        )
    }

    public func dismiss(id: String, in run: AgentRun) -> AgentRun {
        guard run.plan.recommendations.contains(where: { $0.id == id && $0.status != .dismissed }) else {
            return run
        }
        var recorder = TrajectoryRecorder(runID: run.runID, events: run.trajectory)
        recorder.record(
            component: "human",
            type: .humanCheckpoint,
            payload: .object(["decision": .string("dismissed"), "recommendation_id": .string(id)])
        )
        return AgentRun(
            runID: run.runID,
            window: run.window,
            transactions: run.transactions,
            plan: SavingsPlan(recommendations: run.plan.recommendations.map {
                $0.id == id ? $0.withStatus(.dismissed) : $0
            }),
            trajectory: recorder.events,
            simulatedActions: run.simulatedActions
        )
    }

    private func invoke<T>(
        _ name: String,
        transactions: [Transaction],
        recorder: inout TrajectoryRecorder,
        body: () -> [T]
    ) -> [T] {
        recorder.recordCall(tool: name, transactionCount: transactions.count)
        let result = body()
        recorder.recordResult(tool: name, candidateCount: result.count)
        return result
    }

    private func verify(
        _ candidate: CandidateRecommendation,
        facts: AnalysisFacts,
        transactions: [Transaction],
        window: AnalysisWindow,
        attempt: Int,
        recorder: inout TrajectoryRecorder
    ) -> VerificationResult {
        recorder.recordCall(tool: "recommendation_verifier", transactionCount: transactions.count, attempt: attempt)
        let result = verifier.verify(candidate, facts: facts, transactions: transactions, window: window)
        recorder.recordResult(
            tool: "recommendation_verifier",
            candidateCount: 1,
            accepted: result.status == .accepted,
            attempt: attempt
        )
        recorder.record(
            component: "verifier",
            type: .verification,
            payload: .object([
                "status": .string(result.status.rawValue),
                "reason_count": .int(result.reasons.count),
                "recommendation_id": .string(candidate.id),
            ])
        )
        return result
    }
}
