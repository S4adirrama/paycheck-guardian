import Foundation

public enum DomainError: Error, Equatable, LocalizedError, Sendable {
    case invalidMoney(String)
    case nonPositiveMoney
    case invalidPaycheckDate
    case blankField(String)
    case emptyEvidence
    case invalidUTF8
    case emptyInput
    case invalidCSV(String)
    case invalidDate(String)
    case invalidMerchant
    case unsupportedCurrency(String)
    case missingReceiptField(String)
    case duplicateReceiptField(String)
    case resourceMissing(String)

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
        case .invalidUTF8:
            "The selected file is not valid UTF-8 text."
        case .emptyInput:
            "The selected file contains no transactions."
        case .invalidCSV(let reason):
            "Invalid CSV: \(reason)"
        case .invalidDate(let value):
            "Invalid ISO-8601 date: \(value)"
        case .invalidMerchant:
            "Merchant names must contain at least one letter or number."
        case .unsupportedCurrency(let currency):
            "Only USD transactions are supported, not \(currency)."
        case .missingReceiptField(let field):
            "Receipt is missing the \(field) field."
        case .duplicateReceiptField(let field):
            "Receipt contains the \(field) field more than once."
        case .resourceMissing(let name):
            "Bundled resource is missing: \(name)"
        }
    }
}
