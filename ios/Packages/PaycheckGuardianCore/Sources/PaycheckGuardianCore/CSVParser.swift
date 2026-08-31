import CryptoKit
import Foundation

public struct CSVTransactionParser: Sendable {
    private let normalizer: MerchantNormalizer

    public init(normalizer: MerchantNormalizer) {
        self.normalizer = normalizer
    }

    public func parse(data: Data, sourceName: String, isSynthetic: Bool) throws -> [Transaction] {
        guard let text = String(data: data, encoding: .utf8) else {
            throw DomainError.invalidUTF8
        }
        let records = try CSVRecords.parse(text)
        guard let header = records.first else {
            throw DomainError.emptyInput
        }
        let names = header.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
        let required = ["date", "description", "amount"]
        let missing = required.filter { !names.contains($0) }
        guard missing.isEmpty else {
            throw DomainError.invalidCSV("missing required columns: \(missing.joined(separator: ", "))")
        }

        let indices = Dictionary(uniqueKeysWithValues: names.enumerated().map { ($0.element, $0.offset) })
        var transactions: [Transaction] = []
        for (offset, values) in records.dropFirst().enumerated() {
            if values.allSatisfy({ $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
                continue
            }
            guard values.count == header.count else {
                throw DomainError.invalidCSV("row \(offset + 2) has \(values.count) fields; expected \(header.count)")
            }
            let dateText = values[indices["date"]!].trimmingCharacters(in: .whitespacesAndNewlines)
            let merchantRaw = values[indices["description"]!].trimmingCharacters(in: .whitespacesAndNewlines)
            let amountText = values[indices["amount"]!].trimmingCharacters(in: .whitespacesAndNewlines)
            let currency = indices["currency"].map { values[$0].trimmingCharacters(in: .whitespacesAndNewlines).uppercased() } ?? "USD"
            guard currency == "USD" else {
                throw DomainError.unsupportedCurrency(currency)
            }
            let normalized = try normalizer.normalize(merchantRaw)
            let amount = try Money(amountText)
            let transactionDate = try ISODate.parse(dateText)
            let evidenceSeed = "\(offset)|\(dateText)|\(merchantRaw)|\(amount.description)"
            transactions.append(
                try Transaction(
                    id: OpaqueID.digest(evidenceSeed),
                    date: transactionDate,
                    merchantRaw: merchantRaw,
                    merchantNormalized: normalized.displayName,
                    amountUSD: amount,
                    category: normalized.category == "other" ? (indices["category"].map { values[$0] } ?? "other") : normalized.category,
                    source: .bankCSV,
                    sourceReference: OpaqueID.digest("source|\(sourceName)|\(offset)"),
                    isSynthetic: isSynthetic
                )
            )
        }
        guard !transactions.isEmpty else {
            throw DomainError.emptyInput
        }
        return transactions
    }

    public func merge(_ groups: [[Transaction]]) -> [Transaction] {
        var seen = Set<String>()
        return groups.flatMap { $0 }
            .sorted { ($0.date, $0.id) < ($1.date, $1.id) }
            .filter { seen.insert($0.id).inserted }
    }
}

enum ISODate {
    static func parse(_ value: String) throws -> Date {
        let parts = value.split(separator: "-", omittingEmptySubsequences: false)
        guard parts.count == 3,
              let year = Int(parts[0]), let month = Int(parts[1]), let day = Int(parts[2]),
              let date = Calendar.utcGregorian.date(from: DateComponents(year: year, month: month, day: day)),
              Calendar.utcGregorian.dateComponents([.year, .month, .day], from: date) == DateComponents(year: year, month: month, day: day)
        else {
            throw DomainError.invalidDate(value)
        }
        return date
    }
}

enum OpaqueID {
    static func digest(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8)).prefix(8).map { String(format: "%02x", $0) }.joined()
    }
}

private enum CSVRecords {
    static func parse(_ text: String) throws -> [[String]] {
        var records: [[String]] = []
        var record: [String] = []
        var field = ""
        var quoted = false
        var index = text.startIndex

        while index < text.endIndex {
            let character = text[index]
            if character == "\"" {
                let next = text.index(after: index)
                if quoted, next < text.endIndex, text[next] == "\"" {
                    field.append("\"")
                    index = next
                } else {
                    quoted.toggle()
                }
            } else if character == ",", !quoted {
                record.append(field)
                field = ""
            } else if (character == "\n" || character == "\r"), !quoted {
                if character == "\r" {
                    let next = text.index(after: index)
                    if next < text.endIndex, text[next] == "\n" { index = next }
                }
                record.append(field)
                records.append(record)
                record = []
                field = ""
            } else {
                field.append(character)
            }
            index = text.index(after: index)
        }
        guard !quoted else {
            throw DomainError.invalidCSV("unterminated quoted field")
        }
        if !field.isEmpty || !record.isEmpty {
            record.append(field)
            records.append(record)
        }
        return records
    }
}
