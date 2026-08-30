import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class MoneyAndModelTests: XCTestCase {
    func testMoneyRoundsHalfUpToCents() throws {
        XCTAssertEqual(try Money("10.125").amount, Decimal(string: "10.13")!)
    }

    func testMoneyRejectsZeroAndNegativeValues() {
        XCTAssertThrowsError(try Money("0"))
        XCTAssertThrowsError(try Money("-1.00"))
    }

    func testAnalysisWindowRejectsSameDayPaycheck() {
        XCTAssertThrowsError(
            try AnalysisWindow(
                analysisDate: date("2026-07-10"),
                nextPaycheck: date("2026-07-10")
            )
        )
    }

    func testProrationIsPositiveForTomorrow() throws {
        let value = try Money("15.49").prorated(
            from: date("2026-07-10"),
            to: date("2026-07-11")
        )

        XCTAssertEqual(value.amount, Decimal(string: "0.51")!)
    }

    func testTransactionRejectsBlankIdentityFields() throws {
        XCTAssertThrowsError(
            try Transaction(
                id: " ",
                date: date("2026-07-10"),
                merchantRaw: "Netflix",
                merchantNormalized: "Netflix",
                amountUSD: Money("15.49"),
                category: "streaming",
                source: .bankCSV,
                sourceReference: "source-1",
                isSynthetic: true
            )
        )
    }
}

private func date(_ value: String) -> Date {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    let pieces = value.split(separator: "-").compactMap { Int($0) }
    return calendar.date(from: DateComponents(year: pieces[0], month: pieces[1], day: pieces[2]))!
}
