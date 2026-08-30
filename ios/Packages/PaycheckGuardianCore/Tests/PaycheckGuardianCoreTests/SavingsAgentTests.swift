import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class SavingsAgentTests: XCTestCase {
    func testEveryToolCallIsImmediatelyFollowedByResult() throws {
        let run = try SavingsAgent().run(transactions: subscriptionRows(), window: agentWindow())
        let toolEvents = run.trajectory.filter { $0.type == .toolCalled || $0.type == .toolResult }

        XCTAssertFalse(toolEvents.isEmpty)
        XCTAssertTrue(toolEvents.count.isMultiple(of: 2))
        for index in stride(from: 0, to: toolEvents.count, by: 2) {
            XCTAssertEqual(toolEvents[index].type, .toolCalled)
            XCTAssertEqual(toolEvents[index + 1].type, .toolResult)
            XCTAssertEqual(toolEvents[index].toolName, toolEvents[index + 1].toolName)
        }
        XCTAssertTrue(toolEvents.contains { $0.toolName == "recommendation_verifier" })
    }

    func testCorrectableCandidateRetriesOnceWithCanonicalValue() throws {
        let agent = SavingsAgent(draftTransform: { draft in
            try! CandidateRecommendation(
                id: draft.id,
                kind: draft.kind,
                target: draft.target,
                action: draft.action,
                title: draft.title,
                rationale: draft.rationale,
                evidenceIDs: draft.evidenceIDs,
                monthlySavingsUSD: Money("1.00"),
                nextPaycheckSavingsUSD: Money("1.00"),
                confidence: draft.confidence,
                caveat: draft.caveat
            )
        })

        let run = try agent.run(transactions: subscriptionRows(amount: "16.49"), window: agentWindow())

        XCTAssertEqual(run.plan.recommendations.first?.monthlySavingsUSD, try Money("16.49"))
        XCTAssertEqual(run.trajectory.filter { $0.type == .retry }.count, 1)
        XCTAssertEqual(
            run.trajectory.filter { $0.toolName == "recommendation_verifier" && $0.type == .toolCalled }.count,
            2
        )
    }

    func testEvidenceCannotAppearInTwoRetainedRecommendations() throws {
        let rows = try [
            agentRow("d1", "2026-07-01", "DoorDash", "20.00", "food_delivery"),
            agentRow("d2", "2026-07-02", "DoorDash", "20.00", "food_delivery"),
            agentRow("d3", "2026-07-20", "DoorDash", "25.00", "food_delivery"),
        ]

        let plan = try SavingsAgent().run(transactions: rows, window: agentWindow()).plan
        let evidence = plan.recommendations.flatMap(\.evidenceIDs)

        XCTAssertEqual(evidence.count, Set(evidence).count)
        XCTAssertEqual(plan.recommendations.count, 1)
    }

    func testAgentRetainsAtMostThreeRecommendations() throws {
        let rows = try subscriptionRows()
            + subscriptionRows(merchant: "Hulu", prefix: "h", amount: "9.99")
            + subscriptionRows(merchant: "Spotify", prefix: "s", amount: "11.99", category: "music")
            + subscriptionRows(merchant: "Apple iCloud", prefix: "i", amount: "2.99", category: "cloud_storage")

        let plan = try SavingsAgent().run(transactions: rows, window: agentWindow()).plan

        XCTAssertEqual(plan.recommendations.count, 3)
    }

    func testTrajectoryContainsNoMerchantOrFilename() throws {
        let parser = try CSVTransactionParser(normalizer: .bundled())
        let csv = Data("date,description,amount\n2026-05-01,NETFLIX,15.49\n2026-05-31,NETFLIX,15.49\n2026-06-30,NETFLIX,15.49\n".utf8)
        let rows = try parser.parse(data: csv, sourceName: "statement.csv", isSynthetic: true)
        let run = try SavingsAgent().run(transactions: rows, window: agentWindow())
        let data = try JSONEncoder().encode(run.trajectory)
        let json = String(decoding: data, as: UTF8.self)

        XCTAssertFalse(json.localizedCaseInsensitiveContains("netflix"))
        XCTAssertFalse(json.localizedCaseInsensitiveContains("statement.csv"))
    }

    func testApprovalIsFreshVerifiedAndIdempotent() throws {
        let agent = SavingsAgent()
        let initial = try agent.run(transactions: subscriptionRows(), window: agentWindow())
        let id = try XCTUnwrap(initial.plan.recommendations.first?.id)

        let once = try agent.approve(id: id, in: initial)
        let twice = try agent.approve(id: id, in: once)

        XCTAssertEqual(once.simulatedActions, twice.simulatedActions)
        XCTAssertEqual(twice.simulatedActions.count, 1)
        XCTAssertEqual(twice.plan.recommendations.first?.status, .approvedForSimulation)
    }

    func testDismissalRemovesRecommendationFromActiveTotal() throws {
        let agent = SavingsAgent()
        let initial = try agent.run(transactions: subscriptionRows(), window: agentWindow())
        let id = try XCTUnwrap(initial.plan.recommendations.first?.id)

        let dismissed = agent.dismiss(id: id, in: initial)

        XCTAssertEqual(dismissed.plan.activeRecommendations.count, 0)
        XCTAssertEqual(dismissed.plan.nextPaycheckTotalUSD, 0)
    }
}

private func subscriptionRows(
    merchant: String = "Netflix",
    prefix: String = "n",
    amount: String = "15.49",
    category: String = "streaming"
) throws -> [Transaction] {
    try [
        agentRow("\(prefix)1", "2026-05-01", merchant, amount, category),
        agentRow("\(prefix)2", "2026-05-31", merchant, amount, category),
        agentRow("\(prefix)3", "2026-06-30", merchant, amount, category),
    ]
}

private func agentWindow() throws -> AnalysisWindow {
    try AnalysisWindow(
        analysisDate: ISODate.parse("2026-07-10"),
        nextPaycheck: ISODate.parse("2026-07-22")
    )
}

private func agentRow(
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
