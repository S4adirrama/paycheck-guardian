import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class TrajectoryTests: XCTestCase {
    func testRecursiveRedactionMasksSensitiveKeys() throws {
        let value: TraceValue = .object([
            "safe": .string("visible"),
            "nested": .object([
                "authorization": .string("Bearer private"),
                "merchant": .string("Netflix"),
            ]),
        ])

        let redacted = TrajectoryRedactor.redact(value)
        let data = try JSONEncoder().encode(redacted)
        let json = String(decoding: data, as: UTF8.self)

        XCTAssertTrue(json.contains("visible"))
        XCTAssertFalse(json.localizedCaseInsensitiveContains("private"))
        XCTAssertFalse(json.localizedCaseInsensitiveContains("netflix"))
        XCTAssertTrue(json.contains("[REDACTED]"))
    }

    func testOpaqueTraceIDDoesNotContainMerchantOrSourceName() {
        let id = TrajectoryRecorder.opaqueID(seed: "Netflix|statement.csv")

        XCTAssertFalse(id.localizedCaseInsensitiveContains("netflix"))
        XCTAssertFalse(id.localizedCaseInsensitiveContains("statement"))
        XCTAssertEqual(id.count, 16)
    }
}
