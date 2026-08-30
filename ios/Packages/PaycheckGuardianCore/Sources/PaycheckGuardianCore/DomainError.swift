import Foundation

public enum DomainError: Error, Equatable, LocalizedError, Sendable {
    case invalidMoney(String)
    case nonPositiveMoney
    case invalidPaycheckDate
    case blankField(String)
    case emptyEvidence

    public var errorDescription: String? {
        switch self {
        case .invalidMoney(let value):
            "Invalid USD amount: \(value)"
        case .nonPositiveMoney:
            "USD amounts must be greater than zero."
        case .invalidPaycheckDate:
            "The next paycheck must be later than the analysis date."
        case .blankField(let field):
            "\(field) cannot be blank."
        case .emptyEvidence:
            "A recommendation must include evidence."
        }
    }
}
