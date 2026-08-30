import Foundation

public enum EvaluationArtifactWriter {
    public static func write(_ report: EvaluationReport, to directory: URL) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try writeJSON(metricsObject(report), to: directory.appendingPathComponent("metrics.json"))
        try writeJSON(perCaseObject(report), to: directory.appendingPathComponent("per-case-results.json"))
        try writeJSON(trajectoryObject(report), to: directory.appendingPathComponent("final-trajectories.json"))
        try comparisonMarkdown(report).write(
            to: directory.appendingPathComponent("comparison.md"),
            atomically: true,
            encoding: .utf8
        )
    }

    private static func metricsObject(_ report: EvaluationReport) -> [String: Any] {
        var object = metadata(report)
        for mode in EvaluationMode.allCases {
            guard let metrics = report.metrics[mode] else { continue }
            object[mode.rawValue] = metricObject(metrics)
        }
        object["case_fingerprints"] = report.inputFingerprintsByMode[.baseline] ?? [:]
        return object
    }

    private static func perCaseObject(_ report: EvaluationReport) -> [String: Any] {
        var object = metadata(report)
        var cases: [String: Any] = [:]
        let caseIDs = Set(report.perCaseScores.values.flatMap(\.keys)).sorted()
        for caseID in caseIDs {
            var modes: [String: Any] = [:]
            for mode in EvaluationMode.allCases {
                if let score = report.perCaseScores[mode]?[caseID] {
                    modes[mode.rawValue] = scoreObject(score)
                }
            }
            cases[caseID] = modes
        }
        object["per_case"] = cases
        return object
    }

    private static func trajectoryObject(_ report: EvaluationReport) -> [String: Any] {
        var object = metadata(report)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        var trajectories: [String: Any] = [:]
        for (caseID, run) in report.finalRuns {
            if let encoded = try? encoder.encode(run.trajectory),
               let json = try? JSONSerialization.jsonObject(with: encoded) {
                trajectories[caseID] = json
            }
        }
        object["trajectories"] = trajectories
        return object
    }

    private static func metadata(_ report: EvaluationReport) -> [String: Any] {
        [
            "package_version": "0.1.0",
            "language": "Swift",
            "execution_mode": "offline",
            "model_cost_usd": "0.00",
            "case_count": report.caseCount,
        ]
    }

    private static func metricObject(_ metrics: ModeMetrics) -> [String: Any] {
        [
            "true_positives": metrics.truePositives,
            "false_positives": metrics.falsePositives,
            "false_negatives": metrics.falseNegatives,
            "precision": decimal(metrics.precision),
            "recall": decimal(metrics.recall),
            "f1": decimal(metrics.f1),
            "evidence_coverage": decimal(metrics.evidenceCoverage),
            "mean_savings_error_usd": decimal(metrics.meanSavingsErrorUSD),
            "unsupported_claims": metrics.unsupportedClaims,
        ]
    }

    private static func scoreObject(_ score: CaseScore) -> [String: Any] {
        [
            "true_positives": score.truePositives,
            "false_positives": score.falsePositives,
            "false_negatives": score.falseNegatives,
            "precision": decimal(score.precision),
            "recall": decimal(score.recall),
            "f1": decimal(score.f1),
            "evidence_coverage": decimal(score.evidenceCoverage),
            "mean_savings_error_usd": decimal(score.meanSavingsErrorUSD),
            "unsupported_claims": score.unsupportedClaims,
        ]
    }

    private static func decimal(_ value: Decimal) -> String {
        String(format: "%.4f", NSDecimalNumber(decimal: value).doubleValue)
    }

    private static func writeJSON(_ object: [String: Any], to url: URL) throws {
        var data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
        data.append(0x0A)
        try data.write(to: url, options: .atomic)
    }

    private static func comparisonMarkdown(_ report: EvaluationReport) -> String {
        var lines = [
            "# Swift offline evaluation comparison",
            "",
            "| Mode | Precision | Recall | F1 | Evidence coverage | Unsupported claims |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for mode in EvaluationMode.allCases {
            guard let metrics = report.metrics[mode] else { continue }
            lines.append(
                "| \(mode.rawValue) | \(decimal(metrics.precision)) | \(decimal(metrics.recall)) | \(decimal(metrics.f1)) | \(decimal(metrics.evidenceCoverage)) | \(metrics.unsupportedClaims) |"
            )
        }
        lines.append(contentsOf: [
            "",
            "All modes received identical retained synthetic transaction rows. No online model was called.",
            "",
        ])
        return lines.joined(separator: "\n")
    }
}
