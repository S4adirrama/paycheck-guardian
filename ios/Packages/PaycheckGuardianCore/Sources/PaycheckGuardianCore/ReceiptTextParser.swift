import Foundation

public struct ReceiptTextParser: Sendable {
    private let normalizer: MerchantNormalizer

    public init(normalizer: MerchantNormalizer) {
        self.normalizer = normalizer
    }

    public func parse(_ text: String, sourceID: String, isSynthetic: Bool) throws -> Transaction {
        var values: [String: String] = [:]
        for line in text.components(separatedBy: .newlines) {
            let pieces = line.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
            guard pieces.count == 2 else { continue }
            let key = pieces[0].trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
            let value = pieces[1].trimmingCharacters(in: .whitespacesAndNewlines)
            guard values[key] == nil else {
                throw DomainError.duplicateReceiptField(key)
            }
            values[key] = value
        }
        for field in ["DATE", "MERCHANT", "TOTAL"] where values[field, default: ""].isEmpty {
            throw DomainError.missingReceiptField(field)
        }
        let currency = values["CURRENCY", default: "USD"].uppercased()
        guard currency == "USD" else {
            throw DomainError.unsupportedCurrency(currency)
        }
        let merchantRaw = values["MERCHANT"]!
        let normalized = try normalizer.normalize(merchantRaw)
        let amount = try Money(values["TOTAL"]!.replacingOccurrences(of: "$", with: ""))
        let transactionDate = try ISODate.parse(values["DATE"]!)
        return try Transaction(
            id: OpaqueID.digest("receipt|\(sourceID)|\(values["DATE"]!)|\(merchantRaw)|\(amount.description)"),
            date: transactionDate,
            merchantRaw: merchantRaw,
            merchantNormalized: normalized.displayName,
            amountUSD: amount,
            category: normalized.category,
            source: .receipt,
            sourceReference: OpaqueID.digest("receipt-source|\(sourceID)"),
            isSynthetic: isSynthetic
        )
    }
}
