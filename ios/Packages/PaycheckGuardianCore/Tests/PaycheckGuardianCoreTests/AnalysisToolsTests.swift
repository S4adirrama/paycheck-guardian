import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class AnalysisToolsTests: XCTestCase {
    func testMonthlyStreamingIsCancellable() throws {
        let rows = try [
            transaction("n1", "2026-05-01", "Netflix", "15.49", "streaming"),
            transaction("n2", "2026-05-31", "Netflix", "15.49", "streaming"),
            transaction("n3", "2026-06-30", "Netflix", "15.49", "streaming"),
        ]

        let candidate = try XCTUnwrap(AnalysisTools.findRecurring(rows).first)

        XCTAssertEqual(candidate.intervalDays, 30)
        XCTAssertEqual(candidate.monthlyAmount, try Money("15.49"))
        XCTAssertTrue(candidate.cancellable)
        XCTAssertEqual(candidate.evidenceIDs, ["n1", "n2", "n3"])
    }

    func testAnnualSubscriptionUsesMonthlyEquivalent() throws {
        let rows = try [
            transaction("p1", "2025-07-01", "Amazon Prime", "139.99", "subscription"),
            transaction("p2", "2026-07-01", "Amazon Prime", "139.99", "subscription"),
        ]

        XCTAssertEqual(AnalysisTools.findRecurring(rows).first?.monthlyAmount, try Money("11.67"))
    }

    func testTelecomRecurrenceIsNeverCancellable() throws {
        let rows = try [
            transaction("v1", "2026-06-01", "Verizon", "75.00", "telecom"),
            transaction("v2", "2026-07-01", "Verizon", "75.00", "telecom"),
        ]

        XCTAssertFalse(try XCTUnwrap(AnalysisTools.findRecurring(rows).first).cancellable)
    }

    func testDuplicateRequiresSameMerchantAmountWithinTwoDays() throws {
        let rows = try [
            transaction("d1", "2026-07-09", "DoorDash", "29.50", "food_delivery"),
            transaction("d2", "2026-07-10", "DoorDash", "29.50", "food_delivery"),
            transaction("d3", "2026-07-20", "DoorDash", "29.50", "food_delivery"),
        ]

        let duplicates = AnalysisTools.findDuplicates(rows)

        XCTAssertEqual(duplicates.count, 1)
        XCTAssertEqual(duplicates[0].evidenceIDs, ["d1", "d2"])
    }

    func testDiscretionaryPatternNeedsThreeChargesInsideThirtyDays() throws {
        let rows = try [
            transaction("d1", "2026-07-01", "DoorDash", "18.00", "food_delivery"),
            transaction("d2", "2026-07-11", "DoorDash", "21.00", "food_delivery"),
            transaction("d3", "2026-07-21", "DoorDash", "24.00", "food_delivery"),
        ]

        let pattern = try XCTUnwrap(AnalysisTools.findDiscretionaryPatterns(rows).first)

        XCTAssertEqual(pattern.chargeCount, 3)
        XCTAssertEqual(pattern.monthlyAmount, try Money("63.00"))
    }

    func testAnomalyNeedsTwoStableComparisonsAndMaterialExcess() throws {
        let rows = try [
            transaction("g1", "2026-05-05", "Grocery Mart", "20.00", "groceries"),
            transaction("g2", "2026-06-05", "Grocery Mart", "21.00", "groceries"),
            transaction("g3", "2026-07-05", "Grocery Mart", "75.00", "groceries"),
        ]

        let anomaly = try XCTUnwrap(AnalysisTools.findAnomalies(rows).first)

        XCTAssertEqual(anomaly.typicalAmount, try Money("20.50"))
        XCTAssertEqual(anomaly.monthlyAmount, try Money("54.50"))
        XCTAssertEqual(anomaly.evidenceIDs, ["g1", "g2", "g3"])
    }

    func testCategorySummaryOwnsEveryCategoryEvidenceID() throws {
        let rows = try [
            transaction("a", "2026-07-01", "Cafe One", "5.00", "coffee"),
            transaction("b", "2026-07-02", "Cafe Two", "7.00", "coffee"),
            transaction("c", "2026-07-03", "Rent", "1500.00", "housing"),
        ]

        let summary = try XCTUnwrap(AnalysisTools.summarizeCategories(rows).first { $0.category == "coffee" })

        XCTAssertEqual(summary.chargeCount, 2)
        XCTAssertEqual(summary.totalAmount, try Money("12.00"))
        XCTAssertEqual(summary.evidenceIDs, ["a", "b"])
    }

    func testRunAllIncludesAllToolFamilies() throws {
        let facts = AnalysisTools.runAll(try [
            transaction("a", "2026-07-01", "Cafe", "5.00", "coffee"),
        ])

        XCTAssertEqual(facts.categorySummaries.count, 1)
        XCTAssertTrue(facts.recurring.isEmpty)
        XCTAssertTrue(facts.duplicates.isEmpty)
        XCTAssertTrue(facts.anomalies.isEmpty)
        XCTAssertTrue(facts.discretionaryPatterns.isEmpty)
    }
}

private func transaction(
    _ id: String,
    _ dateText: String,
    _ merchant: String,
    _ amount: String,
    _ category: String
) throws -> Transaction {
    try Transaction(
        id: id,
        date: ISODate.parse(dateText),
        merchantRaw: merchant,
        merchantNormalized: merchant,
        amountUSD: Money(amount),
        category: category,
        source: .bankCSV,
        sourceReference: "source-\(id)",
        isSynthetic: true
    )
}
