import Foundation

public struct NormalizedMerchant: Codable, Hashable, Sendable {
    public let displayName: String
    public let category: String
}

public struct MerchantNormalizer: Sendable {
    private struct Rule: Codable, Hashable, Sendable {
        let merchant: String
        let category: String
    }

    private let rules: [String: Rule]

    public static func bundled() throws -> MerchantNormalizer {
        guard let url = Bundle.module.url(forResource: "merchant-aliases", withExtension: "json") else {
            throw DomainError.resourceMissing("merchant-aliases.json")
        }
        return try MerchantNormalizer(data: Data(contentsOf: url))
    }

    public init(data: Data) throws {
        let decoded = try JSONDecoder().decode([String: Rule].self, from: data)
        rules = Dictionary(uniqueKeysWithValues: decoded.map { (Self.clean($0.key), $0.value) })
    }

    public func normalize(_ raw: String) throws -> NormalizedMerchant {
        let cleaned = Self.clean(raw)
        guard !cleaned.isEmpty else {
            throw DomainError.invalidMerchant
        }
        if let match = rules.keys.sorted(by: { $0.count > $1.count }).first(where: {
            cleaned == $0 || cleaned.hasPrefix($0 + " ")
        }), let rule = rules[match] {
            return NormalizedMerchant(displayName: rule.merchant, category: rule.category)
        }
        return NormalizedMerchant(
            displayName: cleaned.lowercased().split(separator: " ").map { $0.capitalized }.joined(separator: " "),
            category: "other"
        )
    }

    private static func clean(_ raw: String) -> String {
        raw.uppercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }
}
