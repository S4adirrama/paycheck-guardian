import Foundation

public struct Money: Codable, Hashable, Sendable, Comparable, CustomStringConvertible {
    public let amount: Decimal

    public init(_ value: Decimal) throws {
        var source = value
        var rounded = Decimal()
        NSDecimalRound(&rounded, &source, 2, .plain)
        guard rounded > 0 else {
            throw DomainError.nonPositiveMoney
        }
        amount = rounded
    }

    public init(_ text: String) throws {
        guard let value = Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")) else {
            throw DomainError.invalidMoney(text)
        }
        try self.init(value)
    }

    public func prorated(from analysisDate: Date, to nextPaycheck: Date) throws -> Money {
        let window = try AnalysisWindow(analysisDate: analysisDate, nextPaycheck: nextPaycheck)
        let days = Calendar.utcGregorian.dateComponents(
            [.day],
            from: window.analysisDate,
            to: window.nextPaycheck
        ).day ?? 0
        return try Money(amount * Decimal(days) * Decimal(12) / Decimal(365))
    }

    public static func < (lhs: Money, rhs: Money) -> Bool {
        lhs.amount < rhs.amount
    }

    public var description: String {
        NSDecimalNumber(decimal: amount).stringValue
    }
}

extension Calendar {
    static var utcGregorian: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        return calendar
    }
}
