import XCTest
import PaycheckGuardianCore
@testable import PaycheckGuardianApp

@MainActor
final class AppModelTests: XCTestCase {
    func testDemoRunsToVerifiedPlan() async throws {
        let model = AppModel()

        await model.runDemo()

        XCTAssertEqual(model.route, .plan)
        XCTAssertFalse(model.activeRecommendations.isEmpty)
        XCTAssertTrue(model.activeRecommendations.allSatisfy { $0.status == .proposed })
        XCTAssertNil(model.presentedError)
    }

    func testDismissalRecalculatesHeadlineTotal() async throws {
        let model = AppModel()
        await model.runDemo()
        let recommendation = try XCTUnwrap(model.activeRecommendations.first)
        let before = model.nextPaycheckTotal

        model.dismiss(recommendation.id)

        XCTAssertLessThan(model.nextPaycheckTotal, before)
        XCTAssertFalse(model.activeRecommendations.contains { $0.id == recommendation.id })
    }

    func testSameDayPaycheckShowsValidationError() async {
        let model = AppModel()
        model.nextPaycheck = model.analysisDate

        await model.analyzeCurrentTransactions()

        XCTAssertEqual(model.route, .setup)
        XCTAssertNotNil(model.presentedError)
    }

    func testMultiFileImportMergesAndDeduplicatesCSVRows() async throws {
        let csv = "date,description,amount\n2026-07-01,NETFLIX,15.49\n"
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let first = directory.appendingPathComponent("first.csv")
        let second = directory.appendingPathComponent("second.csv")
        try Data(csv.utf8).write(to: first)
        try Data(csv.utf8).write(to: second)
        let model = AppModel()

        await model.importFiles([first, second])

        XCTAssertEqual(model.importedTransactionCount, 1)
        XCTAssertEqual(model.route, .setup)
        XCTAssertNil(model.presentedError)
    }

    func testBundledReceiptImageIsRecognizedAndParsedLocally() async throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "receipt-01", withExtension: "png"))
        let model = AppModel()

        await model.importFiles([url])

        XCTAssertEqual(model.importedTransactionCount, 1)
        XCTAssertEqual(model.transactions.first?.merchantNormalized, "DoorDash")
        XCTAssertEqual(model.transactions.first?.amountUSD, try Money("28.40"))
        XCTAssertNil(model.presentedError)
    }
}
