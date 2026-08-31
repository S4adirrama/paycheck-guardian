import Foundation
import PaycheckGuardianCore
import SwiftUI

struct UserFacingError: Identifiable, Equatable {
    let id = UUID()
    let title: String
    let message: String

    static func == (lhs: UserFacingError, rhs: UserFacingError) -> Bool {
        lhs.title == rhs.title && lhs.message == rhs.message
    }
}

@MainActor
final class AppModel: ObservableObject {
    enum Route: Equatable {
        case welcome
        case setup
        case analyzing
        case plan
        case trace
    }

    @Published private(set) var route: Route = .welcome
    @Published private(set) var run: AgentRun?
    @Published var analysisDate: Date
    @Published var nextPaycheck: Date
    @Published var presentedError: UserFacingError?
    @Published private(set) var importedTransactionCount = 0

    private let agent = SavingsAgent()
    private var currentTransactions: [PaycheckGuardianCore.Transaction] = []

    init() {
        analysisDate = Self.date("2026-08-01")
        nextPaycheck = Self.date("2026-08-15")
        if ProcessInfo.processInfo.arguments.contains("--invalid-dates") {
            nextPaycheck = analysisDate
            route = .setup
        }
    }

    var activeRecommendations: [VerifiedRecommendation] {
        run?.plan.activeRecommendations ?? []
    }

    var nextPaycheckTotal: Decimal {
        run?.plan.nextPaycheckTotalUSD ?? 0
    }

    var monthlyTotal: Decimal {
        run?.plan.monthlyTotalUSD ?? 0
    }

    var transactions: [PaycheckGuardianCore.Transaction] {
        run?.transactions ?? currentTransactions
    }

    func showSetup() {
        route = .setup
    }

    func showPlan() {
        if run != nil { route = .plan }
    }

    func showTrace() {
        if run != nil { route = .trace }
    }

    func runDemo() async {
        do {
            let normalizer = try MerchantNormalizer.bundled()
            let parser = CSVTransactionParser(normalizer: normalizer)
            guard let url = Bundle.main.url(forResource: "demo-transactions", withExtension: "csv") else {
                throw DomainError.resourceMissing("demo-transactions.csv")
            }
            currentTransactions = try parser.parse(
                data: Data(contentsOf: url),
                sourceName: "bundled-demo",
                isSynthetic: true
            )
            importedTransactionCount = currentTransactions.count
            await analyzeCurrentTransactions()
        } catch {
            present(error, fallbackTitle: "Demo unavailable")
        }
    }

    func analyzeCurrentTransactions() async {
        do {
            let window = try AnalysisWindow(analysisDate: analysisDate, nextPaycheck: nextPaycheck)
            guard !currentTransactions.isEmpty else { throw DomainError.emptyInput }
            route = .analyzing
            await Task.yield()
            run = try agent.run(transactions: currentTransactions, window: window)
            presentedError = nil
            route = .plan
        } catch {
            route = .setup
            present(error, fallbackTitle: "Check your review setup")
        }
    }

    func importFiles(_ urls: [URL]) async {
        do {
            let normalizer = try MerchantNormalizer.bundled()
            let csvParser = CSVTransactionParser(normalizer: normalizer)
            let receiptParser = ReceiptTextParser(normalizer: normalizer)
            var groups: [[PaycheckGuardianCore.Transaction]] = []
            for (index, url) in urls.enumerated() {
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                let data = try Data(contentsOf: url)
                let sourceID = "import-\(index)"
                switch url.pathExtension.lowercased() {
                case "png", "jpg", "jpeg":
                    let text = try VisionReceiptImporter.recognize(data: data)
                    groups.append([try receiptParser.parse(text, sourceID: sourceID, isSynthetic: false)])
                case "txt":
                    guard let text = String(data: data, encoding: .utf8) else {
                        throw DomainError.invalidUTF8
                    }
                    if text.lowercased().contains("date,description,amount") {
                        groups.append(try csvParser.parse(data: data, sourceName: sourceID, isSynthetic: false))
                    } else {
                        groups.append([try receiptParser.parse(text, sourceID: sourceID, isSynthetic: false)])
                    }
                default:
                    groups.append(try csvParser.parse(data: data, sourceName: sourceID, isSynthetic: false))
                }
            }
            currentTransactions = csvParser.merge(groups)
            importedTransactionCount = currentTransactions.count
            presentedError = nil
            route = .setup
        } catch {
            present(error, fallbackTitle: "Couldn’t import transactions")
        }
    }

    func approve(_ id: String) {
        guard let run else { return }
        do {
            self.run = try agent.approve(id: id, in: run)
        } catch {
            present(error, fallbackTitle: "Simulation not approved")
        }
    }

    func dismiss(_ id: String) {
        guard let run else { return }
        self.run = agent.dismiss(id: id, in: run)
    }

    func reset() {
        run = nil
        currentTransactions = []
        importedTransactionCount = 0
        analysisDate = Self.date("2026-08-01")
        nextPaycheck = Self.date("2026-08-15")
        presentedError = nil
        route = .welcome
    }

    private func present(_ error: Error, fallbackTitle: String) {
        presentedError = UserFacingError(
            title: fallbackTitle,
            message: (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        )
    }

    private static func date(_ value: String) -> Date {
        let components = value.split(separator: "-").compactMap { Int($0) }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        return calendar.date(
            from: DateComponents(year: components[0], month: components[1], day: components[2])
        )!
    }
}
