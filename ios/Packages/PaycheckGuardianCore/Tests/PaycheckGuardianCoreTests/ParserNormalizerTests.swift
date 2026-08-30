import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class ParserNormalizerTests: XCTestCase {
    func testAliasNormalizationGroupsNetflixVariants() throws {
        let normalizer = try MerchantNormalizer.bundled()

        XCTAssertEqual(try normalizer.normalize("NETFLIX * 800-585").displayName, "Netflix")
        XCTAssertEqual(try normalizer.normalize("NETFLIX ORDER 23A").category, "streaming")
    }

    func testPunctuationOnlyMerchantIsRejected() throws {
        let parser = try CSVTransactionParser(normalizer: .bundled())
        let csv = "date,description,amount,currency\n2026-07-01,***,12.00,USD\n"

        XCTAssertThrowsError(
            try parser.parse(data: Data(csv.utf8), sourceName: "fixture.csv", isSynthetic: true)
        ) { error in
            XCTAssertEqual(error as? DomainError, .invalidMerchant)
        }
    }

    func testCSVParserHandlesQuotedMerchantAndUSDDefault() throws {
        let parser = try CSVTransactionParser(normalizer: .bundled())
        let csv = "date,description,amount\n2026-07-01,\"CAFE, WEST\",12.40\n"

        let row = try XCTUnwrap(
            parser.parse(data: Data(csv.utf8), sourceName: "fixture.csv", isSynthetic: true).first
        )

        XCTAssertEqual(row.merchantNormalized, "Cafe West")
        XCTAssertEqual(row.amountUSD, try Money("12.40"))
        XCTAssertTrue(row.isSynthetic)
    }

    func testCSVParserRejectsNonUSDTransactions() throws {
        let parser = try CSVTransactionParser(normalizer: .bundled())
        let csv = "date,description,amount,currency\n2026-07-01,CAFE,12.40,EUR\n"

        XCTAssertThrowsError(
            try parser.parse(data: Data(csv.utf8), sourceName: "fixture.csv", isSynthetic: true)
        ) { error in
            XCTAssertEqual(error as? DomainError, .unsupportedCurrency("EUR"))
        }
    }

    func testMultiFileMergeRemovesIdenticalEvidenceRows() throws {
        let parser = try CSVTransactionParser(normalizer: .bundled())
        let csv = Data("date,description,amount\n2026-07-01,NETFLIX,15.49\n".utf8)
        let first = try parser.parse(data: csv, sourceName: "first.csv", isSynthetic: true)
        let second = try parser.parse(data: csv, sourceName: "second.csv", isSynthetic: true)

        XCTAssertEqual(parser.merge([first, second]).count, 1)
    }

    func testReceiptTextParsesRequiredFields() throws {
        let parser = try ReceiptTextParser(normalizer: .bundled())
        let text = "DATE: 2026-07-08\nMERCHANT: Coffee Corner\nTOTAL: $12.40"

        let row = try parser.parse(text, sourceID: "opaque-1", isSynthetic: true)

        XCTAssertEqual(row.amountUSD, try Money("12.40"))
        XCTAssertEqual(row.category, "other")
        XCTAssertEqual(row.source, .receipt)
    }

    func testReceiptWithoutTotalIsRejected() throws {
        let parser = try ReceiptTextParser(normalizer: .bundled())

        XCTAssertThrowsError(
            try parser.parse("MERCHANT: Cafe\nDATE: 2026-07-08", sourceID: "opaque-1", isSynthetic: true)
        ) { error in
            XCTAssertEqual(error as? DomainError, .missingReceiptField("TOTAL"))
        }
    }
}
