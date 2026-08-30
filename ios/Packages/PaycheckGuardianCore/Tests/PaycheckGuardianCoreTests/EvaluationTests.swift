import Foundation
import XCTest
@testable import PaycheckGuardianCore

final class EvaluationTests: XCTestCase {
    func testMatchRequiresEveryTruthEvidenceID() throws {
        let prediction = PredictedOpportunity(
            kind: .subscription,
            target: "Netflix",
            evidenceIDs: ["n1", "n2"],
            monthlySavingsUSD: try Money("15.49"),
            confidence: .high,
            caveat: nil
        )
        let truth = GroundTruthOpportunity(
            kind: .subscription,
            target: "Netflix",
            requiredEvidenceIDs: ["n1", "n2", "n3"],
            monthlySavingsUSD: try Money("15.49"),
            expectedConfidence: nil,
            caveatRequired: false
        )

        XCTAssertFalse(Evaluator.matches(prediction, truth: truth))
    }

    func testAllModesReceiveIdenticalOriginalRows() throws {
        let report = try Evaluator().run(cases: EvaluationFixtures.bundled())

        for fingerprints in report.inputFingerprintsByMode.values {
            XCTAssertEqual(fingerprints, report.inputFingerprintsByMode[.baseline])
        }
    }

    func testFinalWorkflowReachesRetainedTargets() throws {
        let report = try Evaluator().run(cases: EvaluationFixtures.bundled())
        let metrics = try XCTUnwrap(report.metrics[.final])

        XCTAssertEqual(report.caseCount, 12)
        XCTAssertEqual(metrics.precision, Decimal(1))
        XCTAssertEqual(metrics.recall, Decimal(1))
        XCTAssertEqual(metrics.f1, Decimal(1))
        XCTAssertEqual(metrics.unsupportedClaims, 0)
        XCTAssertEqual(metrics.truePositives, 13)
        XCTAssertEqual(metrics.falsePositives, 0)
        XCTAssertEqual(metrics.falseNegatives, 0)
        XCTAssertEqual(metrics.evidenceCoverage, Decimal(1))
        XCTAssertEqual(metrics.meanSavingsErrorUSD, 0)
    }

    func testUnsafeAblationIsDistinctAndPoorerThanFinal() throws {
        let report = try Evaluator().run(cases: EvaluationFixtures.bundled())
        let unsafe = try XCTUnwrap(report.metrics[.removedUnsafeRecurrence])
        let final = try XCTUnwrap(report.metrics[.final])

        XCTAssertEqual(unsafe.f1, Decimal(string: "0.0800"))
        XCTAssertEqual(unsafe.unsupportedClaims, 11)
        XCTAssertGreaterThan(unsafe.unsupportedClaims, final.unsupportedClaims)
        XCTAssertNotEqual(
            report.predictions[.removedUnsafeRecurrence],
            report.predictions[.final]
        )
    }

    func testUnverifiedModeRetainsUnsafeDraftsThatVerifierRemoves() throws {
        let report = try Evaluator().run(cases: EvaluationFixtures.bundled())
        let unverified = try XCTUnwrap(report.metrics[.unverifiedAgent])
        let final = try XCTUnwrap(report.metrics[.final])

        XCTAssertEqual(unverified.precision, Decimal(string: "0.8125"))
        XCTAssertEqual(unverified.recall, Decimal(1))
        XCTAssertEqual(unverified.f1, Decimal(string: "0.8966"))
        XCTAssertEqual(unverified.unsupportedClaims, 3)
        XCTAssertEqual(final.unsupportedClaims, 0)
    }

    func testArtifactWriterProducesMetricsCasesAndSanitizedTrajectory() throws {
        let report = try Evaluator().run(cases: EvaluationFixtures.bundled())
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)

        try EvaluationArtifactWriter.write(report, to: directory)

        let metrics = try String(contentsOf: directory.appendingPathComponent("metrics.json"))
        let cases = try String(contentsOf: directory.appendingPathComponent("per-case-results.json"))
        let trajectory = try String(contentsOf: directory.appendingPathComponent("final-trajectories.json"))
        XCTAssertTrue(metrics.contains("\"f1\" : \"1.0000\""))
        XCTAssertTrue(cases.contains("monthly_streaming"))
        XCTAssertTrue(trajectory.contains("tool_called"))
        XCTAssertFalse(trajectory.localizedCaseInsensitiveContains("netflix"))
    }
}
