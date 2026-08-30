import Foundation
import PaycheckGuardianCore

do {
    let arguments = CommandLine.arguments
    let outputPath: String
    if let flag = arguments.firstIndex(of: "--output-directory"), arguments.indices.contains(flag + 1) {
        outputPath = arguments[flag + 1]
    } else {
        outputPath = "artifacts/ios/evaluation"
    }
    let cases = try EvaluationFixtures.bundled()
    let report = try Evaluator().run(cases: cases)
    let outputURL = URL(fileURLWithPath: outputPath, isDirectory: true)
    try EvaluationArtifactWriter.write(report, to: outputURL)
    guard let final = report.metrics[.final] else {
        throw NSError(domain: "PaycheckGuardianEvaluation", code: 1)
    }
    print(
        "Swift evaluation complete: \(report.caseCount) cases, "
            + "final F1 \(final.f1), unsupported claims \(final.unsupportedClaims)."
    )
    print("Artifacts: \(outputURL.standardizedFileURL.path)")
} catch {
    FileHandle.standardError.write(Data("Evaluation failed: \(error.localizedDescription)\n".utf8))
    exit(1)
}
